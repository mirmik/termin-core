from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import source_size_policy


def _write_policy(repo: Path, threshold: int = 3) -> None:
    path = repo / source_size_policy.POLICY_MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "source_size": {
                    "threshold": threshold,
                    "extensions": [".py"],
                    "exclude_roots": ["build", "vendor/generated"],
                },
            }
        ),
        encoding="utf-8",
    )


def test_finds_files_at_threshold_and_excludes_nested_build_dirs(
    tmp_path: Path,
) -> None:
    _write_policy(tmp_path)
    source = tmp_path / "module" / "large.py"
    source.parent.mkdir()
    source.write_text("one\ntwo\nthree\n", encoding="utf-8")
    generated = tmp_path / "module" / "build" / "generated.py"
    generated.parent.mkdir()
    generated.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    policy = source_size_policy.load_source_size_policy(tmp_path)

    assert source_size_policy.find_long_files(tmp_path, policy) == (
        ("module/large.py", 3),
    )


def test_rejects_unsafe_exclude_root(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    path = tmp_path / source_size_policy.POLICY_MANIFEST
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_size"]["exclude_roots"] = ["../outside"]
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(
        source_size_policy.SourceSizePolicyError,
        match="exclude root must be repository-relative",
    ):
        source_size_policy.load_source_size_policy(tmp_path)
