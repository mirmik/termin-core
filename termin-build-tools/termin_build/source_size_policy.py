"""Manifest-driven repository source-size policy."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


POLICY_MANIFEST = Path("build-system/repository-policies.json")


class SourceSizePolicyError(ValueError):
    """Raised when source-size policy metadata is invalid."""


@dataclass(frozen=True)
class SourceSizePolicy:
    threshold: int
    extensions: tuple[str, ...]
    exclude_roots: tuple[str, ...]


def _string_tuple(raw: object, context: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise SourceSizePolicyError(f"{context} must be a non-empty list")
    if any(not isinstance(item, str) or not item for item in raw):
        raise SourceSizePolicyError(f"{context} must contain non-empty strings")
    if len(raw) != len(set(raw)):
        raise SourceSizePolicyError(f"{context} contains duplicate values")
    return tuple(raw)


def load_source_size_policy(repo_root: Path) -> SourceSizePolicy:
    path = repo_root / POLICY_MANIFEST
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceSizePolicyError(f"policy manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceSizePolicyError(f"invalid policy manifest {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise SourceSizePolicyError(f"unsupported or missing schema in {path}")
    raw = data.get("source_size")
    if not isinstance(raw, dict):
        raise SourceSizePolicyError(f"{path}: source_size must be an object")
    threshold = raw.get("threshold")
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold <= 0:
        raise SourceSizePolicyError(f"{path}: source_size.threshold must be positive")
    extensions = _string_tuple(raw.get("extensions"), f"{path}: extensions")
    if any(not extension.startswith(".") for extension in extensions):
        raise SourceSizePolicyError(f"{path}: extensions must start with '.'")
    exclude_roots = _string_tuple(raw.get("exclude_roots"), f"{path}: exclude_roots")
    for root in exclude_roots:
        candidate = Path(root)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise SourceSizePolicyError(
                f"{path}: exclude root must be repository-relative: {root}"
            )
    return SourceSizePolicy(threshold, extensions, exclude_roots)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _is_excluded(path: Path, root: Path) -> bool:
    if len(root.parts) == 1:
        return root.name in path.parts
    return _is_within(path, root)


def find_long_files(
    repo_root: Path, policy: SourceSizePolicy
) -> tuple[tuple[str, int], ...]:
    excluded = tuple(Path(root) for root in policy.exclude_roots)
    extensions = {extension.lower() for extension in policy.extensions}
    results = []
    for current, directory_names, file_names in os.walk(repo_root):
        relative_current = Path(current).relative_to(repo_root)
        directory_names[:] = [
            name
            for name in directory_names
            if not any(_is_excluded(relative_current / name, root) for root in excluded)
        ]
        if any(_is_excluded(relative_current, root) for root in excluded):
            continue
        for name in file_names:
            path = Path(current) / name
            if path.suffix.lower() not in extensions:
                continue
            try:
                with path.open("rb") as stream:
                    line_count = sum(1 for _ in stream)
            except (PermissionError, IsADirectoryError):
                continue
            if line_count >= policy.threshold:
                results.append((path.relative_to(repo_root).as_posix(), line_count))
    return tuple(sorted(results, key=lambda entry: (-entry[1], entry[0])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--threshold", "-t", type=int)
    parser.add_argument("--exclude", "-e", action="append")
    parser.add_argument("--extension", "-x", action="append")
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args(argv)
    repo_root = args.root.resolve()
    try:
        policy = load_source_size_policy(repo_root)
        if args.threshold is not None:
            if args.threshold <= 0:
                raise SourceSizePolicyError("threshold override must be positive")
            policy = SourceSizePolicy(
                args.threshold, policy.extensions, policy.exclude_roots
            )
        if args.exclude:
            policy = SourceSizePolicy(
                policy.threshold,
                policy.extensions,
                (*policy.exclude_roots, *args.exclude),
            )
        if args.extension:
            extensions = tuple(
                value if value.startswith(".") else f".{value}"
                for value in args.extension
            )
            policy = SourceSizePolicy(
                policy.threshold, extensions, policy.exclude_roots
            )
        results = find_long_files(repo_root, policy)
    except SourceSizePolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not results:
        print(f"No source files with >= {policy.threshold} lines found.")
        return 0
    print(f"Source files with >= {policy.threshold} lines:\n")
    for path, lines in results:
        print(f"  {lines:>6}  {path}")
    print(f"\nTotal: {len(results)} file(s)")
    return 1 if args.fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
