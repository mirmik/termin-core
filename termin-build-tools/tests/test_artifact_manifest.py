from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from termin_build import artifact_manifest
from termin_build.artifact_manifest import ArtifactManifestError
from termin_build.cmake_ext import TerminCMakeBuildExt
from termin_build import sdk_verification


EXTENSION = "termin.sample._sample_native"
TARGET = "_sample_native"


def _write_manifest(
    root: Path,
    artifact_path: Path,
    *,
    kind: str = artifact_manifest.SDK_MANIFEST_KIND,
    path_value: str | None = None,
    digest: str | None = None,
) -> Path:
    manifest_path = root / (
        artifact_manifest.SDK_MANIFEST_NAME
        if kind == artifact_manifest.SDK_MANIFEST_KIND
        else artifact_manifest.BUILD_MANIFEST_NAME
    )
    data = {
        "schema": artifact_manifest.SCHEMA_VERSION,
        "manifest_kind": kind,
        "artifacts": [
            {
                "kind": "python-extension",
                "distribution": "termin-sample",
                "extension": EXTENSION,
                "target": TARGET,
                "python_abi": artifact_manifest.current_python_abi(),
                "path": path_value
                if path_value is not None
                else (
                    artifact_path.relative_to(root).as_posix()
                    if kind == artifact_manifest.SDK_MANIFEST_KIND
                    else str(artifact_path.resolve())
                ),
                "sha256": digest or artifact_manifest.sha256_file(artifact_path),
                "runtime_dependencies": [],
            }
        ],
    }
    data["native_build_id"] = artifact_manifest.compute_native_build_id(
        data["artifacts"]
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    return manifest_path


def test_sdk_manifest_remains_valid_after_relocation(tmp_path: Path) -> None:
    original = tmp_path / "original-sdk"
    binary = original / "lib" / "python" / "termin" / "sample" / "sample.so"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"native")
    _write_manifest(original, binary)

    relocated = tmp_path / "relocated-sdk"
    original.rename(relocated)
    manifest = artifact_manifest.ArtifactManifest.load(
        relocated / artifact_manifest.SDK_MANIFEST_NAME
    )

    resolved = manifest.resolve_extension(EXTENSION, expected_target=TARGET)
    assert resolved.path == relocated / "lib/python/termin/sample/sample.so"


def test_sdk_manifest_rejects_path_escape(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    outside = tmp_path / "outside.so"
    sdk_root.mkdir()
    outside.write_bytes(b"native")
    manifest_path = _write_manifest(sdk_root, outside, path_value="../outside.so")

    manifest = artifact_manifest.ArtifactManifest.load(manifest_path)
    with pytest.raises(ArtifactManifestError, match="escapes SDK root"):
        manifest.resolve_extension(EXTENSION)


def test_sdk_manifest_rejects_missing_and_tampered_payload(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    binary = sdk_root / "lib" / "sample.so"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"native")
    manifest_path = _write_manifest(sdk_root, binary)
    manifest = artifact_manifest.ArtifactManifest.load(manifest_path)

    binary.write_bytes(b"tampered")
    with pytest.raises(ArtifactManifestError, match="hash mismatch"):
        manifest.resolve_extension(EXTENSION)

    binary.unlink()
    with pytest.raises(ArtifactManifestError, match="is missing"):
        manifest.resolve_extension(EXTENSION)


def test_explicit_build_manifest_uses_exact_absolute_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root = tmp_path / "build"
    binary = build_root / "bin" / "sample.so"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"fresh")
    manifest_path = _write_manifest(
        build_root,
        binary,
        kind=artifact_manifest.BUILD_MANIFEST_KIND,
    )
    stale = tmp_path / "sdk" / "lib" / "python" / "sample.so"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")
    monkeypatch.setenv("TERMIN_ARTIFACT_MANIFEST", str(manifest_path))
    monkeypatch.setenv("TERMIN_SDK", str(tmp_path / "sdk"))

    command = object.__new__(TerminCMakeBuildExt)
    resolved = command._find_binding_module("termin.sample", TARGET)

    assert resolved.path == binary


