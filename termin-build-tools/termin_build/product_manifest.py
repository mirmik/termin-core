"""Typed product-closure manifests and repository validation."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .package_manifest import PackageEntry, load_manifest as load_package_manifest


PRODUCT_MANIFEST_DIR = Path("build-system/products")
_MODULE_ROLES = frozenset(
    {"application", "binding-runtime", "build-tooling", "runtime"}
)


class ProductManifestError(ValueError):
    """Raised when a product manifest does not match its closed schema."""


@dataclass(frozen=True)
class ProductModule:
    path: str
    role: str
    internal_dependencies: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    inactive_dependencies: tuple[str, ...]
    native_targets: tuple[str, ...]
    inactive_native_targets: tuple[str, ...]
    python_distribution: str | None


@dataclass(frozen=True)
class ProductExternalModule:
    path: str
    python_distribution: str | None


@dataclass(frozen=True)
class ProductExternalProduct:
    id: str
    modules: tuple[ProductExternalModule, ...]
    cmake_packages: tuple[str, ...]


@dataclass(frozen=True)
class ProductPythonRuntime:
    abi: str
    owner: str
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class ProductManifest:
    id: str
    description: str
    modules: tuple[ProductModule, ...]
    external_products: tuple[ProductExternalProduct, ...]
    cmake_packages: tuple[str, ...]
    python_runtime: ProductPythonRuntime
    test_suites: tuple[str, ...]
    smoke_fixtures: tuple[str, ...]
    resources: tuple[str, ...]
    forbidden_dependency_roots: tuple[str, ...]
    forbidden_artifact_markers: tuple[str, ...]

    @property
    def module_paths(self) -> tuple[str, ...]:
        return tuple(module.path for module in self.modules)

    @property
    def python_distributions(self) -> tuple[str, ...]:
        return tuple(
            module.python_distribution
            for module in self.modules
            if module.python_distribution is not None
        )


def load_product_manifest(repo_root: Path, product_id: str) -> ProductManifest:
    path = repo_root / PRODUCT_MANIFEST_DIR / f"{product_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProductManifestError(f"product manifest does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ProductManifestError(f"{path}: invalid JSON: {error}") from error
    return _parse_product_manifest(data, path)


def _parse_product_manifest(data: object, path: Path) -> ProductManifest:
    root = _object(data, str(path))
    schema = root.get("schema")
    if schema not in {1, 2}:
        raise ProductManifestError(f"{path}: unsupported schema {schema!r}")
    _require_keys(
        root,
        {
            "schema",
            "id",
            "description",
            "modules",
            "cmake_packages",
            "python_runtime",
            "test_suites",
            "smoke_fixtures",
            "resources",
            "forbidden_dependency_roots",
            "forbidden_artifact_markers",
        },
        str(path),
        allowed={
            "schema",
            "id",
            "description",
            "modules",
            "external_products",
            "cmake_packages",
            "python_runtime",
            "test_suites",
            "smoke_fixtures",
            "resources",
            "forbidden_dependency_roots",
            "forbidden_artifact_markers",
        },
    )
    if schema == 2 and "external_products" not in root:
        raise ProductManifestError(f"{path}: schema 2 requires external_products")

    product_id = _non_empty_string(root["id"], f"{path}: id")
    if path.stem != product_id:
        raise ProductManifestError(
            f"{path}: product id {product_id!r} must match filename {path.stem!r}"
        )

    raw_modules = _list(root["modules"], f"{path}: modules")
    modules: list[ProductModule] = []
    for index, value in enumerate(raw_modules):
        context = f"{path}: modules[{index}]"
        raw = _object(value, context)
        allowed = {
            "path",
            "role",
            "internal_dependencies",
            "external_dependencies",
            "inactive_dependencies",
            "native_targets",
            "inactive_native_targets",
            "python_distribution",
        }
        required = {"path", "role", "internal_dependencies", "native_targets"}
        if schema == 2:
            required.update({"external_dependencies", "inactive_dependencies"})
        _require_keys(raw, required, context, allowed=allowed)
        role = _non_empty_string(raw["role"], f"{context}.role")
        if role not in _MODULE_ROLES:
            expected = ", ".join(sorted(_MODULE_ROLES))
            raise ProductManifestError(
                f"{context}.role: unsupported value {role!r}; expected {expected}"
            )
        distribution = raw.get("python_distribution")
        if distribution is not None:
            distribution = _non_empty_string(
                distribution, f"{context}.python_distribution"
            )
        modules.append(
            ProductModule(
                path=_relative_path(raw["path"], f"{context}.path"),
                role=role,
                internal_dependencies=_string_tuple(
                    raw["internal_dependencies"],
                    f"{context}.internal_dependencies",
                    relative_paths=True,
                ),
                external_dependencies=_string_tuple(
                    raw.get("external_dependencies", []),
                    f"{context}.external_dependencies",
                    relative_paths=True,
                ),
                inactive_dependencies=_string_tuple(
                    raw.get("inactive_dependencies", []),
                    f"{context}.inactive_dependencies",
                    relative_paths=True,
                ),
                native_targets=_string_tuple(
                    raw["native_targets"], f"{context}.native_targets"
                ),
                inactive_native_targets=_string_tuple(
                    raw.get("inactive_native_targets", []),
                    f"{context}.inactive_native_targets",
                ),
                python_distribution=distribution,
            )
        )

    external_products: list[ProductExternalProduct] = []
    for product_index, value in enumerate(
        _list(root.get("external_products", []), f"{path}: external_products")
    ):
        context = f"{path}: external_products[{product_index}]"
        raw_product = _object(value, context)
        _require_keys(raw_product, {"id", "modules", "cmake_packages"}, context)
        external_modules: list[ProductExternalModule] = []
        for module_index, module_value in enumerate(
            _list(raw_product["modules"], f"{context}.modules")
        ):
            module_context = f"{context}.modules[{module_index}]"
            raw_module = _object(module_value, module_context)
            _require_keys(
                raw_module,
                {"path", "python_distribution"},
                module_context,
            )
            distribution = raw_module["python_distribution"]
            if distribution is not None:
                distribution = _non_empty_string(
                    distribution,
                    f"{module_context}.python_distribution",
                )
            external_modules.append(
                ProductExternalModule(
                    path=_relative_path(raw_module["path"], f"{module_context}.path"),
                    python_distribution=distribution,
                )
            )
        external_products.append(
            ProductExternalProduct(
                id=_non_empty_string(raw_product["id"], f"{context}.id"),
                modules=tuple(external_modules),
                cmake_packages=_string_tuple(
                    raw_product["cmake_packages"], f"{context}.cmake_packages"
                ),
            )
        )

    runtime_context = f"{path}: python_runtime"
    raw_runtime = _object(root["python_runtime"], runtime_context)
    _require_keys(raw_runtime, {"abi", "owner", "inputs"}, runtime_context)
    runtime = ProductPythonRuntime(
        abi=_non_empty_string(raw_runtime["abi"], f"{runtime_context}.abi"),
        owner=_non_empty_string(raw_runtime["owner"], f"{runtime_context}.owner"),
        inputs=_string_tuple(
            raw_runtime["inputs"], f"{runtime_context}.inputs", relative_paths=True
        ),
    )

    return ProductManifest(
        id=product_id,
        description=_non_empty_string(root["description"], f"{path}: description"),
        modules=tuple(modules),
        external_products=tuple(external_products),
        cmake_packages=_string_tuple(root["cmake_packages"], f"{path}: cmake_packages"),
        python_runtime=runtime,
        test_suites=_string_tuple(root["test_suites"], f"{path}: test_suites"),
        smoke_fixtures=_string_tuple(
            root["smoke_fixtures"], f"{path}: smoke_fixtures", relative_paths=True
        ),
        resources=_string_tuple(
            root["resources"], f"{path}: resources", relative_paths=True
        ),
        forbidden_dependency_roots=_string_tuple(
            root["forbidden_dependency_roots"],
            f"{path}: forbidden_dependency_roots",
            relative_paths=True,
        ),
        forbidden_artifact_markers=_string_tuple(
            root["forbidden_artifact_markers"],
            f"{path}: forbidden_artifact_markers",
        ),
    )


def validate_product_manifest(repo_root: Path, manifest: ProductManifest) -> list[str]:
    errors: list[str] = []
    module_paths = manifest.module_paths
    module_set = set(module_paths)
    forbidden = set(manifest.forbidden_dependency_roots)
    external_product_ids = tuple(product.id for product in manifest.external_products)
    external_modules = tuple(
        module
        for product in manifest.external_products
        for module in product.modules
    )
    external_module_paths = tuple(module.path for module in external_modules)
    external_module_set = set(external_module_paths)
    external_cmake_packages = tuple(
        package
        for product in manifest.external_products
        for package in product.cmake_packages
    )

    _append_duplicates(errors, "module path", module_paths)
    _append_duplicates(errors, "external product id", external_product_ids)
    _append_duplicates(errors, "external module path", external_module_paths)
    _append_duplicates(errors, "external CMake package", external_cmake_packages)
    _append_duplicates(errors, "Python distribution", manifest.python_distributions)
    _append_duplicates(errors, "CMake package", manifest.cmake_packages)
    _append_duplicates(errors, "test suite", manifest.test_suites)
    _append_duplicates(
        errors, "forbidden artifact marker", manifest.forbidden_artifact_markers
    )

    overlap = sorted(module_set & forbidden)
    if overlap:
        errors.append("product modules are also forbidden: " + ", ".join(overlap))
    external_overlap = sorted(module_set & external_module_set)
    if external_overlap:
        errors.append(
            "product modules are also external: " + ", ".join(external_overlap)
        )
    valid_runtime_owners = {manifest.id, *external_product_ids}
    if manifest.python_runtime.owner not in valid_runtime_owners:
        errors.append(
            "Python runtime owner must be the product or a declared external "
            f"product, got {manifest.python_runtime.owner!r}"
        )

    packages = load_package_manifest(repo_root)
    packages_by_path = {package.path: package for package in packages}
    package_sources = _package_sources(repo_root)
    modules_by_path = _repository_modules(repo_root, packages)
    module_paths_by_id = {
        module_id: module_path for module_path, module_id in modules_by_path.items()
    }
    cmake_internal_packages = {
        path.replace("-", "_"): path for path in modules_by_path
    }
    test_suites = _test_suites(repo_root)

    for external_module in external_modules:
        package = packages_by_path.get(external_module.path)
        if package is None:
            errors.append(
                f"external module is absent from package catalog: {external_module.path}"
            )
            continue
        if package_sources[external_module.path] == "repository":
            errors.append(
                f"external module is repository-owned: {external_module.path}"
            )
        if package.distribution != external_module.python_distribution:
            errors.append(
                f"{external_module.path}: external distribution "
                f"{external_module.python_distribution!r} does not match package "
                f"catalog {package.distribution!r}"
            )

    for module in manifest.modules:
        module_dir = repo_root / module.path
        if not module_dir.is_dir():
            errors.append(f"module path does not exist: {module.path}")
        if module.path not in modules_by_path:
            errors.append(f"module is absent from repository catalog: {module.path}")

        declared_dependencies = set(module.internal_dependencies)
        unknown_dependencies = sorted(declared_dependencies - module_set)
        if unknown_dependencies:
            errors.append(
                f"{module.path}: internal dependencies outside product closure: "
                + ", ".join(unknown_dependencies)
            )
        forbidden_dependencies = sorted(declared_dependencies & forbidden)
        if forbidden_dependencies:
            errors.append(
                f"{module.path}: forbidden dependencies: "
                + ", ".join(forbidden_dependencies)
            )
        external_dependencies = set(module.external_dependencies)
        unknown_external = sorted(external_dependencies - external_module_set)
        if unknown_external:
            errors.append(
                f"{module.path}: external dependencies outside declared products: "
                + ", ".join(unknown_external)
            )
        forbidden_external = sorted(external_dependencies & forbidden)
        if forbidden_external:
            errors.append(
                f"{module.path}: forbidden external dependencies: "
                + ", ".join(forbidden_external)
            )
        inactive_dependencies = set(module.inactive_dependencies)
        unknown_inactive = sorted(inactive_dependencies - modules_by_path.keys())
        if unknown_inactive:
            errors.append(
                f"{module.path}: inactive dependencies outside repository catalog: "
                + ", ".join(unknown_inactive)
            )
        dependency_sets = {
            "internal": declared_dependencies,
            "external": external_dependencies,
            "inactive": inactive_dependencies,
        }
        dependency_items = tuple(dependency_sets.items())
        for index, (left_name, left) in enumerate(dependency_items):
            for right_name, right in dependency_items[index + 1 :]:
                dependency_overlap = sorted(left & right)
                if dependency_overlap:
                    errors.append(
                        f"{module.path}: dependencies are both {left_name} and "
                        f"{right_name}: " + ", ".join(dependency_overlap)
                    )

        package = packages_by_path.get(module.path)
        if module.python_distribution is not None:
            if package is None:
                errors.append(
                    f"{module.path}: Python distribution {module.python_distribution!r} "
                    "has no package catalog entry"
                )
            elif package.distribution != module.python_distribution:
                errors.append(
                    f"{module.path}: product distribution {module.python_distribution!r} "
                    f"does not match package catalog {package.distribution!r}"
                )

        discovered = _discover_internal_dependencies(
            repo_root, module, packages_by_path, cmake_internal_packages
        )
        accounted_dependencies = (
            declared_dependencies | external_dependencies | inactive_dependencies
        )
        undeclared = sorted(discovered - accounted_dependencies)
        stale = sorted(declared_dependencies - discovered)
        stale_external = sorted(external_dependencies - discovered)
        stale_inactive = sorted(inactive_dependencies - discovered)
        if undeclared:
            errors.append(
                f"{module.path}: discovered undeclared internal dependencies: "
                + ", ".join(undeclared)
            )
        if stale:
            errors.append(
                f"{module.path}: declared internal dependencies not found in metadata: "
                + ", ".join(stale)
            )
        if stale_external:
            errors.append(
                f"{module.path}: declared external dependencies not found in metadata: "
                + ", ".join(stale_external)
            )
        if stale_inactive:
            errors.append(
                f"{module.path}: declared inactive dependencies not found in metadata: "
                + ", ".join(stale_inactive)
            )

        discovered_targets = _discover_native_targets(module_dir)
        declared_targets = set(module.native_targets)
        inactive_targets = set(module.inactive_native_targets)
        overlap_targets = sorted(declared_targets & inactive_targets)
        if overlap_targets:
            errors.append(
                f"{module.path}: native targets are both active and inactive: "
                + ", ".join(overlap_targets)
            )
        accounted_targets = declared_targets | inactive_targets
        undeclared_targets = sorted(discovered_targets - accounted_targets)
        stale_targets = sorted(declared_targets - discovered_targets)
        stale_inactive_targets = sorted(inactive_targets - discovered_targets)
        if undeclared_targets:
            errors.append(
                f"{module.path}: discovered undeclared native targets: "
                + ", ".join(undeclared_targets)
            )
        if stale_targets:
            errors.append(
                f"{module.path}: declared native targets not found in CMake: "
                + ", ".join(stale_targets)
            )
        if stale_inactive_targets:
            errors.append(
                f"{module.path}: inactive native targets not found in CMake: "
                + ", ".join(stale_inactive_targets)
            )

    for suite in manifest.test_suites:
        owner = test_suites.get(suite)
        if owner is None:
            errors.append(f"unknown test suite: {suite}")
        elif module_paths_by_id.get(owner, owner) not in module_set:
            errors.append(
                f"test suite {suite} belongs to module outside product closure: {owner}"
            )
    for owned_path in (
        *manifest.python_runtime.inputs,
        *manifest.smoke_fixtures,
        *manifest.resources,
    ):
        if not (repo_root / owned_path).exists():
            errors.append(f"owned product path does not exist: {owned_path}")

    return errors


def product_python_packages(
    manifest: ProductManifest, packages: list[PackageEntry]
) -> list[PackageEntry]:
    by_distribution = {package.distribution: package for package in packages}
    missing = sorted(set(manifest.python_distributions) - by_distribution.keys())
    if missing:
        raise ProductManifestError(
            "product references unknown Python distributions: " + ", ".join(missing)
        )
    return [by_distribution[name] for name in manifest.python_distributions]


def validate_repository_product_manifests(repo_root: Path) -> list[str]:
    directory = repo_root / PRODUCT_MANIFEST_DIR
    if not directory.is_dir():
        return []
    errors: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            manifest = load_product_manifest(repo_root, path.stem)
        except ProductManifestError as error:
            errors.append(str(error))
            continue
        errors.extend(
            f"product {manifest.id}: {error}"
            for error in validate_product_manifest(repo_root, manifest)
        )
    return errors


def _repository_modules(
    repo_root: Path, packages: list[PackageEntry]
) -> dict[str, str]:
    path = repo_root / "build-system/modules.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {package.path: package.path for package in packages}
    for raw in data["modules"]:
        result[raw["path"]] = raw["id"]
    return result


def _package_sources(repo_root: Path) -> dict[str, str]:
    path = repo_root / "build-system/packages.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        raw["path"]: raw.get("source", "repository")
        for raw in data["packages"]
    }


def _test_suites(repo_root: Path) -> dict[str, str]:
    path = repo_root / "build-system/test-suites.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {raw["id"]: raw["module"] for raw in data["suites"]}


def _discover_internal_dependencies(
    repo_root: Path,
    module: ProductModule,
    packages_by_path: dict[str, PackageEntry],
    cmake_internal_packages: dict[str, str],
) -> set[str]:
    distribution_to_path = {
        package.distribution: package.path for package in packages_by_path.values()
    }
    discovered: set[str] = set()
    module_dir = repo_root / module.path

    setup_path = module_dir / "setup.py"
    if setup_path.is_file():
        for requirement in _setup_requirements(setup_path):
            dependency = distribution_to_path.get(_requirement_name(requirement))
            if dependency is not None and dependency != module.path:
                discovered.add(dependency)

    pyproject_path = module_dir / "pyproject.toml"
    if pyproject_path.is_file():
        try:
            import tomllib
        except ModuleNotFoundError as error:
            raise ProductManifestError(
                "product validation requires Python 3.11 or newer"
            ) from error
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        dependencies = data.get("project", {}).get("dependencies", [])
        if isinstance(dependencies, list):
            for requirement in dependencies:
                if not isinstance(requirement, str):
                    continue
                dependency = distribution_to_path.get(_requirement_name(requirement))
                if dependency is not None and dependency != module.path:
                    discovered.add(dependency)

    cmake_files = [module_dir / "CMakeLists.txt", module_dir / "python/CMakeLists.txt"]
    cmake_files.extend(sorted((module_dir / "cmake").glob("*.cmake*")))
    for cmake_path in cmake_files:
        if not cmake_path.is_file():
            continue
        text = cmake_path.read_text(encoding="utf-8")
        for package_name in re.findall(
            r"(?:termin_require_package|find_(?:dependency|package))\s*\(\s*([A-Za-z0-9_-]+)",
            text,
        ):
            dependency = cmake_internal_packages.get(package_name)
            if dependency is not None and dependency != module.path:
                discovered.add(dependency)
    return discovered


def _discover_native_targets(module_dir: Path) -> set[str]:
    cmake_files = [module_dir / "CMakeLists.txt", module_dir / "python/CMakeLists.txt"]
    cmake_files.extend(sorted((module_dir / "cmake").glob("*.cmake*")))
    variables: dict[str, str] = {}
    texts: list[str] = []
    for path in cmake_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        texts.append(text)
        for name, value in re.findall(
            r"set\s*\(\s*([A-Za-z0-9_]+)\s+\"([^\"]+)\"\s*\)", text
        ):
            variables[name] = value

    targets: set[str] = set()
    for text in texts:
        for match in re.finditer(
            r"(add_library|nanobind_add_module|nanobind_build_library|termin_[A-Za-z0-9_]+_add_tool)"
            r"\s*\(\s*(\"[^\"]+\"|[^\s\)]+)(?:\s+([^\s\)]+))?",
            text,
        ):
            function, raw_target, second = match.groups()
            if function == "add_library" and second == "ALIAS":
                continue
            target = raw_target.strip('"')
            variable_match = re.fullmatch(r"\$\{([A-Za-z0-9_]+)\}", target)
            if variable_match is not None:
                target = variables.get(variable_match.group(1), "")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.+-]*", target):
                targets.add(target)
    return targets


def _setup_requirements(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "setup":
            continue
        for keyword in node.keywords:
            if keyword.arg != "install_requires":
                continue
            if not isinstance(keyword.value, (ast.List, ast.Tuple)):
                return ()
            requirements: list[str] = []
            for element in keyword.value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    requirements.append(element.value)
            return tuple(requirements)
    return ()


def _requirement_name(requirement: str) -> str:
    return re.split(r"[<>=!~;\[\s]", requirement.strip(), maxsplit=1)[0]


def _append_duplicates(errors: list[str], label: str, values: tuple[str, ...]) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    for value in duplicates:
        errors.append(f"duplicate {label}: {value}")


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProductManifestError(f"{context}: expected object")
    return value


def _list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ProductManifestError(f"{context}: expected list")
    return value


def _require_keys(
    value: dict[str, object],
    required: set[str],
    context: str,
    *,
    allowed: set[str] | None = None,
) -> None:
    effective_allowed = required if allowed is None else allowed
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - effective_allowed)
    if missing:
        raise ProductManifestError(f"{context}: missing fields: {', '.join(missing)}")
    if unknown:
        raise ProductManifestError(f"{context}: unknown fields: {', '.join(unknown)}")


def _non_empty_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductManifestError(f"{context}: expected non-empty string")
    return value


def _relative_path(value: object, context: str) -> str:
    text = _non_empty_string(value, context)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or text != path.as_posix():
        raise ProductManifestError(f"{context}: expected normalized repository-relative path")
    return text


def _string_tuple(
    value: object,
    context: str,
    *,
    relative_paths: bool = False,
) -> tuple[str, ...]:
    values = _list(value, context)
    result: list[str] = []
    for index, item in enumerate(values):
        item_context = f"{context}[{index}]"
        result.append(
            _relative_path(item, item_context)
            if relative_paths
            else _non_empty_string(item, item_context)
        )
    return tuple(result)
