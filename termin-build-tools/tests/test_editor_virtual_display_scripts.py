from __future__ import annotations

import runpy
import struct
import zlib
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPOSITORY_ROOT / "scripts" / "termin-editor-virtual-display"
WRAPPER_GLOBALS = runpy.run_path(str(WRAPPER))
SMOKE_GLOBALS = runpy.run_path(str(REPOSITORY_ROOT / "scripts" / "smoke-editor-virtual-display"))
VirtualDisplayError = WRAPPER_GLOBALS["VirtualDisplayError"]
_editor_environment = WRAPPER_GLOBALS["_editor_environment"]
_validate_glxinfo = WRAPPER_GLOBALS["_validate_glxinfo"]
_png_has_visible_pixel = SMOKE_GLOBALS["_png_has_visible_pixel"]


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
    assert environment["TERMIN_EDITOR_MCP_SESSION_FILE"] == str(tmp_path / "session.json")


def _write_rgb_png(path: Path, pixel: tuple[int, int, int]) -> None:
    raw = b"\x00" + bytes(pixel)
    chunks = []
    for chunk_type, payload in (
        (b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)),
        (b"IDAT", zlib.compress(raw)),
        (b"IEND", b""),
    ):
        chunks.append(
            struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", zlib.crc32(chunk_type + payload))
        )
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(chunks))


def test_virtual_display_smoke_detects_visible_png_pixel(tmp_path: Path) -> None:
    black = tmp_path / "black.png"
    visible = tmp_path / "visible.png"
    _write_rgb_png(black, (0, 0, 0))
    _write_rgb_png(visible, (0, 1, 0))

    assert not _png_has_visible_pixel(black)
    assert _png_has_visible_pixel(visible)
