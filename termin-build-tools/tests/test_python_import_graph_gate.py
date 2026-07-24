from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import sysconfig

import pytest

from termin_build import sdk_verification


def test_installed_product_roots_include_payload_player_and_headless(
    tmp_path: Path,
) -> None:
    launcher_module = "termin." + "launcher"
    manifest = {
        "schema": sdk_verification.APPLICATION_PAYLOAD_MANIFEST_SCHEMA,
        "payloads": [
            {
                "imports": [
                    "termin.editor",
                    "termin.editor._editor_native",
                    launcher_module,
                ]
            }
        ],
    }
    (tmp_path / sdk_verification.APPLICATION_PAYLOAD_MANIFEST_NAME).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    roots = sdk_verification._installed_product_import_roots(tmp_path)

    assert roots == [
        "termin.editor",
        "termin.editor._editor_native",
        launcher_module,
        "termin.engine",
        "termin.player",
        "termin.player.headless",
    ]


def test_import_graph_probe_starts_isolated_and_treats_warnings_as_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(sdk_verification.subprocess, "run", fake_run)

    result = sdk_verification._run_python_import_graph_probe(
        launcher=tmp_path / "termin_python",
        extensions=["termin.sample._native"],
        entry_modules=["termin.sample"],
        runtime_paths=[],
        free_threaded=True,
        environment={"TERMIN_SDK": str(tmp_path)},
    )

    assert result.returncode == 0
    assert calls[0][0][:4] == [
        str(tmp_path / "termin_python"),
        "-W",
        sdk_verification._GIL_WARNING_FILTER,
        "-c",
    ]
    script = calls[0][0][4]
    assert "started with the GIL enabled" in script
    assert "GIL enabled after importing" in script
    assert "termin.sample._native" in script
    assert "termin.sample" in script


@pytest.mark.skipif(
    sys.platform != "linux"
    or not bool(sysconfig.get_config_var("Py_GIL_DISABLED") or 0),
    reason="requires a Linux free-threaded CPython build",
)
def test_import_graph_probe_rejects_gil_requiring_extension(
    tmp_path: Path,
) -> None:
    compiler = shlex.split(str(sysconfig.get_config_var("CC") or "cc"))
    if not compiler or shutil.which(compiler[0]) is None:
        pytest.skip("C compiler is unavailable")

    source = Path(__file__).parent / "fixtures" / "gil_required_module.c"
    extension = (
        tmp_path
        / f"_termin_gil_required_fixture{sysconfig.get_config_var('EXT_SUFFIX')}"
    )
    include = Path(str(sysconfig.get_config_var("INCLUDEPY")))
    compile_result = subprocess.run(
        [
            *compiler,
            "-shared",
            "-fPIC",
            f"-I{include}",
            str(source),
            "-o",
            str(extension),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    environment = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE"):
        environment.pop(name, None)
    result = sdk_verification._run_python_import_graph_probe(
        launcher=Path(sys.executable),
        extensions=["_termin_gil_required_fixture"],
        entry_modules=[],
        runtime_paths=[],
        free_threaded=True,
        environment=environment,
        import_paths=[str(tmp_path)],
    )

    assert result.returncode != 0
    assert "_termin_gil_required_fixture" in result.stderr
    assert "GIL" in result.stderr
