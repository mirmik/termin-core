"""Termin SDK build orchestration helpers."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .package_manifest import load_manifest, repo_root_from


EXPECTED_SUBMODULE_FILES = {
    "termin-thirdparty/manifold": ("CMakeLists.txt",),
    "termin-thirdparty/clipper2": ("CPP/CMakeLists.txt",),
    "termin-thirdparty/guard": ("guard_c.h", "guard_main.h"),
    "termin-thirdparty/vulkan-memory-allocator": ("include/vk_mem_alloc.h",),
    "termin-thirdparty/openxr-sdk": ("include/openxr/openxr.h",),
    "termin-thirdparty/recastnavigation": (
        "Recast/CMakeLists.txt",
        "Detour/CMakeLists.txt",
    ),
}


@dataclass(frozen=True)
class DoctorProfile:
    name: str
    submodules: tuple[str, ...]
    needs_cmake: bool = True
    needs_git: bool = True
    needs_nanobind: bool = False


PROFILES = {
    "sdk-cpp": DoctorProfile(
        name="sdk-cpp",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/recastnavigation",
        ),
    ),
    "sdk-bindings": DoctorProfile(
        name="sdk-bindings",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/recastnavigation",
        ),
        needs_nanobind=True,
    ),
    "cpp-tests": DoctorProfile(
        name="cpp-tests",
        submodules=(
            "termin-thirdparty/manifold",
            "termin-thirdparty/clipper2",
            "termin-thirdparty/guard",
            "termin-thirdparty/recastnavigation",
        ),
    ),
}


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _submodule_ready(repo_root: Path, relative_path: str) -> bool:
    full_path = repo_root / relative_path
    if not full_path.is_dir():
        return False
    expected_files = EXPECTED_SUBMODULE_FILES.get(relative_path)
    if expected_files:
        return all((full_path / expected).exists() for expected in expected_files)
    try:
        next(full_path.iterdir())
    except StopIteration:
        return False
    return True


def missing_submodules(repo_root: Path, paths: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for path in paths:
        normalized_path = _normalize_path(path)
        if normalized_path in seen:
            continue
        seen.add(normalized_path)
        normalized.append(normalized_path)
    return [
        path for path in normalized
        if not _submodule_ready(repo_root, path)
    ]


def ensure_submodules(repo_root: Path, paths: list[str]) -> int:
    missing = missing_submodules(repo_root, paths)
    if not missing:
        return 0
    if shutil.which("git") is None:
        print("ERROR: required git submodules are missing and git was not found:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    print("Initializing missing third-party submodules:")
    for path in missing:
        print(f"  - {path}")
    result = subprocess.run(
        ["git", "-C", str(repo_root), "submodule", "update", "--init", "--recursive", "--", *missing],
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    still_missing = missing_submodules(repo_root, missing)
    if still_missing:
        print("ERROR: required git submodules are still missing after initialization:", file=sys.stderr)
        for path in still_missing:
            print(f"  - {path}", file=sys.stderr)
        return 1
    return 0


def _tool_error(tool: str) -> str | None:
    if shutil.which(tool) is None:
        return f"required tool not found in PATH: {tool}"
    return None


def _nanobind_error() -> str | None:
    try:
        import nanobind  # noqa: F401
    except Exception as e:
        return f"nanobind is not importable for {sys.executable}: {e}"
    return None


def _pip_cache_warning() -> str | None:
    pip_cache = Path.home() / ".cache" / "pip"
    if pip_cache.exists() and not os.access(pip_cache, os.W_OK):
        return f"pip cache is not writable and pip will disable cache: {pip_cache}"
    parent = pip_cache.parent
    if parent.exists() and not os.access(parent, os.W_OK):
        return f"pip cache parent is not writable and pip may disable cache: {parent}"
    return None


def _profile_submodules(profile: DoctorProfile, vulkan: str) -> list[str]:
    paths = list(profile.submodules)
    if vulkan == "ON":
        paths.append("termin-thirdparty/vulkan-memory-allocator")
    return paths


def _artifact_roots(build_dir: Path) -> list[Path]:
    roots = [build_dir / "bin"]
    for config in ("Release", "Debug", "RelWithDebInfo", "MinSizeRel"):
        roots.append(build_dir / "bin" / config)
    return roots


def _find_native_artifact(build_dir: Path, target: str) -> Path | None:
    patterns = (
        f"{target}.*.so",
        f"{target}.*.pyd",
        f"{target}.pyd",
        f"{target}.so",
    )
    for root in _artifact_roots(build_dir):
        if not root.is_dir():
            continue
        for pattern in patterns:
            matches = sorted(root.glob(pattern))
            if matches:
                return matches[0]
    return None


def write_artifacts(repo_root: Path, build_dir: Path, sdk_prefix: Path) -> int:
    packages = load_manifest(repo_root)
    artifacts = []
    missing_required = []

    for package in packages:
        for native_extension in package.native_extensions:
            build_path = _find_native_artifact(build_dir, native_extension.target)
            if build_path is None:
                if native_extension.optional:
                    continue
                missing_required.append(
                    f"{package.path}: {native_extension.extension} "
                    f"(target {native_extension.target})"
                )
                continue
            artifacts.append(
                {
                    "package_path": package.path,
                    "distribution": package.distribution,
                    "extension": native_extension.extension,
                    "target": native_extension.target,
                    "build_path": str(build_path.resolve()),
                    "optional": native_extension.optional,
                    "features": list(
                        dict.fromkeys((*package.features, *native_extension.features))
                    ),
                }
            )

    if missing_required:
        print("ERROR: required native artifacts are missing:", file=sys.stderr)
        for missing in missing_required:
            print(f"  - {missing}", file=sys.stderr)
        return 1

    sdk_prefix.mkdir(parents=True, exist_ok=True)
    artifact_manifest = {
        "schema": 1,
        "build_dir": str(build_dir.resolve()),
        "sdk_prefix": str(sdk_prefix.resolve()),
        "artifacts": artifacts,
    }
    output = sdk_prefix / "termin-artifacts.json"
    output.write_text(
        json.dumps(artifact_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote artifact manifest: {output}")
    return 0


def doctor(
    repo_root: Path,
    profile_name: str,
    vulkan: str,
    init_submodules: bool,
    require_nanobind: bool,
) -> int:
    profile = PROFILES[profile_name]
    errors = []
    warnings = []

    if profile.needs_git:
        error = _tool_error("git")
        if error:
            errors.append(error)
    if profile.needs_cmake:
        error = _tool_error("cmake")
        if error:
            errors.append(error)
    if profile.needs_nanobind or require_nanobind:
        error = _nanobind_error()
        if error:
            errors.append(error)

    warning = _pip_cache_warning()
    if warning:
        warnings.append(warning)

    required_submodules = _profile_submodules(profile, vulkan)
    missing = missing_submodules(repo_root, required_submodules)
    if missing and init_submodules:
        result = ensure_submodules(repo_root, required_submodules)
        if result != 0:
            return result
        missing = missing_submodules(repo_root, required_submodules)
    if missing:
        errors.append(
            "required submodules are missing: "
            + ", ".join(missing)
        )

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Termin build doctor OK ({profile.name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to auto-discovery from cwd.",
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="Run build preflight checks.")
    doctor_parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="sdk-bindings",
    )
    doctor_parser.add_argument(
        "--vulkan",
        choices=("ON", "OFF"),
        default="ON",
    )
    doctor_parser.add_argument(
        "--init-submodules",
        action="store_true",
        help="Initialize missing required git submodules.",
    )
    doctor_parser.add_argument(
        "--require-nanobind",
        action="store_true",
        help="Require nanobind even if the selected profile does not.",
    )

    ensure_parser = subparsers.add_parser(
        "ensure-submodules",
        help="Initialize the requested submodules if they are missing.",
    )
    ensure_parser.add_argument("paths", nargs="+")

    artifacts_parser = subparsers.add_parser(
        "write-artifacts",
        help="Write sdk/termin-artifacts.json from build outputs and package manifest.",
    )
    artifacts_parser.add_argument("--build-dir", type=Path, required=True)
    artifacts_parser.add_argument("--sdk-prefix", type=Path, required=True)

    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from(Path.cwd())

    if args.command == "doctor":
        return doctor(
            repo_root=repo_root,
            profile_name=args.profile,
            vulkan=args.vulkan,
            init_submodules=args.init_submodules,
            require_nanobind=args.require_nanobind,
        )
    if args.command == "ensure-submodules":
        return ensure_submodules(repo_root, args.paths)
    if args.command == "write-artifacts":
        return write_artifacts(
            repo_root=repo_root,
            build_dir=args.build_dir,
            sdk_prefix=args.sdk_prefix,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
