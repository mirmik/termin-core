from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_taskfile_is_the_cross_platform_public_command_interface() -> None:
    taskfile = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")

    for task_name in (
        "build",
        "test",
        "smoke",
        "build:android",
        "build:web",
        "docs:build",
        "docs:serve",
    ):
        assert f"  {task_name}:\n" in taskfile

    assert "./scripts/build/sdk.sh" in taskfile
    assert "./scripts/build/sdk.ps1" in taskfile
    assert "./scripts/test/all.sh" in taskfile
    assert "./scripts/test/all.ps1" in taskfile
    assert "\\" not in taskfile


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


def test_web_toolchain_uses_a_shared_versioned_cache() -> None:
    setup = (REPO_ROOT / "scripts/build/setup-web-toolchain.sh").read_text(
        encoding="utf-8"
    )
    web_build = (REPO_ROOT / "scripts/build/web.sh").read_text(encoding="utf-8")

    assert "XDG_CACHE_HOME" in setup
    assert "termin/toolchains/emscripten/$version/emsdk" in setup
    assert "TERMIN_EMSDK_DIR" in setup
    assert 'flock 9' in setup
    assert 'setup-web-toolchain.sh\" --print-path' in web_build
    assert '[[ ! -x "$emcmake" || ! -x "$emcc" ]]' in web_build
