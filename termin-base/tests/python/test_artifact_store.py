from pathlib import Path

import pytest

from termin.artifacts import (
    ArtifactStore,
    clear_artifact_store,
    current_artifact_store,
    get_artifact_store,
    set_artifact_store,
)


def test_artifact_store_roundtrip(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    store.write_scene_artifact(
        scene_name="main",
        entity_uuid="entity-1",
        component_type="NavMeshBuilderComponent",
        artifact_name="navmesh_Human",
        data=b"artifact-data",
    )

    assert (
        tmp_path
        / ".termin"
        / "artifacts"
        / "main"
        / "entity-1"
        / "NavMeshBuilderComponent"
        / "navmesh_Human"
    ).read_bytes() == b"artifact-data"
    assert store.read_scene_artifact(
        scene_name="main",
        entity_uuid="entity-1",
        component_type="NavMeshBuilderComponent",
        artifact_name="navmesh_Human",
    ) == b"artifact-data"


def test_artifact_store_rejects_nested_segments(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError):
        store.scene_artifact_path(
            scene_name="main",
            entity_uuid="entity-1",
            component_type="NavMeshBuilderComponent",
            artifact_name="../navmesh",
        )


def test_artifact_store_global_instance(tmp_path: Path) -> None:
    clear_artifact_store()
    with pytest.raises(RuntimeError):
        get_artifact_store()

    store = ArtifactStore(tmp_path)
    set_artifact_store(store)
    assert current_artifact_store() is store
    assert get_artifact_store() is store

    clear_artifact_store()
    assert current_artifact_store() is None
