"""Generate and activate an explicit checkout overlay over installed SDK Python."""

from __future__ import annotations

import argparse
import hashlib
import importlib.abc
import importlib.metadata
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .package_manifest import load_manifest, repo_root_from


SCHEMA_VERSION = 1
_EXCLUDED_SOURCE_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "sdk",
    "tests",
}


class OverlayError(RuntimeError):
    """Raised when an overlay is stale, ambiguous, or malformed."""


def _normalized_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sdk_site_packages(sdk_root: Path) -> Path:
    windows = sdk_root / "python" / "Lib" / "site-packages"
    if windows.is_dir():
        return windows
    candidates = sorted((sdk_root / "lib").glob("python3.*/site-packages"))
    if len(candidates) != 1:
        raise OverlayError(
            f"expected one SDK site-packages directory under {sdk_root}, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sdk_fingerprint(sdk_root: Path) -> str:
    artifacts = sdk_root / "termin-artifacts.json"
    if not artifacts.is_file():
        raise OverlayError(f"SDK artifact manifest is missing: {artifacts}")
    return _sha256(artifacts)


def _source_python_files(package_root: Path) -> tuple[Path, ...]:
    result = []
    for current, directory_names, file_names in os.walk(package_root):
        directory_names[:] = [
            name
            for name in directory_names
            if name not in _EXCLUDED_SOURCE_DIRECTORIES and not name.endswith(".egg-info")
        ]
        current_path = Path(current)
        result.extend(current_path / name for name in file_names if name.endswith(".py"))
    return tuple(result)


def _ends_with_parts(path: Path, suffix: Path) -> bool:
    return len(path.parts) >= len(suffix.parts) and path.parts[-len(suffix.parts) :] == suffix.parts


def _find_source_file(
    package_root: Path,
    source_files: tuple[Path, ...],
    installed_relative: Path,
) -> Path | None:
    candidates = [
        path
        for path in source_files
        if _ends_with_parts(path.relative_to(package_root), installed_relative)
    ]
    if not candidates:
        return None
    if len(candidates) > 1:
        rendered = ", ".join(str(path) for path in sorted(candidates))
        raise OverlayError(
            f"ambiguous source mapping for {installed_relative}: {rendered}"
        )
    return candidates[0]


def _distribution_index(site_packages: Path) -> dict[str, importlib.metadata.Distribution]:
    result = {}
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        name = distribution.metadata.get("Name")
        if name:
            result[_normalized_distribution_name(name)] = distribution
    return result


def create_overlay_manifest(
    repo_root: Path,
    sdk_root: Path,
    output_path: Path,
    extra_sites: tuple[Path, ...] = (),
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    sdk_root = sdk_root.resolve()
    site_packages = _sdk_site_packages(sdk_root).resolve()
    distributions = _distribution_index(site_packages)
    mappings: dict[str, dict[str, str]] = {}

    for package in load_manifest(repo_root):
        distribution = distributions.get(_normalized_distribution_name(package.distribution))
        if distribution is None:
            raise OverlayError(
                f"SDK distribution is missing for overlay: {package.distribution}"
            )
        package_root = (repo_root / package.path).resolve()
        source_files = _source_python_files(package_root)
        for installed_file in distribution.files or ():
            relative = Path(str(installed_file))
            if (
                relative.suffix != ".py"
                or ".." in relative.parts
                or relative.parts[0].endswith(".dist-info")
            ):
                continue
            source_file = _find_source_file(package_root, source_files, relative)
            if source_file is None:
                continue
            if relative.name == "__init__.py":
                module = ".".join(relative.parent.parts)
                if not module or module == "termin":
                    continue
                entry = {
                    "kind": "package",
                    "source": str(source_file.parent),
                    "source_paths": [str(source_file.parent)],
                    "installed": str((site_packages / relative.parent).resolve()),
                }
            else:
                module = ".".join(relative.with_suffix("").parts)
                entry = {
                    "kind": "module",
                    "source": str(source_file),
                    "installed": str((site_packages / relative).resolve()),
                }
            previous = mappings.get(module)
            if previous is not None and previous != entry:
                if previous["kind"] != "package" or entry["kind"] != "package":
                    raise OverlayError(f"multiple source owners for Python module {module}")
                previous_paths = list(previous.get("source_paths", [previous["source"]]))
                entry["source_paths"] = list(
                    dict.fromkeys([entry["source"], *previous_paths])
                )
            mappings[module] = entry

    resolved_extra_sites = []
    for path in extra_sites:
        resolved = path.resolve()
        if not resolved.is_dir():
            raise OverlayError(f"overlay extra site is missing: {resolved}")
        resolved_extra_sites.append(str(resolved))

    manifest: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "repo_root": str(repo_root),
        "sdk_root": str(sdk_root),
        "sdk_fingerprint": _sdk_fingerprint(sdk_root),
        "python_abi": f"{sys.version_info.major}.{sys.version_info.minor}",
        "extra_sites": resolved_extra_sites,
        "mappings": dict(sorted(mappings.items())),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


@dataclass(frozen=True)
class _Mapping:
    kind: str
    source: Path
    installed: Path
    source_paths: tuple[Path, ...] = ()


class _OverlayFinder(importlib.abc.MetaPathFinder):
    def __init__(self, mappings: dict[str, _Mapping]) -> None:
        self._mappings = mappings

    def find_spec(self, fullname: str, path=None, target=None):
        del path, target
        mapping = self._mappings.get(fullname)
        if mapping is None:
            return None
        if mapping.kind == "package":
            source_paths = mapping.source_paths or (mapping.source,)
            return importlib.util.spec_from_file_location(
                fullname,
                mapping.source / "__init__.py",
                submodule_search_locations=[
                    str(mapping.installed),
                    *(str(source_path) for source_path in source_paths),
                ],
            )
        return importlib.util.spec_from_file_location(fullname, mapping.source)


def activate_overlay(manifest_path: str | Path) -> None:
    path = Path(manifest_path).resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OverlayError(f"failed to read Python overlay manifest {path}: {error}") from error
    if raw.get("schema") != SCHEMA_VERSION:
        raise OverlayError(f"unsupported Python overlay schema in {path}")

    sdk_root = Path(str(raw.get("sdk_root", ""))).resolve()
    if os.environ.get("TERMIN_SDK") != str(sdk_root):
        raise OverlayError(
            f"Python overlay expects TERMIN_SDK={sdk_root}, "
            f"got {os.environ.get('TERMIN_SDK')!r}"
        )
    expected_abi = str(raw.get("python_abi", ""))
    actual_abi = f"{sys.version_info.major}.{sys.version_info.minor}"
    if expected_abi != actual_abi:
        raise OverlayError(
            f"Python overlay ABI mismatch: expected {expected_abi}, running {actual_abi}"
        )
    if raw.get("sdk_fingerprint") != _sdk_fingerprint(sdk_root):
        raise OverlayError(
            "Python overlay is stale for the current SDK; regenerate the test environment"
        )

    raw_mappings = raw.get("mappings")
    if not isinstance(raw_mappings, dict):
        raise OverlayError(f"Python overlay mappings must be an object: {path}")
    mappings = {}
    for module, entry in raw_mappings.items():
        if not isinstance(module, str) or not isinstance(entry, dict):
            raise OverlayError(f"invalid Python overlay mapping in {path}")
        kind = entry.get("kind")
        if kind not in {"package", "module"}:
            raise OverlayError(f"invalid overlay mapping kind for {module}: {kind!r}")
        source = Path(str(entry.get("source", ""))).resolve()
        installed = Path(str(entry.get("installed", ""))).resolve()
        raw_source_paths = entry.get("source_paths", [str(source)])
        if not isinstance(raw_source_paths, list):
            raise OverlayError(f"overlay source_paths must be a list for {module}")
        source_paths = tuple(Path(str(item)).resolve() for item in raw_source_paths)
        source_probe = source / "__init__.py" if kind == "package" else source
        if (
            not source_probe.is_file()
            or (
                kind == "package"
                and (
                    not installed.is_dir()
                    or any(not path.is_dir() for path in source_paths)
                )
            )
        ):
            raise OverlayError(f"overlay mapping path is missing for {module}")
        mappings[module] = _Mapping(
            kind=kind,
            source=source,
            installed=installed,
            source_paths=source_paths,
        )

    extra_sites = raw.get("extra_sites", [])
    if not isinstance(extra_sites, list):
        raise OverlayError(f"Python overlay extra_sites must be a list: {path}")
    for extra_site in reversed(extra_sites):
        resolved = Path(str(extra_site)).resolve()
        if not resolved.is_dir():
            raise OverlayError(f"overlay extra site is missing: {resolved}")
        sys.path.insert(0, str(resolved))

    sys.meta_path.insert(0, _OverlayFinder(mappings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extra-site", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from(Path.cwd())
    manifest = create_overlay_manifest(
        repo_root,
        args.sdk_root,
        args.output,
        tuple(args.extra_site),
    )
    print(
        f"Wrote Python overlay with {len(manifest['mappings'])} mappings: "
        f"{args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
