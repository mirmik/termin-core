"""Thin build extension for termin pip packages.

Pip-path architecture: native shared libraries and nanobind binding modules
live in a separately-built SDK ($TERMIN_SDK, /opt/termin, or
%LOCALAPPDATA%/termin-sdk). This extension does NOT invoke CMake; it locates
pre-built binding .so files in the SDK and copies them into the pip package.

Usage in setup.py:

    from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

    class BuildExt(TerminCMakeBuildExt):
        module_names = ["_display_native", "_viewport_native"]
        source_dir = _DIR

    setup(
        ...
        ext_modules=[
            Extension("termin.display._display_native", sources=[]),
            Extension("termin.viewport._viewport_native", sources=[]),
        ],
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
import sys


def _find_sdk():
    env = os.environ.get("TERMIN_SDK")
    if env:
        p = Path(env)
        if (p / "lib").is_dir():
            return p
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        default = Path(local) / "termin-sdk"
    else:
        default = Path("/opt/termin")
    if (default / "lib").is_dir():
        return default
    return None


class TerminCMakeBuild(_build):
    """Ensure build_ext runs before build_py so .so files land in the wheel."""
    def run(self):
        self.run_command("build_ext")
        super().run()


class TerminCMakeBuildExt(build_ext):
    """Copy pre-built binding modules from $TERMIN_SDK into the pip package.

    Subclasses must set:
        module_names: list of binding base names (e.g. ["_display_native"]).
        source_dir: absolute path to the setup.py directory.
    """

    module_names = []
    source_dir = None
    # Legacy knobs kept for compatibility; ignored in thin mode.
    upstream_packages = {}
    bundle_libs = False
    bundle_includes = False

    @classmethod
    def compute_local_version(cls, base_version):
        # pip caches wheels by (name, version, source path). Our local source
        # tree is stable, but the .so files we copy out of $TERMIN_SDK are
        # not — they get rebuilt whenever C/C++ changes. Without help, pip
        # reinstalls the stale cached wheel and the freshly-built .so never
        # reaches site-packages. We expose the SDK state through the version
        # string: pip then sees a different version on every SDK rebuild and
        # invalidates its cache automatically.
        sdk = _find_sdk()
        if sdk is None:
            return base_version
        sdk_python = sdk / "lib" / "python"
        if not sdk_python.is_dir():
            return base_version
        # Scan all native binding modules regardless of platform. On
        # Linux the binding is `.so`, on Windows `.pyd`, on macOS also
        # `.so` (or occasionally `.dylib` for transitive deps). If we
        # only look for `.so` the Windows path silently returns 0 and
        # pip ends up serving a cached wheel built against the
        # previous SDK.
        max_mtime_ns = 0
        for pattern in ("*.so", "*.pyd", "*.dylib"):
            for so in sdk_python.rglob(pattern):
                try:
                    mt = so.stat().st_mtime_ns
                except OSError:
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

    def _find_sdk_module(self, sdk, pkg_dotted_path, module_name):
        """Locate a built binding .so inside the SDK python tree."""
        pkg_fs_path = pkg_dotted_path.replace(".", "/")
        search_dir = sdk / "lib" / "python" / pkg_fs_path
        if not search_dir.is_dir():
            raise RuntimeError(
                f"SDK Python directory {search_dir} does not exist. "
                f"Run build-sdk-bindings.sh to build the SDK."
            )
        patterns = [f"{module_name}.*.so", f"{module_name}.*.pyd", f"{module_name}.pyd"]
        for pat in patterns:
            matches = sorted(search_dir.glob(pat))
            if matches:
                return matches[0]
        raise RuntimeError(
            f"Cannot find binding {module_name} in {search_dir}. "
            f"Did the SDK build succeed?"
        )

    def build_extension(self, ext):
        sdk = self._sdk()
        pkg_dotted, module_name = ext.name.rsplit(".", 1)

        built = self._find_sdk_module(sdk, pkg_dotted, module_name)

        ext_path = Path(self.get_ext_fullpath(ext.name))
        ext_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, ext_path)

        # Also copy into the source tree so editable installs and build_py
        # pick up the binding alongside the Python sources.
        source_dir = self._get_source_dir()
        src_pkg_dir = source_dir / "python" / pkg_dotted.replace(".", "/")
        if src_pkg_dir.exists():
            shutil.copy2(built, src_pkg_dir / built.name)
