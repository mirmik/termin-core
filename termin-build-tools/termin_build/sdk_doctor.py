"""Build prerequisites and third-party submodule diagnostics."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


EXPECTED_SUBMODULE_FILES = {
    "termin-thirdparty/eigen": ("CMakeLists.txt",),
    "termin-thirdparty/manifold": ("CMakeLists.txt",),
    "termin-thirdparty/clipper2": ("CPP/CMakeLists.txt",),
    "termin-thirdparty/guard": ("guard_c.h", "guard_main.h"),
    "termin-thirdparty/zlib": ("CMakeLists.txt", "zlib.h"),
    "termin-thirdparty/libpng": ("CMakeLists.txt", "png.h"),
    "termin-thirdparty/libjpeg-turbo": ("CMakeLists.txt", "src/jpeglib.h"),
    "termin-thirdparty/libwebp": ("CMakeLists.txt", "src/webp/decode.h"),
    "termin-thirdparty/libogg": ("CMakeLists.txt", "include/ogg/ogg.h"),
    "termin-thirdparty/libvorbis": ("CMakeLists.txt", "include/vorbis/vorbisfile.h"),
    "termin-thirdparty/cgltf": ("cgltf.h",),
    "termin-thirdparty/sdl2": ("CMakeLists.txt", "include/SDL.h"),
    "termin-thirdparty/vulkan-memory-allocator": ("include/vk_mem_alloc.h",),
    "termin-thirdparty/openxr-sdk": ("include/openxr/openxr.h",),
    "termin-thirdparty/recastnavigation": (
        "Recast/CMakeLists.txt",
        "Detour/CMakeLists.txt",
    ),
}


SDK_NATIVE_SUBMODULES = (
    "termin-thirdparty/manifold",
    "termin-thirdparty/clipper2",
    "termin-thirdparty/recastnavigation",
    "termin-thirdparty/eigen",
    "termin-thirdparty/zlib",
    "termin-thirdparty/libpng",
    "termin-thirdparty/libjpeg-turbo",
    "termin-thirdparty/libwebp",
    "termin-thirdparty/libogg",
    "termin-thirdparty/libvorbis",
    "termin-thirdparty/cgltf",
)

SDK_GRAPHICS_SUBMODULES = (
    "termin-thirdparty/recastnavigation",
    "termin-thirdparty/eigen",
    "termin-thirdparty/zlib",
    "termin-thirdparty/libpng",
    "termin-thirdparty/libjpeg-turbo",
    "termin-thirdparty/libwebp",
)


@dataclass(frozen=True)
class DoctorProfile:
    name: str
    submodules: tuple[str, ...]
    needs_cmake: bool = True
    needs_git: bool = True
    needs_nanobind: bool = False
    needs_pip: bool = False
    needs_copy_backend: bool = False
    needs_sdk_writable: bool = False


PROFILES = {
    "sdk": DoctorProfile(
        name="sdk",
        submodules=SDK_NATIVE_SUBMODULES,
        needs_nanobind=True,
        needs_pip=True,
        needs_copy_backend=True,
        needs_sdk_writable=True,
    ),
    "sdk-cpp": DoctorProfile(
        name="sdk-cpp",
        submodules=SDK_NATIVE_SUBMODULES,
        needs_sdk_writable=True,
    ),
    "sdk-bindings": DoctorProfile(
        name="sdk-bindings",
        submodules=SDK_NATIVE_SUBMODULES,
        needs_nanobind=True,
        needs_copy_backend=True,
        needs_sdk_writable=True,
    ),
    "sdk-graphics": DoctorProfile(
        name="sdk-graphics",
        submodules=SDK_GRAPHICS_SUBMODULES,
        needs_nanobind=True,
        needs_pip=True,
        needs_copy_backend=True,
        needs_sdk_writable=True,
    ),
    "sdk-cpp-graphics": DoctorProfile(
        name="sdk-cpp-graphics",
        submodules=SDK_GRAPHICS_SUBMODULES,
        needs_sdk_writable=True,
    ),
    "sdk-bindings-graphics": DoctorProfile(
        name="sdk-bindings-graphics",
        submodules=SDK_GRAPHICS_SUBMODULES,
        needs_nanobind=True,
        needs_copy_backend=True,
        needs_sdk_writable=True,
    ),
    "cpp-tests": DoctorProfile(
        name="cpp-tests",
        submodules=SDK_NATIVE_SUBMODULES + ("termin-thirdparty/guard",),
    ),
}


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _submodule_ready(repo_root: Path, relative_path: str) -> bool:
    full_path = repo_root / relative_path
    if not full_path.is_dir():
        return False
    expected_files = EXPECTED_SUBMODULE_FILES.get(relative_path)
    if expected_files:
        return all((full_path / expected).exists() for expected in expected_files)
    try:
        next(full_path.iterdir())
    except StopIteration:
        return False
    return True


def missing_submodules(repo_root: Path, paths: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for path in paths:
        normalized_path = _normalize_path(path)
        if normalized_path in seen:
            continue
        seen.add(normalized_path)
        normalized.append(normalized_path)
    return [
        path for path in normalized
        if not _submodule_ready(repo_root, path)
    ]


def ensure_submodules(repo_root: Path, paths: list[str]) -> int:
    missing = missing_submodules(repo_root, paths)
    if not missing:
        return 0
    if shutil.which("git") is None:
        print(
            "ERROR: required git submodules are missing and git was not found:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    print("Initializing missing third-party submodules:")
    for path in missing:
        print(f"  - {path}")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "submodule",
            "update",
            "--init",
            "--recursive",
            "--",
            *missing,
        ],
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    still_missing = missing_submodules(repo_root, missing)
    if still_missing:
        print(
            "ERROR: required git submodules are still missing after initialization:",
            file=sys.stderr,
        )
        for path in still_missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    return 0


def profile_submodules(profile: DoctorProfile, vulkan: str, sdl: str = "OFF") -> list[str]:
    paths = list(profile.submodules)
    if vulkan == "ON":
        paths.append("termin-thirdparty/vulkan-memory-allocator")
    if sdl == "ON":
        paths.append("termin-thirdparty/sdl2")
    return paths
