from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import sdk
from termin_build import artifact_manifest
from termin_build.application_payload import (
    INSTALLED_MANIFEST_NAME,
    install_application_payloads,
    load_application_payloads,
)
from termin_build.package_manifest import load_manifest
from termin_build.python_abi import PythonAbiIdentity


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_empty_artifact_manifest(sdk_root: Path) -> None:
    python_abi = PythonAbiIdentity.current()
    artifacts: list[dict[str, object]] = []
    (sdk_root / artifact_manifest.SDK_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": artifact_manifest.SCHEMA_VERSION,
                "manifest_kind": artifact_manifest.SDK_MANIFEST_KIND,
                "python_abi": python_abi.to_dict(),
                "native_build_id": artifact_manifest.compute_native_build_id(
                    artifacts,
                    python_abi,
                ),
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )


def test_termin_app_is_an_explicit_application_payload_not_a_distribution() -> None:
    repo_root = _repo_root()
    distributions = {entry.distribution for entry in load_manifest(repo_root)}
    payloads = load_application_payloads(repo_root)

    assert "termin-app" not in distributions
    assert not (repo_root / "termin-app/setup.py").exists()
    assert [payload.name for payload in payloads] == ["termin-desktop"]
    assert payloads[0].paths == (
        "__init__.py",
        "editor",
        "editor_core",
        "editor_native",
        "editor_tcgui",
        "launcher",
        "resources",
    )
    assert payloads[0].native_extensions[0].extension == (
        "termin.editor._editor_native"
    )


def test_representative_library_subset_has_no_termin_app_dependency() -> None:
    repo_root = _repo_root()
    packages = load_manifest(repo_root)
    by_distribution = {entry.distribution: entry for entry in packages}
    subset = {"tcbase", "tgfx", "termin-display", "termin-gui-native"}

    assert subset <= by_distribution.keys()
    for package in packages:
        package_root = repo_root / package.path
        for metadata_path in (package_root / "setup.py", package_root / "pyproject.toml"):
            if metadata_path.is_file():
                assert "termin-app" not in metadata_path.read_text(
                    encoding="utf-8"
                ).lower(), metadata_path


def test_application_payload_install_uses_only_declared_roots(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_root = repo_root / "app/termin"
    editor = source_root / "editor"
    editor.mkdir(parents=True)
    (source_root / "__init__.py").write_text("ROOT = True\n", encoding="utf-8")
    (editor / "__init__.py").write_text("EDITOR = True\n", encoding="utf-8")
    (source_root / "private.py").write_text("LEAK = True\n", encoding="utf-8")
    manifest_path = repo_root / "build-system/application-python-payloads.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "payloads": [
                    {
                        "name": "test-app",
                        "source_root": "app/termin",
                        "destination_root": "termin",
                        "paths": ["__init__.py", "editor"],
                        "native_extensions": [
                            {
                                "extension": "termin.editor._editor_native",
                                "target": "_editor_native",
                            }
                        ],
                        "imports": ["termin.editor"],
                        "executables": ["test_editor"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    native = tmp_path / "build/_editor_native.so"
    native.parent.mkdir()
    native.write_bytes(b"native")
    sdk_root = tmp_path / "sdk"
    site_packages = sdk_root / "lib/python3.10/site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_artifact_manifest(sdk_root)

    installed_manifest = install_application_payloads(
        repo_root,
        sdk_root,
        site_packages,
        lambda target: native if target == "_editor_native" else None,
        runtime_python_abi=PythonAbiIdentity.current(),
    )

    assert installed_manifest == sdk_root / INSTALLED_MANIFEST_NAME
    assert (site_packages / "termin/__init__.py").is_file()
    assert (site_packages / "termin/editor/__init__.py").is_file()
    assert (site_packages / "termin/editor/_editor_native.so").is_file()
    assert not (site_packages / "termin/private.py").exists()
    installed = json.loads(installed_manifest.read_text(encoding="utf-8"))
    assert installed["python_abi"] == PythonAbiIdentity.current().to_dict()
    assert {entry["kind"] for entry in installed["files"]} == {
        "source",
        "native-extension",
    }


def test_application_payload_install_rejects_library_collision(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_root = repo_root / "app/termin"
    source_root.mkdir(parents=True)
    (source_root / "__init__.py").write_text("APP = True\n", encoding="utf-8")
    manifest_path = repo_root / "build-system/application-python-payloads.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "payloads": [
                    {
                        "name": "test-app",
                        "source_root": "app/termin",
                        "destination_root": "termin",
                        "paths": ["__init__.py"],
                        "native_extensions": [],
                        "imports": [],
                        "executables": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    sdk_root = tmp_path / "sdk"
    site_packages = sdk_root / "lib/python3.10/site-packages"
    installed_init = site_packages / "termin/__init__.py"
    installed_init.parent.mkdir(parents=True)
    installed_init.write_text("LIBRARY = True\n", encoding="utf-8")
    _write_empty_artifact_manifest(sdk_root)

    with pytest.raises(RuntimeError, match="collides with an installed library"):
        install_application_payloads(
            repo_root,
            sdk_root,
            site_packages,
            lambda _target: None,
            runtime_python_abi=PythonAbiIdentity.current(),
        )


def test_application_native_extension_is_not_attributed_to_a_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    source_root = repo_root / "app/termin"
    source_root.mkdir(parents=True)
    (source_root / "__init__.py").write_text("APP = True\n", encoding="utf-8")
    build_system = repo_root / "build-system"
    build_system.mkdir()
    (build_system / "packages.json").write_text(
        json.dumps({"schema": 1, "packages": []}), encoding="utf-8"
    )
    (build_system / "application-python-payloads.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "payloads": [
                    {
                        "name": "test-app",
                        "source_root": "app/termin",
                        "destination_root": "termin",
                        "paths": ["__init__.py"],
                        "native_extensions": [
                            {
                                "extension": "termin.editor._editor_native",
                                "target": "_editor_native",
                            }
                        ],
                        "imports": [],
                        "executables": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    build_artifact = repo_root / "build/bin/_editor_native.so"
    build_artifact.parent.mkdir(parents=True)
    build_artifact.write_bytes(b"native")
    sdk_root = repo_root / "sdk"
    installed_artifact = (
        sdk_root / "lib/python3.10/site-packages/termin/editor/_editor_native.so"
    )
    installed_artifact.parent.mkdir(parents=True)
    installed_artifact.write_bytes(b"native")
    monkeypatch.setattr(sdk, "_native_runtime_dependencies", lambda _path: [])
    monkeypatch.setattr(sdk, "write_desktop_capabilities", lambda **_kwargs: None)

    assert sdk.write_artifacts(repo_root, repo_root / "build", sdk_root) == 0

    artifacts = json.loads(
        (sdk_root / "termin-artifacts.json").read_text(encoding="utf-8")
    )["artifacts"]
    assert artifacts[0]["application_payload"] == "test-app"
    assert "distribution" not in artifacts[0]
