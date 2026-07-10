"""Repository module catalog and test execution planner."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import uuid
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
    pytest_mark_expression: str | None


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
class PythonTestInventory:
    patterns: tuple[str, ...]
    exclude_roots: tuple[str, ...]
    exclude_directory_names: tuple[str, ...]


@dataclass(frozen=True)
class NativeTestInventory:
    patterns: tuple[str, ...]
    extensions: tuple[str, ...]
    exclude_roots: tuple[str, ...]
    exclude_directory_names: tuple[str, ...]
    source_classifications: tuple["NativeSourceClassification", ...]


@dataclass(frozen=True)
class NativeSourceClassification:
    path: str
    profiles: tuple[str, ...]
    capabilities: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class RepositoryCatalog:
    modules: tuple[ModuleEntry, ...]
    profiles: tuple[ProfileEntry, ...]
    suites: tuple[SuiteEntry, ...]
    python_test_inventory: PythonTestInventory
    native_test_inventory: NativeTestInventory


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


def _string_with_default(
    raw: dict[str, object],
    field: str,
    context: str,
    defaults: dict[str, object],
) -> str:
    if field in raw:
        return _required_string(raw, field, context)
    return _required_string(defaults, field, f"{context} defaults")


def _optional_string(
    raw: dict[str, object], field: str, context: str
) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}: {field} must be a non-empty string or null")
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


def _string_tuple_with_default(
    raw: dict[str, object],
    field: str,
    context: str,
    defaults: dict[str, object],
    *,
    required: bool = False,
) -> tuple[str, ...]:
    if field in raw:
        return _string_tuple(raw, field, context, required=required)
    return _string_tuple(
        defaults,
        field,
        f"{context} defaults",
        required=required,
    )


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
) -> tuple[
    tuple[ProfileEntry, ...],
    tuple[SuiteEntry, ...],
    PythonTestInventory,
    NativeTestInventory,
]:
    path = repo_root / TEST_MANIFEST
    data = _read_json(path)

    raw_defaults = data.get("suite_defaults", {})
    if not isinstance(raw_defaults, dict):
        raise ManifestError(f"{path}: suite_defaults must be an object")

    raw_inventory = data.get("python_test_inventory")
    if not isinstance(raw_inventory, dict):
        raise ManifestError(f"{path}: python_test_inventory must be an object")
    inventory_context = f"{path}: python_test_inventory"
    inventory = PythonTestInventory(
        patterns=_string_tuple(
            raw_inventory, "patterns", inventory_context, required=True
        ),
        exclude_roots=_string_tuple(
            raw_inventory, "exclude_roots", inventory_context
        ),
        exclude_directory_names=_string_tuple(
            raw_inventory, "exclude_directory_names", inventory_context
        ),
    )

    raw_native_inventory = data.get("native_test_inventory")
    if not isinstance(raw_native_inventory, dict):
        raise ManifestError(f"{path}: native_test_inventory must be an object")
    native_inventory_context = f"{path}: native_test_inventory"
    raw_source_classifications = raw_native_inventory.get(
        "source_classifications", []
    )
    if not isinstance(raw_source_classifications, list) or any(
        not isinstance(entry, dict) for entry in raw_source_classifications
    ):
        raise ManifestError(
            f"{native_inventory_context}: source_classifications must be a list of objects"
        )
    source_classifications = []
    for index, raw in enumerate(raw_source_classifications):
        context = f"{native_inventory_context}: source_classifications[{index}]"
        source_classifications.append(
            NativeSourceClassification(
                path=_required_string(raw, "path", context),
                profiles=_string_tuple(raw, "profiles", context, required=True),
                capabilities=_string_tuple(raw, "capabilities", context),
                reason=_required_string(raw, "reason", context),
            )
        )
    native_inventory = NativeTestInventory(
        patterns=_string_tuple(
            raw_native_inventory, "patterns", native_inventory_context, required=True
        ),
        extensions=_string_tuple(
            raw_native_inventory, "extensions", native_inventory_context, required=True
        ),
        exclude_roots=_string_tuple(
            raw_native_inventory, "exclude_roots", native_inventory_context
        ),
        exclude_directory_names=_string_tuple(
            raw_native_inventory, "exclude_directory_names", native_inventory_context
        ),
        source_classifications=tuple(source_classifications),
    )

    profiles = []
    for index, raw in enumerate(_object_list(data, "profiles", path)):
        context = f"{path}: profiles[{index}]"
        profiles.append(
            ProfileEntry(
                id=_required_string(raw, "id", context),
                description=_required_string(raw, "description", context),
                pytest_mark_expression=_optional_string(
                    raw, "pytest_mark_expression", context
                ),
            )
        )

    suites = []
    for index, raw in enumerate(_object_list(data, "suites", path)):
        context = f"{path}: suites[{index}]"
        executor = _required_string(raw, "executor", context)
        executor_defaults = raw_defaults.get(executor, {})
        if not isinstance(executor_defaults, dict):
            raise ManifestError(
                f"{path}: suite_defaults.{executor} must be an object"
            )
        suites.append(
            SuiteEntry(
                id=_required_string(raw, "id", context),
                module=_required_string(raw, "module", context),
                executor=executor,
                roots=_string_tuple(raw, "roots", context, required=True),
                profiles=_string_tuple_with_default(
                    raw,
                    "profiles",
                    context,
                    executor_defaults,
                    required=True,
                ),
                environment=_string_with_default(
                    raw, "environment", context, executor_defaults
                ),
                platforms=_string_tuple_with_default(
                    raw, "platforms", context, executor_defaults
                ),
                capabilities=_string_tuple_with_default(
                    raw, "capabilities", context, executor_defaults
                ),
            )
        )
    return tuple(profiles), tuple(suites), inventory, native_inventory


def load_catalog(repo_root: Path) -> RepositoryCatalog:
    modules = load_modules(repo_root)
    profiles, suites, inventory, native_inventory = load_profiles_and_suites(repo_root)
    return RepositoryCatalog(
        modules=modules,
        profiles=profiles,
        suites=suites,
        python_test_inventory=inventory,
        native_test_inventory=native_inventory,
    )


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


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def discover_python_tests(
    repo_root: Path,
    inventory: PythonTestInventory,
) -> tuple[str, ...]:
    exclude_roots = tuple(Path(path) for path in inventory.exclude_roots)
    excluded_names = set(inventory.exclude_directory_names)
    discovered = []

    for current, directory_names, file_names in os.walk(repo_root):
        current_path = Path(current)
        relative_current = current_path.relative_to(repo_root)
        kept_directories = []
        for directory_name in directory_names:
            relative = relative_current / directory_name
            if directory_name in excluded_names:
                continue
            if any(_is_within(relative, excluded) for excluded in exclude_roots):
                continue
            kept_directories.append(directory_name)
        directory_names[:] = kept_directories

        if any(_is_within(relative_current, excluded) for excluded in exclude_roots):
            continue
        for file_name in file_names:
            if any(fnmatch.fnmatch(file_name, pattern) for pattern in inventory.patterns):
                discovered.append((relative_current / file_name).as_posix())
    return tuple(sorted(discovered))


def _pytest_owners(test_path: str, suites: Iterable[SuiteEntry]) -> list[str]:
    path = Path(test_path)
    owners = []
    for suite in suites:
        if suite.executor != "pytest":
            continue
        for root in suite.roots:
            if _is_within(path, Path(root)):
                owners.append(suite.id)
                break
    return sorted(owners)


def discover_native_tests(
    repo_root: Path,
    inventory: NativeTestInventory,
) -> tuple[str, ...]:
    """Find repository-owned C/C++ test translation units below test directories."""
    exclude_roots = tuple(Path(path) for path in inventory.exclude_roots)
    excluded_names = set(inventory.exclude_directory_names)
    discovered = []
    for current, directory_names, file_names in os.walk(repo_root):
        current_path = Path(current)
        relative_current = current_path.relative_to(repo_root)
        directory_names[:] = [
            name
            for name in directory_names
            if name not in excluded_names
            and not any(_is_within(relative_current / name, excluded) for excluded in exclude_roots)
        ]
        if any(_is_within(relative_current, excluded) for excluded in exclude_roots):
            continue
        if "tests" not in {part.lower() for part in relative_current.parts}:
            continue
        for file_name in file_names:
            if (
                Path(file_name).suffix.lower() in inventory.extensions
                and any(fnmatch.fnmatch(file_name, pattern) for pattern in inventory.patterns)
            ):
                discovered.append((relative_current / file_name).as_posix())
    return tuple(sorted(discovered))


def _native_owners(test_path: str, suites: Iterable[SuiteEntry]) -> list[str]:
    path = Path(test_path)
    return sorted(
        suite.id
        for suite in suites
        if suite.executor == "ctest"
        and any(_is_within(path, Path(root)) for root in suite.roots)
    )


def _ctest_labels(raw_test: object) -> tuple[str, ...]:
    if not isinstance(raw_test, dict):
        return ()
    properties = raw_test.get("properties")
    if not isinstance(properties, list):
        return ()
    for property_entry in properties:
        if not isinstance(property_entry, dict) or property_entry.get("name") != "LABELS":
            continue
        value = property_entry.get("value")
        if isinstance(value, list) and all(isinstance(label, str) for label in value):
            return tuple(value)
    return ()


def validate_ctest_inventory(
    catalog: RepositoryCatalog, ctest_payload: object
) -> list[str]:
    """Validate CTest's configured registrations against native-suite metadata."""
    if not isinstance(ctest_payload, dict):
        return ["CTest JSON root must be an object"]
    tests = ctest_payload.get("tests")
    if not isinstance(tests, list):
        return ["CTest JSON must contain a tests array"]

    errors = []
    observed_modules = set()
    for raw_test in tests:
        name = raw_test.get("name") if isinstance(raw_test, dict) else None
        test_name = name if isinstance(name, str) else "<unnamed>"
        labels = _ctest_labels(raw_test)
        module_labels = [label for label in labels if label.startswith("termin:module:")]
        tier_labels = [label for label in labels if label.startswith("termin:tier:")]
        capability_labels = [
            label for label in labels if label.startswith("termin:capability:")
        ]
        if len(module_labels) != 1:
            errors.append(f"CTest test {test_name}: expected one termin:module label")
        else:
            observed_modules.add(module_labels[0].removeprefix("termin:module:"))
        if len(tier_labels) != 1:
            errors.append(f"CTest test {test_name}: expected one termin:tier label")
        if not capability_labels:
            errors.append(f"CTest test {test_name}: missing termin:capability label")

    for suite in catalog.suites:
        if suite.executor == "ctest" and suite.module not in observed_modules:
            errors.append(f"{suite.id}: no configured CTest registration for module {suite.module}")
    return errors


