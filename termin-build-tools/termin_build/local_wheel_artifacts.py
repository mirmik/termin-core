"""Build identity and atomic publication for first-party SDK wheels."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

from .artifact_manifest import (
    ArtifactManifest,
    ArtifactManifestError,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
)
from .package_manifest import PackageEntry
from .python_abi import PythonAbiIdentity


LOCAL_WHEEL_MANIFEST_NAME = "termin-local-wheel-artifacts.json"
LOCAL_WHEEL_MANIFEST_SCHEMA = 1
LOCAL_WHEEL_MANIFEST_KIND = "termin-local-wheel-artifact-set"


class LocalWheelArtifactError(RuntimeError):
    """The local wheel set is incomplete, stale, mixed, or corrupted."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wheel_entries(wheel_dir: Path) -> list[dict[str, str]]:
    return [{"filename": wheel.name, "sha256": _sha256_file(wheel)} for wheel in sorted(wheel_dir.glob("*.whl"))]


def _artifact_manifest(sdk_prefix: Path) -> ArtifactManifest:
    try:
        manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        manifest.require_kind(SDK_MANIFEST_KIND)
        manifest.validate_all(expected_python_abi=manifest.python_abi)
        return manifest
    except (ArtifactManifestError, OSError) as error:
        raise LocalWheelArtifactError(
            f"cannot validate SDK artifact manifest: {error}"
        ) from error


def write_local_wheel_manifest(
    wheel_dir: Path,
    *,
    sdk_prefix: Path,
    expected_wheel_count: int,
) -> Path:
    artifact_manifest = _artifact_manifest(sdk_prefix)
    wheels = _wheel_entries(wheel_dir)
    if len(wheels) != expected_wheel_count:
        raise LocalWheelArtifactError(
            f"expected {expected_wheel_count} local wheels, found {len(wheels)} under {wheel_dir}"
        )
    payload = {
        "schema": LOCAL_WHEEL_MANIFEST_SCHEMA,
        "manifest_kind": LOCAL_WHEEL_MANIFEST_KIND,
        "native_build_id": artifact_manifest.native_build_id,
        "python_abi": artifact_manifest.python_abi.to_dict(),
        "wheels": wheels,
    }
    output = wheel_dir / LOCAL_WHEEL_MANIFEST_NAME
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def validate_local_wheel_artifact_set(
    wheel_dir: Path,
    *,
    sdk_prefix: Path,
    expected_wheel_count: int | None = None,
) -> dict[str, object]:
    manifest_path = wheel_dir / LOCAL_WHEEL_MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LocalWheelArtifactError(f"cannot read local wheel artifact manifest {manifest_path}: {error}") from error
    if not isinstance(payload, dict):
        raise LocalWheelArtifactError("local wheel artifact manifest must be an object")
    if payload.get("schema") != LOCAL_WHEEL_MANIFEST_SCHEMA:
        raise LocalWheelArtifactError("unsupported local wheel artifact schema")
    if payload.get("manifest_kind") != LOCAL_WHEEL_MANIFEST_KIND:
        raise LocalWheelArtifactError("invalid local wheel artifact manifest kind")

    artifact_manifest = _artifact_manifest(sdk_prefix)
    if payload.get("native_build_id") != artifact_manifest.native_build_id:
        raise LocalWheelArtifactError("local wheel artifact native_build_id does not match the SDK")
    try:
        wheel_abi = PythonAbiIdentity.from_mapping(
            payload.get("python_abi"),
            context="local wheel artifact Python ABI",
        )
        wheel_abi.require_matches(
            artifact_manifest.python_abi,
            context="local wheel artifact/SDK Python ABI",
        )
    except RuntimeError as error:
        raise LocalWheelArtifactError(str(error)) from error

    declared = payload.get("wheels")
    if not isinstance(declared, list):
        raise LocalWheelArtifactError("local wheel artifact list is missing")
    actual_entries = _wheel_entries(wheel_dir)
    if declared != actual_entries:
        raise LocalWheelArtifactError("local wheel files do not match their artifact manifest")
    allowed_files = {
        LOCAL_WHEEL_MANIFEST_NAME,
        *(entry["filename"] for entry in actual_entries),
    }
    unexpected = sorted(
        entry.name for entry in wheel_dir.iterdir() if entry.name not in allowed_files
    )
    if unexpected:
        raise LocalWheelArtifactError(
            "local wheel artifact directory contains unexpected entries: "
            + ", ".join(unexpected)
        )
    if expected_wheel_count is not None and len(actual_entries) != expected_wheel_count:
        raise LocalWheelArtifactError(
            f"expected {expected_wheel_count} local wheels, found {len(actual_entries)} under {wheel_dir}"
        )
    return payload


