"""SDK Python runtime metadata and package cleanup."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from .package_manifest import load_manifest
from .sdk import (
    LEGACY_BUNDLED_RUNTIME_PACKAGES,
    RUNTIME_LOCK_RELATIVE,
    RUNTIME_MANIFEST_NAME,
    RUNTIME_MANIFEST_SCHEMA,
    _python_executable,
    _python_version_and_paths,
)

_DISTRIBUTION_NORMALIZE_RE = re.compile(r"[-_.]+")


def _normalized_distribution_name(name: str) -> str:
    return _DISTRIBUTION_NORMALIZE_RE.sub("-", name).lower()


def _metadata_distribution_name(metadata_path: Path) -> str | None:
    return _metadata_distribution_field(metadata_path, "name")


def _metadata_distribution_field(metadata_path: Path, field: str) -> str | None:
    for metadata_file_name in ("METADATA", "PKG-INFO"):
        metadata_file = metadata_path / metadata_file_name
        if not metadata_file.is_file():
            continue
        text = metadata_file.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.lower().startswith(field.lower() + ":"):
                value = line.split(":", 1)[1].strip()
                return value or None
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


_REQUIREMENT_NAME_RE = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9_.-]*)")
_EXACT_REQUIREMENT_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;]+)$"
)


def _load_runtime_lock(repo_root: Path) -> dict[str, tuple[str, str]]:
    lock_path = repo_root / RUNTIME_LOCK_RELATIVE
    if not lock_path.is_file():
        raise RuntimeError(f"SDK Python runtime lock is missing: {lock_path}")

    requirements: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        requirement = raw_line.split("#", 1)[0].strip()
        if not requirement:
            continue
        match = _EXACT_REQUIREMENT_RE.fullmatch(requirement)
        if match is None:
            raise RuntimeError(
                f"runtime lock entry must use an exact name==version pin at "
                f"{lock_path}:{line_number}: {requirement}"
            )
        name, version = match.groups()
        normalized = _normalized_distribution_name(name)
        if normalized in requirements:
            raise RuntimeError(f"duplicate runtime lock distribution: {name}")
        requirements[normalized] = (name, version)
    if not requirements:
        raise RuntimeError(f"SDK Python runtime lock is empty: {lock_path}")
    return requirements


def _requirement_distribution_names(requirements_path: Path) -> set[str]:
    names: set[str] = set()
    if not requirements_path.is_file():
        return names
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        requirement = line.split("#", 1)[0].strip()
        if not requirement or requirement.startswith(("-", ".")):
            continue
        match = _REQUIREMENT_NAME_RE.match(requirement)
        if match is not None:
            names.add(match.group(1))
    return names


def _distribution_metadata_paths(site_packages: Path) -> list[Path]:
    if not site_packages.is_dir():
        return []
    return sorted(
        child
        for child in site_packages.iterdir()
        if child.is_dir()
        and (child.name.endswith(".dist-info") or child.name.endswith(".egg-info"))
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_record_path(site_packages: Path, recorded: str) -> Path:
    parts = list(Path(recorded).parts)
    while parts and parts[0] == "..":
        parts.pop(0)
    return (site_packages.joinpath(*parts)).resolve()


def _verify_distribution_records(
    site_packages: Path,
    metadata_paths: list[Path],
) -> list[str]:
    expected_hashes: dict[tuple[Path, str], set[str]] = {}
    display_paths: dict[Path, str] = {}
    errors: list[str] = []
    resolved_site = site_packages.resolve()
    for metadata_path in metadata_paths:
        record_path = metadata_path / "RECORD"
        if not record_path.is_file():
            continue
        with record_path.open(newline="", encoding="utf-8") as record_file:
            for row in csv.reader(record_file):
                if not row or not row[0] or len(row) < 2 or not row[1]:
                    continue
                if row[0].endswith((".pyc", ".pyo")):
                    continue
                installed_path = _target_record_path(site_packages, row[0])
                if not installed_path.is_relative_to(resolved_site):
                    errors.append(f"RECORD path escapes site-packages: {row[0]}")
                    continue
                try:
                    algorithm, expected = row[1].split("=", 1)
                    hashlib.new(algorithm)
                except (ValueError, TypeError):
                    errors.append(f"unsupported RECORD hash: {row[1]}")
                    continue
                expected_hashes.setdefault((installed_path, algorithm), set()).add(expected)
                display_paths[installed_path] = installed_path.relative_to(resolved_site).as_posix()

    for (installed_path, algorithm), allowed_hashes in expected_hashes.items():
        display = display_paths[installed_path]
        if not installed_path.is_file():
            errors.append(f"recorded file is missing: {display}")
            continue
        digest = hashlib.new(algorithm)
        with installed_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")
        if actual not in allowed_hashes:
            errors.append(f"recorded file hash mismatch: {display}")
    return errors


def _runtime_distribution_entries(
    site_packages: Path,
    runtime_lock: dict[str, tuple[str, str]],
    local_names: set[str],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    allowed = set(runtime_lock) | local_names
    for metadata_path in _distribution_metadata_paths(site_packages):
        name = _distribution_name_from_metadata_dir(metadata_path)
        version = _metadata_distribution_field(metadata_path, "version")
        if name is None or version is None:
            raise RuntimeError(f"invalid distribution metadata: {metadata_path}")
        normalized = _normalized_distribution_name(name)
        if normalized in seen:
            raise RuntimeError(f"duplicate SDK Python distribution: {name}")
        if normalized not in allowed:
            raise RuntimeError(f"undeclared SDK Python distribution: {name}=={version}")
        if normalized in runtime_lock and runtime_lock[normalized][1] != version:
            raise RuntimeError(
                f"runtime distribution version mismatch: {name}=={version}, "
                f"locked {runtime_lock[normalized][1]}"
            )
        record_path = metadata_path / "RECORD"
        if not record_path.is_file():
            raise RuntimeError(f"SDK Python distribution has no RECORD: {name}")
        entries.append(
            {
                "name": name,
                "version": version,
                "kind": "runtime" if normalized in runtime_lock else "termin",
                "metadata": metadata_path.relative_to(site_packages).as_posix(),
                "record_sha256": _sha256_file(record_path),
            }
        )
        seen.add(normalized)
    missing = allowed - seen
    if missing:
        rendered = ", ".join(sorted(missing))
        raise RuntimeError(f"missing SDK Python distributions: {rendered}")
    return sorted(entries, key=lambda entry: _normalized_distribution_name(entry["name"]))


def write_python_runtime_manifest(
    repo_root: Path,
    sdk_prefix: Path,
    site_packages: Path,
) -> Path:
    runtime_lock = _load_runtime_lock(repo_root)
    local_names = {
        _normalized_distribution_name(package.distribution)
        for package in load_manifest(repo_root)
    }
    entries = _runtime_distribution_entries(site_packages, runtime_lock, local_names)
    lock_path = repo_root / RUNTIME_LOCK_RELATIVE
    installed_lock = sdk_prefix / "python-runtime-lock.txt"
    shutil.copy2(lock_path, installed_lock)
    python_info = _python_version_and_paths(_python_executable())
    manifest = {
        "schema": RUNTIME_MANIFEST_SCHEMA,
        "python_abi": str(python_info["version"]),
        "platform": sys.platform,
        "runtime_lock": installed_lock.relative_to(sdk_prefix).as_posix(),
        "runtime_lock_sha256": _sha256_file(installed_lock),
        "site_packages": site_packages.relative_to(sdk_prefix).as_posix(),
        "distributions": entries,
    }
    output = sdk_prefix / RUNTIME_MANIFEST_NAME
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote Python runtime manifest: {output}")
    return output


def _remove_metadata_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _remove_recorded_distribution_files(target_dir: Path, metadata_path: Path) -> None:
    record_path = metadata_path / "RECORD"
    if not record_path.is_file():
        return

    resolved_target = target_dir.resolve()
    with record_path.open(newline="", encoding="utf-8") as record_file:
        for row in csv.reader(record_file):
            if not row or not row[0]:
                continue
            installed_path = (target_dir / row[0]).resolve()
            if not installed_path.is_relative_to(resolved_target):
                continue
            if installed_path == metadata_path.resolve():
                continue
            if installed_path.is_file() or installed_path.is_symlink():
                installed_path.unlink()


def _clear_target_distribution_metadata(target_dir: Path, distribution_names: set[str]) -> None:
    if not target_dir.is_dir() or not distribution_names:
        return
    normalized_names = {
        _normalized_distribution_name(name)
        for name in distribution_names
    }
    removed = []
    for child in target_dir.iterdir():
        if not (child.name.endswith(".dist-info") or child.name.endswith(".egg-info")):
            continue
        distribution_name = _distribution_name_from_metadata_dir(child)
        if distribution_name is None:
            continue
        if _normalized_distribution_name(distribution_name) not in normalized_names:
            continue
        if child.name.endswith(".dist-info"):
            _remove_recorded_distribution_files(target_dir, child)
        _remove_metadata_path(child)
        removed.append(child.name)
    if removed:
        print(
            "Removed stale target package artifacts: "
            + ", ".join(sorted(removed))
        )


def _clear_legacy_bundled_runtime_packages(target_dir: Path) -> None:
    if not target_dir.is_dir():
        return
    removed = []
    _clear_target_distribution_metadata(
        target_dir,
        set(LEGACY_BUNDLED_RUNTIME_PACKAGES),
    )
    for package_names in LEGACY_BUNDLED_RUNTIME_PACKAGES.values():
        for package_name in package_names:
            path = target_dir / package_name
            if not path.exists():
                continue
            _remove_metadata_path(path)
            removed.append(path.name)
    if removed:
        print(
            "Removed legacy bundled runtime package artifacts: "
            + ", ".join(sorted(removed))
        )


def _clear_target_python_package_metadata(target_dir: Path, packages) -> None:
    package_names = {
        package.distribution
        for package in packages
    }
    _clear_target_distribution_metadata(target_dir, package_names)