def validate_native_compile_inventory(
    repo_root: Path,
    catalog: RepositoryCatalog,
    compile_commands: object,
    profile: str,
    capabilities: Iterable[str],
) -> list[str]:
    """Ensure each declared native test translation unit reached CMake's graph."""
    if not isinstance(compile_commands, list):
        return ["compile_commands.json root must be an array"]
    compiled_sources = set()
    for entry in compile_commands:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            continue
        source = Path(entry["file"])
        try:
            compiled_sources.add(source.resolve().relative_to(repo_root).as_posix())
        except ValueError:
            continue
    enabled_capabilities = set(capabilities)
    classifications = {
        entry.path: entry
        for entry in catalog.native_test_inventory.source_classifications
    }
    errors = []
    for source in discover_native_tests(repo_root, catalog.native_test_inventory):
        classification = classifications.get(source)
        required_in_configuration = classification is None or (
            profile in classification.profiles
            and set(classification.capabilities) <= enabled_capabilities
        )
        if required_in_configuration and source not in compiled_sources:
            errors.append(
                f"native test source is absent from configured CMake graph: {source}"
            )
    return errors


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
    inventory = catalog.python_test_inventory
    for pattern in inventory.patterns:
        if "/" in pattern or "\\" in pattern:
            errors.append(f"Python test pattern must match file names only: {pattern}")
    for exclude_root in inventory.exclude_roots:
        if not _is_repository_relative(exclude_root):
            errors.append(
                f"Python test exclude root must be repository-relative: {exclude_root}"
            )
    for directory_name in inventory.exclude_directory_names:
        if Path(directory_name).name != directory_name or directory_name in ("", ".", ".."):
            errors.append(
                "Python test excluded directory must be a single name: "
                f"{directory_name}"
            )
    native_inventory = catalog.native_test_inventory
    for pattern in native_inventory.patterns:
        if "/" in pattern or "\\" in pattern:
            errors.append(f"Native test pattern must match file names only: {pattern}")
    for extension in native_inventory.extensions:
        if not extension.startswith(".") or len(extension) == 1:
            errors.append(f"Native test extension must start with '.': {extension}")
    for exclude_root in native_inventory.exclude_roots:
        if not _is_repository_relative(exclude_root):
            errors.append(
                f"Native test exclude root must be repository-relative: {exclude_root}"
            )
    for directory_name in native_inventory.exclude_directory_names:
        if Path(directory_name).name != directory_name or directory_name in ("", ".", ".."):
            errors.append(
                "Native test excluded directory must be a single name: "
                f"{directory_name}"
            )
    native_classifications = native_inventory.source_classifications
    for source in _duplicates(entry.path for entry in native_classifications):
        errors.append(f"duplicate native source classification: {source}")
    native_test_paths = set(discover_native_tests(repo_root, native_inventory))
    for classification in native_classifications:
        if not _is_repository_relative(classification.path):
            errors.append(
                "Native source classification path must be repository-relative: "
                f"{classification.path}"
            )
        elif classification.path not in native_test_paths:
            errors.append(
                "Native source classification does not name a discovered native test: "
                f"{classification.path}"
            )
        for profile in classification.profiles:
            if profile not in profile_ids:
                errors.append(
                    f"Native source classification {classification.path}: "
                    f"unknown profile: {profile}"
                )
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

    if not errors:
        for test_path in discover_python_tests(repo_root, inventory):
            owners = _pytest_owners(test_path, catalog.suites)
            if not owners:
                errors.append(f"orphan Python test: {test_path}")
            elif len(owners) > 1:
                errors.append(
                    f"Python test has multiple suite owners: {test_path}: "
                    + ", ".join(owners)
                )
        for test_path in discover_native_tests(repo_root, native_inventory):
            owners = _native_owners(test_path, catalog.suites)
            if not owners:
                errors.append(f"orphan native test: {test_path}")
            elif len(owners) > 1:
                errors.append(
                    f"Native test has multiple suite owners: {test_path}: "
                    + ", ".join(owners)
                )
    return errors


