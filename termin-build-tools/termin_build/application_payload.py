"""Manifest-driven installation of application-owned Python payloads."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .artifact_manifest import sha256_file
from .package_manifest import NativeExtension


SOURCE_MANIFEST = Path("build-system/application-python-payloads.json")
INSTALLED_MANIFEST_NAME = "application-python-payloads.json"
SOURCE_SCHEMA = 1
INSTALLED_SCHEMA = 1

_IGNORED_DIRECTORY_NAMES = {"__pycache__"}
_IGNORED_FILE_SUFFIXES = {".pyc", ".pyo", ".so", ".pyd", ".dylib", ".dll"}


@dataclass(frozen=True)
class ApplicationPayload:
    name: str
    source_root: str
    destination_root: str
    paths: tuple[str, ...]
    native_extensions: tuple[NativeExtension, ...]
    imports: tuple[str, ...]
    executables: tuple[str, ...]


def _safe_relative_path(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{context} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"{context} escapes its declared root: {value!r}")
    return path.as_posix()


def _string_tuple(value: object, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise RuntimeError(f"{context} must be a list of non-empty strings")
    return tuple(value)


def load_application_payloads(repo_root: Path) -> tuple[ApplicationPayload, ...]:
    manifest_path = repo_root / SOURCE_MANIFEST
    if not manifest_path.is_file():
        return ()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read application payload manifest: {error}") from error
    if not isinstance(data, dict) or data.get("schema") != SOURCE_SCHEMA:
        raise RuntimeError(f"unsupported application payload manifest: {manifest_path}")
    raw_payloads = data.get("payloads")
    if not isinstance(raw_payloads, list):
        raise RuntimeError(f"{manifest_path}: payloads must be a list")

    payloads = []
    names = set()
    for index, raw in enumerate(raw_payloads):
        context = f"{manifest_path}: payloads[{index}]"
        if not isinstance(raw, dict):
            raise RuntimeError(f"{context} must be an object")
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"{context}.name must be a non-empty string")
        if name in names:
            raise RuntimeError(f"{context}: duplicate payload name {name!r}")
        names.add(name)
        source_root = _safe_relative_path(
            raw.get("source_root"), context=f"{context}.source_root"
        )
        destination_root = _safe_relative_path(
            raw.get("destination_root"), context=f"{context}.destination_root"
        )
        paths = tuple(
            _safe_relative_path(item, context=f"{context}.paths")
            for item in _string_tuple(raw.get("paths"), context=f"{context}.paths")
        )
        if len(set(paths)) != len(paths):
            raise RuntimeError(f"{context}.paths contains duplicates")

        raw_extensions = raw.get("native_extensions", [])
        if not isinstance(raw_extensions, list):
            raise RuntimeError(f"{context}.native_extensions must be a list")
        native_extensions = []
        for extension_index, raw_extension in enumerate(raw_extensions):
            extension_context = (
                f"{context}.native_extensions[{extension_index}]"
            )
            if not isinstance(raw_extension, dict):
                raise RuntimeError(f"{extension_context} must be an object")
            extension = raw_extension.get("extension")
            target = raw_extension.get("target")
            if not isinstance(extension, str) or not extension:
                raise RuntimeError(f"{extension_context}.extension is required")
            if not isinstance(target, str) or not target:
                raise RuntimeError(f"{extension_context}.target is required")
            native_extensions.append(
                NativeExtension(
                    extension=extension,
                    target=target,
                    optional=bool(raw_extension.get("optional", False)),
                    features=tuple(raw_extension.get("features", [])),
                )
            )

        payload = ApplicationPayload(
            name=name,
            source_root=source_root,
            destination_root=destination_root,
            paths=paths,
            native_extensions=tuple(native_extensions),
            imports=_string_tuple(raw.get("imports", []), context=f"{context}.imports"),
            executables=_string_tuple(
                raw.get("executables", []), context=f"{context}.executables"
            ),
        )
        source_root_path = repo_root / payload.source_root
        if not source_root_path.is_dir():
            raise RuntimeError(
                f"application payload source root is missing: {source_root_path}"
            )
        for relative in payload.paths:
            if not (source_root_path / relative).exists():
                raise RuntimeError(
                    f"application payload source is missing: "
                    f"{source_root_path / relative}"
                )
        payloads.append(payload)
    return tuple(payloads)


def _iter_payload_files(source: Path) -> Iterable[tuple[Path, Path]]:
    if source.is_file():
        yield source, Path(source.name)
        return
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in _IGNORED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if not path.is_file() or path.suffix.lower() in _IGNORED_FILE_SUFFIXES:
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        yield path, relative


def _copy_payload_file(source: Path, destination: Path) -> None:
    if destination.exists():
        raise RuntimeError(
            f"application payload collides with an installed library file: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def install_application_payloads(
    repo_root: Path,
    sdk_prefix: Path,
    site_packages: Path,
    resolve_native_artifact: Callable[[str], Path | None],
) -> Path:
    records: list[dict[str, object]] = []
    installed_payloads = []
    sdk_root = sdk_prefix.resolve()
    site_root = site_packages.resolve()
    for payload in load_application_payloads(repo_root):
        source_root = (repo_root / payload.source_root).resolve()
        destination_root = site_root / payload.destination_root
        for declared_path in payload.paths:
            declared_source = source_root / declared_path
            declared_destination = destination_root / declared_path
            if declared_source.is_file():
                files = ((declared_source, Path(declared_source.name)),)
                target_root = declared_destination.parent
            else:
                files = _iter_payload_files(declared_source)
                target_root = declared_destination
            for source, relative in files:
                destination = target_root / relative
                _copy_payload_file(source, destination)
                records.append(
                    {
                        "kind": "source",
                        "payload": payload.name,
                        "path": destination.relative_to(sdk_root).as_posix(),
                        "sha256": sha256_file(destination),
                    }
                )

        for extension in payload.native_extensions:
            artifact = resolve_native_artifact(extension.target)
            if artifact is None:
                if extension.optional:
                    continue
                raise RuntimeError(
                    f"application payload {payload.name} is missing native target "
                    f"{extension.target} for {extension.extension}"
                )
            package_path = Path(*extension.extension.rsplit(".", 1)[0].split("."))
            destination = site_root / package_path / artifact.name
            _copy_payload_file(artifact, destination)
            records.append(
                {
                    "kind": "native-extension",
                    "payload": payload.name,
                    "extension": extension.extension,
                    "target": extension.target,
                    "path": destination.relative_to(sdk_root).as_posix(),
                    "sha256": sha256_file(destination),
                }
            )

        installed_payloads.append(
            {
                "name": payload.name,
                "imports": list(payload.imports),
                "executables": list(payload.executables),
            }
        )

    manifest = {
        "schema": INSTALLED_SCHEMA,
        "site_packages": site_root.relative_to(sdk_root).as_posix(),
        "payloads": installed_payloads,
        "files": sorted(records, key=lambda record: str(record["path"])),
    }
    output = sdk_root / INSTALLED_MANIFEST_NAME
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote application Python payload manifest: {output}")
    return output
