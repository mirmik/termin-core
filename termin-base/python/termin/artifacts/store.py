from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath


DEFAULT_ARTIFACTS_DIR = ".termin/artifacts"
_log = logging.getLogger(__name__)


class ArtifactStore:
    """Filesystem storage for generated project artifacts.

    The store is intentionally ignorant of scene/component classes. Callers
    pass stable scene/entity/component identifiers and own the artifact bytes.
    """

    def __init__(
        self,
        project_root: str | Path,
        artifacts_dir: str | Path = DEFAULT_ARTIFACTS_DIR,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        artifacts_path = Path(artifacts_dir)
        self.root = artifacts_path if artifacts_path.is_absolute() else self.project_root / artifacts_path

    def scene_artifact_path(
        self,
        *,
        scene_name: str,
        entity_uuid: str,
        component_type: str,
        artifact_name: str,
    ) -> Path:
        scene_segment = _path_segment(scene_name, field_name="scene_name")
        entity_segment = _path_segment(entity_uuid, field_name="entity_uuid")
        component_segment = _path_segment(component_type, field_name="component_type")
        artifact_segment = _path_segment(artifact_name, field_name="artifact_name")
        return self.root / scene_segment / entity_segment / component_segment / artifact_segment

    def read_scene_artifact(
        self,
        *,
        scene_name: str,
        entity_uuid: str,
        component_type: str,
        artifact_name: str,
    ) -> bytes | None:
        path = self.scene_artifact_path(
            scene_name=scene_name,
            entity_uuid=entity_uuid,
            component_type=component_type,
            artifact_name=artifact_name,
        )
        if not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception as exc:
            _log.error("[ArtifactStore] failed to read %s: %s", path, exc)
            return None

    def write_scene_artifact(
        self,
        *,
        scene_name: str,
        entity_uuid: str,
        component_type: str,
        artifact_name: str,
        data: bytes,
    ) -> None:
        path = self.scene_artifact_path(
            scene_name=scene_name,
            entity_uuid=entity_uuid,
            component_type=component_type,
            artifact_name=artifact_name,
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except Exception as exc:
            _log.error("[ArtifactStore] failed to write %s: %s", path, exc)
            raise

    def delete_scene_artifact(
        self,
        *,
        scene_name: str,
        entity_uuid: str,
        component_type: str,
        artifact_name: str,
    ) -> None:
        path = self.scene_artifact_path(
            scene_name=scene_name,
            entity_uuid=entity_uuid,
            component_type=component_type,
            artifact_name=artifact_name,
        )
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            _log.error("[ArtifactStore] failed to delete %s: %s", path, exc)
            raise


_current_artifact_store: ArtifactStore | None = None


def set_artifact_store(store: ArtifactStore | None) -> None:
    global _current_artifact_store
    _current_artifact_store = store


def clear_artifact_store() -> None:
    set_artifact_store(None)


def current_artifact_store() -> ArtifactStore | None:
    return _current_artifact_store


def get_artifact_store() -> ArtifactStore:
    if _current_artifact_store is None:
        _log.error("[ArtifactStore] no active artifact store is configured")
        raise RuntimeError("No active artifact store is configured")
    return _current_artifact_store


def _path_segment(value: str, *, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip().replace("\\", "/")
    posix = PurePosixPath(normalized)
    if (
        normalized == ""
        or posix.is_absolute()
        or normalized == "."
        or ".." in posix.parts
        or len(posix.parts) != 1
    ):
        raise ValueError(f"Invalid artifact path segment for {field_name}: {value!r}")
    return normalized
