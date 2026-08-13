from __future__ import annotations

import ast
from pathlib import Path

from termin_build.application_payload import load_application_payloads
from termin_build.package_manifest import load_manifest
from termin_build.sdk_profiles import (
    sdk_profile,
    select_application_payloads,
    select_python_packages,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_graphics_sdk_profile_has_only_graphics_python_closure() -> None:
    packages = select_python_packages(
        sdk_profile("graphics"),
        load_manifest(REPO_ROOT),
    )

    paths = [package.path for package in packages]
    assert "tcplot" in paths
    assert "termin-gui-native" in paths
    assert "termin-nodegraph" in paths
    assert "termin-visual-scene" in paths
    assert "termin-window" in paths
    assert "termin-assets" not in paths
    assert "termin-engine" not in paths
    assert "termin-render" not in paths
    assert "termin-physics" not in paths


def test_graphics_sdk_profile_has_no_desktop_application_payload() -> None:
    payloads = select_application_payloads(
        sdk_profile("graphics"),
        load_application_payloads(REPO_ROOT),
    )

    assert payloads == ()


def test_graphics_shader_runtime_declares_only_its_core_dependency() -> None:
    metadata = (REPO_ROOT / "termin-shader-runtime" / "setup.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(metadata)
    setup_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setup"
    )
    install_requires = next(
        keyword.value
        for keyword in setup_call.keywords
        if keyword.arg == "install_requires"
    )

    assert isinstance(install_requires, ast.List)
    assert [ast.literal_eval(element) for element in install_requires.elts] == ["tcbase"]
