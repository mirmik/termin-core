"""Setuptools helpers backed by the Termin Python package manifest."""

from __future__ import annotations

import json
import os
from pathlib import Path

from setuptools import Extension

from .cmake_ext import _find_sdk, _sdk_python_artifact_roots
from .package_manifest import PackageEntry, load_manifest, repo_root_from

_CMAKE_CONFIG_DIRS = ("Release", "Debug", "RelWithDebInfo", "MinSizeRel")
_ARTIFACT_PATTERNS = (
    "{target}.*.so",
    "{target}.so",
    "{target}.*.pyd",
    "{target}.pyd",
    "{target}.*.dylib",
    "{target}.dylib",
)


def _entry_for_source(source_dir: Path) -> tuple[Path, PackageEntry]:
    source_dir = source_dir.resolve()
    repo_root = repo_root_from(source_dir)
    package_path = source_dir.relative_to(repo_root).as_posix()
    for package in load_manifest(repo_root):
        if package.path == package_path:
            return repo_root, package
    raise RuntimeError(
        f"Cannot find package manifest entry for {package_path}"
    )


def _artifact_manifest_has_extension(sdk: Path, extension_name: str) -> bool:
    manifest = sdk / "termin-artifacts.json"
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for artifact in data.get("artifacts", []):
        if artifact.get("extension") != extension_name:
            continue
        build_path = Path(str(artifact.get("build_path", "")))
        return build_path.is_file()
    return False


def _candidate_roots(repo_root: Path, source_dir: Path) -> list[Path]:
    roots = []
    bindings_dir = os.environ.get("TERMIN_BINDINGS_DIR")
    if bindings_dir:
        roots.append(Path(bindings_dir))
    for parent in (source_dir, *source_dir.parents):
        roots.append(parent / "build" / "Release" / "bin")
        roots.append(parent / "build" / "Debug" / "bin")
    roots.append(repo_root / "build" / "Release" / "bin")
    roots.append(repo_root / "build" / "Debug" / "bin")
    sdk = _find_sdk()
    if sdk is not None:
        roots.extend(_sdk_python_artifact_roots(sdk))
    unique = []
    seen = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _native_artifact_exists(
    repo_root: Path,
    source_dir: Path,
    extension_name: str,
    target: str,
) -> bool:
    sdk = _find_sdk()
    if sdk is not None and _artifact_manifest_has_extension(sdk, extension_name):
        return True

    package_path = extension_name.rsplit(".", 1)[0].replace(".", "/")
    for root in _candidate_roots(repo_root, source_dir):
        if not root.is_dir():
            continue
        search_roots = [root]
        for config in _CMAKE_CONFIG_DIRS:
            search_roots.append(root / config)
        for search_root in search_roots:
            if not search_root.is_dir():
                continue
            candidate_dirs = (search_root, search_root / package_path)
            for candidate_dir in candidate_dirs:
                if not candidate_dir.is_dir():
                    continue
                for pattern in _ARTIFACT_PATTERNS:
                    if list(candidate_dir.glob(pattern.format(target=target))):
                        return True
    return False


def native_extensions_for_source(source_dir: str | os.PathLike[str]) -> list[Extension]:
    """Create setuptools Extension objects from build-system/packages.json."""

    source_path = Path(source_dir)
    repo_root, package = _entry_for_source(source_path)
    extensions = []
    for native_extension in package.native_extensions:
        if native_extension.optional and not _native_artifact_exists(
            repo_root,
            source_path,
            native_extension.extension,
            native_extension.target,
        ):
            continue
        extensions.append(Extension(native_extension.extension, sources=[]))
    return extensions


def native_module_names_for_source(source_dir: str | os.PathLike[str]) -> list[str]:
    """Return binding module basenames for compatibility with old setup.py code."""

    source_path = Path(source_dir)
    _, package = _entry_for_source(source_path)
    return [
        native_extension.extension.rsplit(".", 1)[1]
        for native_extension in package.native_extensions
    ]
