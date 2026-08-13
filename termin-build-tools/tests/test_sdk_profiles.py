from __future__ import annotations

from pathlib import Path

from termin_build.application_payload import load_application_payloads
from termin_build.package_manifest import load_manifest
from termin_build.sdk_profiles import (
    load_sdk_profiles,
    select_application_payloads,
    select_python_packages,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = load_sdk_profiles(REPO_ROOT)


def test_core_sdk_profile_is_projected_from_product_manifest() -> None:
    packages = select_python_packages(
        PROFILES.profile("core"),
        load_manifest(REPO_ROOT),
        repo_root=REPO_ROOT,
    )

    assert [str(package.path) for package in packages] == [
        "termin-build-tools",
        "termin-nanobind-sdk",
        "termin-base",
        "termin-dispatch",
        "termin-inspect",
        "termin-mcp",
    ]


def test_core_sdk_profile_has_no_application_payload() -> None:
    payloads = select_application_payloads(
        PROFILES.profile("core"),
        load_application_payloads(REPO_ROOT),
    )

    assert payloads == ()


def test_core_sdk_profile_owns_minimal_runtime_and_verification_recipe() -> None:
    profile = PROFILES.profile("core")

    assert profile.runtime_lock.as_posix() == "build-system/python-runtime-core-lock.txt"
    assert profile.sdk_prefix == "sdk"
    assert profile.csharp_profile is None
    assert profile.embedded_python_hosts == ()
    assert profile.launcher_import_roots == (
        "tcbase",
        "termin.dispatch",
        "termin.inspect",
        "termin.mcp",
    )
