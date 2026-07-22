"""SDK capability manifest generation for installed Android ABI prefixes."""

from __future__ import annotations

import json
import platform
import sys
import uuid
from pathlib import Path


SDK_CAPABILITIES_NAME = "termin-sdk-capabilities.json"
ANDROID_ABI_CAPABILITIES_RELATIVE = Path("share/termin/android-capabilities.json")


def _desktop_target() -> tuple[str, str]:
    if sys.platform == "win32":
        target_os = "windows"
    elif sys.platform.startswith("linux"):
        target_os = "linux"
    else:
        raise RuntimeError(f"unsupported desktop SDK operating system: {sys.platform}")

    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        target_arch = "x86_64"
    else:
        raise RuntimeError(f"unsupported desktop SDK architecture: {machine or 'unknown'}")
    return target_os, target_arch


def _cmake_cache_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("//", "#")) or "=" not in line:
            continue
        declaration, value = line.split("=", 1)
        name, separator, _type = declaration.partition(":")
        if separator:
            values[name] = value
    return values


def _cmake_bool(value: str | None) -> bool:
    return value is not None and value.upper() in {"1", "ON", "TRUE", "YES", "Y"}


def _write_json_atomic(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_versioned_object(path: Path, label: str) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"failed to read {label} {path}: {error}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise RuntimeError(f"unsupported {label}: {path}")
    return data


def _installed_loader_exists(abi_prefix: Path) -> bool:
    candidates = (
        abi_prefix / "lib" / "libopenxr_loader.so",
        abi_prefix / "bin" / "libopenxr_loader.so",
    )
    if any(path.is_file() for path in candidates):
        return True
    return any(path.is_file() for path in (abi_prefix / "lib").glob("libopenxr_loader.so.*"))


def _build_abi_capabilities(
    cache: dict[str, str],
    abi_prefix: Path,
    abi: str,
) -> dict[str, object]:
    vulkan_library = cache.get("ANDROID_VULKAN_LIB", "")
    return {
        "version": 1,
        "abi": abi,
        "openxr_headers": _cmake_bool(cache.get("TERMIN_OPENXR_HAS_HEADERS")),
        "openxr_loader": _installed_loader_exists(abi_prefix),
        "vulkan": (
            _cmake_bool(cache.get("TERMIN_ENABLE_VULKAN"))
            and bool(vulkan_library)
            and not vulkan_library.endswith("-NOTFOUND")
            and Path(vulkan_library).is_file()
        ),
    }


def _discover_android_capabilities(
    android_sdk_root: Path,
) -> dict[str, dict[str, object]]:
    discovered: dict[str, dict[str, object]] = {}
    if not android_sdk_root.is_dir():
        return discovered
    for child in android_sdk_root.iterdir():
        path = child / ANDROID_ABI_CAPABILITIES_RELATIVE
        if child.is_dir() and path.is_file():
            discovered[child.name] = _read_versioned_object(
                path, "Android capabilities"
            )
    return discovered


def _update_aggregate_manifest(
    manifest: dict[str, object],
    discovered: dict[str, dict[str, object]],
) -> None:
    android_abis = sorted(discovered)
    quest_abis = [
        name
        for name in android_abis
        if all(
            discovered[name].get(capability) is True
            for capability in ("openxr_headers", "openxr_loader", "vulkan")
        )
    ]
    platforms = manifest.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        raise RuntimeError("SDK capability field 'platforms' must be an object")
    platforms["android"] = {
        "abis": android_abis,
        "vulkan": bool(android_abis)
        and all(discovered[name].get("vulkan") is True for name in android_abis),
        "python_runtime": False,
    }
    platforms["quest_openxr"] = {
        "abis": quest_abis,
        "openxr_headers": bool(quest_abis),
        "openxr_loader": bool(quest_abis),
        "vulkan": bool(quest_abis),
    }


def write_desktop_capabilities(*, sdk_root: Path) -> None:
    """Record the installed desktop payload and its exact build target."""

    manifest_path = sdk_root / SDK_CAPABILITIES_NAME
    manifest = (
        _read_versioned_object(manifest_path, "SDK capability manifest")
        if manifest_path.is_file()
        else {"version": 1, "sdk_version": "", "tools": {}}
    )
    target_os, target_arch = _desktop_target()
    executable_suffix = ".exe" if target_os == "windows" else ""
    player_path = sdk_root / "bin" / f"termin_player{executable_suffix}"
    shaderc_path = sdk_root / "bin" / f"termin_shaderc{executable_suffix}"
    native_patterns = ("*.dll",) if target_os == "windows" else ("*.so", "*.so.*")
    native_libraries = any(
        path.is_file()
        for directory in (sdk_root / "bin", sdk_root / "lib")
        if directory.is_dir()
        for pattern in native_patterns
        for path in directory.glob(pattern)
    )
    if target_os == "windows":
        python_runtime = (sdk_root / "python" / "Lib" / "os.py").is_file()
    else:
        python_runtime = any((path / "os.py").is_file() for path in (sdk_root / "lib").glob("python3.*"))

    platforms = manifest.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        raise RuntimeError("SDK capability field 'platforms' must be an object")
    platforms["desktop"] = {
        "os": target_os,
        "arch": target_arch,
        "player": player_path.is_file(),
        "native_libraries": native_libraries,
        "python_runtime": python_runtime,
        "builtin_shaders": (sdk_root / "share" / "termin" / "builtin_shaders").is_dir(),
    }
    tools = manifest.setdefault("tools", {})
    if not isinstance(tools, dict):
        raise RuntimeError("SDK capability field 'tools' must be an object")
    tools["termin_player"] = player_path.relative_to(sdk_root).as_posix()
    tools["termin_shaderc"] = shaderc_path.relative_to(sdk_root).as_posix()
    _write_json_atomic(manifest_path, manifest)


def write_android_capabilities(
    *,
    sdk_root: Path,
    android_sdk_root: Path,
    abi: str,
    build_dir: Path,
) -> int:
    cache_path = build_dir / "CMakeCache.txt"
    if not cache_path.is_file():
        print(f"ERROR: Android CMake cache not found: {cache_path}", file=sys.stderr)
        return 1

    manifest_path = sdk_root / SDK_CAPABILITIES_NAME
    try:
        manifest = (
            _read_versioned_object(manifest_path, "SDK capability manifest")
            if manifest_path.is_file()
            else {"version": 1, "sdk_version": "", "tools": {}}
        )
        abi_prefix = android_sdk_root / abi
        abi_path = abi_prefix / ANDROID_ABI_CAPABILITIES_RELATIVE
        abi_data = _build_abi_capabilities(
            _cmake_cache_values(cache_path), abi_prefix, abi
        )
        _write_json_atomic(abi_path, abi_data)
        discovered = _discover_android_capabilities(android_sdk_root)
        _update_aggregate_manifest(manifest, discovered)
        _write_json_atomic(manifest_path, manifest)
    except (OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Wrote Android SDK capabilities: {manifest_path}")
    return 0
