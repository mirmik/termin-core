"""Composition of immutable installed SDK inputs."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .artifact_manifest import (
    ArtifactManifest,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
    sha256_file,
)
from .python_abi import PythonAbiIdentity
from .sdk_profiles import load_installed_sdk_product


SDK_INPUTS_NAME = "sdk-inputs.json"
SDK_INPUTS_SCHEMA = 1


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
    expected_build_id: str,
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
    if manifest.native_build_id != expected_build_id:
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
