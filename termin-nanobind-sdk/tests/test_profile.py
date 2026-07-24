from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
IGNORED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "build",
    "sdk",
    "termin-thirdparty",
}


def _repository_files(
    suffixes: set[str],
    names: set[str] | None = None,
) -> list[Path]:
    exact_names = names or set()
    files: list[Path] = []
    for directory, child_directories, filenames in os.walk(REPO_ROOT):
        child_directories[:] = [
            name for name in child_directories if name not in IGNORED_DIRECTORIES
        ]
        root = Path(directory)
        files.extend(
            root / filename
            for filename in filenames
            if Path(filename).suffix in suffixes or filename in exact_names
        )
    return files


def _balanced_calls(source: str, function_name: str) -> list[str]:
    calls: list[str] = []
    start_pattern = re.compile(rf"\b{re.escape(function_name)}\s*\(")
    for match in start_pattern.finditer(source):
        depth = 1
        cursor = match.end()
        while cursor < len(source) and depth:
            character = source[cursor]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            cursor += 1
        if depth:
            raise AssertionError(f"unterminated {function_name} call")
        calls.append(source[match.end() : cursor - 1])
    return calls


def test_every_nanobind_entry_point_uses_the_canonical_shared_profile() -> None:
    entry_points: dict[str, Path] = {}
    for path in _repository_files({".cc", ".cpp", ".cxx", ".h", ".hpp"}):
        source = path.read_text(encoding="utf-8", errors="replace")
        for name in re.findall(
            r"\bNB_MODULE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)",
            source,
        ):
            assert name not in entry_points, f"duplicate NB_MODULE {name}"
            entry_points[name] = path

    module_targets: dict[str, Path] = {}
    for path in _repository_files({".cmake"}, {"CMakeLists.txt"}):
        source = path.read_text(encoding="utf-8", errors="replace")
        for arguments in _balanced_calls(source, "nanobind_add_module"):
            fields = arguments.split()
            if (
                not fields
                or fields[0] == "name"
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", fields[0])
            ):
                continue
            name = fields[0]
            assert name not in module_targets, f"duplicate nanobind target {name}"
            assert "NB_SHARED" in fields, f"{path}: {name} bypasses NB_SHARED"
            assert "NB_STATIC" not in fields, f"{path}: {name} requests NB_STATIC"
            module_targets[name] = path

    assert entry_points
    assert entry_points.keys() == module_targets.keys(), (
        f"entry points without canonical targets: "
        f"{sorted(entry_points.keys() - module_targets.keys())}; "
        f"targets without entry points: "
        f"{sorted(module_targets.keys() - entry_points.keys())}"
    )


def test_cmake_consumers_do_not_link_bare_nanobind_runtime() -> None:
    bypasses = []
    for path in _repository_files({".cmake"}, {"CMakeLists.txt"}):
        if path.is_relative_to(REPO_ROOT / "termin-nanobind-sdk" / "cmake"):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?m)^\s+nanobind\s*$", source):
            bypasses.append(path.relative_to(REPO_ROOT).as_posix())
    assert not bypasses, f"bare nanobind runtime links bypass the SDK profile: {bypasses}"


def test_installed_cmake_package_applies_interpreter_abi_profile(
    tmp_path: Path,
) -> None:
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake is unavailable")
    sdk_root = Path(os.environ["TERMIN_SDK"])
    build_python_candidates = (
        REPO_ROOT / "build/python-runtime/build-env/bin/python",
        REPO_ROOT / "build/python-runtime/build-env/Scripts/python.exe",
    )
    build_python = next(
        (path for path in build_python_candidates if path.is_file()),
        None,
    )
    if build_python is None:
        pytest.skip("pinned SDK Python build environment is unavailable")
    source_dir = tmp_path / "source"
    build_dir = tmp_path / "build"
    source_dir.mkdir()
    (source_dir / "probe.cpp").write_text(
        "#include <nanobind/nanobind.h>\n"
        "NB_MODULE(_profile_probe, module) { (void) module; }\n",
        encoding="utf-8",
    )
    (source_dir / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(termin_nanobind_profile_probe LANGUAGES CXX)\n"
        "find_package(Python COMPONENTS Interpreter Development REQUIRED)\n"
        "find_package(nanobind CONFIG REQUIRED)\n"
        "nanobind_add_module(_profile_probe NB_SHARED probe.cpp)\n"
        "get_target_property(profile_links _profile_probe LINK_LIBRARIES)\n"
        "get_target_property(profile_definitions _profile_probe COMPILE_DEFINITIONS)\n"
        'file(WRITE "${CMAKE_BINARY_DIR}/profile.txt" '
        '"${profile_links}\\n${profile_definitions}\\n")\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            cmake,
            "-S",
            str(source_dir),
            "-B",
            str(build_dir),
            f"-DCMAKE_PREFIX_PATH={sdk_root}",
            f"-DPython_EXECUTABLE={build_python}",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
    build_result = subprocess.run(
        [cmake, "--build", str(build_dir)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert build_result.returncode == 0, build_result.stdout
    profile = (build_dir / "profile.txt").read_text(encoding="utf-8")
    assert "nanobind::nanobind-ft" in profile
    assert "Python::Module" in profile
    assert "NB_FREE_THREADED" in profile


def test_installed_runtime_target_does_not_require_python_development(
    tmp_path: Path,
) -> None:
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake is unavailable")
    sdk_root = Path(os.environ["TERMIN_SDK"])
    source_dir = tmp_path / "source"
    build_dir = tmp_path / "build"
    source_dir.mkdir()
    (source_dir / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(termin_nanobind_runtime_probe LANGUAGES CXX)\n"
        "find_package(nanobind CONFIG REQUIRED)\n"
        "if(NOT TARGET nanobind::nanobind-ft)\n"
        '  message(FATAL_ERROR "canonical runtime target is missing")\n'
        "endif()\n"
        "if(COMMAND nanobind_add_module)\n"
        '  message(FATAL_ERROR "binding helpers require an explicit Python package")\n'
        "endif()\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            cmake,
            "-S",
            str(source_dir),
            "-B",
            str(build_dir),
            f"-DCMAKE_PREFIX_PATH={sdk_root}",
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
