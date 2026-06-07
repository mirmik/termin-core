import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_MANIFEST = REPO_ROOT / "build-system" / "packages.json"


@dataclass(frozen=True)
class PackageMetadata:
    dist_name: str
    source_path: str
    install_requires: tuple[str, ...]


def _normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise AssertionError(f"Could not parse requirement: {requirement!r}")
    return _normalize_dist_name(match.group(1))


def _read_shared_package_list() -> list[str]:
    content = json.loads(PACKAGE_MANIFEST.read_text())
    return [package["path"] for package in content["packages"]]


def _literal_string_list(node: ast.AST | None) -> tuple[str, ...]:
    if node is None:
        return ()
    if not isinstance(node, (ast.List, ast.Tuple)):
        raise AssertionError("install_requires must be a literal list/tuple")

    values = []
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            raise AssertionError("install_requires entries must be literal strings")
        values.append(item.value)
    return tuple(values)


def _read_pyproject_metadata(source_path: str) -> PackageMetadata | None:
    pyproject_path = REPO_ROOT / source_path / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    content = pyproject_path.read_text()
    project_match = re.search(r"(?ms)^\[project\]\s*(.*?)(?:^\[|\Z)", content)
    if project_match is None:
        return None

    project_body = project_match.group(1)
    name_match = re.search(r'(?m)^name\s*=\s*"([^"]+)"', project_body)
    if name_match is None:
        return None

    dependencies = ()
    dependencies_match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", project_body)
    if dependencies_match is not None:
        dependencies = tuple(re.findall(r'"([^"]+)"', dependencies_match.group(1)))

    return PackageMetadata(
        dist_name=name_match.group(1),
        source_path=source_path,
        install_requires=dependencies,
    )


def _read_setup_metadata(source_path: str) -> PackageMetadata | None:
    setup_path = REPO_ROOT / source_path / "setup.py"
    if not setup_path.exists():
        return None

    tree = ast.parse(setup_path.read_text(), filename=str(setup_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "setup":
            continue

        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}
        name_node = keywords.get("name")
        assert isinstance(name_node, ast.Constant), f"{source_path}: setup(name=...) must be literal"
        assert isinstance(name_node.value, str), f"{source_path}: setup(name=...) must be string"

        return PackageMetadata(
            dist_name=name_node.value,
            source_path=source_path,
            install_requires=_literal_string_list(keywords.get("install_requires")),
        )

    raise AssertionError(f"{source_path}: setup(...) call not found")


def test_shared_python_package_list_is_topological():
    package_paths = _read_shared_package_list()
    metadata = []
    for source_path in package_paths:
        package_metadata = (
            _read_setup_metadata(source_path)
            or _read_pyproject_metadata(source_path)
        )
        assert package_metadata is not None, (
            f"{source_path} is listed but has no setup.py or [project] metadata"
        )
        metadata.append(package_metadata)

    package_by_name = {}
    for index, package in enumerate(metadata):
        normalized_name = _normalize_dist_name(package.dist_name)
        assert normalized_name not in package_by_name, (
            f"Duplicate distribution name {package.dist_name!r} in shared package list"
        )
        package_by_name[normalized_name] = (index, package)

    violations = []
    for package_index, package in enumerate(metadata):
        for requirement in package.install_requires:
            dependency_name = _requirement_name(requirement)
            dependency = package_by_name.get(dependency_name)
            if dependency is None:
                continue

            dependency_index, dependency_package = dependency
            if dependency_index > package_index:
                violations.append(
                    f"{package.source_path} depends on {dependency_package.source_path}, "
                    f"but {dependency_package.source_path} is listed later"
                )

    assert not violations, "Invalid TERMIN_PYTHON_PACKAGES order:\n" + "\n".join(violations)
