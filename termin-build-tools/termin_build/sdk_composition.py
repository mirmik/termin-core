"""Composition of immutable installed SDK inputs."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .artifact_manifest import (
    ArtifactManifest,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
    sha256_file,
)
from .local_wheel_artifacts import compose_local_wheel_artifact_set
from .python_abi import PythonAbiIdentity
from .sdk_profiles import (
    INSTALLED_SDK_PRODUCT_NAME,
    InstalledSdkProduct,
    load_installed_sdk_product,
)


SDK_INPUTS_NAME = "sdk-inputs.json"
SDK_INPUTS_SCHEMA = 1
SDK_COMPOSITION_NAME = "sdk-composition.json"
SDK_COMPOSITION_SCHEMA = 1
_COMPOSABLE_ROOTS = ("bin", "include", "lib", "share")


@dataclass(frozen=True)
class InstalledSdkInput:
    root: Path
    product_id: str
    native_build_id: str
    python_abi: PythonAbiIdentity
    manifest_sha256: str
    distributions: tuple[str, ...]


def load_installed_sdk_input(
    root: Path,
    *,
    expected_product: str,
    expected_build_id: str | None = None,
    expected_python_abi: PythonAbiIdentity,
) -> InstalledSdkInput:
    root = root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"installed {expected_product} SDK does not exist: {root}")
    product = load_installed_sdk_product(root)
    if product.profile_id != expected_product:
        raise RuntimeError(
            f"installed SDK product mismatch: expected {expected_product!r}, "
            f"got {product.profile_id!r} from {root}"
        )
    manifest_path = root / SDK_MANIFEST_NAME
    manifest = ArtifactManifest.load(manifest_path)
    manifest.require_kind(SDK_MANIFEST_KIND)
    manifest.validate_all(expected_python_abi=expected_python_abi)
    if (
        expected_build_id is not None
        and manifest.native_build_id != expected_build_id
    ):
        raise RuntimeError(
            f"installed {expected_product} SDK build identity mismatch: "
            f"expected {expected_build_id}, got {manifest.native_build_id}"
        )
    runtime_path = root / "python-runtime-manifest.json"
    try:
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"cannot read installed {expected_product} Python runtime manifest: {error}"
        ) from error
    if runtime.get("native_build_id") != manifest.native_build_id:
        raise RuntimeError(
            f"installed {expected_product} runtime/artifact build identities differ"
        )
    raw_distributions = runtime.get("distributions")
    if not isinstance(raw_distributions, list):
        raise RuntimeError(
            f"installed {expected_product} runtime manifest has no distributions list"
        )
    distributions: list[str] = []
    for entry in raw_distributions:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            raise RuntimeError(
                f"installed {expected_product} runtime manifest has an invalid distribution"
            )
        if entry.get("kind") == "termin":
            distributions.append(name)
    required_paths = (
        root / "wheels",
        root / "lib" / "cmake" / "termin_base",
        root / "lib" / "cmake" / "termin_dispatch",
        root / "lib" / "cmake" / "termin_inspect",
        root / "lib" / "cmake" / "termin_python_host",
        root / "lib" / "cmake" / "nanobind",
    )
    missing = [str(path) for path in required_paths if not path.is_dir()]
    if missing:
        raise RuntimeError(
            f"installed {expected_product} SDK is incomplete; missing: "
            + ", ".join(missing)
        )
    return InstalledSdkInput(
        root=root,
        product_id=expected_product,
        native_build_id=manifest.native_build_id,
        python_abi=manifest.python_abi,
        manifest_sha256=sha256_file(manifest_path),
        distributions=tuple(distributions),
    )


def stage_installed_sdk_input(input_sdk: InstalledSdkInput, output_root: Path) -> None:
    output_root = output_root.resolve()
    if output_root == input_sdk.root or output_root.is_relative_to(input_sdk.root):
        raise RuntimeError(
            f"composed SDK output must not overlap its immutable input: {output_root}"
        )
    if input_sdk.root.is_relative_to(output_root):
        raise RuntimeError(
            f"immutable SDK input must not be inside composed output: {input_sdk.root}"
        )
    if output_root.exists():
        shutil.rmtree(output_root)
    shutil.copytree(input_sdk.root, output_root, symlinks=True)
    write_sdk_inputs(output_root, (input_sdk,))


def write_sdk_inputs(
    output_root: Path, inputs: tuple[InstalledSdkInput, ...]
) -> Path:
    payload = {
        "schema": SDK_INPUTS_SCHEMA,
        "inputs": [
            {
                "product_id": item.product_id,
                "native_build_id": item.native_build_id,
                "python_abi": item.python_abi.to_dict(),
                "artifact_manifest_sha256": item.manifest_sha256,
                "distributions": list(item.distributions),
            }
            for item in inputs
        ],
    }
    path = output_root / SDK_INPUTS_NAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _load_component(root: Path, *, expected_kind: str) -> tuple[InstalledSdkProduct, ArtifactManifest]:
    root = root.resolve()
    product = load_installed_sdk_product(root)
    if product.artifact_kind != expected_kind:
        raise RuntimeError(
            f"SDK component {root} has artifact_kind={product.artifact_kind!r}; "
            f"expected {expected_kind!r}"
        )
    manifest = ArtifactManifest.load(root / SDK_MANIFEST_NAME)
    manifest.require_kind(SDK_MANIFEST_KIND)
    manifest.validate_all(expected_python_abi=manifest.python_abi)
    return product, manifest


def _component_record(root: Path, product: InstalledSdkProduct, manifest: ArtifactManifest) -> dict[str, object]:
    return {
        "product_id": product.profile_id,
        "artifact_kind": product.artifact_kind,
        "native_build_id": manifest.native_build_id,
        "python_abi": manifest.python_abi.to_dict(),
        "artifact_manifest_sha256": sha256_file(root / SDK_MANIFEST_NAME),
    }


def _payload_entries(root: Path) -> set[Path]:
    entries: set[Path] = set()
    for top_name in _COMPOSABLE_ROOTS:
        top = root / top_name
        if not top.is_dir():
            continue
        for path in top.rglob("*"):
            if path.is_file() or path.is_symlink():
                entries.add(path.relative_to(root))
    return entries


def _populate_composed_sdk(
    *,
    base_root: Path,
    resolved_layers: tuple[Path, ...],
    components: list[tuple[Path, InstalledSdkProduct, ArtifactManifest]],
    output_root: Path,
) -> None:
    shutil.copytree(base_root, output_root, symlinks=True)
    for layer_root, product, _manifest in components[1:]:
        for top_name in _COMPOSABLE_ROOTS:
            source = layer_root / top_name
            if source.is_dir():
                shutil.copytree(
                    source,
                    output_root / top_name,
                    symlinks=True,
                    dirs_exist_ok=True,
                )
        metadata_root = (
            output_root / "share" / "termin" / "sdk-layers" / product.profile_id
        )
        metadata_root.mkdir(parents=True, exist_ok=True)
        for name in (
            SDK_MANIFEST_NAME,
            INSTALLED_SDK_PRODUCT_NAME,
            "python-runtime-manifest.json",
            SDK_INPUTS_NAME,
            "termin-sdk-capabilities.json",
            "application-python-payloads.json",
        ):
            source = layer_root / name
            if source.is_file():
                shutil.copy2(source, metadata_root / name)
        layer_wheel_manifest = (
            layer_root / "wheels" / "termin-local-wheel-artifacts.json"
        )
        if layer_wheel_manifest.is_file():
            shutil.copy2(
                layer_wheel_manifest, metadata_root / layer_wheel_manifest.name
            )

    inputs = (base_root, *resolved_layers)
    primary_wheels = base_root / "wheels"
    wheel_manifests = tuple(
        root / "wheels" / "termin-local-wheel-artifacts.json" for root in inputs
    )
    if any(path.exists() for path in wheel_manifests):
        if not all(path.is_file() for path in wheel_manifests):
            raise RuntimeError("all composed SDK components must publish wheel manifests")
        compose_local_wheel_artifact_set(
            primary_wheels,
            tuple(
                (
                    layer_root / "wheels",
                    layer_root,
                    len(tuple((layer_root / "wheels").glob("*.whl"))),
                )
                for layer_root in resolved_layers
            ),
            output_root / "wheels",
            sdk_prefix=output_root,
            expected_primary_wheel_count=len(tuple(primary_wheels.glob("*.whl"))),
        )

    payload = {
        "schema": SDK_COMPOSITION_SCHEMA,
        "base_product": components[0][1].profile_id,
        "components": [
            _component_record(root, product, manifest)
            for root, product, manifest in components
        ],
    }
    (output_root / SDK_COMPOSITION_NAME).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def compose_installed_sdk(
    *, base_root: Path, layer_roots: tuple[Path, ...], output_root: Path
) -> Path:
    """Compose one standalone SDK and ordered thin layers into a new prefix."""
    if not layer_roots:
        raise RuntimeError("at least one SDK layer is required")
    base_root = base_root.resolve()
    output_root = output_root.resolve()
    resolved_layers = tuple(root.resolve() for root in layer_roots)
    inputs = (base_root, *resolved_layers)
    for input_root in inputs:
        if output_root == input_root or output_root.is_relative_to(input_root):
            raise RuntimeError(
                f"composed SDK output must not overlap immutable input {input_root}"
            )
        if input_root.is_relative_to(output_root):
            raise RuntimeError(
                f"immutable SDK input must not be inside composed output {output_root}"
            )

    base_product, base_manifest = _load_component(base_root, expected_kind="standalone")
    components = [(base_root, base_product, base_manifest)]
    occupied = _payload_entries(base_root)
    seen_products = {base_product.profile_id}
    for layer_root in resolved_layers:
        layer_product, layer_manifest = _load_component(layer_root, expected_kind="layer")
        if layer_product.profile_id in seen_products:
            raise RuntimeError(f"duplicate SDK product {layer_product.profile_id!r}")
        seen_products.add(layer_product.profile_id)
        if layer_manifest.python_abi != base_manifest.python_abi:
            raise RuntimeError(
                f"SDK Python ABI mismatch between {base_product.profile_id} and "
                f"{layer_product.profile_id}"
            )
        layer_inputs_path = layer_root / SDK_INPUTS_NAME
        try:
            layer_inputs = json.loads(layer_inputs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"cannot read layer inputs {layer_inputs_path}: {error}"
            ) from error
        matching_base = [
            item
            for item in layer_inputs.get("inputs", [])
            if isinstance(item, dict) and item.get("product_id") == base_product.profile_id
        ]
        if (
            len(matching_base) != 1
            or matching_base[0].get("native_build_id")
            != base_manifest.native_build_id
        ):
            raise RuntimeError(
                f"SDK layer {layer_product.profile_id} was not built against "
                f"{base_product.profile_id} {base_manifest.native_build_id}"
            )
        layer_entries = _payload_entries(layer_root)
        collisions = sorted(occupied & layer_entries)
        if collisions:
            preview = ", ".join(path.as_posix() for path in collisions[:10])
            raise RuntimeError(
                f"SDK payload collision while adding {layer_product.profile_id}: {preview}"
            )
        occupied.update(layer_entries)
        components.append((layer_root, layer_product, layer_manifest))

    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_root.name}.compose-", dir=output_root.parent
    ) as temporary:
        prepared = Path(temporary) / "sdk"
        _populate_composed_sdk(
            base_root=base_root,
            resolved_layers=resolved_layers,
            components=components,
            output_root=prepared,
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        prepared.replace(output_root)
    return output_root / SDK_COMPOSITION_NAME