def test_sdk_selection_never_falls_back_to_competing_checkout_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_root = tmp_path / "sdk"
    sdk_root.mkdir()
    manifest_path = sdk_root / artifact_manifest.SDK_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(
            {
                "schema": artifact_manifest.SCHEMA_VERSION,
                "manifest_kind": artifact_manifest.SDK_MANIFEST_KIND,
                "native_build_id": artifact_manifest.compute_native_build_id([]),
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    competing = tmp_path / "build" / "Release" / "bin" / "sample.so"
    competing.parent.mkdir(parents=True)
    competing.write_bytes(b"stale")
    monkeypatch.setenv("TERMIN_SDK", str(sdk_root))
    monkeypatch.chdir(tmp_path)

    command = object.__new__(TerminCMakeBuildExt)
    with pytest.raises(ArtifactManifestError, match="has no entry"):
        command._find_binding_module("termin.sample", TARGET)


def test_manifest_rejects_wrong_kind_target_and_abi(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    binary = sdk_root / "sample.so"
    sdk_root.mkdir()
    binary.write_bytes(b"native")
    manifest_path = _write_manifest(sdk_root, binary)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = data["artifacts"][0]
    entry["kind"] = "shared-library"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="expected 'python-extension'"):
        artifact_manifest.ArtifactManifest.load(manifest_path).resolve_extension(EXTENSION)

    entry["kind"] = "python-extension"
    entry["python_abi"] = "wrong-abi"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="ABI mismatch"):
        artifact_manifest.ArtifactManifest.load(manifest_path).resolve_extension(EXTENSION)

    entry["python_abi"] = artifact_manifest.current_python_abi()
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ArtifactManifestError, match="target mismatch"):
        artifact_manifest.ArtifactManifest.load(manifest_path).resolve_extension(
            EXTENSION, expected_target="wrong-target"
        )


def test_local_version_is_content_stable_and_changes_with_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_root = tmp_path / "sdk"
    binary = sdk_root / "sample.so"
    sdk_root.mkdir()
    binary.write_bytes(b"first")
    _write_manifest(sdk_root, binary)
    monkeypatch.setenv("TERMIN_SDK", str(sdk_root))

    first = TerminCMakeBuildExt.compute_local_version("0.1.0")
    binary.touch()
    assert TerminCMakeBuildExt.compute_local_version("0.1.0") == first

    binary.write_bytes(b"second")
    _write_manifest(sdk_root, binary)
    second = TerminCMakeBuildExt.compute_local_version("0.1.0")
    assert second != first
    assert second.startswith("0.1.0+sdk")


def _write_test_wheel(
    path: Path,
    *,
    version: str,
    payload_name: str,
    payload: bytes,
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"termin_sample-{version}.dist-info/METADATA",
            f"Name: termin-sample\nVersion: {version}\n",
        )
        archive.writestr(f"termin/sample/{payload_name}", payload)


def test_wheelhouse_verification_rejects_stale_version_and_payload(
    tmp_path: Path,
) -> None:
    sdk_root = tmp_path / "sdk"
    binary = sdk_root / "lib" / "python" / "termin" / "sample" / "sample.so"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"native")
    manifest_path = _write_manifest(sdk_root, binary)
    manifest = artifact_manifest.ArtifactManifest.load(manifest_path)
    version = f"0.1.0+sdk{manifest.native_build_id}"
    (sdk_root / "python-runtime-manifest.json").write_text(
        json.dumps(
            {
                "native_build_id": manifest.native_build_id,
                "distributions": [{"name": "termin-sample", "version": version}],
            }
        ),
        encoding="utf-8",
    )
    wheel_dir = sdk_root / "wheels"
    wheel_dir.mkdir()
    wheel = wheel_dir / "termin_sample.whl"
    _write_test_wheel(
        wheel,
        version=version,
        payload_name=binary.name,
        payload=b"native",
    )
    assert sdk_verification.verify_python_wheelhouse(sdk_root) == 0

    _write_test_wheel(
        wheel,
        version="0.1.0+sdkstale",
        payload_name=binary.name,
        payload=b"native",
    )
    assert sdk_verification.verify_python_wheelhouse(sdk_root) == 1

    _write_test_wheel(
        wheel,
        version=version,
        payload_name=binary.name,
        payload=b"tampered",
    )
    assert sdk_verification.verify_python_wheelhouse(sdk_root) == 1
