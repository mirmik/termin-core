"""Build extension for termin pip packages.

This extension does NOT invoke CMake. It resolves pre-built binding modules
through an installed SDK manifest, or through an explicitly selected build
manifest, and copies them into the pip package. When requested, it also bundles
the manifest-declared shared libraries into ``<package>/lib``.

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
from setuptools.command.build_ext import build_ext
from setuptools.command.build import build as _build
from pathlib import Path
import os
import shutil
import sys

from .artifact_manifest import load_selected_manifest

_logger = logging.getLogger(__name__)
def _find_sdk():
    env = os.environ.get("TERMIN_SDK")
    return Path(env) if env else None


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


def _truthy_env(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "off", "no"}


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

    def _find_binding_module(self, pkg_dotted_path, module_name):
        """Resolve one pre-built binding module without fallback discovery."""
        extension_name = f"{pkg_dotted_path}.{module_name}"
        manifest = load_selected_manifest()
        return manifest.resolve_extension(
            extension_name,
            expected_target=module_name,
        )

    def _copy_runtime_libs(self, artifact, package_dir):
        if not _truthy_env("TERMIN_PIP_BUNDLE_LIBS", True):
            return
        lib_dir = package_dir / "lib"
        for dependency in artifact.runtime_dependencies:
            lib_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dependency.path, lib_dir / dependency.name)

    def _copy_to_source_enabled(self):
        return _truthy_env("TERMIN_PIP_COPY_TO_SOURCE", bool(self.inplace))

    def build_extension(self, ext):
        pkg_dotted, module_name = ext.name.rsplit(".", 1)

        artifact = self._find_binding_module(pkg_dotted, module_name)
        built = artifact.path

        ext_path = Path(self.get_ext_fullpath(ext.name))
        ext_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, ext_path)
        self._copy_runtime_libs(artifact, ext_path.parent)

        # Editable installs need the binding beside the Python sources. Regular
        # wheel builds keep generated native files in build_lib only.
        source_dir = self._get_source_dir()
        src_pkg_dir = source_dir / "python" / pkg_dotted.replace(".", "/")
        if self._copy_to_source_enabled() and src_pkg_dir.exists():
            shutil.copy2(built, src_pkg_dir / built.name)
            self._copy_runtime_libs(artifact, src_pkg_dir)
