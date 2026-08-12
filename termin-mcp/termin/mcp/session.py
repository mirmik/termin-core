"""SDK-scoped discovery paths for independently addressable MCP runtimes."""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path


_RUNTIME_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def canonical_sdk_root(sdk_root: str | Path | None = None) -> Path:
    """Return the canonical SDK root used to identify a Termin installation."""

    candidate = Path(sys.prefix if sdk_root is None else sdk_root)
    return Path(os.path.normcase(str(candidate.expanduser().resolve(strict=False))))


def sdk_session_registry_dir(
    runtime_name: str,
    *,
    sdk_root: str | Path | None = None,
    temp_dir: str | Path | None = None,
) -> Path:
    """Return the SDK-scoped session registry for a named runtime consumer."""

    if not _RUNTIME_NAME_PATTERN.fullmatch(runtime_name) or runtime_name in {".", ".."}:
        raise ValueError(
            "runtime_name must be a non-empty path-safe identifier containing only "
            "letters, digits, '.', '_' or '-'"
        )
    root = canonical_sdk_root(sdk_root)
    identity = hashlib.sha256(os.fsencode(str(root))).hexdigest()[:16]
    directory = Path(tempfile.gettempdir() if temp_dir is None else temp_dir)
    return directory / f"termin-{runtime_name}-mcp-{identity}" / "sessions"


def new_sdk_session_file(
    runtime_name: str,
    *,
    sdk_root: str | Path | None = None,
    temp_dir: str | Path | None = None,
    instance_id: str | None = None,
) -> Path:
    """Allocate an instance descriptor path in a runtime's SDK-scoped registry."""

    resolved_instance_id = instance_id or uuid.uuid4().hex
    if Path(resolved_instance_id).name != resolved_instance_id or resolved_instance_id in {".", ".."}:
        raise ValueError("instance_id must be a single path component")
    return (
        sdk_session_registry_dir(
            runtime_name,
            sdk_root=sdk_root,
            temp_dir=temp_dir,
        )
        / f"{resolved_instance_id}.json"
    )
