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


def test_central_runners_propagate_window_capability_to_python_planner() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for suffix in ("sh", "ps1"):
        central = (repo_root / f"run-tests.{suffix}").read_text(encoding="utf-8")
        python = (repo_root / f"run-tests-python.{suffix}").read_text(
            encoding="utf-8"
        )

        assert "TERMIN_TEST_CAPABILITIES" in central
        assert "--no-sdl" in central
        assert "TERMIN_TEST_CAPABILITIES" in python
        assert "--capability" in python


def test_cpp_runners_build_shader_compiler_before_python_resolution() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    linux_runner = (repo_root / "run-tests-cpp.sh").read_text(encoding="utf-8")
    windows_runner = (repo_root / "run-tests-cpp.ps1").read_text(encoding="utf-8")

    # Resolving an existing path is not a freshness guarantee.  Both central
    # C++ runners must explicitly build the producer target in the active
    # graph before run-tests.sh/run-tests.ps1 resolve TERMIN_SHADERC.
    assert linux_runner.count("--target termin_shaderc") == 1
    assert '$NativeBuildTargets += "termin_shaderc"' in windows_runner


def test_cpp_runners_build_exact_planner_selected_targets() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    linux_runner = (repo_root / "run-tests-cpp.sh").read_text(encoding="utf-8")
    windows_runner = (repo_root / "run-tests-cpp.ps1").read_text(encoding="utf-8")

    assert '--target "${CTEST_BUILD_TARGETS[@]}"' in linux_runner
    assert "$NativeBuildTargets = @($CtestBuildTargets)" in windows_runner
    assert "-Target $NativeBuildTargets" in windows_runner
    assert "termin_native_tests_with_window" not in linux_runner
    assert "termin_native_tests_with_window" not in windows_runner


def test_windows_cmake_helper_builds_multiple_targets_as_one_solution_graph() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    helper = (repo_root / "scripts" / "Invoke-CMakeBuild.ps1").read_text(
        encoding="utf-8"
    )

    assert '$Target.Count -gt 1' in helper
    assert '"/t:$($Target -join \';\')"' in helper
    assert "Get-TerminVisualStudioSolution" in helper
    assert "& $msbuildPath @msbuildArgs" in helper
