"""Strict validation for wheelhouses consumed by an isolated Python runtime."""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from itertools import product
from pathlib import Path

from .python_abi import PythonAbiIdentity


_DISTRIBUTION_NORMALIZE_RE = re.compile(r"[-_.]+")


class WheelhouseError(RuntimeError):
    """The wheelhouse cannot exactly satisfy its lock for the target runtime."""


@dataclass(frozen=True)
class WheelArtifact:
    path: Path
    name: str
    version: str
    tags: frozenset[str]
    abi_tags: frozenset[str]


def _normalized_distribution_name(name: str) -> str:
    return _DISTRIBUTION_NORMALIZE_RE.sub("-", name).lower()


def _wheel_metadata_file(
    archive: zipfile.ZipFile,
    suffix: str,
    *,
    wheel_name: str,
) -> str:
    matching = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(matching) != 1:
        raise WheelhouseError(
            f"wheel has {len(matching)} {suffix.rsplit('/', 1)[-1]} files: "
            f"{wheel_name}"
        )
    return matching[0]


def inspect_wheel(path: Path) -> WheelArtifact:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_name = _wheel_metadata_file(
                archive,
                ".dist-info/METADATA",
                wheel_name=path.name,
            )
            wheel_metadata_name = _wheel_metadata_file(
                archive,
                ".dist-info/WHEEL",
                wheel_name=path.name,
            )
            metadata = archive.read(metadata_name).decode("utf-8", errors="replace")
            wheel_metadata = archive.read(wheel_metadata_name).decode(
                "utf-8",
                errors="replace",
            )
    except (OSError, zipfile.BadZipFile) as error:
        raise WheelhouseError(f"cannot read wheel {path.name}: {error}") from error

    fields: dict[str, str] = {}
    for line in metadata.splitlines():
        if line.startswith(("Name:", "Version:")):
            key, value = line.split(":", 1)
            fields[key.lower()] = value.strip()
    if not fields.get("name") or not fields.get("version"):
        raise WheelhouseError(f"wheel metadata has no Name/Version: {path.name}")

    tags: set[str] = set()
    abi_tags: set[str] = set()
    for line in wheel_metadata.splitlines():
        if not line.startswith("Tag:"):
            continue
        compressed = line.split(":", 1)[1].strip()
        parts = compressed.rsplit("-", 2)
        if len(parts) != 3:
            raise WheelhouseError(f"wheel has malformed Tag {compressed!r}: {path.name}")
        interpreters, abis, platforms = (part.split(".") for part in parts)
        abi_tags.update(abis)
        tags.update(
            f"{interpreter}-{abi}-{platform}"
            for interpreter, abi, platform in product(
                interpreters,
                abis,
                platforms,
            )
        )
    if not tags:
        raise WheelhouseError(f"wheel metadata has no Tag fields: {path.name}")

    return WheelArtifact(
        path=path,
        name=fields["name"],
        version=fields["version"],
        tags=frozenset(tags),
        abi_tags=frozenset(abi_tags),
    )


def supported_wheel_tags(python: Path) -> frozenset[str]:
    script = (
        "import json; "
        "from packaging.tags import sys_tags; "
        "print(json.dumps([str(tag) for tag in sys_tags()]))"
    )
    result = subprocess.run(
        [str(python), "-I", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise WheelhouseError(
            f"cannot query supported wheel tags from {python}: {detail}"
        )
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise WheelhouseError(
            f"target Python returned invalid supported-tags JSON: {error}"
        ) from error
    if not isinstance(values, list) or not values or not all(
        isinstance(value, str) and value for value in values
    ):
        raise WheelhouseError("target Python returned an empty or invalid supported-tags set")
    return frozenset(values)


def require_wheel_python_abi(
    abi_tags: set[str] | frozenset[str],
    python_abi: PythonAbiIdentity,
    *,
    wheel_name: str,
) -> None:
    native_abi_tags = set(abi_tags) - {"none"}
    expected_abi_tag = python_abi.wheel_abi_tag
    if native_abi_tags and expected_abi_tag not in native_abi_tags:
        rendered = ", ".join(sorted(native_abi_tags))
        raise WheelhouseError(
            f"wheel {wheel_name} Python ABI mismatch: expected "
            f"{expected_abi_tag}, got {rendered}"
        )


def validate_locked_wheelhouse(
    wheel_dir: Path,
    locked_requirements: dict[str, tuple[str, str]],
    *,
    python_abi: PythonAbiIdentity,
    supported_tags: set[str] | frozenset[str],
) -> None:
    if not wheel_dir.is_dir():
        raise WheelhouseError(f"wheelhouse directory is missing: {wheel_dir}")

    artifacts: dict[str, list[WheelArtifact]] = {}
    errors: list[str] = []
    wheel_paths = sorted(wheel_dir.glob("*.whl"))
    if not wheel_paths:
        raise WheelhouseError(f"wheelhouse contains no wheels: {wheel_dir}")
    for wheel_path in wheel_paths:
        try:
            artifact = inspect_wheel(wheel_path)
            require_wheel_python_abi(
                artifact.abi_tags,
                python_abi,
                wheel_name=wheel_path.name,
            )
            if artifact.tags.isdisjoint(supported_tags):
                raise WheelhouseError(
                    f"wheel {wheel_path.name} has no tag supported by target "
                    f"{python_abi.wheel_abi_tag}"
                )
            normalized = _normalized_distribution_name(artifact.name)
            artifacts.setdefault(normalized, []).append(artifact)
        except WheelhouseError as error:
            errors.append(str(error))

    for normalized, (locked_name, locked_version) in locked_requirements.items():
        matching = [
            artifact
            for artifact in artifacts.get(normalized, [])
            if artifact.version == locked_version
        ]
        if len(matching) != 1:
            available = ", ".join(
                f"{artifact.name}=={artifact.version} ({artifact.path.name})"
                for artifact in artifacts.get(normalized, [])
            )
            errors.append(
                f"lock requires exactly one compatible {locked_name}=={locked_version} "
                f"wheel, found {len(matching)}"
                + (f"; available: {available}" if available else "")
            )

    for normalized, matching in artifacts.items():
        locked = locked_requirements.get(normalized)
        for artifact in matching:
            if locked is None or artifact.version != locked[1]:
                errors.append(
                    f"wheelhouse contains artifact outside the exact lock: "
                    f"{artifact.path.name}"
                )

    if errors:
        rendered = "\n".join(f"  - {error}" for error in errors)
        raise WheelhouseError(
            f"wheelhouse is incompatible with target {python_abi.wheel_abi_tag}:\n"
            f"{rendered}"
        )
