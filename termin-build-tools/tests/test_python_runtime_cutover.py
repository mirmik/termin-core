from __future__ import annotations

import json
from pathlib import Path

from termin_build.package_manifest import (
    CANONICAL_REQUIRES_PYTHON,
    load_manifest,
    package_requires_python,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_all_sdk_packages_require_python_314() -> None:
    for package in load_manifest(REPO_ROOT):
        package_dir = REPO_ROOT / package.path
        assert (
            package_requires_python(package_dir)
            == CANONICAL_REQUIRES_PYTHON
        ), package.path


def test_toolchain_lock_is_the_only_runtime_identity() -> None:
    lock = json.loads(
        (REPO_ROOT / "build-system/python-toolchain-lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert lock["version"] == "3.14.6"
    assert lock["python_abi"] == {
        "version": "3.14",
        "free_threaded": True,
        "py_gil_disabled": True,
    }

    cmake_contract = (
        REPO_ROOT / "cmake/TerminPython.cmake"
    ).read_text(encoding="utf-8")
    assert "include_guard(DIRECTORY)" in cmake_contract
    assert 'TERMIN_CANONICAL_PYTHON_VERSION "3.14"' in cmake_contract
    assert "Py_GIL_DISABLED" in cmake_contract
    assert "^cpython-314t" in cmake_contract


def test_production_configuration_has_no_legacy_python_runtime() -> None:
    roots = [
        REPO_ROOT / ".github/workflows",
        REPO_ROOT / "cmake",
        REPO_ROOT / "CMakeLists.txt",
        REPO_ROOT / "build-sdk-bindings.sh",
        REPO_ROOT / "build-sdk-bindings.ps1",
        REPO_ROOT / "termin-app",
        REPO_ROOT / "termin-nanobind-sdk",
    ]
    legacy_markers = (
        "python3.10",
        "Python 3.10",
        "libpython3.10",
        "cp310",
        "TERMIN_REQUIRE_FREE_THREADED_PYTHON",
        "TERMIN_EXPECTED_PYTHON_ABI_VERSION",
    )
    offenders: list[str] = []
    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or "tests" in path.parts:
                continue
            if path.suffix not in {
                "",
                ".cmake",
                ".cpp",
                ".h",
                ".md",
                ".ps1",
                ".py",
                ".sh",
                ".txt",
                ".yml",
            } and path.name != "CMakeLists.txt":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(marker in text for marker in legacy_markers):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
