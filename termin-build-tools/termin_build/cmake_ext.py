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

from setuptools.command.build_ext import build_ext
from setuptools.command.build import build as _build
from pathlib import Path
import os
import shutil

from .artifact_manifest import load_selected_manifest

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
        manifest = load_selected_manifest(required=False)
        if manifest is None:
            return base_version
        # The manifest also contains application-owned native payloads.  They
        # are installed after library wheels and may legitimately be absent
        # while those wheels are being materialized.  Individual extensions
        # are verified by ``resolve_extension`` when build_ext consumes them.
        return f"{base_version}+sdk{manifest.native_build_id}"

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
