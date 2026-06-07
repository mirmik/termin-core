"""Build extension for termin pip packages.

This extension does NOT invoke CMake. It locates pre-built binding modules in
``$TERMIN_BINDINGS_DIR`` (normally ``build/<cfg>/bin``) and copies them into the
pip package. When requested, it also bundles the shared libraries needed by the
extension into ``<package>/lib`` so a venv install can run without an SDK.

Usage in setup.py:

    from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
    from termin_build.setup_helpers import native_extensions_for_source

    class BuildExt(TerminCMakeBuildExt):
        source_dir = _DIR

    setup(
        ...
        ext_modules=native_extensions_for_source(_DIR),
        cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    )

The class names `TerminCMakeBuild` / `TerminCMakeBuildExt` are kept for
backward compatibility with existing subproject setup.py files; the class no
longer runs CMake.
"""

import logging
import json
from setuptools.command.build_ext import build_ext
from setuptools.command.build import build as _build
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

_logger = logging.getLogger(__name__)
_CMAKE_CONFIG_DIRS = ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")


def _find_sdk():
    env = os.environ.get("TERMIN_SDK")
    if env:
        p = Path(env)
        if (p / "lib").is_dir():
            return p
    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        candidate = parent / "sdk"
        if (candidate / "lib").is_dir():
            return candidate
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        default = Path(local) / "termin-sdk"
    else:
        default = Path("/opt/termin")
    if (default / "lib").is_dir():
        return default
    return None


def _sdk_python_artifact_roots(sdk):
    roots = []
    if sys.platform == "win32":
        roots.append(sdk / "python" / "Lib" / "site-packages")
    else:
        lib_dir = sdk / "lib"
        if lib_dir.is_dir():
            roots.extend(
                sorted(lib_dir.glob("python*/site-packages"), reverse=True)
            )
    roots.append(sdk / "lib" / "python")
    return roots


def _cmake_artifact_roots(root):
    yield root
    for config in _CMAKE_CONFIG_DIRS:
        yield root / config


def _truthy_env(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "off", "no"}


def _artifact_manifest_path():
    sdk = _find_sdk()
    if sdk is None:
        return None
    manifest = sdk / "termin-artifacts.json"
    if manifest.is_file():
        return manifest
    return None


class TerminCMakeBuild(_build):
    """Ensure build_ext runs before build_py so .so files land in the wheel."""
    def run(self):
        self.run_command("build_ext")
        super().run()


