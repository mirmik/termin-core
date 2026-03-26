"""Common CMake build extension for termin SDK pip packages.

Usage in setup.py:

    from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

    class BuildExt(TerminCMakeBuildExt):
        module_names = ["_tgfx_native"]
        upstream_packages = {"tcbase": "libtermin_base", "tmesh": "libtermin_mesh"}

    setup(
        ...
        cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    )
"""

from setuptools.command.build_ext import build_ext
from setuptools.command.build import build as _build
from pathlib import Path
import importlib
import shutil
import subprocess
import sys
import os


def split_prefix_path(raw):
    """Normalize CMAKE_PREFIX_PATH from environment."""
    if not raw:
        return []
    normalized = raw.replace(";", os.pathsep)
    return [p for p in normalized.split(os.pathsep) if p]


def get_sdk_prefix():
    """Resolve SDK prefix for finding dependencies."""
    override = os.environ.get("TERMIN_SDK_PREFIX")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        return Path(base) / "termin-sdk"
    return None


def copytree(src, dst):
    """Recursively copy directory, handling symlinks per-platform."""
    if dst.exists():
        shutil.rmtree(dst)
    follow = sys.platform == "win32"
    shutil.copytree(src, dst, symlinks=not follow)


def copy_upstream_libs(src_lib_dir, dst_lib_dir, name_prefix):
    """Copy shared libraries matching name_prefix from src to dst."""
    if not src_lib_dir.exists():
        return
    dst_lib_dir.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        for f in src_lib_dir.glob(f"{name_prefix}*.dll"):
            shutil.copy2(f, dst_lib_dir / f.name)
        for f in src_lib_dir.glob(f"{name_prefix}*.lib"):
            shutil.copy2(f, dst_lib_dir / f.name)
    else:
        # Copy real files first, then symlinks
        for f in sorted(src_lib_dir.glob(f"{name_prefix}*.so*")):
            dst = dst_lib_dir / f.name
            if f.is_file() and not f.is_symlink():
                shutil.copy2(f, dst)
        for f in sorted(src_lib_dir.glob(f"{name_prefix}*.so*")):
            dst = dst_lib_dir / f.name
            if f.is_symlink():
                if dst.exists() or dst.is_symlink():
                    dst.unlink()
                dst.symlink_to(os.readlink(f))


class TerminCMakeBuild(_build):
    """Hook build_ext to run before build_py."""
    def run(self):
        self.run_command("build_ext")
        super().run()


