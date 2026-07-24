"""Strict resolution for Termin build and installed SDK artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .python_abi import PythonAbiError, PythonAbiIdentity


SCHEMA_VERSION = 3
SDK_MANIFEST_KIND = "termin-sdk-artifacts"
BUILD_MANIFEST_KIND = "termin-build-artifacts"
SDK_MANIFEST_NAME = "termin-artifacts.json"
BUILD_MANIFEST_NAME = "termin-build-artifacts.json"
BUILD_ID_LENGTH = 20


class ArtifactManifestError(RuntimeError):
    """Raised when an artifact manifest or its payload violates the contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_native_build_id(
    artifacts: list[dict[str, Any]],
    python_abi: PythonAbiIdentity,
) -> str:
    """Return a stable identity for native payloads and bundled dependencies."""
    payloads: set[tuple[str, str]] = set()
    for entry in artifacts:
        extension = entry.get("extension")
        digest = entry.get("sha256")
        if isinstance(extension, str) and isinstance(digest, str):
            payloads.add((f"extension:{extension}", digest))
        dependencies = entry.get("runtime_dependencies", [])
        if not isinstance(dependencies, list):
            continue
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue
            path = dependency.get("path")
            dependency_digest = dependency.get("sha256")
            if isinstance(path, str) and isinstance(dependency_digest, str):
                payloads.add((f"runtime:{path}", dependency_digest))
    digest = hashlib.sha256()
    digest.update(b"python-abi\0")
    digest.update(python_abi.canonical_json().encode("utf-8"))
    digest.update(b"\0")
    for identity, payload_hash in sorted(payloads):
        digest.update(identity.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()[:BUILD_ID_LENGTH]


@dataclass(frozen=True)
class ResolvedRuntimeDependency:
    name: str
    path: Path


@dataclass(frozen=True)
class ResolvedArtifact:
    extension: str
    target: str
    path: Path
    runtime_dependencies: tuple[ResolvedRuntimeDependency, ...]
    metadata: dict[str, Any]


class ArtifactManifest:
    def __init__(self, path: Path, data: dict[str, Any]) -> None:
        self.path = path.resolve()
        self.root = self.path.parent
        self.data = data
        self.kind = str(data.get("manifest_kind", ""))
        if data.get("schema") != SCHEMA_VERSION:
            raise ArtifactManifestError(
                f"unsupported artifact manifest schema in {self.path}: "
                f"expected {SCHEMA_VERSION}, got {data.get('schema')!r}"
            )
        if self.kind not in {SDK_MANIFEST_KIND, BUILD_MANIFEST_KIND}:
            raise ArtifactManifestError(
                f"invalid manifest_kind in {self.path}: {self.kind!r}"
            )
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, list):
            raise ArtifactManifestError(
                f"artifact manifest {self.path} must contain an artifacts list"
            )
        self._artifacts = artifacts
        try:
            self.python_abi = PythonAbiIdentity.from_mapping(
                data.get("python_abi"),
                context=f"artifact manifest {self.path} Python ABI",
            )
        except PythonAbiError as error:
            raise ArtifactManifestError(str(error)) from error
        self.native_build_id = str(data.get("native_build_id", ""))
        expected_build_id = compute_native_build_id(artifacts, self.python_abi)
        if self.native_build_id != expected_build_id:
            raise ArtifactManifestError(
                f"native_build_id mismatch in {self.path}: "
                f"expected {expected_build_id}, got {self.native_build_id!r}"
            )

    @classmethod
    def load(cls, path: Path) -> "ArtifactManifest":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactManifestError(
                f"cannot read Termin artifact manifest {path}: {error}"
            ) from error
        if not isinstance(data, dict):
            raise ArtifactManifestError(
                f"artifact manifest {path} must contain a JSON object"
            )
        return cls(path, data)

    def _resolve_path(self, raw_path: object, *, context: str) -> Path:
        if not isinstance(raw_path, str) or not raw_path:
            raise ArtifactManifestError(f"{context} has no artifact path")
        path = Path(raw_path)
        if self.kind == SDK_MANIFEST_KIND:
            if path.is_absolute() or ".." in path.parts:
                raise ArtifactManifestError(
                    f"{context} escapes SDK root with path {raw_path!r}"
                )
            resolved = (self.root / path).resolve()
            try:
                resolved.relative_to(self.root)
            except ValueError as error:
                raise ArtifactManifestError(
                    f"{context} resolves outside SDK root: {resolved}"
                ) from error
            return resolved
        if not path.is_absolute():
            raise ArtifactManifestError(
                f"{context} in an explicit build manifest must use an absolute path"
            )
        return path.resolve()

    @staticmethod
    def _verify_file(path: Path, expected_hash: object, *, context: str) -> None:
        if not path.is_file():
            raise ArtifactManifestError(f"{context} is missing: {path}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ArtifactManifestError(f"{context} has an invalid sha256 value")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise ArtifactManifestError(
                f"{context} hash mismatch for {path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    def has_extension(self, extension: str) -> bool:
        return any(entry.get("extension") == extension for entry in self._artifacts)

    def require_kind(self, expected_kind: str) -> None:
        if self.kind != expected_kind:
            raise ArtifactManifestError(
                f"artifact manifest {self.path} has kind {self.kind!r}, "
                f"expected {expected_kind!r}"
            )

    def validate_all(
        self,
        *,
        expected_python_abi: PythonAbiIdentity | None = None,
    ) -> None:
        extensions = []
        for entry in self._artifacts:
            extension = entry.get("extension")
            if not isinstance(extension, str) or not extension:
                raise ArtifactManifestError(
                    f"artifact manifest {self.path} contains an entry without an extension"
                )
            extensions.append(extension)
        for extension in extensions:
            self.resolve_extension(
                extension,
                expected_python_abi=expected_python_abi,
            )

    def resolve_extension(
        self,
        extension: str,
        *,
        expected_target: str | None = None,
        expected_python_abi: PythonAbiIdentity | None = None,
    ) -> ResolvedArtifact:
        matches = [
            entry for entry in self._artifacts if entry.get("extension") == extension
        ]
        if not matches:
            raise ArtifactManifestError(
                f"artifact manifest {self.path} has no entry for {extension}"
            )
        if len(matches) != 1:
            raise ArtifactManifestError(
                f"artifact manifest {self.path} has duplicate entries for {extension}"
            )
        entry = matches[0]
        context = f"artifact {extension} in {self.path}"
        if entry.get("kind") != "python-extension":
            raise ArtifactManifestError(
                f"{context} has kind {entry.get('kind')!r}, expected 'python-extension'"
            )
        target = entry.get("target")
        if not isinstance(target, str) or not target:
            raise ArtifactManifestError(f"{context} has no target")
        if expected_target is not None and target != expected_target:
            raise ArtifactManifestError(
                f"{context} target mismatch: expected {expected_target!r}, got {target!r}"
            )
        expected_abi = expected_python_abi or PythonAbiIdentity.current()
        if self.python_abi != expected_abi:
            raise ArtifactManifestError(
                f"{context} Python ABI mismatch: expected "
                f"{expected_abi.canonical_json()}, got "
                f"{self.python_abi.canonical_json()}"
            )
        path = self._resolve_path(entry.get("path"), context=context)
        self._verify_file(path, entry.get("sha256"), context=context)

        dependencies = []
        raw_dependencies = entry.get("runtime_dependencies", [])
        if not isinstance(raw_dependencies, list):
            raise ArtifactManifestError(
                f"{context} runtime_dependencies must be a list"
            )
        for dependency in raw_dependencies:
            if not isinstance(dependency, dict):
                raise ArtifactManifestError(
                    f"{context} contains an invalid runtime dependency"
                )
            name = dependency.get("name")
            if not isinstance(name, str) or not name:
                raise ArtifactManifestError(
                    f"{context} contains a runtime dependency without a name"
                )
            dependency_context = f"runtime dependency {name} for {extension}"
            dependency_path = self._resolve_path(
                dependency.get("path"), context=dependency_context
            )
            self._verify_file(
                dependency_path,
                dependency.get("sha256"),
                context=dependency_context,
            )
            dependencies.append(ResolvedRuntimeDependency(name, dependency_path))
        return ResolvedArtifact(
            extension=extension,
            target=target,
            path=path,
            runtime_dependencies=tuple(dependencies),
            metadata=entry,
        )


def selected_manifest_path() -> Path | None:
    explicit = os.environ.get("TERMIN_ARTIFACT_MANIFEST")
    if explicit:
        return Path(explicit)
    sdk = os.environ.get("TERMIN_SDK")
    if sdk:
        return Path(sdk) / SDK_MANIFEST_NAME
    return None


def load_selected_manifest(*, required: bool = True) -> ArtifactManifest | None:
    path = selected_manifest_path()
    if path is None:
        if not required:
            return None
        raise ArtifactManifestError(
            "no Termin artifact manifest selected; set TERMIN_SDK to an installed "
            "SDK root or TERMIN_ARTIFACT_MANIFEST to an explicit build manifest"
        )
    if not path.is_file():
        raise ArtifactManifestError(f"selected Termin artifact manifest is missing: {path}")
    return ArtifactManifest.load(path)
