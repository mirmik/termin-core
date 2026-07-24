"""Final SDK layout, artifact, and bundled runtime verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from .artifact_manifest import (
    ArtifactManifest,
    ArtifactManifestError,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
)
from .application_payload import (
    INSTALLED_MANIFEST_NAME as APPLICATION_PAYLOAD_MANIFEST_NAME,
    INSTALLED_SCHEMA as APPLICATION_PAYLOAD_MANIFEST_SCHEMA,
)
from .sdk_runtime_metadata import (
    RUNTIME_MANIFEST_NAME,
    RUNTIME_MANIFEST_SCHEMA,
    _distribution_metadata_paths,
    _distribution_name_from_metadata_dir,
    _metadata_distribution_field,
    _normalized_distribution_name,
    _sha256_file,
    _verify_distribution_records,
)
from .python_abi import PythonAbiError, PythonAbiIdentity
from .wheelhouse import require_wheel_python_abi as _require_wheel_python_abi


def _is_windows() -> bool:
    return os.name == "nt"


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _is_duplicate_exception(sdk_prefix: Path, path: Path) -> bool:
    path_text = _normalize_path(str(path))
    sdk_text = _normalize_path(str(sdk_prefix))
    android_prefix = _normalize_path(str(sdk_prefix / "android")) + "/"
    csharp_lib_prefix = _normalize_path(str(sdk_prefix / "csharp" / "lib")) + "/"
    lower_path = path_text.lower()
    csharp_lib_relative = (
        path_text[len(csharp_lib_prefix) :]
        if path_text.startswith(csharp_lib_prefix)
        else ""
    )
    csharp_lib_parts = [part for part in csharp_lib_relative.split("/") if part]
    is_csharp_managed_lib = (
        _is_windows()
        and len(csharp_lib_parts) in (1, 2)
        and csharp_lib_parts[-1].lower().endswith(".dll")
    )
    return (
        path_text.startswith(android_prefix)
        # Managed C# assemblies are intentionally installed both as legacy flat
        # copies and as target-framework-specific lib/<TFM> assemblies.
        or is_csharp_managed_lib
        or "/csharp/runtimes/" in path_text
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
            and lower_path.startswith(
                _normalize_path(str(sdk_prefix / "python")).lower() + "/"
            )
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
        for library_path in sdk_prefix.rglob(pattern):
            if library_path.is_symlink() or not library_path.is_file():
                continue
            if _is_duplicate_exception(sdk_prefix, library_path):
                continue
            previous = seen.get(library_path.name)
            if previous is not None:
                duplicates.append((library_path.name, previous, library_path))
            else:
                seen[library_path.name] = library_path
    if duplicates:
        for name, first, second in duplicates:
            print(f"  DUPLICATE: {name}")
            print(f"    - {first}")
            print(f"    - {second}")
        print(
            f"FAILED: {len(duplicates)} duplicate library/libraries found",
            file=sys.stderr,
        )
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
    for build_artifact in build_artifacts:
        build_mtime = build_artifact.stat().st_mtime
        for sdk_artifact in sdk_prefix.rglob(build_artifact.name):
            sdk_text = _normalize_path(str(sdk_artifact))
            android_prefix = _normalize_path(str(sdk_prefix / "android")) + "/"
            if sdk_text.startswith(android_prefix):
                continue
            if "/csharp/runtimes/" in sdk_text:
                continue
            sdk_mtime = sdk_artifact.stat().st_mtime
            if int(sdk_mtime) < int(build_mtime):
                stale.append((sdk_artifact, build_artifact))
            elif int(sdk_mtime) == int(build_mtime) and sdk_mtime < build_mtime:
                same_second += 1
    if stale:
        for sdk_artifact, build_artifact in stale:
            print(f"  STALE: {sdk_artifact}")
            print(f"    older than: {build_artifact}")
        print(
            f"FAILED: {len(stale)} stale SDK artifact(s) found",
            file=sys.stderr,
        )
        return 1
    print("  OK: SDK artifacts are not older than matching build artifacts")
    if same_second:
        print(
            f"  NOTE: {same_second} matching artifact(s) differed only within "
            "timestamp sub-second precision"
        )
    return 0


def verify_sdk(
    sdk_prefix: Path,
    build_dir: Path,
    *,
    wheelhouse_provenance: bool = True,
) -> int:
    result = verify_no_duplicate_libraries(sdk_prefix)
    if result != 0:
        return result
    result = verify_sdk_artifacts(sdk_prefix, build_dir)
    if result != 0:
        return result
    result = verify_python_runtime_manifest(sdk_prefix)
    if result != 0:
        return result
    if wheelhouse_provenance:
        result = verify_python_wheelhouse(sdk_prefix)
        if result != 0:
            return result
    else:
        print("Verifying: SDK Python wheelhouse provenance")
        print(
            "  SKIP: build used --no-wheels; existing wheelhouse was not rebuilt "
            "and remains unverified"
        )
    result = verify_application_python_payloads(sdk_prefix)
    if result != 0:
        return result
    result = verify_embedded_python_hosts(sdk_prefix)
    if result != 0:
        return result
    result = verify_sdk_python_launcher(sdk_prefix)
    if result != 0:
        return result
    return verify_nanobind_extensions(sdk_prefix)


def _hostile_python_environment(sdk_prefix: Path) -> dict[str, str]:
    hostile_env = os.environ.copy()
    hostile_env.update(
        {
            "PYTHONHOME": str(sdk_prefix / "__invalid_python_home__"),
            "PYTHONPATH": str(sdk_prefix / "__invalid_python_path__"),
            "PYTHONUSERBASE": str(sdk_prefix / "__invalid_user_base__"),
            "PYTHONNOUSERSITE": "0",
            "TERMIN_SDK": str(sdk_prefix.resolve()),
        }
    )
    return hostile_env


def _python_version_and_paths(py_exec: str) -> dict[str, object]:
    script = (
        "import json, site, sys, sysconfig; "
        "print(json.dumps({'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
        "'soabi': sysconfig.get_config_var('SOABI') or '', "
        "'free_threaded': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'py_gil_disabled': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'prefix': sys.prefix, 'base_prefix': sys.base_prefix, "
        "'executable': sys.executable, 'base_executable': sys._base_executable, "
        "'stdlib': sysconfig.get_paths()['stdlib'], "
        "'libdir': sysconfig.get_config_var('LIBDIR') or '', "
        "'ldlibrary': sysconfig.get_config_var('LDLIBRARY') or '', "
        "'sitepackages': site.getsitepackages() + ([site.getusersitepackages()] if site.getusersitepackages() else [])}))"
    )
    result = subprocess.run([py_exec, "-c", script], check=False, text=True, stdout=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"failed to inspect Python runtime: {py_exec}")
    return json.loads(result.stdout)

def verify_sdk_python_launcher(sdk_prefix: Path) -> int:
    launcher_name = "termin_python.exe" if _is_windows() else "termin_python"
    launcher = sdk_prefix / "bin" / launcher_name
    print("Verifying: isolated SDK Python launcher")
    if not launcher.is_file():
        print(f"FAILED: SDK Python launcher is missing: {launcher}", file=sys.stderr)
        return 1

    hostile_env = _hostile_python_environment(sdk_prefix)
    info_result = subprocess.run(
        [str(launcher), "--termin-info"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=hostile_env,
    )
    if info_result.returncode != 0:
        print(
            "FAILED: SDK Python launcher diagnostics failed: "
            + info_result.stderr.strip(),
            file=sys.stderr,
        )
        return 1
    try:
        info = json.loads(info_result.stdout)
    except json.JSONDecodeError as error:
        print(f"FAILED: invalid SDK Python diagnostics JSON: {error}", file=sys.stderr)
        return 1

    expected_root = sdk_prefix.resolve()
    # Windows ships an embedded distribution under ``sdk/python``.  On POSIX
    # the SDK root itself is Python home and the standard library lives below
    # ``sdk/lib/pythonX.Y``; keep this contract aligned with termin_python.
    expected_python_home = (
        (expected_root / "python").resolve() if _is_windows() else expected_root
    )
    if Path(str(info.get("sdk_root", ""))).resolve() != expected_root:
        print("FAILED: SDK Python launcher reported the wrong SDK root", file=sys.stderr)
        return 1
    if Path(str(info.get("python_home", ""))).resolve() != expected_python_home:
        print("FAILED: SDK Python launcher reported the wrong Python home", file=sys.stderr)
        return 1
    expected_flags = {
        "isolated": True,
        "use_environment": False,
        "user_site": False,
    }
    for field, expected in expected_flags.items():
        if info.get(field) is not expected:
            print(
                f"FAILED: SDK Python launcher diagnostic {field}={info.get(field)!r}",
                file=sys.stderr,
            )
            return 1

    smoke = (
        "import pathlib, site, sys, tcbase, termin.engine, termin.tween; "
        f"root = pathlib.Path({str(expected_root)!r}); "
        f"python_home = pathlib.Path({str(expected_python_home)!r}); "
        "assert pathlib.Path(tcbase.__file__).resolve().is_relative_to(root); "
        "assert pathlib.Path(termin.tween.__file__).resolve().is_relative_to(root); "
        "assert site.ENABLE_USER_SITE is False; "
        "assert pathlib.Path(sys.prefix).resolve() == python_home"
    )
    smoke_result = subprocess.run(
        [str(launcher), "-c", smoke],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=hostile_env,
    )
    if smoke_result.returncode != 0:
        print(
            "FAILED: installed SDK Python import smoke failed: "
            + smoke_result.stderr.strip(),
            file=sys.stderr,
        )
        return 1
    print("  OK: launcher ignores ambient Python paths and imports SDK packages")
    return 0


def verify_nanobind_extensions(sdk_prefix: Path) -> int:
    print("Verifying: canonical nanobind ABI and native extension import graph")
    try:
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifact_manifest.require_kind(SDK_MANIFEST_KIND)
        artifact_manifest.validate_all(
            expected_python_abi=artifact_manifest.python_abi,
        )
    except (ArtifactManifestError, PythonAbiError) as error:
        print(f"FAILED: cannot inspect nanobind artifacts: {error}", file=sys.stderr)
        return 1

    free_threaded = artifact_manifest.python_abi.free_threaded
    runtime_stem = "nanobind-ft" if free_threaded else "nanobind"
    obsolete_stem = "nanobind" if free_threaded else "nanobind-ft"
    if _is_windows():
        runtime_name = f"{runtime_stem}.dll"
        obsolete_names = {
            f"{obsolete_stem}.dll",
            f"{obsolete_stem}.lib",
        }
    elif sys.platform == "darwin":
        runtime_name = f"lib{runtime_stem}.dylib"
        obsolete_names = {f"lib{obsolete_stem}.dylib"}
    else:
        runtime_name = f"lib{runtime_stem}.so"
        obsolete_names = {f"lib{obsolete_stem}.so"}

    runtime_candidates = [
        sdk_prefix / "lib" / runtime_name,
        sdk_prefix / "bin" / runtime_name,
    ]
    if not any(path.is_file() for path in runtime_candidates):
        print(
            f"FAILED: canonical nanobind runtime is missing: {runtime_name}",
            file=sys.stderr,
        )
        return 1
    obsolete = [
        path
        for directory in (sdk_prefix / "lib", sdk_prefix / "bin")
        for name in obsolete_names
        if (path := directory / name).is_file()
    ]
    if obsolete:
        print(
            "FAILED: incompatible nanobind runtime remains in SDK: "
            + ", ".join(str(path) for path in obsolete),
            file=sys.stderr,
        )
        return 1

    extensions = []
    runtime_paths = []
    dependency_errors = []
    for artifact in artifact_manifest.data["artifacts"]:
        if artifact.get("kind") != "python-extension":
            continue
        extension = artifact.get("extension")
        if not isinstance(extension, str) or not extension:
            dependency_errors.append("python-extension artifact has no import name")
            continue
        dependencies = artifact.get("runtime_dependencies")
        if not isinstance(dependencies, list):
            dependency_errors.append(f"{extension} has invalid runtime dependencies")
            continue
        names = {
            dependency.get("name")
            for dependency in dependencies
            if isinstance(dependency, dict)
        }
        if runtime_name not in names:
            dependency_errors.append(
                f"{extension} does not link the canonical {runtime_name}"
            )
        if names & obsolete_names:
            dependency_errors.append(
                f"{extension} links an incompatible nanobind runtime"
            )
        runtime_paths.extend(
            str((sdk_prefix / str(dependency["path"])).resolve())
            for dependency in dependencies
            if isinstance(dependency, dict)
            and isinstance(dependency.get("path"), str)
        )
        extensions.append(extension)
    if dependency_errors:
        for error in dependency_errors:
            print(f"  {error}", file=sys.stderr)
        print(
            f"FAILED: {len(dependency_errors)} nanobind dependency error(s)",
            file=sys.stderr,
        )
        return 1
    if not extensions:
        print("FAILED: SDK artifact manifest has no Python extensions", file=sys.stderr)
        return 1

    launcher_name = "termin_python.exe" if _is_windows() else "termin_python"
    launcher = sdk_prefix / "bin" / launcher_name
    import_script = "\n".join(
        (
            "import ctypes, importlib, json, os, pathlib, sys",
            f"names = {extensions!r}",
            f"runtime_paths = {list(dict.fromkeys(runtime_paths))!r}",
            f"free_threaded = {free_threaded!r}",
            "loaded = []",
            "gil_enablers = []",
            "dll_handles = []",
            "if sys.platform == 'win32':",
            "    directories = {str(pathlib.Path(path).parent) for path in runtime_paths}",
            "    dll_handles = [os.add_dll_directory(path) for path in directories]",
            "else:",
            "    pending = runtime_paths",
            "    while pending:",
            "        failed = []",
            "        for path in pending:",
            "            try:",
            "                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)",
            "            except OSError as error:",
            "                failed.append((path, str(error)))",
            "        if len(failed) == len(pending):",
            "            raise RuntimeError(f'cannot preload native dependencies: {failed}')",
            "        pending = [path for path, _error in failed]",
            "for name in names:",
            "    importlib.import_module(name)",
            "    loaded.append(name)",
            "    if free_threaded and sys._is_gil_enabled():",
            "        gil_enablers.append(name)",
            "assert not gil_enablers, gil_enablers",
            "print(json.dumps(loaded))",
        )
    )
    result = subprocess.run(
        [str(launcher), "-c", import_script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_hostile_python_environment(sdk_prefix),
    )
    if result.returncode != 0:
        print(
            "FAILED: native extension import graph smoke failed: "
            + result.stderr.strip(),
            file=sys.stderr,
        )
        return 1
    print(
        f"  OK: {len(extensions)} native extensions use {runtime_name}; "
        f"free-threaded={free_threaded}"
    )
    return 0


def verify_application_python_payloads(sdk_prefix: Path) -> int:
    print("Verifying: application-owned Python payloads")
    manifest_path = sdk_prefix / APPLICATION_PAYLOAD_MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAILED: cannot read application payload manifest: {error}", file=sys.stderr)
        return 1
    if manifest.get("schema") != APPLICATION_PAYLOAD_MANIFEST_SCHEMA:
        print("FAILED: unsupported application payload manifest schema", file=sys.stderr)
        return 1
    try:
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifact_manifest.require_kind(SDK_MANIFEST_KIND)
        payload_abi = PythonAbiIdentity.from_mapping(
            manifest.get("python_abi"),
            context="application payload Python ABI",
        )
        artifact_manifest.python_abi.require_matches(
            payload_abi,
            context="artifact/application payload Python ABI",
        )
    except (ArtifactManifestError, PythonAbiError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1

    sdk_root = sdk_prefix.resolve()
    site_packages = (sdk_root / str(manifest.get("site_packages", ""))).resolve()
    if not site_packages.is_relative_to(sdk_root) or not site_packages.is_dir():
        print("FAILED: application payload site-packages path is invalid", file=sys.stderr)
        return 1

    raw_files = manifest.get("files")
    raw_payloads = manifest.get("payloads")
    if not isinstance(raw_files, list) or not isinstance(raw_payloads, list):
        print("FAILED: application payload manifest has invalid lists", file=sys.stderr)
        return 1
    errors = []
    seen_paths = set()
    for entry in raw_files:
        if not isinstance(entry, dict):
            errors.append("invalid application payload file record")
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            errors.append("application payload file record has no path")
            continue
        path = (sdk_root / raw_path).resolve()
        if not path.is_relative_to(sdk_root):
            errors.append(f"application payload path escapes SDK: {raw_path}")
            continue
        if raw_path in seen_paths:
            errors.append(f"duplicate application payload path: {raw_path}")
            continue
        seen_paths.add(raw_path)
        if not path.is_file():
            errors.append(f"application payload file is missing: {raw_path}")
            continue
        expected_hash = entry.get("sha256")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            errors.append(f"application payload hash mismatch: {raw_path}")
    if errors:
        for error in errors[:50]:
            print(f"  {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} application payload error(s)", file=sys.stderr)
        return 1

    imports = []
    executables = []
    for payload in raw_payloads:
        if not isinstance(payload, dict):
            print("FAILED: invalid application payload entry", file=sys.stderr)
            return 1
        payload_imports = payload.get("imports", [])
        payload_executables = payload.get("executables", [])
        if not isinstance(payload_imports, list) or not all(
            isinstance(module, str) and module for module in payload_imports
        ):
            print("FAILED: invalid application payload imports", file=sys.stderr)
            return 1
        if not isinstance(payload_executables, list) or not all(
            isinstance(name, str) and name for name in payload_executables
        ):
            print("FAILED: invalid application payload executables", file=sys.stderr)
            return 1
        imports.extend(payload_imports)
        executables.extend(payload_executables)

    launcher_name = "termin_python.exe" if _is_windows() else "termin_python"
    launcher = sdk_root / "bin" / launcher_name
    import_script = (
        "import importlib, json, pathlib; "
        f"root = pathlib.Path({str(site_packages)!r}).resolve(); "
        f"names = {imports!r}; "
        "paths = {name: pathlib.Path(importlib.import_module(name).__file__).resolve() "
        "for name in names}; "
        "assert all(path.is_relative_to(root) for path in paths.values()), paths; "
        "print(json.dumps({name: str(path) for name, path in paths.items()}))"
    )
    import_result = subprocess.run(
        [str(launcher), "-c", import_script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_hostile_python_environment(sdk_root),
    )
    if import_result.returncode != 0:
        print(
            "FAILED: application payload import smoke failed: "
            + import_result.stderr.strip(),
            file=sys.stderr,
        )
        return 1

    executable_suffix = ".exe" if _is_windows() else ""
    for executable in executables:
        executable_path = sdk_root / "bin" / f"{executable}{executable_suffix}"
        if not executable_path.is_file():
            print(f"FAILED: application executable is missing: {executable_path}", file=sys.stderr)
            return 1
        result = subprocess.run(
            [str(executable_path), "--termin-python-layout-smoke"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_hostile_python_environment(sdk_root),
        )
        if result.returncode != 0:
            print(
                f"FAILED: {executable} application payload smoke failed: "
                + result.stderr.strip(),
                file=sys.stderr,
            )
            return 1
    print(
        f"  OK: {len(raw_files)} app-owned files, {len(imports)} imports and "
        f"{len(executables)} executable hosts verified"
    )
    return 0


def verify_embedded_python_hosts(sdk_prefix: Path) -> int:
    print("Verifying: embedded Python product hosts")
    executable_suffix = ".exe" if _is_windows() else ""
    player = sdk_prefix / "bin" / f"termin_player{executable_suffix}"
    if not player.is_file():
        print(f"FAILED: embedded Python host is missing: {player}", file=sys.stderr)
        return 1
    result = subprocess.run(
        [str(player), "--termin-python-layout-smoke"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_hostile_python_environment(sdk_prefix),
    )
    if result.returncode != 0:
        print(
            "FAILED: termin_player embedded Python smoke failed: "
            + result.stderr.strip(),
            file=sys.stderr,
        )
        return 1
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        print(
            f"FAILED: termin_player embedded Python smoke returned invalid JSON: {error}",
            file=sys.stderr,
        )
        return 1
    if payload.get("module") != "_termin_player_native":
        print(
            "FAILED: termin_player did not import its raw native module",
            file=sys.stderr,
        )
        return 1
    if payload.get("free_threaded") is not True or payload.get("gil_enabled") is not False:
        print(
            "FAILED: termin_player raw native module enabled the GIL: "
            + json.dumps(payload, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    print("  OK: termin_player raw module imports without enabling the GIL")
    return 0


def verify_python_runtime_manifest(sdk_prefix: Path) -> int:
    print("Verifying: SDK Python runtime manifest")
    manifest_path = sdk_prefix / RUNTIME_MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"FAILED: Python runtime manifest is missing: {manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAILED: invalid Python runtime manifest: {error}", file=sys.stderr)
        return 1
    if manifest.get("schema") != RUNTIME_MANIFEST_SCHEMA:
        print("FAILED: unsupported Python runtime manifest schema", file=sys.stderr)
        return 1
    try:
        runtime_abi = PythonAbiIdentity.from_mapping(
            manifest.get("python_abi"),
            context="Python runtime manifest ABI",
        )
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifact_manifest.require_kind(SDK_MANIFEST_KIND)
        artifact_manifest.validate_all(expected_python_abi=runtime_abi)
    except (ArtifactManifestError, PythonAbiError) as error:
        print(f"FAILED: invalid SDK artifact manifest: {error}", file=sys.stderr)
        return 1
    if manifest.get("native_build_id") != artifact_manifest.native_build_id:
        print("FAILED: Python runtime native_build_id mismatch", file=sys.stderr)
        return 1
    try:
        artifact_manifest.python_abi.require_matches(
            runtime_abi,
            context="artifact/runtime manifest Python ABI",
        )
    except PythonAbiError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1

    lock_path = (sdk_prefix / str(manifest.get("runtime_lock", ""))).resolve()
    if not lock_path.is_relative_to(sdk_prefix.resolve()) or not lock_path.is_file():
        print("FAILED: runtime lock referenced by manifest is missing", file=sys.stderr)
        return 1
    if _sha256_file(lock_path) != manifest.get("runtime_lock_sha256"):
        print("FAILED: installed Python runtime lock hash mismatch", file=sys.stderr)
        return 1

    site_packages = (sdk_prefix / str(manifest.get("site_packages", ""))).resolve()
    if not site_packages.is_relative_to(sdk_prefix.resolve()) or not site_packages.is_dir():
        print("FAILED: site-packages referenced by runtime manifest is missing", file=sys.stderr)
        return 1

    declared_entries = manifest.get("distributions")
    if not isinstance(declared_entries, list):
        print("FAILED: runtime manifest distributions must be a list", file=sys.stderr)
        return 1
    declared: dict[str, dict[str, str]] = {}
    for entry in declared_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            print("FAILED: invalid runtime manifest distribution entry", file=sys.stderr)
            return 1
        normalized = _normalized_distribution_name(entry["name"])
        if normalized in declared:
            print(f"FAILED: duplicate manifest distribution: {entry['name']}", file=sys.stderr)
            return 1
        declared[normalized] = entry

    native_distributions = {
        _normalized_distribution_name(distribution)
        for entry in artifact_manifest.data["artifacts"]
        if isinstance((distribution := entry.get("distribution")), str)
        and distribution
    }
    expected_suffix = f"+sdk{artifact_manifest.native_build_id}"
    for normalized in sorted(native_distributions):
        entry = declared.get(normalized)
        if entry is None:
            print(
                f"FAILED: native distribution missing from runtime manifest: {normalized}",
                file=sys.stderr,
            )
            return 1
        if not str(entry.get("version", "")).endswith(expected_suffix):
            print(
                f"FAILED: native distribution {entry['name']} has version "
                f"{entry.get('version')!r}, expected suffix {expected_suffix}",
                file=sys.stderr,
            )
            return 1

    actual_metadata = _distribution_metadata_paths(site_packages)
    actual_names: set[str] = set()
    errors: list[str] = []
    for metadata_path in actual_metadata:
        name = _distribution_name_from_metadata_dir(metadata_path)
        version = _metadata_distribution_field(metadata_path, "version")
        if name is None or version is None:
            errors.append(f"invalid distribution metadata: {metadata_path.name}")
            continue
        normalized = _normalized_distribution_name(name)
        actual_names.add(normalized)
        entry = declared.get(normalized)
        if entry is None:
            errors.append(f"undeclared distribution: {name}=={version}")
            continue
        if entry.get("version") != version:
            errors.append(
                f"distribution version mismatch: {name}=={version}, "
                f"manifest {entry.get('version')}"
            )
        expected_metadata = entry.get("metadata")
        if expected_metadata != metadata_path.relative_to(site_packages).as_posix():
            errors.append(f"distribution metadata path mismatch: {name}")
        record_path = metadata_path / "RECORD"
        if not record_path.is_file():
            errors.append(f"distribution has no RECORD: {name}")
        elif _sha256_file(record_path) != entry.get("record_sha256"):
            errors.append(f"distribution RECORD hash mismatch: {name}")
    for normalized, entry in declared.items():
        if normalized not in actual_names:
            errors.append(f"manifest distribution is missing: {entry['name']}")
    errors.extend(_verify_distribution_records(site_packages, actual_metadata))
    if errors:
        for error in errors[:50]:
            print(f"  {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} Python runtime manifest error(s)", file=sys.stderr)
        return 1
    print(f"  OK: {len(declared)} declared distributions and RECORD hashes verified")
    return 0


def _wheel_metadata(wheel: Path) -> tuple[str, str, zipfile.ZipFile]:
    archive = zipfile.ZipFile(wheel)
    metadata_names = [
        name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
    ]
    if len(metadata_names) != 1:
        archive.close()
        raise RuntimeError(f"wheel has {len(metadata_names)} METADATA files: {wheel.name}")
    metadata = archive.read(metadata_names[0]).decode("utf-8", errors="replace")
    fields = {}
    for line in metadata.splitlines():
        if line.startswith(("Name:", "Version:")):
            key, value = line.split(":", 1)
            fields[key.lower()] = value.strip()
    if not fields.get("name") or not fields.get("version"):
        archive.close()
        raise RuntimeError(f"wheel metadata has no Name/Version: {wheel.name}")
    return fields["name"], fields["version"], archive


def _wheel_abi_tags(archive: zipfile.ZipFile, *, wheel_name: str) -> set[str]:
    wheel_metadata_names = [
        name for name in archive.namelist() if name.endswith(".dist-info/WHEEL")
    ]
    if len(wheel_metadata_names) != 1:
        raise RuntimeError(
            f"wheel has {len(wheel_metadata_names)} WHEEL files: {wheel_name}"
        )
    metadata = archive.read(wheel_metadata_names[0]).decode(
        "utf-8",
        errors="replace",
    )
    tags = {
        line.split(":", 1)[1].strip()
        for line in metadata.splitlines()
        if line.startswith("Tag:")
    }
    if not tags:
        raise RuntimeError(f"wheel metadata has no Tag fields: {wheel_name}")
    abi_tags = set()
    for tag in tags:
        parts = tag.rsplit("-", 2)
        if len(parts) != 3:
            raise RuntimeError(f"wheel has malformed Tag {tag!r}: {wheel_name}")
        abi_tags.update(parts[1].split("."))
    return abi_tags


def verify_python_wheelhouse(sdk_prefix: Path) -> int:
    wheel_dir = sdk_prefix / "wheels"
    print("Verifying: SDK Python wheelhouse provenance")
    if not wheel_dir.is_dir():
        print("  SKIP: public SDK wheelhouse is not present")
        return 0
    try:
        runtime_manifest = json.loads(
            (sdk_prefix / RUNTIME_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        if runtime_manifest.get("schema") != RUNTIME_MANIFEST_SCHEMA:
            raise RuntimeError("unsupported Python runtime manifest schema")
        runtime_abi = PythonAbiIdentity.from_mapping(
            runtime_manifest.get("python_abi"),
            context="Python runtime manifest ABI",
        )
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifact_manifest.require_kind(SDK_MANIFEST_KIND)
        artifact_manifest.validate_all(expected_python_abi=runtime_abi)
        artifact_manifest.python_abi.require_matches(
            runtime_abi,
            context="artifact/runtime manifest Python ABI",
        )
    except (
        ArtifactManifestError,
        PythonAbiError,
        OSError,
        RuntimeError,
        json.JSONDecodeError,
    ) as error:
        print(f"FAILED: cannot verify SDK wheelhouse: {error}", file=sys.stderr)
        return 1

    runtime_versions = {
        _normalized_distribution_name(str(entry.get("name", ""))): entry.get("version")
        for entry in runtime_manifest.get("distributions", [])
        if isinstance(entry, dict)
    }
    artifacts_by_distribution: dict[str, list[dict[str, object]]] = {}
    for entry in artifact_manifest.data["artifacts"]:
        distribution = entry.get("distribution")
        if not isinstance(distribution, str) or not distribution:
            continue
        normalized = _normalized_distribution_name(distribution)
        artifacts_by_distribution.setdefault(normalized, []).append(entry)

    wheels: dict[str, list[tuple[Path, str, zipfile.ZipFile]]] = {}
    errors = []
    for wheel in sorted(wheel_dir.glob("*.whl")):
        archive = None
        try:
            name, version, archive = _wheel_metadata(wheel)
            abi_tags = _wheel_abi_tags(archive, wheel_name=wheel.name)
            _require_wheel_python_abi(
                abi_tags,
                artifact_manifest.python_abi,
                wheel_name=wheel.name,
            )
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            if archive is not None:
                archive.close()
            errors.append(str(error))
            continue
        normalized = _normalized_distribution_name(name)
        wheels.setdefault(normalized, []).append((wheel, version, archive))
    try:
        if "termin-app" in wheels:
            errors.append("application product termin-app must not have a public wheel")
        for distribution, artifacts in artifacts_by_distribution.items():
            matching = wheels.get(distribution, [])
            if len(matching) != 1:
                errors.append(
                    f"native distribution {distribution} has {len(matching)} public wheels"
                )
                continue
            wheel, version, archive = matching[0]
            expected_version = runtime_versions.get(distribution)
            if version != expected_version:
                errors.append(
                    f"wheel version mismatch for {distribution}: "
                    f"{version!r}, runtime {expected_version!r}"
                )
            members = archive.namelist()
            for artifact in artifacts:
                basename = Path(str(artifact["path"])).name
                payloads = [name for name in members if Path(name).name == basename]
                if len(payloads) != 1:
                    errors.append(
                        f"wheel {wheel.name} contains {len(payloads)} payloads named {basename}"
                    )
                    continue
                actual_hash = hashlib.sha256(archive.read(payloads[0])).hexdigest()
                if actual_hash != artifact.get("sha256"):
                    errors.append(
                        f"wheel native payload hash mismatch: {wheel.name}:{payloads[0]}"
                    )
        for _distribution, matching in wheels.items():
            for wheel, _, archive in matching:
                metadata_names = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                ]
                if len(metadata_names) != 1:
                    continue
                metadata = archive.read(metadata_names[0]).decode(
                    "utf-8", errors="replace"
                )
                requirements = [
                    line.split(":", 1)[1].strip()
                    for line in metadata.splitlines()
                    if line.startswith("Requires-Dist:")
                ]
                for requirement in requirements:
                    match = re.match(r"([A-Za-z0-9_.-]+)", requirement)
                    if (
                        match is not None
                        and _normalized_distribution_name(match.group(1))
                        == "termin-app"
                    ):
                        errors.append(f"wheel {wheel.name} depends on termin-app")
                        break
    finally:
        for matching in wheels.values():
            for _, _, archive in matching:
                archive.close()
    if errors:
        for error in errors[:50]:
            print(f"  {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} wheelhouse provenance error(s)", file=sys.stderr)
        return 1
    subset_names = ("tcbase", "tgfx", "termin-display", "termin-gui-native")
    if not set(subset_names) <= runtime_versions.keys():
        print(
            f"  OK: {len(artifacts_by_distribution)} native wheel versions and "
            "payloads verified"
        )
        return 0
    for name in subset_names:
        matching = wheels.get(name, [])
        if len(matching) != 1:
            print(
                f"FAILED: library subset requires one {name} wheel, found {len(matching)}",
                file=sys.stderr,
            )
            return 1
    print(
        f"  OK: {len(artifacts_by_distribution)} native wheel versions, payloads and "
        "editor-free library subset metadata verified"
    )
    return 0