def _replace_directory(prepared: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(f".{destination.name}.previous-{uuid.uuid4().hex}")
    had_destination = destination.exists()
    if had_destination:
        destination.replace(backup)
    try:
        prepared.replace(destination)
    except Exception:
        if had_destination and backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def build_local_wheel_artifact_set(
    *,
    repo_root: Path,
    sdk_prefix: Path,
    bindings_dir: Path,
    wheel_dir: Path,
    build_python: Path,
    packages: Sequence[PackageEntry],
    run: Callable[..., int],
    clear_build_caches: Callable[[Path], None],
) -> int:
    wheel_dir.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "TERMIN_SDK": str(sdk_prefix),
            "TERMIN_BINDINGS_DIR": str(bindings_dir),
            "TERMIN_PIP_BUNDLE_LIBS": "0",
            "TERMIN_PIP_COPY_TO_SOURCE": "0",
        }
    )
    build_tools = str(repo_root / "termin-build-tools")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = build_tools if not existing_pythonpath else build_tools + os.pathsep + existing_pythonpath
    clear_build_caches(repo_root)

    with tempfile.TemporaryDirectory(
        prefix=f".{wheel_dir.name}.build-",
        dir=wheel_dir.parent,
    ) as temporary_root:
        prepared = Path(temporary_root) / "wheels"
        prepared.mkdir()
        pip_cmd = [str(build_python), "-m", "pip"]
        print("Using pip: " + " ".join(pip_cmd))
        print("TERMIN_PIP_BUNDLE_LIBS=0")
        print("TERMIN_PIP_COPY_TO_SOURCE=0")
        print("")
        print("========================================")
        print(f"  Building {len(packages)} Termin wheels")
        print("========================================")
        print("")
        result = run(
            [
                *pip_cmd,
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "--no-cache-dir",
                "--wheel-dir",
                str(prepared),
                *(str(repo_root / package.path) for package in packages),
            ],
            cwd=repo_root,
            env=env,
        )
        if result != 0:
            return result
        try:
            write_local_wheel_manifest(
                prepared,
                sdk_prefix=sdk_prefix,
                expected_wheel_count=len(packages),
            )
            validate_local_wheel_artifact_set(
                prepared,
                sdk_prefix=sdk_prefix,
                expected_wheel_count=len(packages),
            )
            _replace_directory(prepared, wheel_dir)
        except (LocalWheelArtifactError, OSError) as error:
            print(
                f"ERROR: failed to prepare local wheel artifacts: {error}",
                file=sys.stderr,
            )
            return 1
    return 0


def publish_local_wheel_artifact_set(
    source: Path,
    destination: Path,
    *,
    sdk_prefix: Path,
    expected_wheel_count: int,
) -> None:
    source_payload = validate_local_wheel_artifact_set(
        source,
        sdk_prefix=sdk_prefix,
        expected_wheel_count=expected_wheel_count,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}.publish-",
        dir=destination.parent,
    ) as temporary_root:
        prepared = Path(temporary_root) / "wheels"
        shutil.copytree(source, prepared)
        published_payload = validate_local_wheel_artifact_set(
            prepared,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=expected_wheel_count,
        )
        if published_payload != source_payload:
            raise LocalWheelArtifactError("published wheel artifact set differs from the runtime input")
        _replace_directory(prepared, destination)
