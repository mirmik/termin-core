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


def _clear_directory_except(directory: Path, preserved_names: set[str]) -> None:
    if not directory.is_dir():
        return
    for child in directory.iterdir():
        if child.name in preserved_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


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

    runtime_roots: list[Path] = []
    for key in ("base_prefix", "prefix"):
        value = str(info.get(key) or "")
        if value:
            runtime_roots.append(Path(value))
    if executable.is_file():
        runtime_roots.append(executable.parent)

    launchers: dict[str, Path] = {}
    runtime_libraries: dict[str, Path] = {}
    for root in runtime_roots:
        if not root.is_dir():
            continue
        for launcher in root.glob("python*.exe"):
            launchers.setdefault(launcher.name.lower(), launcher)
        for dll in root.glob("python*.dll"):
            runtime_libraries.setdefault(dll.name.lower(), dll)

    # Replace the runtime as one coherent ABI payload. Leaving python312.dll
    # next to python314t.dll makes FindPython retain the obsolete runtime in an
    # existing consumer cache even though the interpreter and import library
    # have already moved to 3.14t.
    desired_launcher_names = set(launchers)
    if executable.is_file():
        desired_launcher_names.add("python.exe")
    desired_runtime_library_names = set(runtime_libraries)
    for stale in python_home.glob("python*.exe"):
        if stale.name.lower() not in desired_launcher_names:
            stale.unlink()
    for directory in (bin_dir, python_home):
        for stale in directory.glob("python*.dll"):
            if stale.name.lower() not in desired_runtime_library_names:
                stale.unlink()

    if executable.is_file():
        shutil.copy2(executable, python_home / "python.exe")
    for launcher in launchers.values():
        shutil.copy2(launcher, python_home / launcher.name)
    for dll in runtime_libraries.values():
        shutil.copy2(dll, bin_dir / dll.name)
        shutil.copy2(dll, python_home / dll.name)


def _copy_windows_python_development_library(
    sdk_prefix: Path,
    info: dict[str, object],
) -> Path | None:
    if not _is_windows():
        return None

    runtime_library = Path(str(info.get("ldlibrary") or "")).name
    if not runtime_library.lower().endswith(".dll"):
        raise RuntimeError(
            "bundled Windows Python does not report its runtime DLL; "
            f"LDLIBRARY={runtime_library!r}"
        )
    import_library_name = f"{Path(runtime_library).stem}.lib"

    source_dirs: list[Path] = []
    for key in ("libdir", "base_prefix", "prefix"):
        value = str(info.get(key) or "")
        if not value:
            continue
        root = Path(value)
        source_dirs.append(root if key == "libdir" else root / "libs")

    source = next(
        (
            candidate
            for source_dir in source_dirs
            if source_dir.is_dir()
            for candidate in (source_dir / import_library_name,)
            if candidate.is_file()
        ),
        None,
    )
    if source is None:
        rendered = ", ".join(str(path) for path in source_dirs) or "(none)"
        raise RuntimeError(
            f"Python development import library {import_library_name} was not "
            f"found in the pinned Windows runtime; searched: {rendered}"
        )

    destination_dir = sdk_prefix / "lib"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / import_library_name
    for stale in destination_dir.glob("python*.lib"):
        if stale != destination:
            stale.unlink()
    shutil.copy2(source, destination)
    return destination


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

    # The SDK path is stable across Python patch-level upgrades. Merge-copying a
    # new stdlib over it leaves modules removed or renamed by CPython behind and
    # can combine Python sources from one release with the DLL from another.
    # Preserve installed distributions, but replace the stdlib as one coherent
    # payload from the pinned interpreter on every SDK population.
    _clear_directory_except(bundled_py_dir, {"site-packages"})

    if _is_windows():
        _copy_windows_python_runtime_executables(sdk_prefix, info)
        _copy_windows_python_development_library(sdk_prefix, info)
        python_prefix = Path(str(info.get("base_prefix") or info.get("prefix", "")))
        for runtime_dir in ("DLLs", "tcl"):
            source = python_prefix / runtime_dir
            if source.is_dir():
                destination = sdk_prefix / "python" / runtime_dir
                if destination.is_dir():
                    shutil.rmtree(destination)
                shutil.copytree(
                    source,
                    destination,
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