class TerminCMakeBuildExt(build_ext):
    """Copy pre-built binding modules into the pip package.

    Subclasses should set source_dir to the absolute setup.py directory.
    """

    source_dir = None
    upstream_packages = {}
    bundle_libs = False
    bundle_includes = False

    @classmethod
    def compute_local_version(cls, base_version):
        # pip caches wheels by (name, version, source path). The source tree is
        # stable, but the pre-built native artifacts are not. Include their
        # mtimes in the local version so pip cannot serve a stale wheel after a
        # CMake rebuild.
        # Scan all native binding modules regardless of platform. On
        # Linux the binding is `.so`, on Windows `.pyd`, on macOS also
        # `.so` (or occasionally `.dylib` for transitive deps). If we
        # only look for `.so` the Windows path silently returns 0 and
        # pip ends up serving a cached wheel built against the
        # previous SDK.
        max_mtime_ns = 0
        roots = []
        bindings_dir = os.environ.get("TERMIN_BINDINGS_DIR")
        if bindings_dir:
            roots.append(Path(bindings_dir))
        sdk = _find_sdk()
        if sdk is not None:
            roots.extend(_sdk_python_artifact_roots(sdk))
        source_dir = Path(cls.source_dir or Path.cwd())
        for parent in (source_dir, *source_dir.parents):
            roots.append(parent / "build" / "Release" / "bin")
            roots.append(parent / "build" / "Debug" / "bin")
        for pattern in ("*.so", "*.pyd", "*.dylib"):
            for root in roots:
                if not root.is_dir():
                    continue
                for so in root.rglob(pattern):
                    try:
                        mt = so.stat().st_mtime_ns
                    except OSError as e:
                        _logger.debug("Cannot stat native artifact %s: %s", so, e)
                        continue
                    if mt > max_mtime_ns:
                        max_mtime_ns = mt
        if max_mtime_ns == 0:
            return base_version
        return f"{base_version}+sdk{max_mtime_ns // 1_000_000_000}"

    def _get_source_dir(self):
        return Path(self.source_dir) if self.source_dir else Path.cwd()

    def _sdk(self):
        sdk = _find_sdk()
        if sdk is None:
            raise RuntimeError(
                "termin SDK not found. Set TERMIN_SDK or install to /opt/termin."
            )
        return sdk

    def _candidate_binding_roots(self):
        roots = []
        bindings_dir = os.environ.get("TERMIN_BINDINGS_DIR")
        if bindings_dir:
            roots.append(Path(bindings_dir))

        source_dir = self._get_source_dir()
        for parent in (source_dir, *source_dir.parents):
            roots.append(parent / "build" / "Release" / "bin")
            roots.append(parent / "build" / "Debug" / "bin")

        sdk = _find_sdk()
        if sdk is not None:
            roots.extend(_sdk_python_artifact_roots(sdk))

        unique = []
        seen = set()
        for root in roots:
            key = str(root)
            if key in seen:
                continue
            seen.add(key)
            unique.append(root)
        return unique

    def _find_binding_module(self, pkg_dotted_path, module_name):
        """Locate a pre-built binding module."""
        extension_name = f"{pkg_dotted_path}.{module_name}"
        artifact_manifest = _artifact_manifest_path()
        if artifact_manifest is not None:
            try:
                with artifact_manifest.open("r", encoding="utf-8") as f:
                    artifact_data = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                raise RuntimeError(
                    f"Cannot read Termin artifact manifest {artifact_manifest}: {e}"
                ) from e
            for artifact in artifact_data.get("artifacts", []):
                if artifact.get("extension") != extension_name:
                    continue
                build_path = Path(artifact.get("build_path", ""))
                if build_path.is_file():
                    return build_path
                _logger.warning(
                    "Termin artifact manifest entry for %s points to missing "
                    "file %s; falling back to legacy artifact search",
                    extension_name,
                    build_path,
                )
                break

        pkg_fs_path = pkg_dotted_path.replace(".", "/")
        patterns = [f"{module_name}.*.so", f"{module_name}.*.pyd", f"{module_name}.pyd"]
        searched = []
        for root in self._candidate_binding_roots():
            if not root.is_dir():
                searched.append(root)
                continue
            search_dirs = []
            for artifact_root in _cmake_artifact_roots(root):
                search_dirs.append(artifact_root)
                search_dirs.append(artifact_root / pkg_fs_path)
            for search_dir in search_dirs:
                searched.append(search_dir)
                if not search_dir.is_dir():
                    continue
                for pat in patterns:
                    matches = sorted(search_dir.glob(pat))
                    if matches:
                        return matches[0]
        raise RuntimeError(
            f"Cannot find binding {module_name}. "
            f"Set TERMIN_BINDINGS_DIR to the CMake bin directory. "
            f"Searched: {', '.join(str(p) for p in searched)}"
        )

    def _needed_libraries(self, binary):
        if sys.platform == "win32":
            return []
        try:
            result = subprocess.run(
                ["readelf", "-d", str(binary)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return []
        if result.returncode != 0:
            return []
        needed = []
        for line in result.stdout.splitlines():
            match = re.search(r"Shared library: \[(.+?)\]", line)
            if match:
                needed.append(match.group(1))
        return needed

    def _copy_runtime_libs(self, binary, package_dir):
        if not _truthy_env("TERMIN_PIP_BUNDLE_LIBS", True):
            return
        sdk = _find_sdk()
        if sdk is None:
            return
        sdk_lib = sdk / "lib"
        if not sdk_lib.is_dir():
            return

        lib_dir = package_dir / "lib"
        copied = set()
        queue = [binary]
        while queue:
            current = queue.pop()
            for needed in self._needed_libraries(current):
                if needed in copied:
                    continue
                source = sdk_lib / needed
                if not source.exists():
                    continue
                lib_dir.mkdir(parents=True, exist_ok=True)
                dest = lib_dir / needed
                shutil.copy2(source, dest)
                copied.add(needed)
                queue.append(dest)

    def _copy_to_source_enabled(self):
        return _truthy_env("TERMIN_PIP_COPY_TO_SOURCE", bool(self.inplace))

    def build_extension(self, ext):
        pkg_dotted, module_name = ext.name.rsplit(".", 1)

        built = self._find_binding_module(pkg_dotted, module_name)

        ext_path = Path(self.get_ext_fullpath(ext.name))
        ext_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, ext_path)
        self._copy_runtime_libs(ext_path, ext_path.parent)

        # Editable installs need the binding beside the Python sources. Regular
        # wheel builds keep generated native files in build_lib only.
        source_dir = self._get_source_dir()
        src_pkg_dir = source_dir / "python" / pkg_dotted.replace(".", "/")
        if self._copy_to_source_enabled() and src_pkg_dir.exists():
            shutil.copy2(built, src_pkg_dir / built.name)
            self._copy_runtime_libs(src_pkg_dir / built.name, src_pkg_dir)
