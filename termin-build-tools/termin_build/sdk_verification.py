"""Final SDK layout, artifact, and bundled runtime verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from .artifact_manifest import (
    ArtifactManifest,
    ArtifactManifestError,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
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


def verify_sdk(sdk_prefix: Path, build_dir: Path) -> int:
    result = verify_no_duplicate_libraries(sdk_prefix)
    if result != 0:
        return result
    result = verify_sdk_artifacts(sdk_prefix, build_dir)
    if result != 0:
        return result
    result = verify_python_runtime_manifest(sdk_prefix)
    if result != 0:
        return result
    result = verify_python_wheelhouse(sdk_prefix)
    if result != 0:
        return result
    return verify_sdk_python_launcher(sdk_prefix)


def _python_version_and_paths(py_exec: str) -> dict[str, object]:
    script = (
        "import json, site, sys, sysconfig; "
        "print(json.dumps({'version': f'{sys.version_info.major}.{sys.version_info.minor}', "
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

    hostile_env = os.environ.copy()
    hostile_env.update(
        {
            "PYTHONHOME": str(sdk_prefix / "__invalid_python_home__"),
            "PYTHONPATH": str(sdk_prefix / "__invalid_python_path__"),
            "PYTHONUSERBASE": str(sdk_prefix / "__invalid_user_base__"),
            "PYTHONNOUSERSITE": "0",
        }
    )
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
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifact_manifest.require_kind(SDK_MANIFEST_KIND)
        artifact_manifest.validate_all()
    except ArtifactManifestError as error:
        print(f"FAILED: invalid SDK artifact manifest: {error}", file=sys.stderr)
        return 1
    if manifest.get("native_build_id") != artifact_manifest.native_build_id:
        print("FAILED: Python runtime native_build_id mismatch", file=sys.stderr)
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
        _normalized_distribution_name(str(entry.get("distribution", "")))
        for entry in artifact_manifest.data["artifacts"]
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


def verify_python_wheelhouse(sdk_prefix: Path) -> int:
    wheel_dir = sdk_prefix / "wheels"
    print("Verifying: SDK Python wheelhouse provenance")
    if not wheel_dir.is_dir():
        print("  SKIP: public SDK wheelhouse is not present")
        return 0
    try:
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        artifact_manifest.require_kind(SDK_MANIFEST_KIND)
        artifact_manifest.validate_all()
        runtime_manifest = json.loads(
            (sdk_prefix / RUNTIME_MANIFEST_NAME).read_text(encoding="utf-8")
        )
    except (ArtifactManifestError, OSError, json.JSONDecodeError) as error:
        print(f"FAILED: cannot verify SDK wheelhouse: {error}", file=sys.stderr)
        return 1

    runtime_versions = {
        _normalized_distribution_name(str(entry.get("name", ""))): entry.get("version")
        for entry in runtime_manifest.get("distributions", [])
        if isinstance(entry, dict)
    }
    artifacts_by_distribution: dict[str, list[dict[str, object]]] = {}
    for entry in artifact_manifest.data["artifacts"]:
        normalized = _normalized_distribution_name(str(entry.get("distribution", "")))
        artifacts_by_distribution.setdefault(normalized, []).append(entry)

    wheels: dict[str, list[tuple[Path, str, zipfile.ZipFile]]] = {}
    errors = []
    for wheel in sorted(wheel_dir.glob("*.whl")):
        try:
            name, version, archive = _wheel_metadata(wheel)
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            errors.append(str(error))
            continue
        normalized = _normalized_distribution_name(name)
        wheels.setdefault(normalized, []).append((wheel, version, archive))
    try:
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
    finally:
        for matching in wheels.values():
            for _, _, archive in matching:
                archive.close()
    if errors:
        for error in errors[:50]:
            print(f"  {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} wheelhouse provenance error(s)", file=sys.stderr)
        return 1
    print(
        f"  OK: {len(artifacts_by_distribution)} native wheel versions and payloads verified"
    )
    return 0