def catalog_as_json(catalog: RepositoryCatalog) -> dict[str, object]:
    return {
        "schema": 1,
        "modules": [asdict(module) for module in catalog.modules],
        "profiles": [asdict(profile) for profile in catalog.profiles],
        "suites": [asdict(suite) for suite in catalog.suites],
        "python_test_inventory": asdict(catalog.python_test_inventory),
        "native_test_inventory": asdict(catalog.native_test_inventory),
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


def _host_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _safe_suite_directory(suite_id: str) -> str:
    return "".join(
        character if character.isalnum() or character in "_.-" else "-"
        for character in suite_id
    )


def run_pytest_plan(
    repo_root: Path,
    catalog: RepositoryCatalog,
    profile_id: str,
    platform: str,
    python_executable: str,
    python_arguments: tuple[str, ...] = (),
) -> int:
    profile_by_id = {profile.id: profile for profile in catalog.profiles}
    profile = profile_by_id.get(profile_id)
    if profile is None:
        raise ManifestError(f"unknown profile: {profile_id}")

    plan = build_plan(catalog, profile_id, platform)
    pytest_suites = [
        suite for suite in plan["suites"] if suite["executor"] == "pytest"
    ]
    run_root = repo_root / "build" / "pytest-temp" / uuid.uuid4().hex
    cache_root = repo_root / "build" / "pytest-cache"
    run_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    print(f"Pytest execution plan: {profile_id} / {platform}")
    print(f"Pytest suites: {len(pytest_suites)}")
    print(f"Pytest temp root: {run_root}")

    failures = []
    environment = os.environ.copy()
    environment["TEMP"] = str(run_root)
    environment["TMP"] = str(run_root)
    environment["TMPDIR"] = str(run_root)
    for suite in pytest_suites:
        suite_id = suite["id"]
        safe_suite_id = _safe_suite_directory(suite_id)
        suite_temp = run_root / safe_suite_id
        suite_cache = cache_root / safe_suite_id
        suite_temp.mkdir(parents=True, exist_ok=True)
        suite_cache.mkdir(parents=True, exist_ok=True)

        command = [python_executable, *python_arguments, "-m", "pytest"]
        if profile.pytest_mark_expression is not None:
            command.extend(["-m", profile.pytest_mark_expression])
        command.extend(suite["roots"])
        command.extend(
            [
                "--basetemp",
                str(suite_temp),
                "-o",
                f"cache_dir={suite_cache}",
                "-v",
            ]
        )

        print("")
        print("----------------------------------------")
        print(f"  {suite_id}")
        print("----------------------------------------")
        sys.stdout.flush()
        result = subprocess.run(
            command,
            cwd=repo_root,
            env=environment,
            check=False,
        )
        if result.returncode != 0:
            failures.append(suite_id)

    if failures:
        print("")
        print("Python suite failures:", file=sys.stderr)
        for suite_id in failures:
            print(f"  - {suite_id}", file=sys.stderr)
        return 1
    return 0


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


def _cmd_check_ctest(
    repo_root: Path,
    build_dir: Path,
    profile: str,
    capabilities: tuple[str, ...],
) -> int:
    catalog = _load_valid_catalog(repo_root)
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ManifestError(
            "CTest JSON discovery failed for "
            f"{build_dir}: {result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid CTest JSON from {build_dir}: {exc}") from exc
    compile_commands_path = build_dir / "compile_commands.json"
    try:
        compile_commands = json.loads(compile_commands_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(
            f"compile commands are missing: {compile_commands_path}; configure with "
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid compile commands in {compile_commands_path}: {exc}") from exc
    errors = validate_ctest_inventory(catalog, payload)
    errors.extend(
        validate_native_compile_inventory(
            repo_root, catalog, compile_commands, profile, capabilities
        )
    )
    if errors:
        raise ManifestError("\n".join(errors))
    print("CTest inventory OK")
    return 0


def _cmd_run(
    repo_root: Path,
    profile: str,
    platform: str | None,
    python_executable: str,
    python_arguments: tuple[str, ...],
) -> int:
    resolved_platform = platform or _host_platform()
    return run_pytest_plan(
        repo_root,
        _load_valid_catalog(repo_root),
        profile,
        resolved_platform,
        python_executable,
        python_arguments,
    )


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

    ctest_parser = subparsers.add_parser(
        "check-ctest", help="Validate configured CTest labels and native inventory."
    )
    ctest_parser.add_argument("--build-dir", type=Path, required=True)
    ctest_parser.add_argument("--profile", required=True)
    ctest_parser.add_argument("--capability", action="append", default=[])

    run_parser = subparsers.add_parser(
        "run", help="Execute planner-selected automatic Python suites."
    )
    run_parser.add_argument("profile")
    run_parser.add_argument("--platform", choices=sorted(SUPPORTED_PLATFORMS))
    run_parser.add_argument("--python", default=sys.executable, dest="python_executable")
    run_parser.add_argument("--python-arg", action="append", default=[])

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
        if args.command == "check-ctest":
            return _cmd_check_ctest(
                repo_root,
                args.build_dir.resolve(),
                args.profile,
                tuple(args.capability),
            )
        if args.command == "run":
            return _cmd_run(
                repo_root,
                args.profile,
                args.platform,
                args.python_executable,
                tuple(args.python_arg),
            )
    except (ManifestError, OSError) as exc:
        for line in str(exc).splitlines():
            print(f"ERROR: {line}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
