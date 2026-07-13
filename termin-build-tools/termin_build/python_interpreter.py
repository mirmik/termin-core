"""Resolve one authoritative Python interpreter for the SDK build."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _resolve_candidate(value: str) -> Path:
    expanded = Path(value).expanduser()
    if expanded.is_file():
        return expanded.resolve()
    discovered = shutil.which(value)
    if discovered:
        return Path(discovered).resolve()
    raise RuntimeError(f"Python executable does not exist or is not on PATH: {value}")


def resolve_python_executable() -> str:
    """Return one absolute interpreter path and reject conflicting overrides."""
    python_bin = os.environ.get("PYTHON_BIN")
    python_executable = os.environ.get("PYTHON_EXECUTABLE")
    resolved_bin = _resolve_candidate(python_bin) if python_bin else None
    resolved_executable = _resolve_candidate(python_executable) if python_executable else None
    if (
        resolved_bin is not None
        and resolved_executable is not None
        and os.path.normcase(resolved_bin) != os.path.normcase(resolved_executable)
    ):
        raise RuntimeError(
            "PYTHON_BIN and PYTHON_EXECUTABLE resolve to different interpreters: "
            f"{resolved_bin} != {resolved_executable}"
        )
    selected = resolved_bin or resolved_executable or _resolve_candidate(sys.executable)
    return str(selected)
