"""Typed repository-owned SDK product recipes.

This module owns the schema and selection mechanisms.  Concrete product names,
package closures and verification roots live in ``build-system/sdk-profiles.json``
inside the repository being built.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeVar

from .product_manifest import load_product_manifest


SDK_PROFILES_RELATIVE = Path("build-system/sdk-profiles.json")
INSTALLED_SDK_PRODUCT_NAME = "sdk-product.json"
INSTALLED_SDK_PRODUCT_SCHEMA = 1


class SdkProfileError(ValueError):
    """Raised when a repository SDK profile manifest violates its schema."""


@dataclass(frozen=True)
class SdkProfile:
    name: str
    artifact_kind: str
    python_package_paths: frozenset[str] | None
    application_payload_names: frozenset[str] | None
    product_manifest_id: str | None
    runtime_lock: Path
    sdk_prefix: str
    build_directory_suffix: str
    csharp_profile: str | None
    wheel_subset: tuple[str, ...]
    embedded_python_hosts: tuple[str, ...]
    launcher_import_roots: tuple[str, ...]
    native_import_roots: tuple[str, ...]
    forbidden_artifacts_from_product: bool


@dataclass(frozen=True)
class SdkProfileSet:
    default_profile: str
    profiles: tuple[SdkProfile, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(profile.name for profile in self.profiles)

    def profile(self, name: str) -> SdkProfile:
        for profile in self.profiles:
            if profile.name == name:
                return profile
        expected = ", ".join(self.names)
        raise SdkProfileError(
            f"unsupported SDK profile {name!r}; expected: {expected}"
        )


@dataclass(frozen=True)
class InstalledSdkProduct:
    profile_id: str
    artifact_kind: str
    embedded_python_hosts: tuple[str, ...]
    launcher_import_roots: tuple[str, ...]
    native_import_roots: tuple[str, ...]
    forbidden_artifact_markers: tuple[str, ...]


def write_installed_sdk_product(
    sdk_prefix: Path,
    profile: SdkProfile,
    *,
    forbidden_artifact_markers: tuple[str, ...] = (),
) -> Path:
    payload = {
        "schema": INSTALLED_SDK_PRODUCT_SCHEMA,
        "profile_id": profile.name,
        "artifact_kind": profile.artifact_kind,
        "embedded_python_hosts": list(profile.embedded_python_hosts),
        "launcher_import_roots": list(profile.launcher_import_roots),
        "native_import_roots": list(profile.native_import_roots),
        "forbidden_artifact_markers": list(forbidden_artifact_markers),
    }
    sdk_prefix.mkdir(parents=True, exist_ok=True)
    output = sdk_prefix / INSTALLED_SDK_PRODUCT_NAME
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def load_installed_sdk_product(sdk_prefix: Path) -> InstalledSdkProduct:
    path = sdk_prefix / INSTALLED_SDK_PRODUCT_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SdkProfileError(f"cannot read installed SDK product manifest {path}: {error}") from error
    if not isinstance(raw, dict):
        raise SdkProfileError(f"{path}: root must be an object")
    fields = {
        "schema",
        "profile_id",
        "artifact_kind",
        "embedded_python_hosts",
        "launcher_import_roots",
        "native_import_roots",
        "forbidden_artifact_markers",
    }
    if set(raw) != fields:
        raise SdkProfileError(f"{path}: fields must be exactly {sorted(fields)!r}")
    if raw["schema"] != INSTALLED_SDK_PRODUCT_SCHEMA:
        raise SdkProfileError(f"{path}: unsupported schema {raw['schema']!r}")
    return InstalledSdkProduct(
        profile_id=_string(raw["profile_id"], f"{path}: profile_id"),
        artifact_kind=_artifact_kind(raw["artifact_kind"], f"{path}: artifact_kind"),
        embedded_python_hosts=_strings(
            raw["embedded_python_hosts"], f"{path}: embedded_python_hosts"
        ),
        launcher_import_roots=_strings(
            raw["launcher_import_roots"], f"{path}: launcher_import_roots"
        ),
        native_import_roots=_strings(
            raw["native_import_roots"], f"{path}: native_import_roots"
        ),
        forbidden_artifact_markers=_strings(
            raw["forbidden_artifact_markers"], f"{path}: forbidden_artifact_markers"
        ),
    )


def load_sdk_profiles(repo_root: Path) -> SdkProfileSet:
    path = repo_root / SDK_PROFILES_RELATIVE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SdkProfileError(f"SDK profile manifest does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise SdkProfileError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise SdkProfileError(f"{path}: root must be an object")
    expected_root = {"schema", "default_profile", "profiles"}
    if set(raw) != expected_root:
        raise SdkProfileError(
            f"{path}: fields must be exactly {sorted(expected_root)!r}"
        )
    if raw["schema"] != 1:
        raise SdkProfileError(f"{path}: unsupported schema {raw['schema']!r}")
    default_profile = _string(raw["default_profile"], f"{path}: default_profile")
    raw_profiles = raw["profiles"]
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise SdkProfileError(f"{path}: profiles must be a non-empty list")
    profiles = tuple(
        _parse_profile(value, f"{path}: profiles[{index}]")
        for index, value in enumerate(raw_profiles)
    )
    names = tuple(profile.name for profile in profiles)
    if len(names) != len(set(names)):
        raise SdkProfileError(f"{path}: duplicate SDK profile id")
    if default_profile not in names:
        raise SdkProfileError(
            f"{path}: default profile {default_profile!r} is not declared"
        )
    return SdkProfileSet(default_profile=default_profile, profiles=profiles)


def _parse_profile(value: object, context: str) -> SdkProfile:
    if not isinstance(value, dict):
        raise SdkProfileError(f"{context}: profile must be an object")
    fields = {
        "id",
        "artifact_kind",
        "python_packages",
        "product_manifest",
        "application_payloads",
        "runtime_lock",
        "sdk_prefix",
        "build_directory_suffix",
        "csharp_profile",
        "wheel_subset",
        "embedded_python_hosts",
        "launcher_import_roots",
        "native_import_roots",
        "forbidden_artifacts_from_product",
    }
    if set(value) != fields:
        raise SdkProfileError(f"{context}: fields must be exactly {sorted(fields)!r}")
    python_packages = _optional_strings(value["python_packages"], f"{context}.python_packages")
    application_payloads = _optional_strings(
        value["application_payloads"], f"{context}.application_payloads"
    )
    product_manifest = value["product_manifest"]
    if product_manifest is not None:
        product_manifest = _string(product_manifest, f"{context}.product_manifest")
    if python_packages is not None and product_manifest is not None:
        raise SdkProfileError(
            f"{context}: python_packages and product_manifest are mutually exclusive"
        )
    csharp_profile = value["csharp_profile"]
    if csharp_profile is not None:
        csharp_profile = _string(csharp_profile, f"{context}.csharp_profile")
    forbidden = value["forbidden_artifacts_from_product"]
    if not isinstance(forbidden, bool):
        raise SdkProfileError(
            f"{context}.forbidden_artifacts_from_product: expected boolean"
        )
    return SdkProfile(
        name=_string(value["id"], f"{context}.id"),
        artifact_kind=_artifact_kind(
            value["artifact_kind"], f"{context}.artifact_kind"
        ),
        python_package_paths=(
            None if python_packages is None else frozenset(python_packages)
        ),
        application_payload_names=(
            None if application_payloads is None else frozenset(application_payloads)
        ),
        product_manifest_id=product_manifest,
        runtime_lock=_relative_path(value["runtime_lock"], f"{context}.runtime_lock"),
        sdk_prefix=_relative_path(value["sdk_prefix"], f"{context}.sdk_prefix").as_posix(),
        build_directory_suffix=_suffix(
            value["build_directory_suffix"], f"{context}.build_directory_suffix"
        ),
        csharp_profile=csharp_profile,
        wheel_subset=_strings(value["wheel_subset"], f"{context}.wheel_subset"),
        embedded_python_hosts=_strings(
            value["embedded_python_hosts"], f"{context}.embedded_python_hosts"
        ),
        launcher_import_roots=_strings(
            value["launcher_import_roots"], f"{context}.launcher_import_roots"
        ),
        native_import_roots=_strings(
            value["native_import_roots"], f"{context}.native_import_roots"
        ),
        forbidden_artifacts_from_product=forbidden,
    )


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SdkProfileError(f"{context}: expected non-empty string")
    return value


def _suffix(value: object, context: str) -> str:
    if not isinstance(value, str) or "/" in value or "\\" in value:
        raise SdkProfileError(f"{context}: expected a simple string suffix")
    return value


def _artifact_kind(value: object, context: str) -> str:
    result = _string(value, context)
    if result not in {"standalone", "layer"}:
        raise SdkProfileError(f"{context}: expected 'standalone' or 'layer'")
    return result


def _strings(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SdkProfileError(f"{context}: expected list")
    result = tuple(_string(item, f"{context}[{index}]") for index, item in enumerate(value))
    if len(result) != len(set(result)):
        raise SdkProfileError(f"{context}: duplicate value")
    return result


def _optional_strings(value: object, context: str) -> tuple[str, ...] | None:
    return None if value is None else _strings(value, context)


def _relative_path(value: object, context: str) -> Path:
    text = _string(value, context)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise SdkProfileError(f"{context}: expected safe repository-relative path")
    return path


_T = TypeVar("_T")


def select_python_packages(
    profile: SdkProfile,
    packages: Iterable[_T],
    *,
    repo_root: Path | None = None,
) -> list[_T]:
    selected = list(packages)
    selected_paths = profile.python_package_paths
    if profile.product_manifest_id is not None:
        if repo_root is None:
            raise ValueError(
                f"SDK profile {profile.name!r} requires a repository root"
            )
        manifest = load_product_manifest(repo_root, profile.product_manifest_id)
        selected_paths = frozenset(
            module.path
            for module in manifest.modules
            if module.python_distribution is not None
        )
    if selected_paths is None:
        return selected
    by_path = {str(package.path): package for package in selected}
    missing = sorted(selected_paths - by_path.keys())
    if missing:
        raise ValueError(
            f"SDK profile {profile.name!r} references unknown Python packages: "
            + ", ".join(missing)
        )
    return [package for package in selected if str(package.path) in selected_paths]


def select_application_payloads(
    profile: SdkProfile, payloads: Iterable[_T]
) -> tuple[_T, ...]:
    selected = tuple(payloads)
    if profile.application_payload_names is None:
        return selected
    by_name = {str(payload.name): payload for payload in selected}
    missing = sorted(profile.application_payload_names - by_name.keys())
    if missing:
        raise ValueError(
            f"SDK profile {profile.name!r} references unknown application payloads: "
            + ", ".join(missing)
        )
    return tuple(
        payload
        for payload in selected
        if str(payload.name) in profile.application_payload_names
    )
