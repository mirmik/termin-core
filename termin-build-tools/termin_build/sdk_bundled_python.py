"""Bundled Python runtime layout owned by the Termin SDK."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Mapping

from .sdk_python_layout import (
    _bundled_python_dir_name,
    _copy_tree_contents,
    _is_windows,
    _python_executable,
    _python_version_and_paths,
)


def _copy_windows_python_runtime_executables(
    sdk_prefix: Path,
    info: dict[str, object],
) -> None:
    if not _is_windows():
        return

    python_home = sdk_prefix / "python"
    bin_dir = sdk_prefix / "bin"
    python_home.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    executable = Path(str(info.get("base_executable") or info.get("executable") or ""))
    if executable.is_file():
        shutil.copy2(executable, python_home / "python.exe")
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.is_file():
            shutil.copy2(pythonw, python_home / "pythonw.exe")

    dll_roots = []
    for key in ("base_prefix", "prefix"):
        value = str(info.get(key) or "")
        if value:
            dll_roots.append(Path(value))
    if executable.is_file():
        dll_roots.append(executable.parent)

    seen: set[Path] = set()
    for root in dll_roots:
        if not root.is_dir():
            continue
        for dll in root.glob("python*.dll"):
            source = dll.resolve()
            if source in seen:
                continue
            seen.add(source)
            shutil.copy2(dll, bin_dir / dll.name)
            shutil.copy2(dll, python_home / dll.name)


def _copy_linux_python_shared_library(
    sdk_prefix: Path,
    info: dict[str, object],
) -> list[Path]:
    if _is_windows():
        return []

    version = str(info["version"])
    libdir = Path(str(info["libdir"])) if info.get("libdir") else None
    if libdir is None:
        return []

    copied: list[Path] = []
    target_dir = sdk_prefix / "lib"
    target_dir.mkdir(parents=True, exist_ok=True)
    for libpython in libdir.glob(f"libpython{version}*.so*"):
        target = target_dir / libpython.name
        shutil.copy2(libpython, target)
        copied.append(target)
    return copied


def _remove_linux_python_config_artifacts(bundled_py_dir: Path) -> None:
    if _is_windows():
        return
    for config_dir in bundled_py_dir.glob("config-*"):
        if config_dir.is_dir():
            shutil.rmtree(config_dir)


def _ensure_linux_python_shared_library(
    sdk_prefix: Path,
    info: dict[str, object],
) -> None:
    if _is_windows():
        return

    version = str(info["version"])
    lib_dir = sdk_prefix / "lib"
    if list(lib_dir.glob(f"libpython{version}*.so*")):
        return
    copied = _copy_linux_python_shared_library(sdk_prefix, info)
    if copied:
        return
    raise RuntimeError(
        f"shared libpython{version} was not found for bundled SDK Python; "
        "native stdlib modules such as _ctypes require a shared libpython in sdk/lib"
    )


def _copy_python_development_headers(
    sdk_prefix: Path,
    info: dict[str, object],
) -> Path | None:
    source_values = {
        str(info.get("include") or ""),
        str(info.get("platinclude") or ""),
    }
    sources = [Path(value) for value in source_values if value]
    sources = [source for source in sources if source.is_dir()]
    if not sources:
        return None

    version = str(info["version"])
    suffix = "t" if bool(info.get("free_threaded", False)) else ""
    destination = sdk_prefix / "include" / f"python{version}{suffix}"
    destination.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def ensure_bundled_python_cli(
    sdk_prefix: Path,
    *,
    python_executable: Path | None = None,
) -> None:
    if not _is_windows():
        return
    py_exec = (
        str(python_executable)
        if python_executable is not None
        else _python_executable()
    )
    _copy_windows_python_runtime_executables(
        sdk_prefix,
        _python_version_and_paths(py_exec),
    )


def _remove_incompatible_bundled_python_runtimes(
    sdk_prefix: Path,
    info: Mapping[str, object],
) -> None:
    if _is_windows():
        return
    lib_dir = sdk_prefix / "lib"
    expected_name = _bundled_python_dir_name(
        str(info["version"]),
        free_threaded=bool(info.get("free_threaded", False)),
    )
    for candidate in sorted(lib_dir.glob("python3.*")):
        if not candidate.is_dir() or candidate.name == expected_name:
            continue
        print(
            "Removing incompatible bundled Python runtime during ABI migration: "
            f"{candidate}"
        )
        shutil.rmtree(candidate)


def ensure_bundled_python_runtime(
    sdk_prefix: Path,
    *,
    python_executable: Path | None = None,
) -> Path:
    py_exec = (
        str(python_executable)
        if python_executable is not None
        else _python_executable()
    )
    info = _python_version_and_paths(py_exec)
    version = str(info["version"])
    stdlib = Path(str(info["stdlib"]))

    if not stdlib.is_dir():
        raise RuntimeError(f"Python stdlib not found: {stdlib}")

    if _is_windows():
        bundled_py_dir = sdk_prefix / "python" / "Lib"
    else:
        bundled_py_dir = sdk_prefix / "lib" / _bundled_python_dir_name(
            version,
            free_threaded=bool(info.get("free_threaded", False)),
        )
    bundled_site_packages = bundled_py_dir / "site-packages"
    if _is_windows():
        (sdk_prefix / "bin").mkdir(parents=True, exist_ok=True)
        (sdk_prefix / "python").mkdir(parents=True, exist_ok=True)
    else:
        (sdk_prefix / "lib").mkdir(parents=True, exist_ok=True)
    bundled_site_packages.mkdir(parents=True, exist_ok=True)

    if _is_windows():
        _copy_windows_python_runtime_executables(sdk_prefix, info)
        python_prefix = Path(str(info.get("base_prefix") or info.get("prefix", "")))
        for runtime_dir in ("DLLs", "tcl"):
            source = python_prefix / runtime_dir
            if source.is_dir():
                shutil.copytree(
                    source,
                    sdk_prefix / "python" / runtime_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )
    else:
        _ensure_linux_python_shared_library(sdk_prefix, info)
    _copy_python_development_headers(sdk_prefix, info)

    _copy_tree_contents(
        stdlib,
        bundled_py_dir,
        {
            "test",
            "tests",
            "idle_test",
            "turtledemo",
            "lib2to3",
            "site-packages",
        },
    )
    _remove_linux_python_config_artifacts(bundled_py_dir)
    return bundled_py_dir
