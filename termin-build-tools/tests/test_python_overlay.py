from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import python_overlay
from termin_build.artifact_manifest import (
    SCHEMA_VERSION,
    SDK_MANIFEST_KIND,
    compute_native_build_id,
)
from termin_build.python_abi import PythonAbiIdentity


def _write_empty_sdk_manifest(sdk_root: Path) -> None:
    python_abi = PythonAbiIdentity.current()
    (sdk_root / "termin-artifacts.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA_VERSION,
                "manifest_kind": SDK_MANIFEST_KIND,
                "python_abi": python_abi.to_dict(),
                "native_build_id": compute_native_build_id([], python_abi),
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )


def _write_installed_payload_manifest(
    sdk_root: Path,
    payload_names: tuple[str, ...] = (),
) -> None:
    (sdk_root / "application-python-payloads.json").write_text(
        json.dumps(
            {
                "schema": 2,
                "python_abi": PythonAbiIdentity.current().to_dict(),
                "site_packages": "python/Lib/site-packages",
                "payloads": [
                    {"name": name, "imports": [], "executables": []}
                    for name in payload_names
                ],
                "files": [],
            }
        ),
        encoding="utf-8",
    )


def _write_distribution(
    site_packages: Path,
    distribution: str,
    module: str,
) -> None:
    package = site_packages / module
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("INSTALLED = True\n", encoding="utf-8")
    metadata = site_packages / f"{distribution.replace('-', '_')}-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {distribution}\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (metadata / "RECORD").write_text(
        f"{module}/__init__.py,,\n{metadata.name}/METADATA,,\n"
        f"{metadata.name}/RECORD,,\n",
        encoding="utf-8",
    )


def test_overlay_finder_combines_source_and_installed_package_paths(tmp_path: Path) -> None:
    source = tmp_path / "source" / "example"
    installed = tmp_path / "sdk" / "example"
    source.mkdir(parents=True)
    installed.mkdir(parents=True)
    (source / "__init__.py").write_text("VALUE = 'source'\n", encoding="utf-8")

    finder = python_overlay._OverlayFinder(
        {
            "example": python_overlay._Mapping(
                kind="package",
                source=source,
                installed=installed,
                source_paths=(source,),
            )
        }
    )

    spec = finder.find_spec("example")

    assert spec is not None
    assert spec.origin == str(source / "__init__.py")
    assert list(spec.submodule_search_locations or ()) == [
        str(installed),
        str(source),
    ]


def test_activate_overlay_rejects_stale_sdk_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_root = tmp_path / "sdk"
    sdk_root.mkdir()
    python_abi = PythonAbiIdentity.current()
    (sdk_root / "termin-artifacts.json").write_text(
        json.dumps(
            {
                "schema": SCHEMA_VERSION,
                "manifest_kind": SDK_MANIFEST_KIND,
                "python_abi": python_abi.to_dict(),
                "native_build_id": compute_native_build_id([], python_abi),
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "overlay.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": python_overlay.SCHEMA_VERSION,
                "sdk_root": str(sdk_root),
                "sdk_fingerprint": "stale",
                "python_abi": python_abi.to_dict(),
                "extra_sites": [],
                "mappings": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TERMIN_SDK", str(sdk_root))
    with pytest.raises(python_overlay.OverlayError, match="stale"):
        python_overlay.activate_overlay(manifest)


def test_create_overlay_uses_only_distributions_installed_in_sdk(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    sdk_root = tmp_path / "sdk"
    site_packages = sdk_root / "python" / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_sdk_manifest(sdk_root)
    _write_installed_payload_manifest(sdk_root)
    _write_distribution(site_packages, "present-package", "present_package")

    packages = []
    for name in ("present-package", "profile-excluded-package"):
        package_root = repo_root / name
        source = package_root / "python" / name.replace("-", "_") / "__init__.py"
        source.parent.mkdir(parents=True)
        source.write_text(f"SOURCE = {name!r}\n", encoding="utf-8")
        packages.append({"path": name, "distribution": name})
    build_system = repo_root / "build-system"
    build_system.mkdir()
    (build_system / "packages.json").write_text(
        json.dumps({"packages": packages}),
        encoding="utf-8",
    )

    manifest = python_overlay.create_overlay_manifest(
        repo_root,
        sdk_root,
        tmp_path / "overlay.json",
    )

    assert manifest["distributions"] == ["present-package"]
    assert "present_package" in manifest["mappings"]
    assert "profile_excluded_package" not in manifest["mappings"]


def test_create_overlay_uses_only_application_payloads_installed_in_sdk(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    sdk_root = tmp_path / "sdk"
    site_packages = sdk_root / "python" / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    _write_empty_sdk_manifest(sdk_root)
    _write_installed_payload_manifest(sdk_root, ("present-payload",))

    payloads = []
    for name in ("present-payload", "profile-excluded-payload"):
        module = name.replace("-", "_")
        source = repo_root / name / "termin" / module / "__init__.py"
        source.parent.mkdir(parents=True)
        source.write_text(f"SOURCE = {name!r}\n", encoding="utf-8")
        payloads.append(
            {
                "name": name,
                "source_root": f"{name}/termin",
                "destination_root": "termin",
                "paths": [module],
                "native_extensions": [],
                "imports": [],
                "executables": [],
            }
        )
    build_system = repo_root / "build-system"
    build_system.mkdir()
    (build_system / "packages.json").write_text(
        json.dumps({"packages": []}),
        encoding="utf-8",
    )
    (build_system / "application-python-payloads.json").write_text(
        json.dumps({"schema": 1, "payloads": payloads}),
        encoding="utf-8",
    )

    manifest = python_overlay.create_overlay_manifest(
        repo_root,
        sdk_root,
        tmp_path / "overlay.json",
    )

    assert manifest["application_payloads"] == ["present-payload"]
    assert "termin.present_payload" in manifest["mappings"]
    assert "termin.profile_excluded_payload" not in manifest["mappings"]


def test_find_source_file_ignores_generated_build_tree(tmp_path: Path) -> None:
    package_root = tmp_path / "package"
    source = package_root / "python" / "example" / "module.py"
    generated = package_root / "build" / "lib" / "example" / "module.py"
    source.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    source.write_text("SOURCE = True\n", encoding="utf-8")
    generated.write_text("SOURCE = False\n", encoding="utf-8")

    files = python_overlay._source_python_files(package_root)

    assert files == (source,)
    assert python_overlay._find_source_file(
        package_root,
        files,
        Path("example/module.py"),
    ) == source


def test_find_source_file_ignores_generated_install_tree(tmp_path: Path) -> None:
    package_root = tmp_path / "package"
    source = package_root / "python" / "example" / "module.py"
    generated = (
        package_root
        / "install"
        / "lib"
        / "python3.10"
        / "site-packages"
        / "example"
        / "module.py"
    )
    source.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    source.write_text("SOURCE = True\n", encoding="utf-8")
    generated.write_text("SOURCE = True\n", encoding="utf-8")

    files = python_overlay._source_python_files(package_root)

    assert files == (source,)
    assert python_overlay._find_source_file(
        package_root,
        files,
        Path("example/module.py"),
    ) == source
