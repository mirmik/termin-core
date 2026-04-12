"""Runtime helpers for termin pip packages.

Pip-path architecture: the termin SDK (shared libraries, headers, cmake configs)
lives at a single filesystem location — either $TERMIN_SDK, /opt/termin, or
%LOCALAPPDATA%/termin-sdk on Windows. Pip packages ship only Python wrappers
and nanobind binding .so files; they do not bundle shared libraries. At import
time, a pip package calls `preload_sdk_libs(...)` to make its C++ dependencies
available to the dynamic linker before loading its own binding module.
"""

import ctypes
import os
import sys
from pathlib import Path

_sdk_root = None
_preloaded = set()
_windows_dirs_registered = False


def find_sdk():
    """Locate the termin SDK root directory.

    Checks in order:
      1. $TERMIN_SDK environment variable
      2. /opt/termin (Linux/macOS)
      3. %LOCALAPPDATA%/termin-sdk (Windows)

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


def _register_windows_dll_dirs():
    global _windows_dirs_registered
    if _windows_dirs_registered:
        return
    if not hasattr(os, "add_dll_directory"):
        return
    sdk = _require_sdk()
    for sub in ("bin", "lib"):
        d = sdk / sub
        if d.is_dir():
            os.add_dll_directory(str(d))
    _windows_dirs_registered = True


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
    if sys.platform == "win32":
        _register_windows_dll_dirs()
        return

    sdk = _require_sdk()
    lib_dir = sdk / "lib"

    for name in lib_names:
        if name in _preloaded:
            continue
        candidates = [
            lib_dir / f"lib{name}.so",
            lib_dir / f"lib{name}.dylib",
        ]
        found = next((p for p in candidates if p.exists()), None)
        if found is None:
            versioned = sorted(lib_dir.glob(f"lib{name}.so.*")) \
                or sorted(lib_dir.glob(f"lib{name}.*.dylib"))
            if versioned:
                found = versioned[0]
        if found is None:
            raise ImportError(
                f"Cannot find lib{name} in {lib_dir}. Rebuild the SDK or "
                f"check TERMIN_SDK points to a valid installation."
            )
        ctypes.CDLL(str(found), mode=ctypes.RTLD_GLOBAL)
        _preloaded.add(name)
