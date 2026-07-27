"""Validate and package canonical mutable-CI Termin SDK release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from .artifact_manifest import (
    ArtifactManifest,
    ArtifactManifestError,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
)
from .python_abi import PythonAbiError, PythonAbiIdentity
from .sdk_runtime_metadata import (
    RUNTIME_MANIFEST_NAME,
    RUNTIME_MANIFEST_SCHEMA,
)
from .sdk_verification import verify_relocated_sdk


RELEASE_CHANNEL = "latest-ci"
RELEASE_PYTHON_ABI = "py314t"
PLATFORMS = {
    "linux-x86_64": {
        "runtime_platform": "linux",
        "archive_suffix": ".tar.zst",
        "launcher": "bin/termin_python",
    },
    "windows-x86_64": {
        "runtime_platform": "win32",
        "archive_suffix": ".zip",
        "launcher": "bin/termin_python.exe",
    },
}


class SdkReleaseError(RuntimeError):
    """Raised when an SDK cannot be safely published as a canonical asset."""


def asset_name(platform: str) -> str:
    try:
        suffix = PLATFORMS[platform]["archive_suffix"]
    except KeyError as error:
        raise SdkReleaseError(f"unsupported SDK release platform: {platform}") from error
    return f"termin-sdk-{platform}-{RELEASE_PYTHON_ABI}-{RELEASE_CHANNEL}{suffix}"


def checksum_name(platform: str) -> str:
    return asset_name(platform).removesuffix(PLATFORMS[platform]["archive_suffix"]) + ".sha256"


def _load_json_object(path: Path, *, context: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkReleaseError(f"cannot read {context} {path}: {error}") from error
    if not isinstance(payload, dict):
        raise SdkReleaseError(f"{context} must contain a JSON object: {path}")
    return payload


def validate_release_contract(sdk_prefix: Path, platform: str) -> dict[str, object]:
    """Validate the release-specific ABI and identity contract."""

    sdk_prefix = sdk_prefix.resolve()
    try:
        platform_contract = PLATFORMS[platform]
    except KeyError as error:
        raise SdkReleaseError(f"unsupported SDK release platform: {platform}") from error

    required_paths = (
        Path(platform_contract["launcher"]),
        Path("lib"),
        Path("wheels"),
        Path(RUNTIME_MANIFEST_NAME),
        Path(SDK_MANIFEST_NAME),
    )
    missing = [str(path) for path in required_paths if not (sdk_prefix / path).exists()]
    if missing:
        raise SdkReleaseError(
            "SDK release payload is incomplete; missing: " + ", ".join(missing)
        )

    runtime = _load_json_object(
        sdk_prefix / RUNTIME_MANIFEST_NAME,
        context="Python runtime manifest",
    )
    if runtime.get("schema") != RUNTIME_MANIFEST_SCHEMA:
        raise SdkReleaseError(
            "Python runtime manifest schema mismatch: "
            f"expected {RUNTIME_MANIFEST_SCHEMA}, got {runtime.get('schema')!r}"
        )
    if runtime.get("platform") != platform_contract["runtime_platform"]:
        raise SdkReleaseError(
            f"SDK platform mismatch: release target {platform!r} requires "
            f"{platform_contract['runtime_platform']!r}, got {runtime.get('platform')!r}"
        )

    try:
        runtime_abi = PythonAbiIdentity.from_mapping(
            runtime.get("python_abi"),
            context="SDK release Python ABI",
        )
        artifacts = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifacts.require_kind(SDK_MANIFEST_KIND)
        artifacts.validate_all(expected_python_abi=runtime_abi)
        artifacts.python_abi.require_matches(
            runtime_abi,
            context="SDK release artifact/runtime Python ABI",
        )
    except (ArtifactManifestError, PythonAbiError, RuntimeError) as error:
        raise SdkReleaseError(str(error)) from error

    if runtime_abi.version != "3.14":
        raise SdkReleaseError(
            f"SDK release requires Python 3.14, got {runtime_abi.version}"
        )
    if not runtime_abi.free_threaded:
        raise SdkReleaseError("SDK release requires a free-threaded Python ABI")
    if "314t" not in runtime_abi.soabi:
        raise SdkReleaseError(
            f"SDK release SOABI is not CPython 3.14t: {runtime_abi.soabi!r}"
        )
    if runtime.get("native_build_id") != artifacts.native_build_id:
        raise SdkReleaseError(
            "Python runtime native_build_id does not match the artifact manifest"
        )

    native_wheels = sorted(
        wheel.name
        for wheel in (sdk_prefix / "wheels").glob("*.whl")
        if "-none-any.whl" not in wheel.name
    )
    incompatible = [wheel for wheel in native_wheels if "-cp314t-" not in wheel]
    if not native_wheels:
        raise SdkReleaseError("SDK wheelhouse contains no native wheels")
    if incompatible:
        raise SdkReleaseError(
            "SDK wheelhouse contains non-cp314t native wheels: "
            + ", ".join(incompatible)
        )

    return {
        "platform": platform,
        "python_abi": runtime_abi.to_dict(),
        "native_build_id": artifacts.native_build_id,
        "native_wheel_count": len(native_wheels),
    }


def validate_sdk(sdk_prefix: Path, platform: str) -> dict[str, object]:
    contract = validate_release_contract(sdk_prefix, platform)
    if verify_relocated_sdk(sdk_prefix.resolve()) != 0:
        raise SdkReleaseError("relocated SDK verification failed")
    return contract


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_metadata(
    *,
    repository: str,
    source_sha: str,
    source_ref: str,
    platform: str,
    contract: dict[str, object],
) -> bytes:
    payload = {
        "schema": 1,
        "name": "termin-sdk",
        "channel": RELEASE_CHANNEL,
        "repository": repository,
        "sha": source_sha,
        "ref": source_ref,
        "platform": platform,
        "python": RELEASE_PYTHON_ABI,
        "native_build_id": contract["native_build_id"],
        "asset": asset_name(platform),
        "published_by": "termin_build.sdk_release",
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_zip(source: Path, destination: Path, metadata: bytes) -> None:
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                relative = path.relative_to(source).as_posix()
                if relative == "manifest.json":
                    continue
                archive.write(path, relative)
        archive.writestr("manifest.json", metadata)


def _write_tar_zstd(source: Path, destination: Path, metadata: bytes) -> None:
    if shutil.which("tar") is None:
        raise SdkReleaseError("tar is required to package the Linux SDK")
    with tempfile.TemporaryDirectory(prefix="termin-sdk-release-metadata-") as temp:
        metadata_root = Path(temp)
        (metadata_root / "manifest.json").write_bytes(metadata)
        result = subprocess.run(
            [
                "tar",
                "--zstd",
                "--exclude=./manifest.json",
                "-cf",
                str(destination),
                "-C",
                str(source),
                ".",
                "-C",
                str(metadata_root),
                "manifest.json",
            ],
            check=False,
        )
    if result.returncode != 0:
        raise SdkReleaseError(
            f"tar failed while packaging the Linux SDK (exit {result.returncode})"
        )


def _extract_archive(archive: Path, platform: str, destination: Path) -> None:
    suffix = PLATFORMS[platform]["archive_suffix"]
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as source:
            source.extractall(destination)
        return
    result = subprocess.run(
        ["tar", "--zstd", "-xf", str(archive), "-C", str(destination)],
        check=False,
    )
    if result.returncode != 0:
        raise SdkReleaseError(
            f"tar failed while validating the Linux SDK archive (exit {result.returncode})"
        )


def package_sdk(
    *,
    sdk_prefix: Path,
    output_dir: Path,
    platform: str,
    repository: str,
    source_sha: str,
    source_ref: str,
) -> tuple[Path, Path]:
    """Create and verify an archive before atomically replacing published outputs."""

    sdk_prefix = sdk_prefix.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = validate_sdk(sdk_prefix, platform)
    metadata = _release_metadata(
        repository=repository,
        source_sha=source_sha,
        source_ref=source_ref,
        platform=platform,
        contract=contract,
    )
    final_archive = output_dir / asset_name(platform)
    final_checksum = output_dir / checksum_name(platform)

    with tempfile.TemporaryDirectory(
        prefix=".termin-sdk-release-",
        dir=output_dir,
    ) as temp:
        temporary_root = Path(temp)
        prepared_archive = temporary_root / final_archive.name
        if PLATFORMS[platform]["archive_suffix"] == ".zip":
            _write_zip(sdk_prefix, prepared_archive, metadata)
        else:
            _write_tar_zstd(sdk_prefix, prepared_archive, metadata)

        extracted = temporary_root / "extracted"
        extracted.mkdir()
        _extract_archive(prepared_archive, platform, extracted)
        extracted_manifest = _load_json_object(
            extracted / "manifest.json",
            context="SDK release manifest",
        )
        if extracted_manifest.get("asset") != final_archive.name:
            raise SdkReleaseError("extracted SDK release manifest has the wrong asset name")
        validate_sdk(extracted, platform)

        digest = _sha256(prepared_archive)
        prepared_checksum = temporary_root / final_checksum.name
        prepared_checksum.write_text(
            f"{digest}  {final_archive.name}\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(prepared_archive, final_archive)
        os.replace(prepared_checksum, final_checksum)

    return final_archive, final_checksum


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "package"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--sdk-prefix", type=Path, required=True)
        command_parser.add_argument("--platform", choices=sorted(PLATFORMS), required=True)
        if command == "package":
            command_parser.add_argument("--output-dir", type=Path, required=True)
            command_parser.add_argument("--repository", default="mirmik/termin")
            command_parser.add_argument("--source-sha", default="")
            command_parser.add_argument("--source-ref", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_sdk(args.sdk_prefix, args.platform)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        archive, checksum = package_sdk(
            sdk_prefix=args.sdk_prefix,
            output_dir=args.output_dir,
            platform=args.platform,
            repository=args.repository,
            source_sha=args.source_sha,
            source_ref=args.source_ref,
        )
        print(json.dumps({"asset": str(archive), "checksum": str(checksum)}, indent=2))
        return 0
    except (SdkReleaseError, OSError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
