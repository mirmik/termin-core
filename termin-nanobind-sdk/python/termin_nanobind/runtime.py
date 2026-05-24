"""Runtime helpers for termin pip packages.

Termin packages can run in two layouts:

1. Standalone pip install: a package may carry its native dependencies in a
   local ``lib/`` directory next to the binding module.
2. SDK install: shared libraries live in ``$TERMIN_SDK/lib``.

At import time, packages call ``preload_sdk_libs(...)`` before importing their
nanobind module so dependent shared libraries are visible to the dynamic linker.
"""

import ctypes
import os
import sys
from pathlib import Path

_sdk_root = None
_preloaded = set()
_windows_dirs_registered = False
_windows_local_dirs = set()


def find_sdk():
    """Locate the termin SDK root directory.

    Checks in order:
      1. $TERMIN_SDK environment variable
      2. ./sdk from the current project checkout
      3. /opt/termin (Linux/macOS)
      4. %LOCALAPPDATA%/termin-sdk (Windows)

    Returns a Path, or None if no SDK is found.
    """
    global _sdk_root
    if _sdk_root is not None:
        return _sdk_root

    env = os.environ.get("TERMIN_SDK")
    if env:
        p = Path(env)
        if (p / "lib").is_dir():
            _sdk_root = p
            return p

    cwd_sdk = Path.cwd() / "sdk"
    if (cwd_sdk / "lib").is_dir():
        _sdk_root = cwd_sdk
        return cwd_sdk

    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        checkout_sdk = parent / "sdk"
        if (checkout_sdk / "lib").is_dir():
            _sdk_root = checkout_sdk
            return checkout_sdk

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        default = Path(local) / "termin-sdk"
    else:
        default = Path("/opt/termin")

    if (default / "lib").is_dir():
        _sdk_root = default
        return default

    return None


def _require_sdk():
    sdk = find_sdk()
    if sdk is None:
        raise ImportError(
            "termin SDK not found. Set TERMIN_SDK environment variable or "
            "install the SDK to /opt/termin (Linux/macOS) or "
            "%LOCALAPPDATA%/termin-sdk (Windows)."
        )
    return sdk


def _caller_lib_dirs():
    dirs = []
    try:
        frame = sys._getframe(2)
    except ValueError:
        return dirs
    module_file = frame.f_globals.get("__file__")
    if not module_file:
        return dirs

    start = Path(module_file).resolve().parent
    for parent in (start, *start.parents):
        lib_dir = parent / "lib"
        if lib_dir.is_dir():
            dirs.append(lib_dir)
        if parent.name in {"site-packages", "dist-packages"}:
            break
    return dirs


def _register_windows_dll_dirs(local_dirs):
    global _windows_dirs_registered
    if _windows_dirs_registered:
        for d in local_dirs:
            key = str(d)
            if key not in _windows_local_dirs:
                os.add_dll_directory(key)
                _windows_local_dirs.add(key)
        return
    if not hasattr(os, "add_dll_directory"):
        return
    for d in local_dirs:
        os.add_dll_directory(str(d))
        _windows_local_dirs.add(str(d))
    sdk = find_sdk()
    if sdk is None:
        _windows_dirs_registered = True
        return
    for sub in ("bin", "lib"):
        d = sdk / sub
        if d.is_dir():
            os.add_dll_directory(str(d))
    _windows_dirs_registered = True


def _find_library(name, lib_dirs):
    for lib_dir in lib_dirs:
        candidates = [
            lib_dir / f"lib{name}.so",
            lib_dir / f"lib{name}.dylib",
        ]
        found = next((p for p in candidates if p.exists()), None)
        if found is not None:
            return found
        versioned = sorted(lib_dir.glob(f"lib{name}.so.*")) \
            or sorted(lib_dir.glob(f"lib{name}.*.dylib"))
        if versioned:
            return versioned[0]
    return None


def preload_sdk_libs(*lib_names):
    """Preload termin SDK shared libraries into the global symbol namespace.

    Args:
        *lib_names: library base names without the "lib" prefix or extension,
            e.g. "termin_base", "termin_display".

    On Linux/macOS each named library is opened via ctypes.CDLL with
    RTLD_GLOBAL, so that subsequent dlopen of a nanobind binding module
    (which has the same DT_NEEDED entries) reuses the already-loaded
    mappings regardless of its own RPATH.

    On Windows this function registers the SDK lib and bin directories via
    os.add_dll_directory. On Windows the loader searches those directories
    directly, so explicit CDLL preloading is unnecessary.
    """
    local_lib_dirs = _caller_lib_dirs()

    if sys.platform == "win32":
        _register_windows_dll_dirs(local_lib_dirs)
        return

    sdk = find_sdk()
    sdk_lib_dir = sdk / "lib" if sdk is not None else None
    lib_dirs = list(local_lib_dirs)
    if sdk_lib_dir is not None and sdk_lib_dir.is_dir():
        lib_dirs.append(sdk_lib_dir)

    for name in lib_names:
        if name in _preloaded:
            continue
        found = _find_library(name, lib_dirs)
        if found is None:
            searched = ", ".join(str(p) for p in lib_dirs) or "<none>"
            raise ImportError(
                f"Cannot find lib{name}. Searched: {searched}. "
                f"Install a package with bundled native libraries, rebuild the "
                f"SDK, or check TERMIN_SDK points to a valid installation."
            )
        ctypes.CDLL(str(found), mode=ctypes.RTLD_GLOBAL)
        _preloaded.add(name)
