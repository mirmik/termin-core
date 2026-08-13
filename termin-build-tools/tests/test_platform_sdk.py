from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build.platform_sdk import PlatformIdentity, verify_manifest, write_manifest


def _sdk(tmp_path: Path) -> Path:
    sdk = tmp_path / "sdk"
    for package in ("termin_base", "termin_dispatch", "termin_inspect"):
        directory = sdk / "lib" / "cmake" / package
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{package}Config.cmake").write_text(
            f"# {package}\n", encoding="utf-8"
        )
    (sdk / "lib" / "libtermin_base.a").write_bytes(b"base")
    return sdk


def test_platform_manifest_roundtrips_and_binds_artifacts(tmp_path: Path) -> None:
    sdk = _sdk(tmp_path)
    path = write_manifest(
        sdk,
        PlatformIdentity(
            system="android",
            architecture="arm64-v8a",
            toolchain="android-ndk",
            toolchain_version="27.2.12479018",
            api="android-26",
        ),
    )

    payload = verify_manifest(
        sdk,
        expected_system="android",
        expected_architecture="arm64-v8a",
    )

    assert payload == json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["native_build_id"]) == 20
    assert payload["target"]["api"] == "android-26"


def test_platform_manifest_rejects_wrong_platform_and_build(tmp_path: Path) -> None:
    sdk = _sdk(tmp_path)
    write_manifest(
        sdk,
        PlatformIdentity("web", "wasm32", "emscripten", "6.0.5"),
    )

    with pytest.raises(RuntimeError, match="platform mismatch"):
        verify_manifest(sdk, expected_system="android")
    with pytest.raises(RuntimeError, match="build identity mismatch"):
        verify_manifest(sdk, expected_build_id="wrong")


def test_platform_manifest_rejects_modified_artifact(tmp_path: Path) -> None:
    sdk = _sdk(tmp_path)
    write_manifest(
        sdk,
        PlatformIdentity("web", "wasm32", "emscripten", "6.0.5"),
    )
    (sdk / "lib" / "libtermin_base.a").write_bytes(b"modified")

    with pytest.raises(RuntimeError, match="artifact hash mismatch"):
        verify_manifest(sdk)


def test_platform_sdk_rejects_desktop_python_payload(tmp_path: Path) -> None:
    sdk = _sdk(tmp_path)
    (sdk / "wheels").mkdir()

    with pytest.raises(RuntimeError, match="desktop Python payload"):
        write_manifest(
            sdk,
            PlatformIdentity("web", "wasm32", "emscripten", "6.0.5"),
        )
