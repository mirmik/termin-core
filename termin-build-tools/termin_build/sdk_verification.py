"""Final SDK runtime verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .sdk import RUNTIME_MANIFEST_NAME, RUNTIME_MANIFEST_SCHEMA, _python_version_and_paths
from .sdk_runtime_metadata import (
    _distribution_metadata_paths,
    _distribution_name_from_metadata_dir,
    _metadata_distribution_field,
    _normalized_distribution_name,
    _sha256_file,
    _verify_distribution_records,
)

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
    if Path(str(info.get("sdk_root", ""))).resolve() != expected_root:
        print("FAILED: SDK Python launcher reported the wrong SDK root", file=sys.stderr)
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
        "import pathlib, site, sys, tcbase, termin.tween; "
        f"root = pathlib.Path({str(expected_root)!r}); "
        "assert pathlib.Path(tcbase.__file__).resolve().is_relative_to(root); "
        "assert pathlib.Path(termin.tween.__file__).resolve().is_relative_to(root); "
        "assert site.ENABLE_USER_SITE is False; "
        "assert pathlib.Path(sys.prefix).resolve() == root"
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

