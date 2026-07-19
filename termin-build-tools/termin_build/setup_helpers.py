"""Setuptools helpers backed by the Termin Python package manifest."""

from __future__ import annotations

import os
from pathlib import Path

from setuptools import Extension

from .artifact_manifest import load_selected_manifest
from .package_manifest import PackageEntry, load_manifest, repo_root_from


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


def _native_artifact_exists(
    extension_name: str,
    target: str,
) -> bool:
    manifest = load_selected_manifest(required=False)
    if manifest is None or not manifest.has_extension(extension_name):
        return False
    manifest.resolve_extension(extension_name, expected_target=target)
    return True


def native_extensions_for_source(source_dir: str | os.PathLike[str]) -> list[Extension]:
    """Create setuptools Extension objects from build-system/packages.json."""

    source_path = Path(source_dir)
    repo_root, package = _entry_for_source(source_path)
    extensions = []
    for native_extension in package.native_extensions:
        if native_extension.optional and not _native_artifact_exists(
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
