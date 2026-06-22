"""Termin SDK build orchestration helpers."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from .package_manifest import load_manifest, repo_root_from


EXPECTED_SUBMODULE_FILES = {
    "termin-thirdparty/manifold": ("CMakeLists.txt",),
    "termin-thirdparty/clipper2": ("CPP/CMakeLists.txt",),
    "termin-thirdparty/guard": ("guard_c.h", "guard_main.h"),
    "termin-thirdparty/vulkan-memory-allocator": ("include/vk_mem_alloc.h",),
    "termin-thirdparty/openxr-sdk": ("include/openxr/openxr.h",),
    "termin-thirdparty/recastnavigation": (
        "Recast/CMakeLists.txt",
        "Detour/CMakeLists.txt",
    ),
}


@dataclass(frozen=True)
class DoctorProfile:
    name: str
    submodules: tuple[str, ...]
    needs_cmake: bool = True
    needs_git: bool = True
    needs_nanobind: bool = False
    needs_pip: bool = False
    needs_copy_backend: bool = False
    needs_sdk_writable: bool = False


PROFILES = {
    "sdk": DoctorProfile(
        name="sdk",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/recastnavigation",
        ),
        needs_nanobind=True,
        needs_pip=True,
        needs_copy_backend=True,
        needs_sdk_writable=True,
    ),
    "sdk-cpp": DoctorProfile(
        name="sdk-cpp",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/recastnavigation",
        ),
        needs_sdk_writable=True,
    ),
    "sdk-bindings": DoctorProfile(
        name="sdk-bindings",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/recastnavigation",
        ),
        needs_nanobind=True,
        needs_copy_backend=True,
        needs_sdk_writable=True,
    ),
    "cpp-tests": DoctorProfile(
        name="cpp-tests",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/guard",
            "termin-thirdparty/recastnavigation",
        ),
    ),
}

EXTERNAL_PYTHON_PACKAGES = (
    "numpy",
    "sip",
    "sipbuild",
    "PIL",
    "Pillow",
    "scipy",
    "glfw",
    "OpenGL",
    "pyassimp",
    "pyopengl",
    "sdl2",
    "yaml",
    "watchdog",
)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _submodule_ready(repo_root: Path, relative_path: str) -> bool:
    full_path = repo_root / relative_path
    if not full_path.is_dir():
        return False
    expected_files = EXPECTED_SUBMODULE_FILES.get(relative_path)
    if expected_files:
        return all((full_path / expected).exists() for expected in expected_files)
    try:
        next(full_path.iterdir())
    except StopIteration:
        return False
    return True


def missing_submodules(repo_root: Path, paths: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for path in paths:
        normalized_path = _normalize_path(path)
        if normalized_path in seen:
            continue
        seen.add(normalized_path)
        normalized.append(normalized_path)
    return [
        path for path in normalized
        if not _submodule_ready(repo_root, path)
    ]


def ensure_submodules(repo_root: Path, paths: list[str]) -> int:
    missing = missing_submodules(repo_root, paths)
    if not missing:
        return 0
    if shutil.which("git") is None:
        print("ERROR: required git submodules are missing and git was not found:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    print("Initializing missing third-party submodules:")
    for path in missing:
        print(f"  - {path}")
    result = subprocess.run(
        ["git", "-C", str(repo_root), "submodule", "update", "--init", "--recursive", "--", *missing],
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    still_missing = missing_submodules(repo_root, missing)
    if still_missing:
        print("ERROR: required git submodules are still missing after initialization:", file=sys.stderr)
        for path in still_missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    return 0


def _tool_error(tool: str) -> str | None:
    if shutil.which(tool) is None:
        return f"required tool not found in PATH: {tool}"
    return None


def _pip_error() -> str | None:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        check=False,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip()
        suffix = f": {detail}" if detail else ""
        return f"pip is not available for {sys.executable}{suffix}"
    return None


def _copy_backend_error() -> str | None:
    if _is_windows():
        return None
    if shutil.which("rsync") is None:
        return "required copy backend not found in PATH: rsync"
    return None


def _sdk_writable_error(sdk_prefix: Path) -> str | None:
    if sdk_prefix.exists():
        if not sdk_prefix.is_dir():
            return f"SDK prefix exists but is not a directory: {sdk_prefix}"
        if not os.access(sdk_prefix, os.W_OK):
            return f"SDK prefix is not writable: {sdk_prefix}"
        return None

    current = sdk_prefix
    while not current.exists() and current.parent != current:
        current = current.parent
    if not current.exists():
        return f"no existing parent directory for SDK prefix: {sdk_prefix}"
    if not os.access(current, os.W_OK):
        return f"SDK prefix parent is not writable: {current}"
    return None


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    return result.returncode


def _is_windows() -> bool:
    return sys.platform == "win32"


def _powershell_executable() -> str:
    for candidate in ("pwsh", "powershell"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("PowerShell executable not found in PATH")


def _stage_script(repo_root: Path, basename: str) -> list[str]:
    if _is_windows():
        return [
            _powershell_executable(),
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / f"{basename}.ps1"),
        ]
    if basename == "build-sdk-csharp":
        return ["bash", str(repo_root / f"{basename}.sh")]
    return [str(repo_root / f"{basename}.sh")]


def _python_executable() -> str:
    env_python = os.environ.get("PYTHON_EXECUTABLE") or os.environ.get("PYTHON_BIN")
    if env_python:
        return env_python
    return sys.executable


def _python_version_and_paths(py_exec: str) -> dict[str, object]:
    script = (
        "import json, site, sys, sysconfig; "
        "print(json.dumps({"
        "'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
        "'prefix': sys.prefix, "
        "'base_prefix': sys.base_prefix, "
        "'executable': sys.executable, "
        "'base_executable': sys._base_executable, "
        "'stdlib': sysconfig.get_paths()['stdlib'], "
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


def _copy_windows_python_runtime_executables(sdk_prefix: Path, info: dict[str, object]) -> None:
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
            # sdk/bin keeps embedded hosts linked to Python::Python working.
            # sdk/python keeps the bundled command-line python.exe self-contained.
            shutil.copy2(dll, bin_dir / dll.name)
            shutil.copy2(dll, python_home / dll.name)


def ensure_bundled_python_cli(sdk_prefix: Path) -> None:
    if not _is_windows():
        return
    _copy_windows_python_runtime_executables(
        sdk_prefix,
        _python_version_and_paths(_python_executable()),
    )


def ensure_bundled_python_runtime(sdk_prefix: Path) -> Path:
    py_exec = _python_executable()
    info = _python_version_and_paths(py_exec)
    version = str(info["version"])
    stdlib = Path(str(info["stdlib"]))
    libdir = Path(str(info["libdir"])) if info.get("libdir") else None
    ldlibrary = str(info.get("ldlibrary") or "")

    if not stdlib.is_dir():
        raise RuntimeError(f"Python stdlib not found: {stdlib}")

    if _is_windows():
        bundled_py_dir = sdk_prefix / "python" / "Lib"
    else:
        bundled_py_dir = sdk_prefix / "lib" / f"python{version}"
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
    elif libdir is not None and ldlibrary:
        for libpython in libdir.glob(f"libpython{version}*.so*"):
            shutil.copy2(libpython, sdk_prefix / "lib" / libpython.name)

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

    sitepackages = [Path(str(path)) for path in info.get("sitepackages", [])]
    for site_dir in sitepackages:
        if not site_dir.is_dir():
            continue
        for package in EXTERNAL_PYTHON_PACKAGES:
            package_dir = site_dir / package
            if package_dir.is_dir():
                shutil.copytree(
                    package_dir,
                    bundled_site_packages / package_dir.name,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )
            for dist_info in site_dir.glob(f"{package}*.dist-info"):
                shutil.copytree(
                    dist_info,
                    bundled_site_packages / dist_info.name,
                    dirs_exist_ok=True,
                )
        for pattern in ("*.so", "*.pyd", "numpy.libs", "scipy.libs", "pillow.libs", "Pillow.libs"):
            for item in site_dir.glob(pattern):
                target = bundled_site_packages / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)

    return bundled_py_dir


def _nanobind_error() -> str | None:
    try:
        import nanobind  # noqa: F401
    except Exception as e:
        return f"nanobind is not importable for {sys.executable}: {e}"
    return None


def _pip_cache_warning() -> str | None:
    pip_cache = Path.home() / ".cache" / "pip"
    if pip_cache.exists() and not os.access(pip_cache, os.W_OK):
        return f"pip cache is not writable and pip will disable cache: {pip_cache}"
    parent = pip_cache.parent
    if parent.exists() and not os.access(parent, os.W_OK):
        return f"pip cache parent is not writable and pip may disable cache: {parent}"
    return None


def _profile_submodules(profile: DoctorProfile, vulkan: str) -> list[str]:
    paths = list(profile.submodules)
    if vulkan == "ON":
        paths.append("termin-thirdparty/vulkan-memory-allocator")
    return paths


def _artifact_roots(build_dir: Path) -> list[Path]:
    roots = [build_dir / "bin"]
    for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
        roots.append(build_dir / "bin" / config)
    return roots


def _find_native_artifact(build_dir: Path, target: str) -> Path | None:
    patterns = (
        f"{target}.*.so",
        f"{target}.*.pyd",
        f"{target}.pyd",
        f"{target}.so",
    )
    for root in _artifact_roots(build_dir):
        if not root.is_dir():
            continue
        for pattern in patterns:
            matches = sorted(root.glob(pattern))
            if matches:
                return matches[0]
    return None


def _native_runtime_dependencies(binary: Path) -> list[str]:
    if _is_windows():
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
    dependencies = []
    for line in result.stdout.splitlines():
        marker = "Shared library: ["
        if marker not in line:
            continue
        dependency = line.split(marker, 1)[1].split("]", 1)[0]
        dependencies.append(dependency)
    return dependencies


def _find_installed_artifact(
    install_dir: Path,
    extension_name: str,
    target: str,
) -> Path | None:
    package_path = extension_name.rsplit(".", 1)[0].replace(".", "/")
    patterns = (
        f"{target}.*.so",
        f"{target}.so",
        f"{target}.*.pyd",
        f"{target}.pyd",
        f"{target}.*.dylib",
        f"{target}.dylib",
    )
    candidate_dirs = [
        install_dir / "lib" / "python" / package_path,
        install_dir / "python" / "Lib" / "site-packages" / package_path,
    ]
    lib_dir = install_dir / "lib"
    if lib_dir.is_dir():
        candidate_dirs.extend(
            python_dir / "site-packages" / package_path
            for python_dir in sorted(lib_dir.glob("python*"))
            if python_dir.is_dir()
        )
    for candidate_dir in candidate_dirs:
        if not candidate_dir.is_dir():
            continue
        for pattern in patterns:
            matches = sorted(candidate_dir.glob(pattern))
            if matches:
                return matches[0]
    if install_dir.is_dir():
        for pattern in patterns:
            matches = sorted(install_dir.rglob(pattern))
            if matches:
                return matches[0]
    return None


def write_artifacts(
    repo_root: Path,
    build_dir: Path,
    sdk_prefix: Path,
    install_dir: Path | None = None,
) -> int:
    packages = load_manifest(repo_root)
    artifacts = []
    missing_required = []
    artifact_install_dir = install_dir if install_dir is not None else sdk_prefix

    for package in packages:
        for native_extension in package.native_extensions:
            build_path = _find_native_artifact(build_dir, native_extension.target)
            if build_path is None:
                if native_extension.optional:
                    continue
                missing_required.append(
                    f"{package.path}: {native_extension.extension} "
                    f"(target {native_extension.target})"
                )
                continue
            installed_path = _find_installed_artifact(
                artifact_install_dir,
                native_extension.extension,
                native_extension.target,
            )
            artifacts.append(
                {
                    "package_path": package.path,
                    "distribution": package.distribution,
                    "extension": native_extension.extension,
                    "target": native_extension.target,
                    "build_path": str(build_path.resolve()),
                    "install_path": (
                        str(installed_path.resolve())
                        if installed_path is not None
                        else None
                    ),
                    "runtime_dependencies": _native_runtime_dependencies(build_path),
                    "optional": native_extension.optional,
                    "features": list(
                        dict.fromkeys((*package.features, *native_extension.features))
                    ),
                }
            )

    if missing_required:
        print("ERROR: required native artifacts are missing:", file=sys.stderr)
        for missing in missing_required:
            print(f"  - {missing}", file=sys.stderr)
        return 1

    sdk_prefix.mkdir(parents=True, exist_ok=True)
    artifact_manifest = {
        "schema": 1,
        "build_dir": str(build_dir.resolve()),
        "sdk_prefix": str(sdk_prefix.resolve()),
        "artifacts": artifacts,
    }
    output = sdk_prefix / "termin-artifacts.json"
    output.write_text(
        json.dumps(artifact_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote artifact manifest: {output}")
    return 0


def _find_bundled_python_dir(sdk_prefix: Path) -> Path | None:
    if _is_windows():
        windows_lib = sdk_prefix / "python" / "Lib"
        if windows_lib.is_dir():
            return windows_lib
    lib_dir = sdk_prefix / "lib"
    if not lib_dir.is_dir():
        return None
    matches = sorted(path for path in lib_dir.glob("python3.*") if path.is_dir())
    return matches[0] if matches else None


def install_python_packages(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
) -> int:
    bundled_py_dir = _find_bundled_python_dir(sdk_prefix)
    if bundled_py_dir is None or not (bundled_py_dir / "ensurepip").is_dir():
        reason = "not found" if bundled_py_dir is None else "missing ensurepip"
        print(f"Bundled Python stdlib {reason}; syncing it from host Python.")
        bundled_py_dir = ensure_bundled_python_runtime(sdk_prefix)
    if bundled_py_dir is None:
        print(
            f"ERROR: failed to create bundled Python stdlib under {sdk_prefix / 'lib'}/python3.*",
            file=sys.stderr,
        )
        return 1
    ensure_bundled_python_cli(sdk_prefix)

    bundled_site_packages = bundled_py_dir / "site-packages"
    print(f"Bundled Python stdlib:        {bundled_py_dir}")
    print(f"Bundled Python site-packages: {bundled_site_packages}")
    if _is_windows() and bundled_site_packages.is_dir():
        shutil.rmtree(bundled_site_packages)
        bundled_site_packages.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    result = _install_bundled_runtime_requirements(
        repo_root=repo_root,
        bundled_site_packages=bundled_site_packages,
        env=env,
    )
    if result != 0:
        return result
    return install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=build_dir,
        target_dir=bundled_site_packages,
        editable=False,
        force=True,
    )


def _install_bundled_runtime_requirements(
    repo_root: Path,
    bundled_site_packages: Path,
    env: dict[str, str],
) -> int:
    requirements = repo_root / "termin-app" / "requirements.txt"
    return _run(
        [
            _python_executable(),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--target",
            str(bundled_site_packages),
            "-r",
            str(requirements),
        ],
        cwd=repo_root,
        env=env,
    )


def _python_bin() -> str:
    env_python = os.environ.get("PYTHON_BIN")
    if env_python:
        return env_python
    return _python_executable()


def _sdk_valid(path: Path) -> bool:
    return (path / "lib").is_dir()


def _resolve_sdk_prefix(repo_root: Path, sdk_prefix: Path) -> Path:
    env_sdk = os.environ.get("TERMIN_SDK")
    if env_sdk:
        resolved = Path(env_sdk)
        if not _sdk_valid(resolved):
            raise RuntimeError(f"TERMIN_SDK={resolved} is set but does not contain lib/")
        return resolved
    if _sdk_valid(sdk_prefix):
        return sdk_prefix
    if _is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            local_sdk = Path(local_app_data) / "termin-sdk"
            if _sdk_valid(local_sdk):
                return local_sdk
    else:
        opt_sdk = Path("/opt/termin")
        if _sdk_valid(opt_sdk):
            return opt_sdk
    raise RuntimeError(
        f"termin SDK not found. Tried TERMIN_SDK, {sdk_prefix}"
    )


def _resolve_bindings_dir(repo_root: Path, build_dir: Path) -> Path:
    env_bindings = os.environ.get("TERMIN_BINDINGS_DIR")
    candidates = []
    if env_bindings:
        candidates.append(Path(env_bindings))
    candidates.extend(
        (
            build_dir / "bin",
            repo_root / "build" / "Release" / "bin",
            repo_root / "build" / "Debug" / "bin",
        )
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        "Termin Python bindings directory not found. "
        "Set TERMIN_BINDINGS_DIR or build bindings first."
    )


def _clear_python_package_build_caches(repo_root: Path) -> None:
    for package in load_manifest(repo_root):
        package_dir = repo_root / package.path
        build_dir = package_dir / "build"
        if build_dir.is_dir():
            for child in build_dir.iterdir():
                if child.is_dir() and (
                    child.name.startswith("lib.")
                    or child.name.startswith("bdist.")
                ):
                    shutil.rmtree(child, ignore_errors=True)
        for egg_info in package_dir.glob("*.egg-info"):
            if egg_info.is_dir():
                shutil.rmtree(egg_info, ignore_errors=True)


_DISTRIBUTION_NORMALIZE_RE = re.compile(r"[-_.]+")


def _normalized_distribution_name(name: str) -> str:
    return _DISTRIBUTION_NORMALIZE_RE.sub("-", name).lower()


def _metadata_distribution_name(metadata_path: Path) -> str | None:
    for metadata_file_name in ("METADATA", "PKG-INFO"):
        metadata_file = metadata_path / metadata_file_name
        if not metadata_file.is_file():
            continue
        text = metadata_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.lower().startswith("name:"):
                name = line.split(":", 1)[1].strip()
                return name or None
    return None


def _fallback_distribution_name_from_metadata_dir(metadata_path: Path) -> str | None:
    name = metadata_path.name
    for suffix in (".dist-info", ".egg-info"):
        if not name.endswith(suffix):
            continue
        stem = name[: -len(suffix)]
        if suffix == ".dist-info" and "-" in stem:
            return stem.rsplit("-", 1)[0]
        return stem
    return None


def _distribution_name_from_metadata_dir(metadata_path: Path) -> str | None:
    return (
        _metadata_distribution_name(metadata_path)
        or _fallback_distribution_name_from_metadata_dir(metadata_path)
    )


def _remove_metadata_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _clear_target_python_package_metadata(target_dir: Path, packages) -> None:
    if not target_dir.is_dir():
        return
    package_names = {
        _normalized_distribution_name(package.distribution)
        for package in packages
    }
    removed = []
    for child in target_dir.iterdir():
        if not (child.name.endswith(".dist-info") or child.name.endswith(".egg-info")):
            continue
        distribution_name = _distribution_name_from_metadata_dir(child)
        if distribution_name is None:
            continue
        if _normalized_distribution_name(distribution_name) not in package_names:
            continue
        _remove_metadata_path(child)
        removed.append(child.name)
    if removed:
        print(
            "Removed stale target package metadata: "
            + ", ".join(sorted(removed))
        )


def _add_build_tools_pythonpath(env: dict[str, str], repo_root: Path) -> None:
    build_tools = str(repo_root / "termin-build-tools")
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = build_tools + (os.pathsep + current if current else "")


def _bindings_dir_if_available(repo_root: Path, build_dir: Path) -> Path | None:
    env_bindings = os.environ.get("TERMIN_BINDINGS_DIR")
    candidates = []
    if env_bindings:
        candidates.append(Path(env_bindings))
    candidates.extend(
        (
            build_dir / "bin",
            repo_root / "build" / "Release" / "bin",
            repo_root / "build" / "Debug" / "bin",
        )
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _pip_temp_env(repo_root: Path, env: dict[str, str]) -> Path | None:
    if not _is_windows():
        return None
    pip_temp_root = repo_root / "build" / "pip-temp"
    pip_temp_dir = pip_temp_root / uuid.uuid4().hex
    pip_temp_dir.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(pip_temp_dir)
    env["TMP"] = str(pip_temp_dir)
    return pip_temp_dir


def install_pip_packages(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    target_dir: Path | None,
    editable: bool,
    force: bool,
) -> int:
    if target_dir is not None and editable:
        print("ERROR: --editable is incompatible with --target", file=sys.stderr)
        return 1

    try:
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    bindings_dir = _bindings_dir_if_available(repo_root, build_dir)
    env = os.environ.copy()
    env["TERMIN_SDK"] = str(termin_sdk)
    if bindings_dir is not None:
        env["TERMIN_BINDINGS_DIR"] = str(bindings_dir)
    if "TERMIN_PIP_BUNDLE_LIBS" not in env:
        env["TERMIN_PIP_BUNDLE_LIBS"] = "0" if target_dir is not None or editable else "1"
    if "TERMIN_PIP_COPY_TO_SOURCE" not in env:
        env["TERMIN_PIP_COPY_TO_SOURCE"] = "1" if editable else "0"
    _add_build_tools_pythonpath(env, repo_root)

    pip_temp_dir = _pip_temp_env(repo_root, env)
    pip_cmd = [_python_bin(), "-m", "pip"]

    print(f"Using TERMIN_SDK={termin_sdk}")
    if bindings_dir is not None:
        print(f"Using TERMIN_BINDINGS_DIR={bindings_dir}")
    print(f"TERMIN_PIP_BUNDLE_LIBS={env['TERMIN_PIP_BUNDLE_LIBS']}")
    print(f"TERMIN_PIP_COPY_TO_SOURCE={env['TERMIN_PIP_COPY_TO_SOURCE']}")
    print("Using pip: " + " ".join(pip_cmd))
    if pip_temp_dir is not None:
        print(f"Using pip temp: {pip_temp_dir}")

    if force:
        print("--force: clearing per-package pip build caches before install")
        _clear_python_package_build_caches(repo_root)

    force_flags = []
    if force:
        force_flags = ["--force-reinstall", "--no-cache-dir"]

    packages = load_manifest(repo_root)
    if target_dir is not None:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_dir = target_dir.resolve()
        _clear_target_python_package_metadata(target_dir, packages)
        print(f"Install mode: --target {target_dir} (single pip invocation, no-deps)")
        print("")
        print("========================================")
        print(f"  Installing {len(packages)} packages into {target_dir}")
        print("========================================")
        print("")
        pip_args = [
            *pip_cmd,
            "install",
            "--no-build-isolation",
            "--no-deps",
            "--upgrade",
            "--target",
            str(target_dir),
            *force_flags,
            *(str(repo_root / package.path) for package in packages),
        ]
        return _run(pip_args, cwd=repo_root, env=env)

    print("Install mode: current pip environment (sequential pip install)")
    editable_flag = ["-e"] if editable else []
    nodeps_flag = ["--no-deps"] if editable or force else []
    for package in packages:
        mode = " (editable)" if editable else ""
        print("")
        print("========================================")
        print(f"  Installing {package.path}{mode}")
        print("========================================")
        print("")
        result = _run(
            [
                *pip_cmd,
                "install",
                "--no-build-isolation",
                *force_flags,
                *nodeps_flag,
                *editable_flag,
                str(repo_root / package.path),
            ],
            cwd=repo_root,
            env=env,
        )
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  All pip packages installed!")
    print("========================================")
    return 0


def _parse_wheelhouse_args(
    sdk_prefix: Path,
    build_dir: Path,
    stage_args: list[str],
) -> tuple[Path, Path, bool]:
    wheel_dir_env = os.environ.get("WHEEL_DIR")
    wheel_dir = Path(wheel_dir_env) if wheel_dir_env else sdk_prefix / "wheels"
    force = False
    effective_build_dir = build_dir

    index = 0
    while index < len(stage_args):
        arg = stage_args[index]
        if arg in ("--force", "-f"):
            force = True
        elif arg in ("--debug", "-d"):
            if "BUILD_DIR" not in os.environ:
                effective_build_dir = build_dir.parent / "Debug"
        elif arg == "--wheel-dir":
            index += 1
            if index >= len(stage_args):
                raise RuntimeError("--wheel-dir requires a directory")
            wheel_dir = Path(stage_args[index])
        elif arg.startswith("--wheel-dir="):
            wheel_dir = Path(arg.split("=", 1)[1])
        index += 1

    return wheel_dir, effective_build_dir, force


def build_wheelhouse(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    stage_args: list[str],
) -> int:
    try:
        wheel_dir, effective_build_dir, force = _parse_wheelhouse_args(
            sdk_prefix,
            build_dir,
            stage_args,
        )
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
        bindings_dir = _resolve_bindings_dir(repo_root, effective_build_dir)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_dir = wheel_dir.resolve()

    env = os.environ.copy()
    env.update(
        {
            "TERMIN_SDK": str(termin_sdk),
            "TERMIN_BINDINGS_DIR": str(bindings_dir),
            "TERMIN_PIP_BUNDLE_LIBS": "0",
            "TERMIN_PIP_COPY_TO_SOURCE": "0",
            "PYTHONPATH": (
                str(repo_root / "termin-build-tools")
                + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            ),
        }
    )
    pip_cmd = [_python_bin(), "-m", "pip"]

    print(f"Using TERMIN_SDK={termin_sdk}")
    print(f"Using TERMIN_BINDINGS_DIR={bindings_dir}")
    print("Using pip: " + " ".join(pip_cmd))
    print(f"Wheelhouse: {wheel_dir}")
    print("TERMIN_PIP_BUNDLE_LIBS=0")
    print("TERMIN_PIP_COPY_TO_SOURCE=0")

    if force:
        print("--force: clearing wheelhouse and per-package pip build caches")
        for wheel in wheel_dir.glob("*.whl"):
            wheel.unlink()
        _clear_python_package_build_caches(repo_root)

    for package in load_manifest(repo_root):
        print("")
        print("========================================")
        print(f"  Building wheel: {package.path}")
        print("========================================")
        print("")
        result = _run(
            [
                *pip_cmd,
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "--no-cache-dir",
                "--wheel-dir",
                str(wheel_dir),
                str(repo_root / package.path),
            ],
            cwd=repo_root,
            env=env,
        )
        if result != 0:
            return result

    print("")
    print("========================================")
    print(f"  SDK wheelhouse ready: {wheel_dir}")
    print("========================================")
    return 0


def _is_duplicate_exception(sdk_prefix: Path, path: Path) -> bool:
    path_text = _normalize_path(str(path))
    sdk_text = _normalize_path(str(sdk_prefix))
    android_prefix = _normalize_path(str(sdk_prefix / "android")) + "/"
    lower_path = path_text.lower()
    return (
        path_text.startswith(android_prefix)
        or "/csharp/runtimes/" in path_text
        or "/site-packages/scipy/" in path_text
        # The bundled Python keeps pysdl2-dll's extension DLLs available.
        # Embedded hosts set PYSDL2_DLL_PATH with sdk/bin first, so PySDL2
        # binds core SDL2 calls to the same SDK SDL2.dll as termin_display.
        or (
            _is_windows()
            and lower_path.endswith("/site-packages/sdl2dll/dll/sdl2.dll")
        )
        # PyGLFW ships backend-specific copies with the same basename.
        # They are selected by the Python package from distinct x11/wayland
        # directories and are not linked by Termin's native libraries.
        or (
            not _is_windows()
            and (
                lower_path.endswith("/site-packages/glfw/x11/libglfw.so")
                or lower_path.endswith("/site-packages/glfw/wayland/libglfw.so")
            )
        )
        or (
            _is_windows()
            and lower_path.startswith(_normalize_path(str(sdk_prefix / "python")).lower() + "/")
            and Path(lower_path).name.startswith("python")
            and Path(lower_path).suffix == ".dll"
        )
        or not path_text.startswith(sdk_text)
    )


def verify_no_duplicate_libraries(sdk_prefix: Path) -> int:
    print("Verifying: no duplicate libraries")
    seen: dict[str, Path] = {}
    duplicates = []
    patterns = ("*.dll", "*.pyd") if _is_windows() else ("*.so",)
    for pattern in patterns:
        for so_path in sdk_prefix.rglob(pattern):
            if so_path.is_symlink() or not so_path.is_file():
                continue
            if _is_duplicate_exception(sdk_prefix, so_path):
                continue
            previous = seen.get(so_path.name)
            if previous is not None:
                duplicates.append((so_path.name, previous, so_path))
            else:
                seen[so_path.name] = so_path
    if duplicates:
        for name, first, second in duplicates:
            print(f"  DUPLICATE: {name}")
            print(f"    - {first}")
            print(f"    - {second}")
        print(f"FAILED: {len(duplicates)} duplicate library/libraries found", file=sys.stderr)
        return 1
    print("  OK: no duplicate libraries")
    return 0


def verify_sdk_artifacts(sdk_prefix: Path, build_dir: Path) -> int:
    print("Verifying: SDK artifacts are up to date")
    build_bin = build_dir / "bin"
    if not build_bin.is_dir():
        print(f"  WARNING: build bin directory not found: {build_bin}")
        return 0

    stale = []
    same_second = 0
    patterns = ("*.dll", "*.pyd") if _is_windows() else ("*.so",)
    build_artifacts = []
    for pattern in patterns:
        build_artifacts.extend(build_bin.glob(pattern))
    for build_so in build_artifacts:
        build_mtime = build_so.stat().st_mtime
        for sdk_so in sdk_prefix.rglob(build_so.name):
            sdk_text = _normalize_path(str(sdk_so))
            android_prefix = _normalize_path(str(sdk_prefix / "android")) + "/"
            if sdk_text.startswith(android_prefix):
                continue
            if "/csharp/runtimes/" in sdk_text:
                continue
            sdk_mtime = sdk_so.stat().st_mtime
            if int(sdk_mtime) < int(build_mtime):
                stale.append((sdk_so, build_so))
            elif int(sdk_mtime) == int(build_mtime) and sdk_mtime < build_mtime:
                same_second += 1
    if stale:
        for sdk_so, build_so in stale:
            print(f"  STALE: {sdk_so}")
            print(f"    older than: {build_so}")
        print(f"FAILED: {len(stale)} stale SDK artifact(s) found", file=sys.stderr)
        return 1
    print("  OK: SDK artifacts are not older than matching build artifacts")
    if same_second:
        print(
            f"  NOTE: {same_second} matching artifact(s) differed only within "
            "timestamp sub-second precision"
        )
    return 0


def verify_sdk(sdk_prefix: Path, build_dir: Path) -> int:
    result = verify_no_duplicate_libraries(sdk_prefix)
    if result != 0:
        return result
    return verify_sdk_artifacts(sdk_prefix, build_dir)


def _build_dir(repo_root: Path, build_type: str) -> Path:
    env_build_dir = os.environ.get("BUILD_DIR")
    return Path(env_build_dir) if env_build_dir else repo_root / "build" / build_type


def _bundled_site_packages_hint(sdk_prefix: Path) -> Path:
    if _is_windows():
        return sdk_prefix / "python" / "Lib" / "site-packages"
    return sdk_prefix / "lib" / "python3.*" / "site-packages"


def run_sdk_build(
    repo_root: Path,
    build_type: str,
    stage_args: list[str],
    build_wheels: bool,
    dry_run: bool,
) -> int:
    sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
    build_dir = _build_dir(repo_root, build_type)

    stages = (
        (
            "Stage 1/4: C/C++ libraries + Python bindings",
            _stage_script(repo_root, "build-sdk-bindings") + stage_args,
        ),
        (
            "Stage 2/4: C# bindings",
            _stage_script(repo_root, "build-sdk-csharp") + stage_args,
        ),
    )
    for title, command in stages:
        print("")
        print("========================================")
        print(f"  {title}")
        print("========================================")
        print("")
        if dry_run:
            print("+ " + " ".join(command))
        else:
            result = _run(command, cwd=repo_root)
            if result != 0:
                return result

    print("")
    print("========================================")
    print("  Stage 3/4: Populate bundled Python site-packages")
    print("========================================")
    print("")
    if dry_run:
        print(
            "+ install bundled Python packages into "
            f"{_bundled_site_packages_hint(sdk_prefix)}"
        )
    else:
        result = install_python_packages(repo_root, sdk_prefix, build_dir)
        if result != 0:
            return result

    legacy_sdk_python = sdk_prefix / "lib" / "python"
    if not dry_run and legacy_sdk_python.is_dir():
        print(f"Removing legacy SDK Python staging tree: {legacy_sdk_python}")
        shutil.rmtree(legacy_sdk_python)

    print("")
    print("========================================")
    print("  Stage 4/4: Build SDK Python wheelhouse")
    print("========================================")
    print("")
    if build_wheels:
        if dry_run:
            print("+ build SDK Python wheelhouse")
        else:
            wheel_args = list(stage_args)
            if "--force" not in wheel_args and "-f" not in wheel_args:
                wheel_args.insert(0, "--force")
            result = build_wheelhouse(repo_root, sdk_prefix, build_dir, wheel_args)
            if result != 0:
                return result
    else:
        print("Skipping SDK Python wheelhouse build (--no-wheels).")

    print("")
    print("========================================")
    print("  Verifying SDK")
    print("========================================")
    print("")
    if dry_run:
        print("+ verify SDK duplicate libraries and stale artifacts")
    else:
        result = verify_sdk(sdk_prefix, build_dir)
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  All done!")
    print("========================================")
    return 0


def doctor(
    repo_root: Path,
    profile_name: str,
    vulkan: str,
    init_submodules: bool,
    require_nanobind: bool,
    sdk_prefix: Path,
) -> int:
    profile = PROFILES[profile_name]
    errors = []
    warnings = []

    if profile.needs_git:
        error = _tool_error("git")
        if error:
            errors.append(error)
    if profile.needs_cmake:
        error = _tool_error("cmake")
        if error:
            errors.append(error)
    if profile.needs_nanobind or require_nanobind:
        error = _nanobind_error()
        if error:
            errors.append(error)
    if profile.needs_pip:
        error = _pip_error()
        if error:
            errors.append(error)
    if profile.needs_copy_backend:
        error = _copy_backend_error()
        if error:
            errors.append(error)
    if profile.needs_sdk_writable:
        error = _sdk_writable_error(sdk_prefix)
        if error:
            errors.append(error)

    warning = _pip_cache_warning()
    if warning:
        warnings.append(warning)

    required_submodules = _profile_submodules(profile, vulkan)
    missing = missing_submodules(repo_root, required_submodules)
    if missing and init_submodules:
        result = ensure_submodules(repo_root, required_submodules)
        if result != 0:
            return result
        missing = missing_submodules(repo_root, required_submodules)
    if missing:
        errors.append(
            "required submodules are missing: "
            + ", ".join(missing)
        )

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Termin build doctor OK ({profile.name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to auto-discovery from cwd.",
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="Run build preflight checks.")
    doctor_parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="sdk-bindings",
    )
    doctor_parser.add_argument(
        "--vulkan",
        choices=("ON", "OFF"),
        default="ON",
    )
    doctor_parser.add_argument(
        "--init-submodules",
        action="store_true",
        help="Initialize missing required git submodules.",
    )
    doctor_parser.add_argument(
        "--require-nanobind",
        action="store_true",
        help="Require nanobind even if the selected profile does not.",
    )
    doctor_parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=None,
        help="SDK install prefix to validate. Defaults to SDK_PREFIX or ./sdk.",
    )

    ensure_parser = subparsers.add_parser(
        "ensure-submodules",
        help="Initialize the requested submodules if they are missing.",
    )
    ensure_parser.add_argument("paths", nargs="+")

    artifacts_parser = subparsers.add_parser(
        "write-artifacts",
        help="Write sdk/termin-artifacts.json from build outputs and package manifest.",
    )
    artifacts_parser.add_argument("--build-dir", type=Path, required=True)
    artifacts_parser.add_argument("--sdk-prefix", type=Path, required=True)
    artifacts_parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help="CMake install tree to search for installed native artifacts.",
    )

    install_python_parser = subparsers.add_parser(
        "install-python",
        help="Populate the bundled SDK Python site-packages.",
    )
    install_python_parser.add_argument("--build-type", default="Release")

    install_packages_parser = subparsers.add_parser(
        "install-packages",
        help="Install Termin Python packages into the current Python or --target.",
    )
    install_packages_parser.add_argument("--build-type", default="Release")
    install_packages_parser.add_argument("--editable", "-e", action="store_true")
    install_packages_parser.add_argument("--force", "-f", action="store_true")
    install_packages_parser.add_argument("--target", type=Path, default=None)

    wheels_parser = subparsers.add_parser(
        "wheels",
        help="Build SDK-backed Python wheels.",
    )
    wheels_parser.add_argument("--build-type", default="Release")

    verify_parser = subparsers.add_parser(
        "verify-sdk",
        help="Run SDK duplicate/stale artifact checks.",
    )
    verify_parser.add_argument("--build-type", default="Release")

    build_parser = subparsers.add_parser(
        "build",
        help="Build the full SDK through the existing stage scripts.",
    )
    build_parser.add_argument("--debug", "-d", action="store_true")
    build_parser.add_argument("--no-wheels", action="store_true")
    build_parser.add_argument(
        "--wheels",
        action="store_true",
        help="Build the SDK Python wheelhouse explicitly.",
    )
    build_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the SDK build stages without executing them.",
    )

    args, unknown_args = parser.parse_known_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from(Path.cwd())

    if args.command == "doctor":
        sdk_prefix = args.sdk_prefix
        if sdk_prefix is None:
            sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return doctor(
            repo_root=repo_root,
            profile_name=args.profile,
            vulkan=args.vulkan,
            init_submodules=args.init_submodules,
            require_nanobind=args.require_nanobind,
            sdk_prefix=sdk_prefix,
        )
    if args.command == "ensure-submodules":
        return ensure_submodules(repo_root, args.paths)
    if args.command == "write-artifacts":
        return write_artifacts(
            repo_root=repo_root,
            build_dir=args.build_dir,
            sdk_prefix=args.sdk_prefix,
            install_dir=args.install_dir,
        )
    if args.command == "install-python":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return install_python_packages(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
        )
    if args.command == "install-packages":
        if unknown_args:
            print(
                f"ERROR: unknown install-packages option: {unknown_args[0]}",
                file=sys.stderr,
            )
            return 1
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return install_pip_packages(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            target_dir=args.target,
            editable=args.editable,
            force=args.force,
        )
    if args.command == "wheels":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        wheel_args = list(unknown_args)
        if "--force" not in wheel_args and "-f" not in wheel_args:
            wheel_args.insert(0, "--force")
        return build_wheelhouse(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            stage_args=wheel_args,
        )
    if args.command == "verify-sdk":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return verify_sdk(sdk_prefix=sdk_prefix, build_dir=build_dir)
    if args.command == "build":
        build_type = "Debug" if args.debug else "Release"
        stage_args = list(unknown_args)
        if args.debug and "--debug" not in stage_args and "-d" not in stage_args:
            stage_args.insert(0, "--debug")
        return run_sdk_build(
            repo_root=repo_root,
            build_type=build_type,
            stage_args=stage_args,
            build_wheels=not args.no_wheels,
            dry_run=args.dry_run,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
