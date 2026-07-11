import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "tcbase._geom_native",
        "termin.colliders",
        "termin.physics",
    ],
)
def test_native_import_exits_without_nanobind_leak_diagnostics(module_name: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "nanobind: leaked" not in result.stderr
