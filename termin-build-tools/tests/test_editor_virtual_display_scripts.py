from __future__ import annotations

import runpy
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPOSITORY_ROOT / "scripts" / "termin-editor-virtual-display"
WRAPPER_GLOBALS = runpy.run_path(str(WRAPPER))
VirtualDisplayError = WRAPPER_GLOBALS["VirtualDisplayError"]
_editor_environment = WRAPPER_GLOBALS["_editor_environment"]
_validate_glxinfo = WRAPPER_GLOBALS["_validate_glxinfo"]


def _glxinfo(*, vendor: str = "Mesa", renderer: str = "llvmpipe") -> str:
    return "\n".join(
        (
            f"OpenGL vendor string: {vendor}",
            f"OpenGL renderer string: {renderer}",
            "OpenGL core profile version string: 4.6 (Core Profile) Mesa 26.0.3",
            "OpenGL core profile shading language version string: 4.60",
        )
    )


def test_glx_preflight_accepts_supported_mesa_llvmpipe() -> None:
    capabilities = _validate_glxinfo(_glxinfo())

    assert capabilities["vendor"] == "Mesa"
    assert capabilities["renderer"] == "llvmpipe"
    assert capabilities["glsl"] == "4.60"


@pytest.mark.parametrize(
    ("vendor", "renderer", "message"),
    (
        ("NVIDIA Corporation", "NVIDIA GeForce", "requires Mesa"),
        ("Mesa", "AMD Radeon", "requires Mesa llvmpipe"),
    ),
)
def test_glx_preflight_rejects_non_baseline_renderer(
    vendor: str,
    renderer: str,
    message: str,
) -> None:
    with pytest.raises(VirtualDisplayError, match=message):
        _validate_glxinfo(_glxinfo(vendor=vendor, renderer=renderer))


def test_editor_environment_forces_isolated_mcp_and_software_opengl(
    tmp_path: Path,
) -> None:
    environment = _editor_environment(
        {"PATH": "/usr/bin", "TERMIN_BACKEND": "vulkan"},
        sdk_root=tmp_path / "sdk",
        session_file=tmp_path / "session.json",
        gl_version="4.6",
        glsl_version="460",
    )

    assert environment["TERMIN_BACKEND"] == "opengl"
    assert environment["LIBGL_ALWAYS_SOFTWARE"] == "1"
    assert environment["MESA_GL_VERSION_OVERRIDE"] == "4.6"
    assert environment["MESA_GLSL_VERSION_OVERRIDE"] == "460"
    assert environment["TERMIN_EDITOR_MCP"] == "1"
    assert environment["TERMIN_EDITOR_MCP_PORT"] == "0"
    assert environment["TERMIN_EDITOR_MCP_SESSION_FILE"] == str(
        tmp_path / "session.json"
    )
