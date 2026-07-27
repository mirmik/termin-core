from __future__ import annotations

from pathlib import Path

import pytest

from termin_build.artifact_resolution import (
    ArtifactResolutionError,
    resolve_shader_compiler,
)


def _write_cache(build_dir: Path, *, multi_config: bool) -> None:
    build_dir.mkdir(parents=True)
    configuration_types = (
        "CMAKE_CONFIGURATION_TYPES:STRING=Debug;Release\n"
        if multi_config
        else "CMAKE_BUILD_TYPE:STRING=Release\n"
    )
    (build_dir / "CMakeCache.txt").write_text(
        configuration_types,
        encoding="utf-8",
    )


def test_resolve_shader_compiler_from_linux_single_config_graph(
    tmp_path: Path,
) -> None:
    build_dir = tmp_path / "custom-build"
    _write_cache(build_dir, multi_config=False)
    compiler = build_dir / "bin" / "termin_shaderc"
    compiler.parent.mkdir()
    compiler.touch()

    assert resolve_shader_compiler(build_dir, "Release", "linux") == compiler


def test_resolve_shader_compiler_from_windows_multi_config_graph(
    tmp_path: Path,
) -> None:
    build_dir = tmp_path / "custom-build"
    _write_cache(build_dir, multi_config=True)
    compiler = build_dir / "bin" / "Debug" / "termin_shaderc.exe"
    compiler.parent.mkdir(parents=True)
    compiler.touch()

    assert resolve_shader_compiler(build_dir, "Debug", "windows") == compiler


def test_resolver_does_not_fall_back_to_unrelated_layout(
    tmp_path: Path,
) -> None:
    build_dir = tmp_path / "current"
    _write_cache(build_dir, multi_config=True)
    stale_compiler = build_dir / "bin" / "termin_shaderc.exe"
    stale_compiler.parent.mkdir()
    stale_compiler.touch()

    with pytest.raises(
        ArtifactResolutionError,
        match=r"bin[/\\]Release[/\\]termin_shaderc\.exe",
    ):
        resolve_shader_compiler(build_dir, "Release", "windows")


def test_test_runners_have_no_legacy_release_tests_fallback() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    runner_paths = (
        repo_root / "run-tests.sh",
        repo_root / "run-tests.ps1",
        repo_root / "run-tests-python.sh",
        repo_root / "run-tests-python.ps1",
    )

    for runner_path in runner_paths:
        source = runner_path.read_text(encoding="utf-8")
        assert "Release-tests" not in source

    assert "termin_build.artifact_resolution" in runner_paths[0].read_text(
        encoding="utf-8"
    )
    assert "termin_build.artifact_resolution" in runner_paths[1].read_text(
        encoding="utf-8"
    )
