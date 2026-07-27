from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


class ArtifactResolutionError(RuntimeError):
    pass


def _cmake_cache_value(cache_path: Path, name: str) -> str | None:
    if not cache_path.is_file():
        raise ArtifactResolutionError(
            f"CMake cache is missing for the current C++ test graph: {cache_path}"
        )

    prefix = f"{name}:"
    for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(prefix):
            continue
        _, separator, value = line.partition("=")
        if separator:
            return value
    return None


def resolve_shader_compiler(
    build_dir: Path,
    configuration: str,
    platform: str,
) -> Path:
    if (
        not configuration
        or "/" in configuration
        or "\\" in configuration
        or configuration in {".", ".."}
    ):
        raise ArtifactResolutionError(
            f"invalid CMake test configuration: {configuration!r}"
        )

    resolved_build_dir = build_dir.resolve()
    configuration_types = _cmake_cache_value(
        resolved_build_dir / "CMakeCache.txt",
        "CMAKE_CONFIGURATION_TYPES",
    )
    multi_config = bool(configuration_types)

    normalized_platform = platform.lower()
    if normalized_platform in {"windows", "win32"}:
        executable_name = "termin_shaderc.exe"
    elif normalized_platform in {"linux", "darwin"}:
        executable_name = "termin_shaderc"
    else:
        raise ArtifactResolutionError(
            f"unsupported test artifact platform: {platform!r}"
        )

    compiler_dir = resolved_build_dir / "bin"
    if multi_config:
        compiler_dir /= configuration
    compiler_path = compiler_dir / executable_name
    if not compiler_path.is_file():
        graph_kind = "multi-config" if multi_config else "single-config"
        raise ArtifactResolutionError(
            "termin_shaderc produced by the current C++ test graph is missing: "
            f"{compiler_path} ({graph_kind}, configuration {configuration}). "
            "Run the C++ test build successfully before Python tests."
        )
    return compiler_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve artifacts produced by the current C++ test graph."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    shader_parser = subparsers.add_parser("shader-compiler")
    shader_parser.add_argument("--build-dir", type=Path, required=True)
    shader_parser.add_argument("--configuration", required=True)
    shader_parser.add_argument(
        "--platform",
        choices=("linux", "windows"),
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "shader-compiler":
            print(
                resolve_shader_compiler(
                    args.build_dir,
                    args.configuration,
                    args.platform,
                )
            )
            return 0
    except ArtifactResolutionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
