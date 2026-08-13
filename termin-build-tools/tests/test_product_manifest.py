from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build.package_manifest import load_manifest as load_package_manifest
from termin_build.product_manifest import (
    ProductManifestError,
    load_product_manifest,
    product_python_packages,
    validate_product_manifest,
    validate_repository_product_manifests,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_core_product_manifest_matches_repository_closure() -> None:
    manifest = load_product_manifest(REPO_ROOT, "core")

    assert manifest.module_paths == (
        "termin-build-tools",
        "termin-nanobind-sdk",
        "termin-base",
        "termin-dispatch",
        "termin-inspect",
        "termin-python-host",
        "termin-mcp",
    )
    assert manifest.python_runtime.owner == "core"
    assert manifest.python_runtime.abi == "cp314t"
    assert manifest.smoke_fixtures == ("tests/installed-core-consumers",)
    assert manifest.resources == ()
    assert validate_product_manifest(REPO_ROOT, manifest) == []


def test_core_python_package_projection_uses_product_order() -> None:
    manifest = load_product_manifest(REPO_ROOT, "core")

    packages = product_python_packages(manifest, load_package_manifest(REPO_ROOT))

    assert [package.distribution for package in packages] == [
        "termin-build-tools",
        "termin-nanobind",
        "tcbase",
        "termin-dispatch",
        "termin-inspect",
        "termin-mcp",
    ]


def test_repository_control_product_manifest_gate_is_clean() -> None:
    assert validate_repository_product_manifests(REPO_ROOT) == []


def test_core_product_rejects_domain_dependency_in_metadata(tmp_path: Path) -> None:
    manifest_path = REPO_ROOT / "build-system/products/core.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["modules"][2]["internal_dependencies"].append("termin-graphics")
    target = tmp_path / "build-system/products/core.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_product_manifest(tmp_path, "core")

    errors = validate_product_manifest(REPO_ROOT, manifest)
    assert "termin-base: internal dependencies outside product closure: termin-graphics" in errors
    assert "termin-base: forbidden dependencies: termin-graphics" in errors


def test_core_product_rejects_undeclared_native_target(tmp_path: Path) -> None:
    data = json.loads(
        (REPO_ROOT / "build-system/products/core.json").read_text(encoding="utf-8")
    )
    data["modules"][3]["native_targets"].remove("termin_dispatch")
    target = tmp_path / "build-system/products/core.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_product_manifest(tmp_path, "core")

    errors = validate_product_manifest(REPO_ROOT, manifest)
    assert "termin-dispatch: discovered undeclared native targets: termin_dispatch" in errors


def test_product_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    data = json.loads(
        (REPO_ROOT / "build-system/products/core.json").read_text(encoding="utf-8")
    )
    data["fallback_source_root"] = "../termin-core"
    target = tmp_path / "build-system/products/core.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ProductManifestError, match="unknown fields: fallback_source_root"):
        load_product_manifest(tmp_path, "core")


def test_product_manifest_schema_two_accepts_explicit_external_closure(
    tmp_path: Path,
) -> None:
    data = json.loads(
        (REPO_ROOT / "build-system/products/core.json").read_text(encoding="utf-8")
    )
    data["schema"] = 2
    data["external_products"] = []
    for module in data["modules"]:
        module["external_dependencies"] = []
        module["inactive_dependencies"] = []
    target = tmp_path / "build-system/products/core.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_product_manifest(tmp_path, "core")

    assert manifest.external_products == ()
