from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import sdk_release


def _minimal_sdk(tmp_path: Path, *, platform: str = "win32") -> Path:
    sdk = tmp_path / "sdk"
    (sdk / "bin").mkdir(parents=True)
    (sdk / "lib").mkdir()
    (sdk / "wheels").mkdir()
    launcher = "termin_python.exe" if platform == "win32" else "termin_python"
    (sdk / "bin" / launcher).write_bytes(b"launcher")
    (sdk / "wheels" / "tgfx-0.1.0-cp314-cp314t-win_amd64.whl").write_bytes(b"wheel")
    abi = {
        "version": "3.14",
        "soabi": "cp314t-win_amd64",
        "free_threaded": True,
        "py_gil_disabled": True,
    }
    (sdk / "python-runtime-manifest.json").write_text(
        json.dumps(
            {
                "schema": 4,
                "platform": platform,
                "native_build_id": "0123456789abcdefghij",
                "python_abi": abi,
            }
        ),
        encoding="utf-8",
    )
    (sdk / "termin-artifacts.json").write_text(
        json.dumps(
            {
                "schema": 3,
                "manifest_kind": "termin-sdk-artifacts",
                "native_build_id": "0123456789abcdefghij",
                "python_abi": abi,
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    return sdk


class _FakeArtifacts:
    native_build_id = "0123456789abcdefghij"

    def __init__(self) -> None:
        self.python_abi = sdk_release.PythonAbiIdentity(
            version="3.14",
            soabi="cp314t-win_amd64",
            free_threaded=True,
            py_gil_disabled=True,
        )

    def require_kind(self, expected: str) -> None:
        assert expected == "termin-sdk-artifacts"

    def validate_all(self, *, expected_python_abi: object) -> None:
        assert expected_python_abi == self.python_abi


def test_canonical_asset_names() -> None:
    assert (
        sdk_release.asset_name("linux-x86_64")
        == "termin-sdk-linux-x86_64-py314t-latest-ci.tar.zst"
    )
    assert (
        sdk_release.asset_name("windows-x86_64")
        == "termin-sdk-windows-x86_64-py314t-latest-ci.zip"
    )
    assert (
        sdk_release.checksum_name("windows-x86_64")
        == "termin-sdk-windows-x86_64-py314t-latest-ci.sha256"
    )


def test_release_contract_accepts_cp314t_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = _minimal_sdk(tmp_path)
    monkeypatch.setattr(
        sdk_release.ArtifactManifest,
        "load",
        lambda path: _FakeArtifacts(),
    )
    result = sdk_release.validate_release_contract(sdk, "windows-x86_64")
    assert result["native_build_id"] == "0123456789abcdefghij"
    assert result["native_wheel_count"] == 1


def test_release_contract_rejects_regular_cp314_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = _minimal_sdk(tmp_path)
    wheel = next((sdk / "wheels").glob("*.whl"))
    wheel.rename(sdk / "wheels" / "tgfx-0.1.0-cp314-cp314-win_amd64.whl")
    monkeypatch.setattr(
        sdk_release.ArtifactManifest,
        "load",
        lambda path: _FakeArtifacts(),
    )
    with pytest.raises(sdk_release.SdkReleaseError, match="non-cp314t"):
        sdk_release.validate_release_contract(sdk, "windows-x86_64")


def test_failed_validation_does_not_replace_existing_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    existing = output / sdk_release.asset_name("windows-x86_64")
    existing.write_bytes(b"known-good")
    monkeypatch.setattr(
        sdk_release,
        "validate_sdk",
        lambda sdk, platform: (_ for _ in ()).throw(
            sdk_release.SdkReleaseError("invalid SDK")
        ),
    )
    with pytest.raises(sdk_release.SdkReleaseError, match="invalid SDK"):
        sdk_release.package_sdk(
            sdk_prefix=tmp_path / "sdk",
            output_dir=output,
            platform="windows-x86_64",
            repository="mirmik/termin",
            source_sha="abc",
            source_ref="master",
        )
    assert existing.read_bytes() == b"known-good"
