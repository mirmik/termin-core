from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import python_overlay


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
    (sdk_root / "termin-artifacts.json").write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "overlay.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": 1,
                "sdk_root": str(sdk_root),
                "sdk_fingerprint": "stale",
                "python_abi": "3.10",
                "extra_sites": [],
                "mappings": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TERMIN_SDK", str(sdk_root))
    with pytest.raises(python_overlay.OverlayError, match="stale"):
        python_overlay.activate_overlay(manifest)


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
