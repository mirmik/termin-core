"""Repository module catalog and test execution planner."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .package_manifest import load_manifest as load_package_manifest
from .package_manifest import repo_root_from


MODULE_MANIFEST = Path("build-system/modules.json")
TEST_MANIFEST = Path("build-system/test-suites.json")
SUPPORTED_EXECUTORS = frozenset(
    {"pytest", "ctest", "process-smoke", "device", "manual"}
)
SUPPORTED_PLATFORMS = frozenset({"linux", "windows", "macos", "android", "quest"})


class ManifestError(ValueError):
    """Raised when repository control-plane metadata is invalid."""


@dataclass(frozen=True)
class ModuleEntry:
    id: str
    path: str
    kinds: tuple[str, ...]
    python_distribution: str | None = None


@dataclass(frozen=True)
class ProfileEntry:
    id: str
    description: str


@dataclass(frozen=True)
class SuiteEntry:
    id: str
    module: str
    executor: str
    roots: tuple[str, ...]
    profiles: tuple[str, ...]
    environment: str
    platforms: tuple[str, ...]
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryCatalog:
    modules: tuple[ModuleEntry, ...]
    profiles: tuple[ProfileEntry, ...]
    suites: tuple[SuiteEntry, ...]


def _read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"manifest root must be an object: {path}")
    if data.get("schema") != 1:
        raise ManifestError(f"unsupported or missing schema in {path}")
    return data


def _required_string(raw: dict[str, object], field: str, context: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}: {field} must be a non-empty string")
    return value


def _string_tuple(
    raw: dict[str, object],
    field: str,
    context: str,
    *,
    required: bool = False,
) -> tuple[str, ...]:
    value = raw.get(field)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value):
        requirement = "a non-empty list" if required else "a list"
        raise ManifestError(f"{context}: {field} must be {requirement} of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ManifestError(f"{context}: {field} must contain only non-empty strings")
    if len(value) != len(set(value)):
        raise ManifestError(f"{context}: {field} contains duplicate values")
    return tuple(value)


def _object_list(data: dict[str, object], field: str, path: Path) -> list[dict[str, object]]:
    value = data.get(field)
    if not isinstance(value, list):
        raise ManifestError(f"{path}: {field} must be a list")
    if any(not isinstance(item, dict) for item in value):
        raise ManifestError(f"{path}: {field} must contain only objects")
    return value


def _module_kinds(repo_root: Path, module_path: str) -> tuple[str, ...]:
    root = repo_root / module_path
    kinds = ["python"]
    if (root / "CMakeLists.txt").is_file():
        kinds.append("cmake")
    if (root / "docs").is_dir():
        kinds.append("documentation")
    return tuple(kinds)


def load_modules(repo_root: Path) -> tuple[ModuleEntry, ...]:
    path = repo_root / MODULE_MANIFEST
    data = _read_json(path)
    package_manifest = _required_string(
        data, "python_package_manifest", str(path)
    )
    if Path(package_manifest) != Path("build-system/packages.json"):
        raise ManifestError(
            f"{path}: python_package_manifest must reference the canonical "
            "build-system/packages.json"
        )

    modules = [
        ModuleEntry(
            id=Path(package.path).name,
            path=package.path,
            kinds=_module_kinds(repo_root, package.path),
            python_distribution=package.distribution,
        )
        for package in load_package_manifest(repo_root)
    ]

    for index, raw in enumerate(_object_list(data, "modules", path)):
        context = f"{path}: modules[{index}]"
        modules.append(
            ModuleEntry(
                id=_required_string(raw, "id", context),
                path=_required_string(raw, "path", context),
                kinds=_string_tuple(raw, "kinds", context, required=True),
            )
        )
    return tuple(modules)


def load_profiles_and_suites(
    repo_root: Path,
) -> tuple[tuple[ProfileEntry, ...], tuple[SuiteEntry, ...]]:
    path = repo_root / TEST_MANIFEST
    data = _read_json(path)

    profiles = []
    for index, raw in enumerate(_object_list(data, "profiles", path)):
        context = f"{path}: profiles[{index}]"
        profiles.append(
            ProfileEntry(
                id=_required_string(raw, "id", context),
                description=_required_string(raw, "description", context),
            )
        )

    suites = []
    for index, raw in enumerate(_object_list(data, "suites", path)):
        context = f"{path}: suites[{index}]"
        suites.append(
            SuiteEntry(
                id=_required_string(raw, "id", context),
                module=_required_string(raw, "module", context),
                executor=_required_string(raw, "executor", context),
                roots=_string_tuple(raw, "roots", context, required=True),
                profiles=_string_tuple(raw, "profiles", context, required=True),
                environment=_required_string(raw, "environment", context),
                platforms=_string_tuple(raw, "platforms", context),
                capabilities=_string_tuple(raw, "capabilities", context),
            )
        )
    return tuple(profiles), tuple(suites)


def load_catalog(repo_root: Path) -> RepositoryCatalog:
    modules = load_modules(repo_root)
    profiles, suites = load_profiles_and_suites(repo_root)
    return RepositoryCatalog(modules=modules, profiles=profiles, suites=suites)


def _duplicates(values: Iterable[str]) -> list[str]:
    items = list(values)
    return sorted({item for item in items if items.count(item) > 1})


def _is_repository_relative(path: str) -> bool:
    candidate = Path(path)
    return (
        not candidate.is_absolute()
        and path not in ("", ".")
        and ".." not in candidate.parts
    )


def validate_catalog(repo_root: Path, catalog: RepositoryCatalog) -> list[str]:
    errors = []
    for module_id in _duplicates(module.id for module in catalog.modules):
        errors.append(f"duplicate module id: {module_id}")
    for module_path in _duplicates(module.path for module in catalog.modules):
        errors.append(f"duplicate module path: {module_path}")
    for profile_id in _duplicates(profile.id for profile in catalog.profiles):
        errors.append(f"duplicate profile id: {profile_id}")
    for suite_id in _duplicates(suite.id for suite in catalog.suites):
        errors.append(f"duplicate suite id: {suite_id}")

    module_ids = {module.id for module in catalog.modules}
    profile_ids = {profile.id for profile in catalog.profiles}
    for module in catalog.modules:
        if not _is_repository_relative(module.path):
            errors.append(
                f"module path must be repository-relative: {module.id}: {module.path}"
            )
            continue
        if not (repo_root / module.path).is_dir():
            errors.append(f"module path does not exist: {module.id}: {module.path}")

    for suite in catalog.suites:
        if suite.module not in module_ids:
            errors.append(f"{suite.id}: unknown module: {suite.module}")
        if suite.executor not in SUPPORTED_EXECUTORS:
            errors.append(f"{suite.id}: unsupported executor: {suite.executor}")
        for profile in suite.profiles:
            if profile not in profile_ids:
                errors.append(f"{suite.id}: unknown profile: {profile}")
        for platform in suite.platforms:
            if platform not in SUPPORTED_PLATFORMS:
                errors.append(f"{suite.id}: unsupported platform: {platform}")
        for root in suite.roots:
            if not _is_repository_relative(root):
                errors.append(
                    f"{suite.id}: test root must be repository-relative: {root}"
                )
                continue
            if not (repo_root / root).exists():
                errors.append(f"{suite.id}: test root does not exist: {root}")
    return errors


def catalog_as_json(catalog: RepositoryCatalog) -> dict[str, object]:
    return {
        "schema": 1,
        "modules": [asdict(module) for module in catalog.modules],
        "profiles": [asdict(profile) for profile in catalog.profiles],
        "suites": [asdict(suite) for suite in catalog.suites],
    }


def build_plan(
    catalog: RepositoryCatalog,
    profile: str,
    platform: str | None,
) -> dict[str, object]:
    profile_ids = {entry.id for entry in catalog.profiles}
    if profile not in profile_ids:
        raise ManifestError(f"unknown profile: {profile}")
    if platform is not None and platform not in SUPPORTED_PLATFORMS:
        raise ManifestError(f"unsupported platform: {platform}")

    suites = []
    for suite in catalog.suites:
        if profile not in suite.profiles:
            continue
        if platform is not None and suite.platforms and platform not in suite.platforms:
            continue
        suites.append(asdict(suite))
    return {
        "schema": 1,
        "profile": profile,
        "platform": platform,
        "suites": suites,
    }


def _load_valid_catalog(repo_root: Path) -> RepositoryCatalog:
    catalog = load_catalog(repo_root)
    errors = validate_catalog(repo_root, catalog)
    if errors:
        raise ManifestError("\n".join(errors))
    return catalog


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _cmd_check(repo_root: Path) -> int:
    _load_valid_catalog(repo_root)
    print("Repository control manifests OK")
    return 0


def _cmd_list(repo_root: Path, subject: str, json_output: bool) -> int:
    catalog = _load_valid_catalog(repo_root)
    entries = {
        "modules": catalog.modules,
        "profiles": catalog.profiles,
        "suites": catalog.suites,
    }[subject]
    if json_output:
        _print_json([asdict(entry) for entry in entries])
    else:
        for entry in entries:
            print(entry.id)
    return 0


def _cmd_plan(
    repo_root: Path,
    profile: str,
    platform: str | None,
    json_output: bool,
) -> int:
    plan = build_plan(_load_valid_catalog(repo_root), profile, platform)
    if json_output:
        _print_json(plan)
    else:
        for suite in plan["suites"]:
            print(suite["id"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Validate repository control manifests.")

    list_parser = subparsers.add_parser("list", help="List catalog entries.")
    list_parser.add_argument("subject", choices=("modules", "profiles", "suites"))
    list_parser.add_argument("--json", action="store_true", dest="json_output")

    plan_parser = subparsers.add_parser("plan", help="Build a test execution plan.")
    plan_parser.add_argument("profile")
    plan_parser.add_argument("--platform", choices=sorted(SUPPORTED_PLATFORMS))
    plan_parser.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from(Path.cwd())
    try:
        if args.command == "check":
            return _cmd_check(repo_root)
        if args.command == "list":
            return _cmd_list(repo_root, args.subject, args.json_output)
        if args.command == "plan":
            return _cmd_plan(
                repo_root,
                args.profile,
                args.platform,
                args.json_output,
            )
    except (ManifestError, OSError) as exc:
        for line in str(exc).splitlines():
            print(f"ERROR: {line}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
