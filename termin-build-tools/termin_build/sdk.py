"""Termin SDK build orchestration helpers."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from .artifact_manifest import (
    BUILD_MANIFEST_KIND,
    BUILD_MANIFEST_NAME,
    SCHEMA_VERSION as ARTIFACT_MANIFEST_SCHEMA,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
    compute_native_build_id,
    sha256_file,
)
from .application_payload import (
    install_application_payloads,
    load_application_payloads,
)
from .package_manifest import PackageEntry, load_manifest, repo_root_from
from .local_wheel_artifacts import (
    LocalWheelArtifactError,
    build_local_wheel_artifact_set,
    publish_local_wheel_artifact_set,
    validate_local_wheel_artifact_set,
)
from .python_abi import PythonAbiError, PythonAbiIdentity
from .python_toolchain import PythonToolchainError, ensure_python_toolchain
from .sdk_bundled_python import (
    _copy_python_development_headers,
    _copy_windows_python_runtime_executables as _copy_windows_python_runtime_executables,
    _ensure_linux_python_shared_library,
    _remove_incompatible_bundled_python_runtimes,
    _remove_linux_python_config_artifacts,
    ensure_bundled_python_cli,
    ensure_bundled_python_runtime,
)
from .sdk_doctor import (
    PROFILES,
    DoctorProfile as DoctorProfile,
    ensure_submodules,
    missing_submodules,
    profile_submodules,
)
from .sdk_python_layout import (
    _find_bundled_python_dir,
    _is_windows,
    _python_executable,
    _python_version_and_paths,
    publish_cmake_python_install,
    resolve_sdk_python_layout,
)
from .sdk_capabilities import write_android_capabilities, write_desktop_capabilities
from .wheelhouse import (
    WheelhouseError,
    supported_wheel_tags,
    validate_locked_wheelhouse,
)


RUNTIME_LOCK_RELATIVE = Path("build-system/python-runtime-lock.txt")
SDK_BUILD_REQUIREMENTS_RELATIVE = Path("build-system/python-sdk-build-requirements.txt")

LEGACY_BUNDLED_RUNTIME_PACKAGES = {
    # Pillow used to be a runtime image dependency. termin-image now owns image
    # decoding, but existing SDK trees may still contain the old package.
    "Pillow": ("PIL", "pillow.libs", "Pillow.libs"),
}

LEGACY_SOURCE_NATIVE_ARTIFACTS = {
    # termin-app used to own the monolithic termin._native binding. Editable
    # installs import from the source tree, so stale local artifacts must be
    # removed after the binding was split into package-owned modules.
    "termin-app": ("termin/_native",),
}


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


def _artifact_roots(build_dir: Path) -> list[Path]:
    roots = []
    for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
        roots.append(build_dir / "bin" / config)
    roots.append(build_dir / "bin")
    return roots


def _find_native_artifact(
    build_dir: Path,
    target: str,
    *,
    python_abi: PythonAbiIdentity,
) -> Path | None:
    patterns = (
        f"{target}.{python_abi.soabi}.so",
        f"{target}.{python_abi.soabi}.pyd",
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
        return _pe_import_dependencies(binary)
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANGUAGE"] = "C"
    try:
        result = subprocess.run(
            ["readelf", "-d", str(binary)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except OSError as error:
        raise RuntimeError(
            f"failed to execute readelf for {binary}: {error}"
        ) from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if not detail:
            detail = f"exit code {result.returncode}"
        raise RuntimeError(f"readelf failed for {binary}: {detail}")
    dependencies = []
    for line in result.stdout.splitlines():
        if "(NEEDED)" not in line:
            continue
        opening = line.rfind("[")
        closing = line.find("]", opening + 1)
        if opening < 0 or closing < 0:
            raise RuntimeError(
                f"readelf returned an unrecognized NEEDED entry for {binary}: "
                f"{line.strip()}"
            )
        dependency = line[opening + 1 : closing]
        dependencies.append(dependency)
    return dependencies


def _pe_import_dependencies(binary: Path) -> list[str]:
    try:
        image = binary.read_bytes()
        if len(image) < 0x40 or image[:2] != b"MZ":
            raise ValueError("missing DOS header")
        pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
        if pe_offset + 24 > len(image) or image[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise ValueError("missing PE header")

        file_header = pe_offset + 4
        section_count = struct.unpack_from("<H", image, file_header + 2)[0]
        optional_size = struct.unpack_from("<H", image, file_header + 16)[0]
        optional = file_header + 20
        if optional + optional_size > len(image):
            raise ValueError("truncated optional header")
        magic = struct.unpack_from("<H", image, optional)[0]
        if magic == 0x10B:
            data_directories = optional + 96
        elif magic == 0x20B:
            data_directories = optional + 112
        else:
            raise ValueError(f"unsupported optional-header magic 0x{magic:04x}")
        if data_directories + 16 > optional + optional_size:
            raise ValueError("missing import directory")
        import_rva, import_size = struct.unpack_from(
            "<II", image, data_directories + 8
        )
        if import_rva == 0 or import_size == 0:
            return []

        sections = []
        section_offset = optional + optional_size
        for index in range(section_count):
            entry = section_offset + index * 40
            if entry + 40 > len(image):
                raise ValueError("truncated section table")
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
                "<IIII", image, entry + 8
            )
            sections.append(
                (virtual_address, max(virtual_size, raw_size), raw_offset, raw_size)
            )

        def file_offset(rva: int) -> int:
            for virtual_address, span, raw_offset, raw_size in sections:
                delta = rva - virtual_address
                if 0 <= delta < span and delta < raw_size:
                    offset = raw_offset + delta
                    if offset < len(image):
                        return offset
            raise ValueError(f"RVA 0x{rva:x} is outside file-backed sections")

        dependencies = []
        descriptor = file_offset(import_rva)
        while True:
            if descriptor + 20 > len(image):
                raise ValueError("truncated import descriptor table")
            fields = struct.unpack_from("<IIIII", image, descriptor)
            if fields == (0, 0, 0, 0, 0):
                break
            name_offset = file_offset(fields[3])
            name_end = image.find(b"\0", name_offset)
            if name_end < 0:
                raise ValueError("unterminated import name")
            dependencies.append(image[name_offset:name_end].decode("ascii"))
            descriptor += 20
        return dependencies
    except (OSError, UnicodeDecodeError, ValueError, struct.error) as error:
        raise RuntimeError(f"failed to inspect PE imports for {binary}: {error}") from error


def _find_installed_artifact(
    install_dir: Path,
    extension_name: str,
    target: str,
    *,
    python_abi: PythonAbiIdentity,
) -> Path | None:
    package_path = extension_name.rsplit(".", 1)[0].replace(".", "/")
    patterns = (
        f"{target}.{python_abi.soabi}.so",
        f"{target}.{python_abi.soabi}.pyd",
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
    application_payloads = load_application_payloads(repo_root)
    python_abi = PythonAbiIdentity.current()
    build_artifacts = []
    sdk_artifacts = []
    missing_required = []
    artifact_install_dir = install_dir if install_dir is not None else sdk_prefix
    sdk_root = sdk_prefix.resolve()

    def bundled_runtime_dependencies(names: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        bundled = []
        external = []
        pending = list(names)
        visited = set()
        while pending:
            name = pending.pop(0)
            if name in visited:
                continue
            visited.add(name)
            candidates = (sdk_root / "lib" / name, sdk_root / "bin" / name)
            dependency_path = next((path for path in candidates if path.is_file()), None)
            if dependency_path is None:
                external.append(name)
                continue
            bundled.append(
                {
                    "name": name,
                    "path": dependency_path.relative_to(sdk_root).as_posix(),
                    "sha256": sha256_file(dependency_path),
                }
            )
            pending.extend(_native_runtime_dependencies(dependency_path))
        return bundled, external

    extension_owners = [
        (
            package.path,
            {"package_path": package.path, "distribution": package.distribution},
            package.features,
            native_extension,
        )
        for package in packages
        for native_extension in package.native_extensions
    ]
    extension_owners.extend(
        (
            payload.name,
            {"application_payload": payload.name},
            (),
            native_extension,
        )
        for payload in application_payloads
        for native_extension in payload.native_extensions
    )

    for owner, ownership, owner_features, native_extension in extension_owners:
        build_path = _find_native_artifact(
            build_dir,
            native_extension.target,
            python_abi=python_abi,
        )
        if build_path is None:
            if native_extension.optional:
                continue
            missing_required.append(
                f"{owner}: {native_extension.extension} "
                f"(target {native_extension.target})"
            )
            continue
        installed_path = _find_installed_artifact(
            artifact_install_dir,
            native_extension.extension,
            native_extension.target,
            python_abi=python_abi,
        )
        if installed_path is None:
            missing_required.append(
                f"{owner}: installed {native_extension.extension} "
                f"(target {native_extension.target})"
            )
            continue
        installed_path = installed_path.resolve()
        try:
            installed_relative = installed_path.relative_to(sdk_root)
        except ValueError:
            missing_required.append(
                f"{owner}: installed artifact is outside SDK root: {installed_path}"
            )
            continue
        try:
            dependency_names = _native_runtime_dependencies(installed_path)
            runtime_dependencies, external_dependencies = bundled_runtime_dependencies(
                dependency_names
            )
        except RuntimeError as error:
            print(
                f"ERROR: failed to inspect native dependencies: {error}",
                file=sys.stderr,
            )
            return 1
        common = {
            "kind": "python-extension",
            **ownership,
            "extension": native_extension.extension,
            "target": native_extension.target,
            "optional": native_extension.optional,
            "features": list(
                dict.fromkeys((*owner_features, *native_extension.features))
            ),
            "external_runtime_dependencies": external_dependencies,
        }
        build_artifacts.append(
            {
                **common,
                "path": str(build_path.resolve()),
                "sha256": sha256_file(build_path),
                "runtime_dependencies": [],
            }
        )
        sdk_artifacts.append(
            {
                **common,
                "path": installed_relative.as_posix(),
                "sha256": sha256_file(installed_path),
                "runtime_dependencies": runtime_dependencies,
            }
        )

    if missing_required:
        print("ERROR: required native artifacts are missing:", file=sys.stderr)
        for missing in missing_required:
            print(f"  - {missing}", file=sys.stderr)
        return 1

    build_manifest = {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "manifest_kind": BUILD_MANIFEST_KIND,
        "python_abi": python_abi.to_dict(),
        "native_build_id": compute_native_build_id(build_artifacts, python_abi),
        "artifacts": build_artifacts,
    }
    build_output = build_dir / BUILD_MANIFEST_NAME
    build_output.parent.mkdir(parents=True, exist_ok=True)
    build_output.write_text(
        json.dumps(build_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sdk_manifest = {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "manifest_kind": SDK_MANIFEST_KIND,
        "python_abi": python_abi.to_dict(),
        "native_build_id": compute_native_build_id(sdk_artifacts, python_abi),
        "artifacts": sdk_artifacts,
    }
    sdk_prefix.mkdir(parents=True, exist_ok=True)
    sdk_output = sdk_prefix / SDK_MANIFEST_NAME
    sdk_output.write_text(
        json.dumps(sdk_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        write_desktop_capabilities(sdk_root=sdk_prefix)
    except (OSError, RuntimeError) as error:
        print(f"ERROR: failed to write desktop SDK capabilities: {error}", file=sys.stderr)
        return 1
    print(f"Wrote build artifact manifest: {build_output}")
    print(f"Wrote SDK artifact manifest: {sdk_output}")
    return 0


def install_python_packages(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    *,
    python_executable: Path | None = None,
) -> int:
    py_exec = str(python_executable) if python_executable else _python_executable()
    info = _python_version_and_paths(py_exec)
    target_python_abi = PythonAbiIdentity.from_runtime_probe(
        info,
        context="SDK target Python",
    )
    _remove_incompatible_bundled_python_runtimes(sdk_prefix, info)
    try:
        bundled_py_dir = _find_bundled_python_dir(
            sdk_prefix,
            expected_version=str(info["version"]),
            expected_free_threaded=bool(info.get("free_threaded", False)),
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if bundled_py_dir is None:
        print("Bundled Python stdlib not found; creating it from the selected target Python.")
    else:
        print("Synchronizing bundled Python stdlib from the selected target Python.")
    try:
        bundled_py_dir = ensure_bundled_python_runtime(
            sdk_prefix,
            python_executable=Path(py_exec),
        )
    except RuntimeError as error:
        print(f"ERROR: failed to synchronize bundled Python stdlib: {error}", file=sys.stderr)
        return 1
    if bundled_py_dir is None:
        print(
            f"ERROR: failed to create bundled Python stdlib under {sdk_prefix / 'lib'}/python3.*",
            file=sys.stderr,
        )
        return 1
    _remove_linux_python_config_artifacts(bundled_py_dir)
    _ensure_linux_python_shared_library(sdk_prefix, info)
    _copy_python_development_headers(sdk_prefix, info)
    ensure_bundled_python_cli(
        sdk_prefix,
        python_executable=Path(py_exec),
    )

    bundled_site_packages = bundled_py_dir / "site-packages"
    print(f"Bundled Python stdlib:        {bundled_py_dir}")
    print(f"Bundled Python site-packages: {bundled_site_packages}")

    try:
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
        bindings_dir = _resolve_bindings_dir(repo_root, build_dir)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        build_python = _ensure_sdk_python_build_environment(
            repo_root,
            base_python=Path(py_exec),
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    external_wheels, local_wheels = _runtime_wheel_dirs(repo_root)
    result = _prepare_external_runtime_wheels(repo_root, external_wheels, build_python)
    if result != 0:
        return result
    result = _build_local_package_wheels(
        repo_root=repo_root,
        termin_sdk=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=local_wheels,
        build_python=build_python,
    )
    if result != 0:
        return result
    result = _install_prepared_runtime_wheels(
        repo_root=repo_root,
        site_packages=bundled_site_packages,
        external_wheels=external_wheels,
        local_wheels=local_wheels,
        build_python=build_python,
        sdk_prefix=sdk_prefix,
    )
    if result != 0:
        return result
    try:
        install_application_payloads(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            site_packages=bundled_site_packages,
            resolve_native_artifact=lambda target: _find_native_artifact(
                build_dir,
                target,
                python_abi=target_python_abi,
            ),
            runtime_python_abi=target_python_abi,
        )
    except RuntimeError as error:
        print(f"ERROR: failed to install application Python payload: {error}", file=sys.stderr)
        return 1
    try:
        write_python_runtime_manifest(
            repo_root,
            sdk_prefix,
            bundled_site_packages,
            runtime_python_abi=target_python_abi,
        )
    except RuntimeError as error:
        print(f"ERROR: failed to write SDK Python runtime manifest: {error}", file=sys.stderr)
        return 1
    return 0


def prepare_build_python_runtime(sdk_prefix: Path) -> int:
    if _is_windows():
        return 0

    py_exec = _python_executable()
    info = _python_version_and_paths(py_exec)
    _remove_incompatible_bundled_python_runtimes(sdk_prefix, info)
    try:
        bundled_py_dir = _find_bundled_python_dir(
            sdk_prefix,
            expected_version=str(info["version"]),
            expected_free_threaded=bool(info.get("free_threaded", False)),
        )
        if (
            bundled_py_dir is None
            or not (bundled_py_dir / "os.py").is_file()
            or not (bundled_py_dir / "ensurepip").is_dir()
        ):
            bundled_py_dir = ensure_bundled_python_runtime(
                sdk_prefix,
                python_executable=Path(py_exec),
            )
        else:
            _remove_linux_python_config_artifacts(bundled_py_dir)
            _ensure_linux_python_shared_library(sdk_prefix, info)
            _copy_python_development_headers(sdk_prefix, info)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Prepared bundled Python runtime for native build: {bundled_py_dir}")
    return 0


def _runtime_wheel_dirs(repo_root: Path) -> tuple[Path, Path]:
    root = Path(
        os.environ.get(
            "TERMIN_PYTHON_RUNTIME_BUILD_DIR",
            str(repo_root / "build" / "python-runtime"),
        )
    )
    return root / "external-wheels", root / "termin-wheels"


def _sdk_build_environment_root(repo_root: Path) -> Path:
    return Path(
        os.environ.get(
            "TERMIN_PYTHON_BUILD_ENV",
            str(repo_root / "build" / "python-runtime" / "build-env"),
        )
    )


def _build_environment_python(environment_root: Path) -> Path:
    if _is_windows():
        return environment_root / "Scripts" / "python.exe"
    return environment_root / "bin" / "python"


def _ensure_sdk_python_build_environment(
    repo_root: Path,
    *,
    base_python: Path | None = None,
) -> Path:
    requirements = repo_root / SDK_BUILD_REQUIREMENTS_RELATIVE
    if not requirements.is_file():
        raise RuntimeError(f"SDK Python build requirements are missing: {requirements}")
    environment_root = _sdk_build_environment_root(repo_root)
    build_python = _build_environment_python(environment_root)
    stamp = environment_root / "python-sdk-build-requirements.txt"
    selected_base = base_python or Path(_python_executable())
    selected_info = _python_version_and_paths(str(selected_base))
    canonical_base = selected_info.get("base_executable")
    if isinstance(canonical_base, str) and canonical_base:
        canonical_base_path = Path(canonical_base)
        if canonical_base_path.is_file():
            selected_base = canonical_base_path
    expected_abi = PythonAbiIdentity.from_runtime_probe(
        selected_info,
        context="SDK Python build environment base",
    )
    if build_python.is_file():
        actual_base: Path | None = None
        try:
            existing_info = _python_version_and_paths(str(build_python))
            actual_abi = PythonAbiIdentity.from_runtime_probe(
                existing_info,
                context="existing SDK Python build environment",
            )
            base_value = existing_info.get("base_executable")
            if isinstance(base_value, str) and base_value:
                actual_base = Path(base_value).resolve()
        except (PythonAbiError, OSError, RuntimeError):
            actual_abi = None
        selected_base = selected_base.resolve()
        base_mismatch = (
            actual_base is not None and actual_base != selected_base
        )
        if actual_abi != expected_abi or base_mismatch:
            rendered = (
                actual_abi.canonical_json()
                if actual_abi is not None
                else "unreadable"
            )
            if base_mismatch:
                rendered += f", base={actual_base}"
            print(
                "Recreating SDK Python build environment for ABI "
                f"{expected_abi.canonical_json()}, base={selected_base} "
                f"(existing: {rendered})"
            )
            shutil.rmtree(environment_root)
    if not build_python.is_file():
        result = _run(
            [str(selected_base), "-m", "venv", str(environment_root)],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            raise RuntimeError(f"failed to create SDK Python build environment: {environment_root}")
    current = stamp.is_file() and stamp.read_bytes() == requirements.read_bytes()
    if not current:
        result = _run(
            [
                str(build_python),
                "-I",
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--no-deps",
                "-r",
                str(requirements),
            ],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            raise RuntimeError("failed to install pinned SDK Python build tools")
        shutil.copy2(requirements, stamp)
    print(f"Using isolated SDK Python build environment: {environment_root}")
    return build_python


def _prepare_external_runtime_wheels(
    repo_root: Path,
    wheel_dir: Path,
    build_python: Path,
) -> int:
    lock_path = repo_root / RUNTIME_LOCK_RELATIVE
    try:
        runtime_lock = _load_runtime_lock(repo_root)
        python_abi = PythonAbiIdentity.from_runtime_probe(
            _python_version_and_paths(str(build_python)),
            context="SDK Python build environment",
        )
        target_tags = supported_wheel_tags(build_python)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    wheel_dir.mkdir(parents=True, exist_ok=True)
    if os.environ.get("TERMIN_PYTHON_RUNTIME_OFFLINE") == "1":
        print(f"Using offline SDK runtime wheelhouse: {wheel_dir}")
        try:
            validate_locked_wheelhouse(
                wheel_dir,
                runtime_lock,
                python_abi=python_abi,
                supported_tags=target_tags,
            )
        except WheelhouseError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0
    print(f"Preparing pinned SDK runtime wheels: {wheel_dir}")
    wheel_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="external-wheels.",
        dir=wheel_dir.parent,
    ) as temporary_root:
        prepared = Path(temporary_root) / "wheels"
        prepared.mkdir()
        result = _run(
            [
                str(build_python),
                "-m",
                "pip",
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "--wheel-dir",
                str(prepared),
                "-r",
                str(lock_path),
            ],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            return result
        try:
            validate_locked_wheelhouse(
                prepared,
                runtime_lock,
                python_abi=python_abi,
                supported_tags=target_tags,
            )
        except WheelhouseError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        shutil.rmtree(wheel_dir)
        prepared.replace(wheel_dir)
    print(
        f"Validated {len(runtime_lock)} exact runtime wheels for "
        f"{python_abi.wheel_abi_tag}"
    )
    return 0


def _install_prepared_runtime_wheels(
    repo_root: Path,
    site_packages: Path,
    external_wheels: Path,
    local_wheels: Path,
    build_python: Path,
    sdk_prefix: Path,
) -> int:
    try:
        runtime_lock = _load_runtime_lock(repo_root)
        python_abi = PythonAbiIdentity.from_runtime_probe(
            _python_version_and_paths(str(build_python)),
            context="SDK Python build environment",
        )
        validate_locked_wheelhouse(
            external_wheels,
            runtime_lock,
            python_abi=python_abi,
            supported_tags=supported_wheel_tags(build_python),
        )
        expected_local_count = len(load_manifest(repo_root))
        validate_local_wheel_artifact_set(
            local_wheels,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=expected_local_count,
        )
    except (LocalWheelArtifactError, RuntimeError) as error:
        print(f"ERROR: cannot install SDK Python runtime: {error}", file=sys.stderr)
        return 1
    wheels = sorted(local_wheels.glob("*.whl"))
    try:
        if site_packages.exists():
            shutil.rmtree(site_packages)
        site_packages.mkdir(parents=True)
    except OSError as error:
        print(
            f"ERROR: cannot replace SDK Python site-packages {site_packages}: {error}",
            file=sys.stderr,
        )
        if _is_windows():
            print(
                "Close Termin editor/player, pytest, and Python processes that may "
                "hold SDK .pyd/.dll files, then retry.",
                file=sys.stderr,
            )
        return 1

    lock_path = repo_root / RUNTIME_LOCK_RELATIVE
    print("Installing SDK Python site-packages offline from prepared wheels")
    return _run(
        [
            str(build_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--no-cache-dir",
            "--find-links",
            str(external_wheels),
            "--target",
            str(site_packages),
            "-r",
            str(lock_path),
            *(str(wheel) for wheel in wheels),
        ],
        cwd=repo_root,
        env=os.environ.copy(),
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
                    child.name == "lib"
                    or child.name.startswith("lib.")
                    or child.name.startswith("bdist.")
                ):
                    shutil.rmtree(child, ignore_errors=True)
        for egg_info in package_dir.rglob("*.egg-info"):
            if egg_info.is_dir():
                shutil.rmtree(egg_info, ignore_errors=True)


def _clear_legacy_source_native_artifacts(repo_root: Path) -> None:
    removed = []
    suffixes = ("so", "pyd", "dylib")
    for package_path, module_stems in LEGACY_SOURCE_NATIVE_ARTIFACTS.items():
        package_dir = repo_root / package_path
        for module_stem in module_stems:
            module_path = package_dir / module_stem
            patterns = [
                f"{module_path.name}.{suffix}"
                for suffix in suffixes
            ] + [
                f"{module_path.name}.*.{suffix}"
                for suffix in suffixes
            ]
            for pattern in patterns:
                for artifact in module_path.parent.glob(pattern):
                    if not artifact.is_file():
                        continue
                    artifact.unlink()
                    removed.append(artifact.relative_to(repo_root).as_posix())
    if removed:
        print(
            "Removed legacy source native artifacts: "
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


def _run_windows_tasklist(args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["tasklist", *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [
        line.rstrip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _windows_module_users(module_name: str) -> list[str]:
    return _run_windows_tasklist(["/m", module_name])


def _windows_python_processes() -> list[str]:
    lines: list[str] = []
    for image_name in ("python.exe", "pythonw.exe", "py.exe", "pytest.exe", "termin_editor.exe", "termin_player.exe"):
        process_lines = _run_windows_tasklist(["/fi", f"imagename eq {image_name}"])
        if process_lines:
            lines.extend(process_lines)
    return lines


def _native_artifacts_for_lock_diagnostics(repo_root: Path, package: PackageEntry) -> list[Path]:
    package_root = repo_root / package.path
    if not package_root.is_dir():
        return []
    artifacts: list[Path] = []
    for pattern in ("*.pyd", "*.dll"):
        artifacts.extend(path for path in package_root.rglob(pattern) if path.is_file())
    return sorted(artifacts)[:50]


def _print_install_failure_summary(
    package: PackageEntry,
    package_index: int,
    package_count: int,
    repo_root: Path,
    editable: bool,
) -> None:
    print(
        f"ERROR: pip install failed for {package.path} "
        f"({package_index}/{package_count}); Python package sync stopped.",
        file=sys.stderr,
    )
    print(
        "ERROR: packages after this point were not installed; rerun the install after fixing the cause.",
        file=sys.stderr,
    )

    if not editable or not _is_windows():
        return

    artifacts = _native_artifacts_for_lock_diagnostics(repo_root, package)
    print(
        "Windows editable install note: native .pyd/.dll files cannot be replaced while "
        "another process has them loaded.",
        file=sys.stderr,
    )
    if artifacts:
        print("Checked native artifacts for loaded-module owners:", file=sys.stderr)
        found_owner = False
        for artifact in artifacts:
            print(f"  - {artifact}", file=sys.stderr)
            for line in _windows_module_users(artifact.name):
                found_owner = True
                print(f"      {line}", file=sys.stderr)
        if not found_owner:
            print("  No loaded-module owner was reported by tasklist /m.", file=sys.stderr)
    else:
        print(f"No native artifacts found under {repo_root / package.path} yet.", file=sys.stderr)

    python_processes = _windows_python_processes()
    if python_processes:
        print("Running Python/Termin processes that may hold native modules:", file=sys.stderr)
        for line in python_processes:
            print(f"  {line}", file=sys.stderr)

    print(
        "Close Termin editor/player, pytest, Python REPLs, and stale venv processes, "
        "then rerun install-pip-packages.ps1 --editable --force.",
        file=sys.stderr,
    )


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
    if editable:
        _clear_legacy_source_native_artifacts(repo_root)

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
    package_count = len(packages)
    for package_index, package in enumerate(packages, start=1):
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
            _print_install_failure_summary(
                package=package,
                package_index=package_index,
                package_count=package_count,
                repo_root=repo_root,
                editable=editable,
            )
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
) -> tuple[Path, Path]:
    wheel_dir_env = os.environ.get("WHEEL_DIR")
    wheel_dir = Path(wheel_dir_env) if wheel_dir_env else sdk_prefix / "wheels"
    effective_build_dir = build_dir

    index = 0
    while index < len(stage_args):
        arg = stage_args[index]
        if arg in ("--debug", "-d"):
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

    return wheel_dir, effective_build_dir


def build_wheelhouse(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    stage_args: list[str],
    *,
    python_executable: Path | None = None,
) -> int:
    try:
        wheel_dir, effective_build_dir = _parse_wheelhouse_args(
            sdk_prefix,
            build_dir,
            stage_args,
        )
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
        bindings_dir = _resolve_bindings_dir(repo_root, effective_build_dir)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Using TERMIN_SDK={termin_sdk}")
    print(f"Using TERMIN_BINDINGS_DIR={bindings_dir}")
    print(f"Wheelhouse: {wheel_dir}")
    try:
        build_python = _ensure_sdk_python_build_environment(
            repo_root,
            base_python=python_executable,
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    result = _build_local_package_wheels(
        repo_root=repo_root,
        termin_sdk=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=wheel_dir,
        build_python=build_python,
    )
    if result != 0:
        return result
    result = _verify_library_wheel_subset_install(wheel_dir, build_python)
    if result != 0:
        return result

    print("")
    print("========================================")
    print(f"  SDK wheelhouse ready: {wheel_dir}")
    print("========================================")
    return 0


def _verify_library_wheel_subset_install(
    wheel_dir: Path,
    build_python: Path,
) -> int:
    wheel_patterns = (
        "tcbase-*.whl",
        "tgfx-*.whl",
        "termin_display-*.whl",
        "termin_gui_native-*.whl",
    )
    wheels = []
    for pattern in wheel_patterns:
        matching = sorted(wheel_dir.glob(pattern))
        if len(matching) != 1:
            print(
                f"ERROR: representative library subset expected one {pattern}, "
                f"found {len(matching)}",
                file=sys.stderr,
            )
            return 1
        wheels.append(matching[0])
    if list(wheel_dir.glob("termin_app-*.whl")):
        print("ERROR: termin-app wheel remains in public wheelhouse", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="termin-wheel-subset-") as temp_dir:
        result = _run(
            [
                str(build_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-compile",
                "--target",
                temp_dir,
                *(str(wheel) for wheel in wheels),
            ],
            cwd=wheel_dir,
            env=os.environ.copy(),
        )
        if result != 0:
            print("ERROR: representative library wheel subset install failed", file=sys.stderr)
            return result
        installed = Path(temp_dir)
        if list(installed.glob("termin_app-*.dist-info")) or (
            installed / "termin/editor"
        ).exists():
            print(
                "ERROR: representative library subset installed editor payload",
                file=sys.stderr,
            )
            return 1
    print("Representative editor-free library wheel subset install OK")
    return 0


def _build_local_package_wheels(
    repo_root: Path,
    termin_sdk: Path,
    bindings_dir: Path,
    wheel_dir: Path,
    build_python: Path,
) -> int:
    return build_local_wheel_artifact_set(
        repo_root=repo_root,
        sdk_prefix=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=wheel_dir.resolve(),
        build_python=build_python,
        packages=load_manifest(repo_root),
        run=_run,
        clear_build_caches=_clear_python_package_build_caches,
    )


def _publish_runtime_wheelhouse(repo_root: Path, sdk_prefix: Path) -> int:
    _, local_wheels = _runtime_wheel_dirs(repo_root)
    wheel_dir = sdk_prefix / "wheels"
    try:
        publish_local_wheel_artifact_set(
            local_wheels,
            wheel_dir,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=len(load_manifest(repo_root)),
        )
    except (LocalWheelArtifactError, OSError) as error:
        print(f"ERROR: failed to publish SDK wheelhouse: {error}", file=sys.stderr)
        return 1
    print(f"Published canonical SDK wheelhouse: {wheel_dir}")
    return 0


# Runtime package metadata and final verification have independent lifecycles,
# but remain re-exported here for callers of the historical sdk module.
from .sdk_runtime_metadata import (
    _clear_target_python_package_metadata,
    _load_runtime_lock,
    write_python_runtime_manifest,
)
from .sdk_verification import (
    verify_nanobind_extensions,
    verify_no_duplicate_libraries as verify_no_duplicate_libraries,
    verify_python_runtime_manifest as verify_python_runtime_manifest,
    verify_python_wheelhouse as verify_python_wheelhouse,
    verify_sdk,
    verify_sdk_artifacts as verify_sdk_artifacts,
    verify_sdk_python_launcher as verify_sdk_python_launcher,
)


def _build_dir(repo_root: Path, build_type: str) -> Path:
    env_build_dir = os.environ.get("BUILD_DIR")
    return Path(env_build_dir) if env_build_dir else repo_root / "build" / build_type


def _bundled_site_packages_hint(sdk_prefix: Path) -> Path:
    if _is_windows():
        return sdk_prefix / "python" / "Lib" / "site-packages"
    return sdk_prefix / "lib" / "python3.*" / "site-packages"


def prepare_pinned_python_build_environment(repo_root: Path) -> Path:
    toolchain = ensure_python_toolchain(repo_root)
    return _ensure_sdk_python_build_environment(
        repo_root,
        base_python=toolchain.python_executable,
    )


def run_sdk_build(
    repo_root: Path,
    build_type: str,
    stage_args: list[str],
    build_csharp: bool,
    dry_run: bool,
) -> int:
    sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
    build_dir = _build_dir(repo_root, build_type)
    build_env = os.environ.copy()
    if dry_run:
        print("+ ensure pinned free-threaded Python toolchain")
        build_python = Path(_python_executable())
    else:
        try:
            build_python = prepare_pinned_python_build_environment(repo_root)
        except (PythonAbiError, PythonToolchainError, OSError, RuntimeError) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
    build_env["PYTHON_BIN"] = str(build_python)
    build_env["PYTHON_EXECUTABLE"] = str(build_python)

    print("")
    print("========================================")
    print("  Stage 1/4: C/C++ libraries + Python bindings")
    print("========================================")
    print("")
    command = _stage_script(repo_root, "build-sdk-bindings") + stage_args
    if dry_run:
        print("+ " + " ".join(command))
    else:
        result = _run(command, cwd=repo_root, env=build_env)
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  Stage 2/4: C# bindings")
    print("========================================")
    print("")
    if build_csharp:
        command = _stage_script(repo_root, "build-sdk-csharp") + stage_args
        if dry_run:
            print("+ " + " ".join(command))
        else:
            result = _run(command, cwd=repo_root, env=build_env)
            if result != 0:
                return result
    else:
        print("Skipping C# bindings (use --csharp on Linux).")

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
        result = install_python_packages(
            repo_root,
            sdk_prefix,
            build_dir,
            python_executable=build_python,
        )
        if result != 0:
            return result

    legacy_sdk_python = sdk_prefix / "lib" / "python"
    if not dry_run and legacy_sdk_python.is_dir():
        print(f"Removing legacy SDK Python staging tree: {legacy_sdk_python}")
        shutil.rmtree(legacy_sdk_python)

    print("")
    print("========================================")
    print("  Stage 4/4: Publish SDK Python wheelhouse")
    print("========================================")
    print("")
    if dry_run:
        print("+ publish Stage 3 wheel artifacts into SDK wheelhouse")
    else:
        result = _publish_runtime_wheelhouse(repo_root, sdk_prefix)
        if result != 0:
            return result
        result = _verify_library_wheel_subset_install(
            sdk_prefix / "wheels",
            build_python,
        )
        if result != 0:
            return result

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

    required_submodules = profile_submodules(profile, vulkan)
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

    android_capabilities_parser = subparsers.add_parser(
        "write-android-capabilities",
        help="Record truthful per-ABI and aggregate Android SDK capabilities.",
    )
    android_capabilities_parser.add_argument("--sdk-root", type=Path, required=True)
    android_capabilities_parser.add_argument(
        "--android-sdk-root", type=Path, required=True
    )
    android_capabilities_parser.add_argument("--abi", required=True)
    android_capabilities_parser.add_argument("--build-dir", type=Path, required=True)

    install_python_parser = subparsers.add_parser(
        "install-python",
        help="Populate the bundled SDK Python site-packages.",
    )
    install_python_parser.add_argument("--build-type", default="Release")

    prepare_python_parser = subparsers.add_parser(
        "prepare-build-python-runtime",
        help="Prepare bundled Python runtime files before native CMake configure.",
    )
    prepare_python_parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=None,
        help="SDK install prefix. Defaults to SDK_PREFIX or ./sdk.",
    )

    subparsers.add_parser(
        "prepare-python-toolchain",
        help="Materialize the pinned free-threaded Python build environment.",
    )

    resolve_python_parser = subparsers.add_parser(
        "resolve-python-layout",
        help="Validate the SDK Python ABI and print its site-packages path.",
    )
    resolve_python_parser.add_argument("--sdk-prefix", type=Path, required=True)
    resolve_python_parser.add_argument(
        "--require-native-bindings",
        action="store_true",
        help="Require the tcbase native extension in the resolved layout.",
    )

    publish_python_parser = subparsers.add_parser(
        "publish-cmake-python",
        help="Normalize the staged CMake Python install into SDK site-packages.",
    )
    publish_python_parser.add_argument("--install-dir", type=Path, required=True)
    publish_python_parser.add_argument("--sdk-prefix", type=Path, required=True)

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

    import_gate_parser = subparsers.add_parser(
        "verify-python-import-graph",
        help="Import the installed SDK graph and require the GIL to remain disabled.",
    )
    import_gate_parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=None,
        help="SDK install prefix. Defaults to SDK_PREFIX or ./sdk.",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Build the full SDK through the existing stage scripts.",
    )
    build_parser.add_argument("--debug", "-d", action="store_true")
    build_parser.add_argument(
        "--csharp",
        action="store_true",
        help="Build C# bindings on Linux (enabled by default on Windows).",
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
    if args.command == "write-android-capabilities":
        return write_android_capabilities(
            sdk_root=args.sdk_root.resolve(),
            android_sdk_root=args.android_sdk_root.resolve(),
            abi=args.abi,
            build_dir=args.build_dir.resolve(),
        )
    if args.command == "install-python":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        try:
            python_executable = prepare_pinned_python_build_environment(repo_root)
        except (
            PythonAbiError,
            PythonToolchainError,
            OSError,
            RuntimeError,
        ) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
        return install_python_packages(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            python_executable=python_executable,
        )
    if args.command == "prepare-build-python-runtime":
        sdk_prefix = args.sdk_prefix
        if sdk_prefix is None:
            sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return prepare_build_python_runtime(sdk_prefix)
    if args.command == "prepare-python-toolchain":
        try:
            python_executable = prepare_pinned_python_build_environment(repo_root)
        except (
            PythonAbiError,
            PythonToolchainError,
            OSError,
            RuntimeError,
        ) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
        print(python_executable.resolve())
        return 0
    if args.command == "resolve-python-layout":
        try:
            site_packages = resolve_sdk_python_layout(
                args.sdk_prefix,
                require_native_bindings=args.require_native_bindings,
            )
        except RuntimeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(site_packages.resolve())
        return 0
    if args.command == "publish-cmake-python":
        try:
            publish_cmake_python_install(
                install_dir=args.install_dir,
                sdk_prefix=args.sdk_prefix,
            )
        except RuntimeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0
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
        try:
            python_executable = prepare_pinned_python_build_environment(repo_root)
        except (
            PythonAbiError,
            PythonToolchainError,
            OSError,
            RuntimeError,
        ) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
        return build_wheelhouse(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            stage_args=wheel_args,
            python_executable=python_executable,
        )
    if args.command == "verify-sdk":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return verify_sdk(sdk_prefix=sdk_prefix, build_dir=build_dir)
    if args.command == "verify-python-import-graph":
        sdk_prefix = args.sdk_prefix or Path(
            os.environ.get("SDK_PREFIX", str(repo_root / "sdk"))
        )
        return verify_nanobind_extensions(sdk_prefix.resolve())
    if args.command == "build":
        obsolete_wheel_flags = {"--no-wheels", "--wheels"} & set(unknown_args)
        if obsolete_wheel_flags:
            obsolete = sorted(obsolete_wheel_flags)[0]
            print(
                f"ERROR: {obsolete} was removed; full SDK builds always publish "
                "the canonical wheel artifact set",
                file=sys.stderr,
            )
            return 2
        build_type = "Debug" if args.debug else "Release"
        stage_args = list(unknown_args)
        if args.debug and "--debug" not in stage_args and "-d" not in stage_args:
            stage_args.insert(0, "--debug")
        return run_sdk_build(
            repo_root=repo_root,
            build_type=build_type,
            stage_args=stage_args,
            build_csharp=_is_windows() or args.csharp,
            dry_run=args.dry_run,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
