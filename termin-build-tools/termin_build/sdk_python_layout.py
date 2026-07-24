"""Canonical Python runtime layout helpers for the Termin SDK."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from .python_interpreter import resolve_python_executable


def _is_windows() -> bool:
    return sys.platform == "win32"


def _python_executable() -> str:
    return resolve_python_executable()


def _python_version_and_paths(py_exec: str) -> dict[str, object]:
    script = (
        "import json, site, sys, sysconfig; "
        "print(json.dumps({"
        "'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
        "'soabi': sysconfig.get_config_var('SOABI') or '', "
        "'free_threaded': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'py_gil_disabled': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'prefix': sys.prefix, "
        "'base_prefix': sys.base_prefix, "
        "'executable': sys.executable, "
        "'base_executable': sys._base_executable, "
        "'stdlib': sysconfig.get_paths()['stdlib'], "
        "'include': sysconfig.get_paths()['include'], "
        "'platinclude': sysconfig.get_paths()['platinclude'], "
        "'libdir': sysconfig.get_config_var('LIBDIR') or '', "
        "'ldlibrary': sysconfig.get_config_var('LDLIBRARY') or '', "
        "'sitepackages': site.getsitepackages() + ([site.getusersitepackages()] if site.getusersitepackages() else [])"
        "}))"
    )
    result = subprocess.run(
        [py_exec, "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to inspect Python runtime: {py_exec}")
    return json.loads(result.stdout)


def _copy_tree_contents(source: Path, dest: Path, ignore_names: set[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if child.name in ignore_names:
            continue
        if child.name == "__pycache__" or child.suffix in {".pyc", ".pyo"}:
            continue
        target = dest / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        else:
            shutil.copy2(child, target)


def _bundled_python_dir_name(version: str, *, free_threaded: bool) -> str:
    suffix = "t" if free_threaded else ""
    return f"python{version}{suffix}"


def _find_bundled_python_dir(
    sdk_prefix: Path,
    *,
    expected_version: str | None = None,
    expected_free_threaded: bool = False,
) -> Path | None:
    if _is_windows():
        windows_lib = sdk_prefix / "python" / "Lib"
        if windows_lib.is_dir():
            return windows_lib
    lib_dir = sdk_prefix / "lib"
    if not lib_dir.is_dir():
        return None
    matches = sorted(path for path in lib_dir.glob("python3.*") if path.is_dir())
    if len(matches) > 1:
        rendered = ", ".join(str(path) for path in matches)
        raise RuntimeError(
            f"SDK contains multiple bundled Python runtimes: {rendered}. "
            "Rebuild the SDK with one Python ABI."
        )
    if not matches:
        return None
    bundled_py_dir = matches[0]
    if expected_version is not None:
        expected = lib_dir / _bundled_python_dir_name(
            expected_version,
            free_threaded=expected_free_threaded,
        )
        if bundled_py_dir != expected:
            raise RuntimeError(
                f"SDK Python ABI mismatch: expected {expected}, found {bundled_py_dir}. "
                "Rebuild the SDK with the active Python interpreter."
            )
    return bundled_py_dir


def resolve_sdk_python_layout(
    sdk_prefix: Path,
    *,
    require_native_bindings: bool = False,
) -> Path:
    info = _python_version_and_paths(_python_executable())
    version = str(info["version"])
    bundled_py_dir = _find_bundled_python_dir(
        sdk_prefix,
        expected_version=version,
        expected_free_threaded=bool(info.get("free_threaded", False)),
    )
    if bundled_py_dir is None:
        raise RuntimeError(
            f"SDK Python {version} runtime was not found under {sdk_prefix}"
        )
    site_packages = bundled_py_dir / "site-packages"
    if not site_packages.is_dir():
        raise RuntimeError(f"SDK site-packages directory was not found: {site_packages}")
    if require_native_bindings:
        tcbase_dir = site_packages / "tcbase"
        native_bindings = tuple(tcbase_dir.glob("_tcbase_native*.so")) + tuple(
            tcbase_dir.glob("_tcbase_native*.pyd")
        )
        if not native_bindings:
            raise RuntimeError(
                f"SDK Python {version} native bindings were not found under {tcbase_dir}"
            )
    return site_packages


def publish_cmake_python_install(
    install_dir: Path,
    sdk_prefix: Path,
) -> Path:
    """Normalize CMake-installed Python modules into SDK site-packages."""
    site_packages = resolve_sdk_python_layout(sdk_prefix)

    source_roots = [install_dir / "lib" / "python"]
    if _is_windows():
        source_roots.append(install_dir / "python" / "Lib" / "site-packages")
    else:
        # CMake's generic install scheme can use pythonX.Y even when extension
        # suffixes and the final runtime layout use the free-threaded "t" ABI.
        # The staging tree is an input to normalization, not an SDK runtime.
        staged_python = _find_bundled_python_dir(install_dir)
        if staged_python is not None:
            source_roots.append(staged_python / "site-packages")

    published_roots = []
    for source_root in source_roots:
        if not source_root.is_dir():
            continue
        if source_root.resolve() != site_packages.resolve():
            _copy_tree_contents(
                source_root,
                site_packages,
                set(),
            )
        published_roots.append(source_root)

    if not published_roots:
        rendered = ", ".join(str(path) for path in source_roots)
        raise RuntimeError(
            f"CMake Python install tree was not found; searched: {rendered}"
        )

    sdk_root = sdk_prefix.resolve()
    for source_root in published_roots:
        resolved_source = source_root.resolve()
        if resolved_source == site_packages.resolve():
            continue
        if resolved_source.is_relative_to(sdk_root):
            shutil.rmtree(source_root)

    for cache_dir in list(site_packages.rglob("__pycache__")):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)
    for bytecode in list(site_packages.rglob("*.py[co]")):
        if bytecode.is_file():
            bytecode.unlink()

    resolve_sdk_python_layout(sdk_prefix, require_native_bindings=True)
    print(f"Published CMake Python install to {site_packages}")
    return site_packages
