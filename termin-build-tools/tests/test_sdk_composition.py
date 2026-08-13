from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build.artifact_manifest import (
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
    SCHEMA_VERSION,
    compute_native_build_id,
)
from termin_build.python_abi import PythonAbiIdentity
from termin_build.sdk_composition import (
    SDK_COMPOSITION_NAME,
    SDK_INPUTS_NAME,
    compose_installed_sdk,
    load_installed_sdk_input,
    stage_installed_sdk_input,
)


def _write_core_sdk(root: Path, abi: PythonAbiIdentity) -> str:
    root.mkdir()
    (root / "sdk-product.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "profile_id": "core",
                "artifact_kind": "standalone",
                "embedded_python_hosts": [],
                "launcher_import_roots": [],
                "native_import_roots": [],
                "forbidden_artifact_markers": [],
            }
        ),
        encoding="utf-8",
    )
    build_id = compute_native_build_id([], abi)
    (root / SDK_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": SCHEMA_VERSION,
                "manifest_kind": SDK_MANIFEST_KIND,
                "python_abi": abi.to_dict(),
                "native_build_id": build_id,
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    (root / "python-runtime-manifest.json").write_text(
        json.dumps(
            {
                "native_build_id": build_id,
                "distributions": [
                    {"name": "packaging", "kind": "runtime"},
                    {"name": "tcbase", "kind": "termin"},
                ],
            }
        ),
        encoding="utf-8",
    )
    for relative in (
        "wheels",
        "lib/cmake/termin_base",
        "lib/cmake/termin_dispatch",
        "lib/cmake/termin_inspect",
        "lib/cmake/termin_python_host",
        "lib/cmake/nanobind",
    ):
        (root / relative).mkdir(parents=True)
    (root / "include" / "core-owned.h").parent.mkdir()
    (root / "include" / "core-owned.h").write_text("core\n", encoding="utf-8")
    return build_id


def _write_layer_sdk(
    root: Path, abi: PythonAbiIdentity, *, core_build_id: str
) -> str:
    root.mkdir()
    (root / "sdk-product.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "profile_id": "graphics",
                "artifact_kind": "layer",
                "embedded_python_hosts": [],
                "launcher_import_roots": [],
                "native_import_roots": [],
                "forbidden_artifact_markers": [],
            }
        ),
        encoding="utf-8",
    )
    build_id = compute_native_build_id([], abi)
    (root / SDK_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": SCHEMA_VERSION,
                "manifest_kind": SDK_MANIFEST_KIND,
                "python_abi": abi.to_dict(),
                "native_build_id": build_id,
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )
    (root / SDK_INPUTS_NAME).write_text(
        json.dumps(
            {
                "schema": 1,
                "inputs": [
                    {"product_id": "core", "native_build_id": core_build_id}
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "lib" / "libgraphics.so").parent.mkdir()
    (root / "lib" / "libgraphics.so").write_text("graphics\n", encoding="utf-8")
    return build_id


def test_installed_core_is_validated_staged_and_recorded(tmp_path: Path) -> None:
    abi = PythonAbiIdentity.current()
    core = tmp_path / "core"
    build_id = _write_core_sdk(core, abi)

    installed = load_installed_sdk_input(
        core,
        expected_product="core",
        expected_build_id=build_id,
        expected_python_abi=abi,
    )
    output = tmp_path / "composed"
    stage_installed_sdk_input(installed, output)

    assert (output / "include" / "core-owned.h").read_text() == "core\n"
    inputs = json.loads((output / SDK_INPUTS_NAME).read_text(encoding="utf-8"))
    assert inputs["inputs"][0]["native_build_id"] == build_id
    assert inputs["inputs"][0]["distributions"] == ["tcbase"]


def test_installed_core_rejects_unpinned_build_identity(tmp_path: Path) -> None:
    abi = PythonAbiIdentity.current()
    core = tmp_path / "core"
    _write_core_sdk(core, abi)

    with pytest.raises(RuntimeError, match="build identity mismatch"):
        load_installed_sdk_input(
            core,
            expected_product="core",
            expected_build_id="0" * 20,
            expected_python_abi=abi,
        )


def test_composed_output_cannot_overlap_immutable_input(tmp_path: Path) -> None:
    abi = PythonAbiIdentity.current()
    core = tmp_path / "core"
    build_id = _write_core_sdk(core, abi)
    installed = load_installed_sdk_input(
        core,
        expected_product="core",
        expected_build_id=build_id,
        expected_python_abi=abi,
    )

    with pytest.raises(RuntimeError, match="must not overlap"):
        stage_installed_sdk_input(installed, core / "output")


def test_standalone_and_layer_compose_without_republishing_metadata(
    tmp_path: Path,
) -> None:
    abi = PythonAbiIdentity.current()
    core = tmp_path / "core"
    core_build_id = _write_core_sdk(core, abi)
    layer = tmp_path / "graphics"
    layer_build_id = _write_layer_sdk(layer, abi, core_build_id=core_build_id)

    output = tmp_path / "complete"
    compose_installed_sdk(
        base_root=core, layer_roots=(layer,), output_root=output
    )

    assert (output / "include" / "core-owned.h").is_file()
    assert (output / "lib" / "libgraphics.so").is_file()
    assert json.loads((output / "sdk-product.json").read_text())["profile_id"] == "core"
    composition = json.loads((output / SDK_COMPOSITION_NAME).read_text())
    assert [item["product_id"] for item in composition["components"]] == [
        "core",
        "graphics",
    ]
    assert composition["components"][1]["native_build_id"] == layer_build_id
    assert (
        output
        / "share"
        / "termin"
        / "sdk-layers"
        / "graphics"
        / SDK_MANIFEST_NAME
    ).is_file()


def test_composition_rejects_payload_collisions(tmp_path: Path) -> None:
    abi = PythonAbiIdentity.current()
    core = tmp_path / "core"
    core_build_id = _write_core_sdk(core, abi)
    layer = tmp_path / "graphics"
    _write_layer_sdk(layer, abi, core_build_id=core_build_id)
    (layer / "include").mkdir()
    (layer / "include" / "core-owned.h").write_text("collision\n")

    with pytest.raises(RuntimeError, match="payload collision"):
        compose_installed_sdk(
            base_root=core,
            layer_roots=(layer,),
            output_root=tmp_path / "complete",
        )
