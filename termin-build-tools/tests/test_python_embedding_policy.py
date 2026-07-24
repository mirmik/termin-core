from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_EMBED_SOURCES = (
    REPO_ROOT / "termin-app/cpp/app/main_launcher.cpp",
    REPO_ROOT / "termin-app/cpp/app/main_minimal.cpp",
    REPO_ROOT / "termin-cli/src/termin_python.cpp",
    REPO_ROOT / "termin-modules/src/module_python_backend.cpp",
    REPO_ROOT / "termin-player/src/player_runtime_host.cpp",
)
REMOVED_SINGLE_PHASE_API = (
    "Py_SetPythonHome",
    "PySys_SetArgv",
    "PySys_SetArgvEx",
    "Py_NoSiteFlag",
    "Py_IgnoreEnvironmentFlag",
    "Py_Initialize()",
)


def test_product_embedding_paths_use_canonical_python_host() -> None:
    for path in PRODUCTION_EMBED_SOURCES:
        source = path.read_text(encoding="utf-8")
        assert "termin/python_host/python_host.hpp" in source, path
        for removed_api in REMOVED_SINGLE_PHASE_API:
            assert removed_api not in source, f"{path}: {removed_api}"


def test_raw_player_module_declares_free_threaded_multiphase_contract() -> None:
    source = (
        REPO_ROOT / "termin-player/src/player_runtime_host.cpp"
    ).read_text(encoding="utf-8")

    assert "PyModuleDef_Init(&native_module)" in source
    assert "Py_MOD_GIL_NOT_USED" in source
    assert "Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED" in source
    assert "PyModule_Create" not in source
