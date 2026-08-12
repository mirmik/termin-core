import sys
from pathlib import Path

import pytest

from termin.mcp.session import (
    canonical_sdk_root,
    new_sdk_session_file,
    sdk_session_registry_dir,
)


def test_registry_is_stable_per_canonical_sdk_root(tmp_path: Path):
    sdk_root = tmp_path / "checkout" / "sdk"

    first = sdk_session_registry_dir("editor", sdk_root=sdk_root, temp_dir=tmp_path)
    second = sdk_session_registry_dir("editor", sdk_root=sdk_root / ".", temp_dir=tmp_path)

    assert first == second
    assert first.parent.name.startswith("termin-editor-mcp-")
    assert first.name == "sessions"


def test_runtime_consumers_and_sdk_installations_have_independent_registries(tmp_path: Path):
    editor = sdk_session_registry_dir("editor", sdk_root=tmp_path / "sdk", temp_dir=tmp_path)
    player = sdk_session_registry_dir("player", sdk_root=tmp_path / "sdk", temp_dir=tmp_path)
    other_sdk = sdk_session_registry_dir(
        "editor",
        sdk_root=tmp_path / "other-sdk",
        temp_dir=tmp_path,
    )

    assert len({editor, player, other_sdk}) == 3


def test_runtime_instances_get_independent_descriptor_paths(tmp_path: Path):
    first = new_sdk_session_file("editor", sdk_root=tmp_path / "sdk", temp_dir=tmp_path)
    second = new_sdk_session_file("editor", sdk_root=tmp_path / "sdk", temp_dir=tmp_path)
    named = new_sdk_session_file(
        "editor",
        sdk_root=tmp_path / "sdk",
        temp_dir=tmp_path,
        instance_id="known-instance",
    )

    assert first != second
    assert first.parent == second.parent == named.parent
    assert first.suffix == second.suffix == ".json"
    assert named.name == "known-instance.json"


@pytest.mark.parametrize("runtime_name", ["", ".", "..", "../editor", "editor/session"])
def test_registry_rejects_unsafe_runtime_names(tmp_path: Path, runtime_name: str):
    with pytest.raises(ValueError, match="runtime_name"):
        sdk_session_registry_dir(runtime_name, sdk_root=tmp_path / "sdk", temp_dir=tmp_path)


def test_canonical_sdk_root_resolves_symlinks(tmp_path: Path):
    sdk_root = tmp_path / "checkout" / "sdk"
    sdk_root.mkdir(parents=True)
    link = tmp_path / "sdk-link"
    try:
        link.symlink_to(sdk_root, target_is_directory=True)
    except OSError as error:
        if sys.platform == "win32" and error.winerror == 1314:
            pytest.skip("Windows symlink creation requires Developer Mode or privilege")
        raise

    assert canonical_sdk_root(link) == canonical_sdk_root(sdk_root)
