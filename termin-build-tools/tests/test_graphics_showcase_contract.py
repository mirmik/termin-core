from __future__ import annotations

import ast
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SHOWCASE_ROOT = REPO_ROOT / "examples" / "graphics-showcase"


def _python_sources() -> list[Path]:
    return sorted(SHOWCASE_ROOT.rglob("*.py"))


def _graphics_profile_example_sources() -> list[Path]:
    roots = (
        REPO_ROOT / "termin-graphics" / "examples",
        REPO_ROOT / "termin-gui-native" / "examples",
        REPO_ROOT / "termin-nodegraph" / "examples",
        REPO_ROOT / "tcplot" / "examples",
        REPO_ROOT / "tcplot-gui-native" / "examples",
    )
    return sorted(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def test_graphics_showcase_has_one_artifact_section_and_documented_registry() -> None:
    sections_source = (
        SHOWCASE_ROOT / "graphics_showcase" / "sections.py"
    ).read_text(encoding="utf-8")
    readme = (SHOWCASE_ROOT / "README.md").read_text(encoding="utf-8")

    expected = {
        "native_ui",
        "plot_2d",
        "plot_3d",
        "visual_scene_nodegraph",
        "plot_nodegraph_composition",
    }
    for name in expected:
        assert f'name="{name}"' in sections_source
        assert f"`{name}`" in readme
    assert sections_source.count("artifact=True") == 1


def test_graphics_showcase_does_not_import_full_or_external_window_hosts() -> None:
    forbidden = {"sdl2", "termin.display", "termin.engine", "termin.runtime"}
    discovered: set[str] = set()
    for source_path in _python_sources():
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                discovered.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                discovered.add(node.module)

    for module in discovered:
        assert not any(
            module == prefix or module.startswith(prefix + ".")
            for prefix in forbidden
        ), module


def test_graphics_showcase_cli_requires_isolated_product_artifacts() -> None:
    main_source = (SHOWCASE_ROOT / "main.py").read_text(encoding="utf-8")
    runner_source = (
        SHOWCASE_ROOT / "graphics_showcase" / "runner.py"
    ).read_text(encoding="utf-8")
    readme = (SHOWCASE_ROOT / "README.md").read_text(encoding="utf-8")

    assert "graphics_showcase.cli import main" in main_source
    assert "sys.path.insert(0, str(_SHOWCASE_ROOT))" in main_source
    assert '"isolated": bool(sys.flags.isolated)' in runner_source
    assert "sdk/bin/termin_python -I" in readme


def test_graphics_showcase_windowed_frontend_uses_the_profile_host() -> None:
    cli_source = (
        SHOWCASE_ROOT / "graphics_showcase" / "cli.py"
    ).read_text(encoding="utf-8")
    windowed_source = (
        SHOWCASE_ROOT / "graphics_showcase" / "windowed.py"
    ).read_text(encoding="utf-8")
    readme = (SHOWCASE_ROOT / "README.md").read_text(encoding="utf-8")

    assert '"--windowed"' in cli_source
    assert "from termin.window import" in windowed_source
    assert "from termin.gui_native.window import GuiWindowAdapter" in windowed_source
    assert "termin.display" not in windowed_source
    assert "for section in section_registry()" in windowed_source
    assert 'tabs.add_page("Overview"' in windowed_source
    assert "tabs.add_page(_SECTION_TITLES[section.name]" in windowed_source
    assert "--windowed" in readme


def test_graphics_showcase_tabbed_frontend_builds_and_renders_every_page() -> None:
    sys.path.insert(0, str(SHOWCASE_ROOT))
    try:
        from graphics_showcase.sections import sdk_font_path
        from graphics_showcase.windowed import (
            _WindowedApplication,
            _build_tabbed_showcase,
        )
        from termin.gui_native import OffscreenGuiComposition

        composition = OffscreenGuiComposition(
            width=1280,
            height=820,
            font_path=str(sdk_font_path()),
            continuous_rendering=False,
        )
        contents = []
        try:
            application = _WindowedApplication(
                composition.document,
                composition.request_repaint,
            )
            tabs, contents = _build_tabbed_showcase(application)
            assert tabs.page_count == 6
            assert [tabs.page_title(index) for index in range(tabs.page_count)] == [
                "Overview",
                "Native UI",
                "Plot 2D",
                "Plot 3D",
                "Nodegraph",
                "Composition",
            ]
            for index in range(tabs.page_count):
                tabs.selected_index = index
                composition.request_repaint()
                assert composition.render_frame(), tabs.page_title(index)
        finally:
            for content in reversed(contents):
                content.cleanup()
            composition.close()
    finally:
        sys.path.remove(str(SHOWCASE_ROOT))


def test_graphics_showcase_has_an_installed_sdk_smoke_gate() -> None:
    smoke = (REPO_ROOT / "scripts" / "smoke-graphics-showcase").read_text(
        encoding="utf-8"
    )
    docs = (REPO_ROOT / "docs" / "smoke-checks.md").read_text(encoding="utf-8")

    assert 'FORBIDDEN_MODULES = ("termin.display", "termin.engine", "termin.runtime")' in smoke
    assert '"PYTHONHOME"' in smoke
    assert '"PYTHONPATH"' in smoke
    assert '"PYTHONUSERBASE"' in smoke
    assert "EXPECTED_SECTIONS" in smoke
    assert "scripts/smoke-graphics-showcase" in docs


def test_graphics_profile_examples_do_not_depend_on_full_or_pysdl_hosts() -> None:
    forbidden = {"sdl2", "termin.display"}
    for source_path in _graphics_profile_example_sources():
        tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
        discovered: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                discovered.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                discovered.add(node.module)
        for module in discovered:
            assert not any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in forbidden
            ), f"{source_path.relative_to(REPO_ROOT)} imports {module}"