class TerminCMakeBuildExt(build_ext):
    """Base class for CMake-based build extensions.

    Subclasses must set:
        module_names: list of native module names (e.g. ["_tgfx_native"])
        source_dir: Path to the project root (default: auto-detected)

    Subclasses may set:
        upstream_packages: dict mapping pip package name to lib prefix
            e.g. {"tcbase": "libtermin_base", "tmesh": "libtermin_mesh"}
        bundle_libs: whether to bundle native libs into the pip package (default: True)
        bundle_includes: whether to bundle include/ dir (default: False)
    """

    module_names = []
    upstream_packages = {}
    bundle_libs = True
    bundle_includes = False
    source_dir = None

    def _get_source_dir(self):
        if self.source_dir:
            return Path(self.source_dir)
        return Path.cwd()

    @staticmethod
    def _find_package_dir(pkg_name):
        """Find installed package directory by import or site-packages scan."""
        try:
            mod = importlib.import_module(pkg_name)
            return Path(mod.__file__).parent
        except Exception:
            pass
        # Fallback: scan site-packages for namespace subpackages
        # whose parent __init__.py may fail to import
        try:
            import site
            for sp in site.getsitepackages() + [site.getusersitepackages()]:
                candidate = Path(sp) / pkg_name.replace(".", "/")
                if candidate.is_dir():
                    return candidate
        except Exception:
            pass
        return None

    def _find_built_module(self, build_temp, cfg, module_name, staging_dir=None):
        patterns = [f"{module_name}.*.so", f"{module_name}.*.pyd", f"{module_name}.pyd"]
        built_files = []
        search_dirs = [build_temp / "python", build_temp / "python" / cfg]
        if staging_dir:
            search_dirs.append(staging_dir)
        for pat in patterns:
            for d in search_dirs:
                built_files.extend(d.rglob(pat))
        return built_files[0] if built_files else None

    def _get_prefix_paths(self):
        """Build CMAKE_PREFIX_PATH from env, SDK, and imported upstream packages."""
        paths = split_prefix_path(os.environ.get("CMAKE_PREFIX_PATH"))

        sdk = get_sdk_prefix()
        if sdk and sdk.exists():
            paths.append(str(sdk))

        for pkg_name in self.upstream_packages:
            pkg_dir = self._find_package_dir(pkg_name)
            if pkg_dir:
                paths.append(str(pkg_dir))

        return paths

    def _bundle_to_dir(self, staging_dir, target_dir):
        """Copy staging libs and upstream libs into target_dir."""
        if self.bundle_libs and (staging_dir / "lib").exists():
            dst_lib = target_dir / "lib"
            if dst_lib.exists():
                shutil.rmtree(dst_lib)
            shutil.copytree(
                staging_dir / "lib", dst_lib,
                symlinks=(sys.platform != "win32"),
                ignore=shutil.ignore_patterns("python"),
            )

        if self.bundle_includes and (staging_dir / "include").exists():
            copytree(staging_dir / "include", target_dir / "include")

        for pkg_name, lib_prefix in self.upstream_packages.items():
            pkg_dir = self._find_package_dir(pkg_name)
            if pkg_dir:
                copy_upstream_libs(pkg_dir / "lib", target_dir / "lib", lib_prefix)

        if sys.platform == "win32" and (staging_dir / "lib").exists():
            for dll in (staging_dir / "lib").glob("*.dll"):
                shutil.copy2(dll, target_dir / dll.name)
            if (staging_dir / "bin").exists():
                for dll in (staging_dir / "bin").glob("*.dll"):
                    shutil.copy2(dll, target_dir / dll.name)

    def _ensure_cmake_build(self):
        if getattr(self, "_cmake_ready", False):
            return

        source_dir = self._get_source_dir()
        build_temp = Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)

        staging_dir = (build_temp / "install").resolve()
        staging_dir.mkdir(parents=True, exist_ok=True)

        cfg = "Debug" if self.debug else "Release"

        cmake_args = [
            str(source_dir),
            f"-DCMAKE_BUILD_TYPE={cfg}",
            "-DTERMIN_BUILD_PYTHON=ON",
            f"-DPython_EXECUTABLE={sys.executable}",
            f"-DCMAKE_INSTALL_PREFIX={staging_dir}",
            "-DCMAKE_INSTALL_LIBDIR=lib",
        ]

        prefix_paths = self._get_prefix_paths()
        if prefix_paths:
            cmake_args.append(f"-DCMAKE_PREFIX_PATH={';'.join(prefix_paths)}")

        subprocess.check_call(["cmake", *cmake_args], cwd=build_temp)
        subprocess.check_call(
            ["cmake", "--build", ".", "--config", cfg, "--parallel"],
            cwd=build_temp,
        )
        subprocess.check_call(
            ["cmake", "--install", ".", "--config", cfg],
            cwd=build_temp,
        )

        modules = {}
        for name in self.module_names:
            built = self._find_built_module(build_temp, cfg, name, staging_dir)
            if not built:
                raise RuntimeError(f"CMake build did not produce {name} module")
            modules[name] = built

        self._cmake_modules = modules
        self._staging_dir = staging_dir
        self._cmake_ready = True

    def build_extension(self, ext):
        self._ensure_cmake_build()

        module_name = ext.name.rsplit(".", 1)[-1]
        built_module = self._cmake_modules.get(module_name)
        if not built_module:
            raise RuntimeError(f"Unknown module requested by setuptools: {module_name}")

        ext_path = Path(self.get_ext_fullpath(ext.name))
        ext_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built_module, ext_path)

        ext_pkg_dir = ext_path.parent
        self._bundle_to_dir(self._staging_dir, ext_pkg_dir)

        # Also copy to source tree so build_py picks them up
        source_dir = self._get_source_dir()
        pkg_name = ext.name.rsplit(".", 1)[0]
        src_pkg_dir = source_dir / "python" / pkg_name
        if src_pkg_dir.exists():
            shutil.copy2(built_module, src_pkg_dir / built_module.name)
            self._bundle_to_dir(self._staging_dir, src_pkg_dir)
