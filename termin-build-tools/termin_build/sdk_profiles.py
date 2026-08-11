"""Canonical SDK build profiles and their Python/application payload closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypeVar


FULL_SDK_PROFILE = "full"
GRAPHICS_SDK_PROFILE = "graphics"
SDK_PROFILE_NAMES = (FULL_SDK_PROFILE, GRAPHICS_SDK_PROFILE)

_GRAPHICS_PYTHON_PACKAGES = frozenset(
    {
        "termin-build-tools",
        "termin-nanobind-sdk",
        "termin-base",
        "termin-dispatch",
        "termin-image",
        "termin-assets",
        "termin-tween",
        "termin-mesh",
        "termin-graphics",
        "termin-visual-scene",
        "termin-inspect",
        "termin-shader-runtime",
        "termin-gui",
        "termin-gui-native",
        "termin-nodegraph",
        "termin-window",
        "tcplot",
        "tcplot-gui-native",
    }
)


@dataclass(frozen=True)
class SdkProfile:
    name: str
    python_package_paths: frozenset[str] | None
    application_payload_names: frozenset[str] | None


PROFILES = {
    FULL_SDK_PROFILE: SdkProfile(
        name=FULL_SDK_PROFILE,
        python_package_paths=None,
        application_payload_names=None,
    ),
    GRAPHICS_SDK_PROFILE: SdkProfile(
        name=GRAPHICS_SDK_PROFILE,
        python_package_paths=_GRAPHICS_PYTHON_PACKAGES,
        application_payload_names=frozenset(),
    ),
}

_T = TypeVar("_T")


def sdk_profile(name: str) -> SdkProfile:
    try:
        return PROFILES[name]
    except KeyError as error:
        expected = ", ".join(SDK_PROFILE_NAMES)
        raise ValueError(f"unsupported SDK profile {name!r}; expected: {expected}") from error


def select_python_packages(profile: SdkProfile, packages: Iterable[_T]) -> list[_T]:
    selected = list(packages)
    if profile.python_package_paths is None:
        return selected
    by_path = {str(package.path): package for package in selected}
    missing = sorted(profile.python_package_paths - by_path.keys())
    if missing:
        raise ValueError(
            f"SDK profile {profile.name!r} references unknown Python packages: "
            + ", ".join(missing)
        )
    return [
        package
        for package in selected
        if str(package.path) in profile.python_package_paths
    ]


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
