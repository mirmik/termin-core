"""Generic build prerequisite and repository-declared submodule diagnostics."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DOCTOR_PROFILES_RELATIVE = Path("build-system/sdk-doctor-profiles.json")


class DoctorProfileError(ValueError):
    """Raised when repository doctor policy violates its closed schema."""


@dataclass(frozen=True)
class DoctorProfile:
    name: str
    submodules: tuple[str, ...]
    needs_cmake: bool = True
    needs_git: bool = True
    needs_nanobind: bool = False
    needs_pip: bool = False
    needs_copy_backend: bool = False
    needs_sdk_writable: bool = False


@dataclass(frozen=True)
class DoctorProfiles:
    profiles: tuple[DoctorProfile, ...]
    expected_submodule_files: dict[str, tuple[str, ...]]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(profile.name for profile in self.profiles)

    def profile(self, name: str) -> DoctorProfile:
        for profile in self.profiles:
            if profile.name == name:
                return profile
        raise DoctorProfileError(
            f"unsupported doctor profile {name!r}; expected: {', '.join(self.names)}"
        )


def load_doctor_profiles(repo_root: Path) -> DoctorProfiles:
    path = repo_root / DOCTOR_PROFILES_RELATIVE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DoctorProfileError(f"cannot read doctor profile manifest {path}: {error}") from error
    if not isinstance(raw, dict) or set(raw) != {"schema", "submodules", "profiles"}:
        raise DoctorProfileError(f"{path}: invalid root schema")
    if raw["schema"] != 1:
        raise DoctorProfileError(f"{path}: unsupported schema {raw['schema']!r}")
    raw_submodules = raw["submodules"]
    if not isinstance(raw_submodules, dict):
        raise DoctorProfileError(f"{path}: submodules must be an object")
    expected: dict[str, tuple[str, ...]] = {}
    for submodule, files in raw_submodules.items():
        normalized = _safe_relative_path(submodule, f"{path}: submodule")
        expected[normalized] = _string_list(files, f"{path}: submodules.{submodule}")
    raw_profiles = raw["profiles"]
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise DoctorProfileError(f"{path}: profiles must be a non-empty list")
    profiles = tuple(
        _parse_profile(value, f"{path}: profiles[{index}]")
        for index, value in enumerate(raw_profiles)
    )
    names = tuple(profile.name for profile in profiles)
    if len(names) != len(set(names)):
        raise DoctorProfileError(f"{path}: duplicate doctor profile id")
    undeclared = sorted(
        {submodule for profile in profiles for submodule in profile.submodules}
        - expected.keys()
    )
    if undeclared:
        raise DoctorProfileError(
            f"{path}: profiles reference undeclared submodules: {', '.join(undeclared)}"
        )
    return DoctorProfiles(profiles=profiles, expected_submodule_files=expected)


def _parse_profile(value: object, context: str) -> DoctorProfile:
    if not isinstance(value, dict):
        raise DoctorProfileError(f"{context}: expected object")
    fields = {
        "id",
        "submodules",
        "needs_nanobind",
        "needs_pip",
        "needs_copy_backend",
        "needs_sdk_writable",
    }
    if set(value) != fields:
        raise DoctorProfileError(f"{context}: fields must be exactly {sorted(fields)!r}")
    flags = {}
    for field in fields - {"id", "submodules"}:
        flag = value[field]
        if not isinstance(flag, bool):
            raise DoctorProfileError(f"{context}.{field}: expected boolean")
        flags[field] = flag
    return DoctorProfile(
        name=_non_empty_string(value["id"], f"{context}.id"),
        submodules=tuple(
            _safe_relative_path(path, f"{context}.submodules")
            for path in _string_list(value["submodules"], f"{context}.submodules")
        ),
        **flags,
    )


def _non_empty_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DoctorProfileError(f"{context}: expected non-empty string")
    return value


def _string_list(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DoctorProfileError(f"{context}: expected list")
    result = tuple(
        _non_empty_string(item, f"{context}[{index}]")
        for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise DoctorProfileError(f"{context}: duplicate value")
    return result


def _safe_relative_path(value: object, context: str) -> str:
    text = _non_empty_string(value, context).replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise DoctorProfileError(f"{context}: expected safe relative path")
    return path.as_posix()


def _submodule_ready(
    repo_root: Path,
    relative_path: str,
    expected_files: dict[str, tuple[str, ...]],
) -> bool:
    full_path = repo_root / relative_path
    if not full_path.is_dir():
        return False
    required = expected_files.get(relative_path, ())
    if required:
        return all((full_path / expected).exists() for expected in required)
    try:
        next(full_path.iterdir())
    except StopIteration:
        return False
    return True


def missing_submodules(
    repo_root: Path,
    paths: list[str],
    *,
    expected_files: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    expected_files = expected_files or {}
    normalized = list(dict.fromkeys(path.replace("\\", "/") for path in paths))
    return [
        path
        for path in normalized
        if not _submodule_ready(repo_root, path, expected_files)
    ]


def ensure_submodules(
    repo_root: Path,
    paths: list[str],
    *,
    expected_files: dict[str, tuple[str, ...]] | None = None,
) -> int:
    missing = missing_submodules(repo_root, paths, expected_files=expected_files)
    if not missing:
        return 0
    if shutil.which("git") is None:
        print(
            "ERROR: required git submodules are missing and git was not found:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    print("Initializing missing third-party submodules:")
    for path in missing:
        print(f"  - {path}")
    command = [
        "git", "-C", str(repo_root), "submodule", "update", "--init",
        "--recursive", "--", *missing,
    ]
    if sys.platform == "win32":
        git_executable = Path(shutil.which("git") or "")
        git_bash = git_executable.parent.parent / "bin" / "sh.exe"
        if git_bash.is_file():
            command = [
                str(git_bash), "-lc", 'exec git "$@"', "termin-git", *command[1:]
            ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        return result.returncode
    still_missing = missing_submodules(
        repo_root, missing, expected_files=expected_files
    )
    if still_missing:
        print(
            "ERROR: required git submodules are still missing after initialization:",
            file=sys.stderr,
        )
        for path in still_missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    return 0


def profile_submodules(
    profile: DoctorProfile,
    vulkan: str,
    sdl: str = "OFF",
) -> list[str]:
    # Backend-specific requirements are product policy and must be declared by
    # the repository as ordinary profile submodules. The arguments remain for
    # CLI compatibility while repositories migrate their callers.
    del vulkan, sdl
    return list(profile.submodules)
