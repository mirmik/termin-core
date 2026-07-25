from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import artifact_manifest
from termin_build.local_wheel_artifacts import (
    LOCAL_WHEEL_MANIFEST_NAME,
    LocalWheelArtifactError,
    build_local_wheel_artifact_set,
    publish_local_wheel_artifact_set,
    validate_local_wheel_artifact_set,
    write_local_wheel_manifest,
)
from termin_build.package_manifest import PackageEntry
from termin_build.python_abi import PythonAbiIdentity


def _write_sdk_manifest(sdk_prefix: Path) -> None:
    python_abi = PythonAbiIdentity.current()
    payload = {
        "schema": artifact_manifest.SCHEMA_VERSION,
        "manifest_kind": artifact_manifest.SDK_MANIFEST_KIND,
        "python_abi": python_abi.to_dict(),
        "native_build_id": artifact_manifest.compute_native_build_id([], python_abi),
        "artifacts": [],
    }
    sdk_prefix.mkdir(parents=True)
    (sdk_prefix / artifact_manifest.SDK_MANIFEST_NAME).write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _packages() -> list[PackageEntry]:
    return [
        PackageEntry("one", "one", (), ()),
        PackageEntry("two", "two", (), ()),
    ]


def test_build_and_publish_use_one_canonical_wheel_payload(tmp_path: Path) -> None:
    sdk_prefix = tmp_path / "sdk"
    build_wheels = tmp_path / "build" / "termin-wheels"
    public_wheels = sdk_prefix / "wheels"
    _write_sdk_manifest(sdk_prefix)
    calls = []

    def run(command, *, cwd, env):
        calls.append((command, cwd, env))
        wheel_dir = Path(command[command.index("--wheel-dir") + 1])
        (wheel_dir / "one-1-py3-none-any.whl").write_bytes(b"one")
        (wheel_dir / "two-1-py3-none-any.whl").write_bytes(b"two")
        return 0

    result = build_local_wheel_artifact_set(
        repo_root=tmp_path,
        sdk_prefix=sdk_prefix,
        bindings_dir=tmp_path / "bindings",
        wheel_dir=build_wheels,
        build_python=tmp_path / "python",
        packages=_packages(),
        run=run,
        clear_build_caches=lambda root: calls.append(("clear", root)),
    )
    assert result == 0
    assert sum(1 for call in calls if isinstance(call, tuple) and len(call) == 3) == 1

    publish_local_wheel_artifact_set(
        build_wheels,
        public_wheels,
        sdk_prefix=sdk_prefix,
        expected_wheel_count=2,
    )

    source = validate_local_wheel_artifact_set(
        build_wheels,
        sdk_prefix=sdk_prefix,
        expected_wheel_count=2,
    )
    published = validate_local_wheel_artifact_set(
        public_wheels,
        sdk_prefix=sdk_prefix,
        expected_wheel_count=2,
    )
    assert published == source
    assert (public_wheels / LOCAL_WHEEL_MANIFEST_NAME).is_file()


def test_validation_rejects_tampered_wheel(tmp_path: Path) -> None:
    sdk_prefix = tmp_path / "sdk"
    wheel_dir = tmp_path / "wheels"
    _write_sdk_manifest(sdk_prefix)
    wheel_dir.mkdir()
    wheel = wheel_dir / "one-1-py3-none-any.whl"
    wheel.write_bytes(b"one")

    write_local_wheel_manifest(
        wheel_dir,
        sdk_prefix=sdk_prefix,
        expected_wheel_count=1,
    )
    wheel.write_bytes(b"tampered")

    with pytest.raises(LocalWheelArtifactError, match="do not match"):
        validate_local_wheel_artifact_set(wheel_dir, sdk_prefix=sdk_prefix)


def test_failed_rebuild_preserves_previous_artifact_set(tmp_path: Path) -> None:
    sdk_prefix = tmp_path / "sdk"
    wheel_dir = tmp_path / "wheels"
    _write_sdk_manifest(sdk_prefix)
    wheel_dir.mkdir()
    previous_wheel = wheel_dir / "one-1-py3-none-any.whl"
    previous_wheel.write_bytes(b"previous")
    write_local_wheel_manifest(
        wheel_dir,
        sdk_prefix=sdk_prefix,
        expected_wheel_count=1,
    )
    previous_manifest = (wheel_dir / LOCAL_WHEEL_MANIFEST_NAME).read_bytes()

    result = build_local_wheel_artifact_set(
        repo_root=tmp_path,
        sdk_prefix=sdk_prefix,
        bindings_dir=tmp_path / "bindings",
        wheel_dir=wheel_dir,
        build_python=tmp_path / "python",
        packages=[PackageEntry("one", "one", (), ())],
        run=lambda *args, **kwargs: 1,
        clear_build_caches=lambda root: None,
    )

    assert result == 1
    assert previous_wheel.read_bytes() == b"previous"
    assert (wheel_dir / LOCAL_WHEEL_MANIFEST_NAME).read_bytes() == previous_manifest
