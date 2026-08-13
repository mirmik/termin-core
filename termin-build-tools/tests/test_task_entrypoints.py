from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_taskfile_is_the_cross_platform_public_command_interface() -> None:
    taskfile = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")

    for task_name in ("build", "test", "smoke", "build:android", "build:web"):
        assert f"  {task_name}:\n" in taskfile

    assert "./scripts/build/sdk.sh" in taskfile
    assert ".\\scripts\\build\\sdk.ps1" in taskfile
    assert "./scripts/test/all.sh" in taskfile
    assert ".\\scripts\\test\\all.ps1" in taskfile


def test_root_has_no_platform_launcher_scripts() -> None:
    root_launchers = [
        path.name
        for path in REPO_ROOT.iterdir()
        if path.is_file() and path.suffix in {".sh", ".ps1"}
    ]

    assert root_launchers == []


def test_internal_cross_platform_launchers_are_paired() -> None:
    expected_pairs = (
        ("build", "sdk"),
        ("build", "bindings"),
        ("build", "cpp"),
        ("test", "all"),
        ("test", "cpp"),
        ("test", "python"),
        ("test", "setup-python-env"),
    )

    for directory, stem in expected_pairs:
        assert (REPO_ROOT / "scripts" / directory / f"{stem}.sh").is_file()
        assert (REPO_ROOT / "scripts" / directory / f"{stem}.ps1").is_file()
