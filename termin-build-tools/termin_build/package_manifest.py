"""Utilities for the Termin SDK Python package manifest."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_MANIFEST = Path("build-system/packages.json")
_PACKAGE_LIST_RE = re.compile(
    r"TERMIN_PYTHON_PACKAGES=\((?P<body>.*?)\)",
    re.DOTALL,
)


@dataclass(frozen=True)
class NativeExtension:
    extension: str
    target: str
    optional: bool
    features: tuple[str, ...]


@dataclass(frozen=True)
class PackageEntry:
    path: str
    distribution: str
    features: tuple[str, ...]
    native_extensions: tuple[NativeExtension, ...]


def repo_root_from(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / DEFAULT_MANIFEST).is_file():
            return candidate
    raise FileNotFoundError(
        f"Cannot find {DEFAULT_MANIFEST} from {start.resolve()}"
    )


def load_manifest(repo_root: Path) -> list[PackageEntry]:
    manifest_path = repo_root / DEFAULT_MANIFEST
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    packages = []
    for raw_package in data["packages"]:
        native_extensions = []
        for raw_extension in raw_package.get("native_extensions", []):
            native_extensions.append(
                NativeExtension(
                    extension=raw_extension["extension"],
                    target=raw_extension["target"],
                    optional=bool(raw_extension.get("optional", False)),
                    features=tuple(raw_extension.get("features", [])),
                )
            )
        packages.append(
            PackageEntry(
                path=raw_package["path"],
                distribution=raw_package["distribution"],
                features=tuple(raw_package.get("features", [])),
                native_extensions=tuple(native_extensions),
            )
        )
    return packages


def package_paths(packages: Iterable[PackageEntry]) -> list[str]:
    return [package.path for package in packages]


def read_shell_package_list(repo_root: Path) -> list[str]:
    bash = shutil.which("bash")
    if bash:
        script = repo_root / "scripts" / "termin-python-packages.sh"
        command = (
            f"source {str(script)!r}; "
            'printf "%s\\n" "${TERMIN_PYTHON_PACKAGES[@]}"'
        )
        result = subprocess.run(
            [bash, "-lc", command],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_root,
        )
        if result.returncode == 0:
            return [line for line in result.stdout.splitlines() if line]

    source = repo_root / "scripts" / "termin-python-packages.sh"
    text = source.read_text(encoding="utf-8")
    match = _PACKAGE_LIST_RE.search(text)
    if match is None:
        raise ValueError(f"Cannot find TERMIN_PYTHON_PACKAGES in {source}")
    paths = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            line = line[:-1].rstrip()
        paths.append(line.strip("\"'"))
    return paths


def setup_extensions(package_dir: Path) -> set[str]:
    setup_py = package_dir / "setup.py"
    if not setup_py.is_file():
        return set()
    tree = ast.parse(setup_py.read_text(encoding="utf-8"), filename=str(setup_py))
    extensions = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "Extension":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            extensions.add(first_arg.value)
    return extensions


def validate(repo_root: Path) -> list[str]:
    errors = []
    packages = load_manifest(repo_root)
    paths = package_paths(packages)

    duplicates = sorted({path for path in paths if paths.count(path) > 1})
    for path in duplicates:
        errors.append(f"duplicate package path in manifest: {path}")

    try:
        shell_paths = read_shell_package_list(repo_root)
    except Exception as e:
        errors.append(str(e))
        shell_paths = []
    if shell_paths and shell_paths != paths:
        errors.append(
            "manifest package order does not match scripts/termin-python-packages.sh"
        )

    for package in packages:
        package_dir = repo_root / package.path
        if not package_dir.is_dir():
            errors.append(f"package path does not exist: {package.path}")
            continue
        setup_py = package_dir / "setup.py"
        pyproject_toml = package_dir / "pyproject.toml"
        if not setup_py.is_file() and not pyproject_toml.is_file():
            errors.append(
                f"package has neither setup.py nor pyproject.toml: {package.path}"
            )
        setup_extension_names = setup_extensions(package_dir)
        for native_extension in package.native_extensions:
            if native_extension.extension not in setup_extension_names:
                errors.append(
                    f"{package.path}: native extension "
                    f"{native_extension.extension} is missing from setup.py"
                )

    return errors


def _cmd_list(repo_root: Path) -> int:
    for package in load_manifest(repo_root):
        print(package.path)
    return 0


def _cmd_check(repo_root: Path) -> int:
    errors = validate(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Package manifest OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to auto-discovery from cwd.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the manifest against current package scripts/setup.py files.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print package paths in manifest order.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from(Path.cwd())
    if args.check:
        return _cmd_check(repo_root)
    if args.list:
        return _cmd_list(repo_root)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
