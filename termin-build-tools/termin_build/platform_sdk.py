"""Manifest and verification for cross-compiled Core SDK install trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path


MANIFEST_NAME = "termin-core-platform.json"
MANIFEST_KIND = "termin-core-platform-sdk"
SCHEMA = 1
REQUIRED_PACKAGES = (
    "termin_base",
    "termin_dispatch",
    "termin_inspect",
)


@dataclass(frozen=True)
class PlatformIdentity:
    system: str
    architecture: str
    toolchain: str
    toolchain_version: str
    api: str = ""

    def to_dict(self) -> dict[str, str]:
        result = {
            "system": self.system,
            "architecture": self.architecture,
            "toolchain": self.toolchain,
            "toolchain_version": self.toolchain_version,
        }
        if self.api:
            result["api"] = self.api
        return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_entries(sdk_root: Path) -> list[dict[str, str]]:
    entries = []
    for path in sorted(sdk_root.rglob("*")):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        entries.append(
            {
                "path": path.relative_to(sdk_root).as_posix(),
                "sha256": _sha256(path),
            }
        )
    return entries


def _native_build_id(
    identity: PlatformIdentity, artifacts: list[dict[str, str]]
) -> str:
    payload = {
        "target": identity.to_dict(),
        "artifacts": artifacts,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _validate_layout(sdk_root: Path) -> None:
    if not sdk_root.is_dir():
        raise RuntimeError(f"Core platform SDK does not exist: {sdk_root}")
    missing = [
        str(sdk_root / "lib" / "cmake" / package)
        for package in REQUIRED_PACKAGES
        if not (sdk_root / "lib" / "cmake" / package).is_dir()
    ]
    if missing:
        raise RuntimeError(
            "Core platform SDK is missing installed CMake packages: "
            + ", ".join(missing)
        )
    forbidden = [
        sdk_root / "bin" / "termin_python",
        sdk_root / "bin" / "termin_python.exe",
        sdk_root / "python-runtime-manifest.json",
        sdk_root / "wheels",
    ]
    present = [str(path) for path in forbidden if path.exists()]
    if present:
        raise RuntimeError(
            "cross-compiled Core SDK contains desktop Python payload: "
            + ", ".join(present)
        )


def write_manifest(sdk_root: Path, identity: PlatformIdentity) -> Path:
    sdk_root = sdk_root.resolve()
    _validate_layout(sdk_root)
    artifacts = _artifact_entries(sdk_root)
    if not artifacts:
        raise RuntimeError(f"Core platform SDK contains no artifacts: {sdk_root}")
    payload = {
        "schema": SCHEMA,
        "manifest_kind": MANIFEST_KIND,
        "product_id": "core",
        "target": identity.to_dict(),
        "native_build_id": _native_build_id(identity, artifacts),
        "artifacts": artifacts,
    }
    path = sdk_root / MANIFEST_NAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def verify_manifest(
    sdk_root: Path,
    *,
    expected_system: str | None = None,
    expected_architecture: str | None = None,
    expected_build_id: str | None = None,
) -> dict[str, object]:
    sdk_root = sdk_root.resolve()
    _validate_layout(sdk_root)
    path = sdk_root / MANIFEST_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read Core platform manifest {path}: {error}") from error
    if payload.get("schema") != SCHEMA or payload.get("manifest_kind") != MANIFEST_KIND:
        raise RuntimeError(f"invalid Core platform manifest schema/kind: {path}")
    if payload.get("product_id") != "core":
        raise RuntimeError(f"Core platform manifest has wrong product identity: {path}")
    target = payload.get("target")
    if not isinstance(target, dict):
        raise RuntimeError(f"Core platform manifest has no target identity: {path}")
    required_target_fields = (
        "system",
        "architecture",
        "toolchain",
        "toolchain_version",
    )
    invalid_target_fields = [
        field
        for field in required_target_fields
        if not isinstance(target.get(field), str) or not target[field]
    ]
    if invalid_target_fields:
        raise RuntimeError(
            "Core platform manifest has invalid target identity fields: "
            + ", ".join(invalid_target_fields)
        )
    actual_system = target.get("system")
    actual_architecture = target.get("architecture")
    actual_build_id = payload.get("native_build_id")
    if expected_system and actual_system != expected_system:
        raise RuntimeError(
            f"Core platform mismatch: expected {expected_system}, got {actual_system}"
        )
    if expected_architecture and actual_architecture != expected_architecture:
        raise RuntimeError(
            "Core architecture mismatch: expected "
            f"{expected_architecture}, got {actual_architecture}"
        )
    if expected_build_id and actual_build_id != expected_build_id:
        raise RuntimeError(
            f"Core build identity mismatch: expected {expected_build_id}, "
            f"got {actual_build_id}"
        )
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError(f"Core platform manifest has no artifacts: {path}")
    manifest_paths: set[str] = set()
    for entry in artifacts:
        if not isinstance(entry, dict):
            raise RuntimeError(f"invalid artifact entry in {path}")
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise RuntimeError(f"invalid artifact entry in {path}")
        if relative in manifest_paths:
            raise RuntimeError(f"duplicate Core platform artifact entry: {relative}")
        manifest_paths.add(relative)
        artifact = sdk_root / relative
        if not artifact.is_file():
            raise RuntimeError(f"Core platform artifact is missing: {artifact}")
        actual_hash = _sha256(artifact)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Core platform artifact hash mismatch: {artifact}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
    identity = PlatformIdentity(
        system=str(actual_system),
        architecture=str(actual_architecture),
        toolchain=str(target.get("toolchain")),
        toolchain_version=str(target.get("toolchain_version")),
        api=str(target.get("api", "")),
    )
    if actual_build_id != _native_build_id(identity, artifacts):
        raise RuntimeError(f"Core platform native_build_id is inconsistent: {path}")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    write = subparsers.add_parser("write")
    write.add_argument("--sdk-root", type=Path, required=True)
    write.add_argument("--system", required=True)
    write.add_argument("--architecture", required=True)
    write.add_argument("--toolchain", required=True)
    write.add_argument("--toolchain-version", required=True)
    write.add_argument("--api", default="")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--sdk-root", type=Path, required=True)
    verify.add_argument("--system")
    verify.add_argument("--architecture")
    verify.add_argument("--build-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "write":
            path = write_manifest(
                args.sdk_root,
                PlatformIdentity(
                    system=args.system,
                    architecture=args.architecture,
                    toolchain=args.toolchain,
                    toolchain_version=args.toolchain_version,
                    api=args.api,
                ),
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = verify_manifest(
                args.sdk_root,
                expected_system=args.system,
                expected_architecture=args.architecture,
                expected_build_id=args.build_id,
            )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(payload["native_build_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
