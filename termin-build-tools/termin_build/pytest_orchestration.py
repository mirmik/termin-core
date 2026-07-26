"""Utilities supporting manifest-driven pytest orchestration."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path


NANOBIND_SHUTDOWN_DIAGNOSTIC = re.compile(
    r"^nanobind: leaked\b.*$", re.IGNORECASE | re.MULTILINE
)
NANOBIND_DIAGNOSTIC_CONTEXT_BEFORE = 3
NANOBIND_DIAGNOSTIC_CONTEXT_AFTER = 20
PYTEST_DURATION_CACHE_SCHEMA = 1
PYTEST_DURATION_SMOOTHING = 0.5


def host_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def safe_suite_directory(suite_id: str) -> str:
    return "".join(
        character if character.isalnum() or character in "_.-" else "-"
        for character in suite_id
    )


def nanobind_shutdown_diagnostic_excerpt(output: str) -> str | None:
    """Return the useful context of a nanobind shutdown leak diagnostic."""
    match = NANOBIND_SHUTDOWN_DIAGNOSTIC.search(output)
    if match is None:
        return None
    lines = output.splitlines()
    diagnostic_line = output[: match.start()].count("\n")
    start = max(0, diagnostic_line - NANOBIND_DIAGNOSTIC_CONTEXT_BEFORE)
    end = min(len(lines), diagnostic_line + NANOBIND_DIAGNOSTIC_CONTEXT_AFTER + 1)
    return "\n".join(lines[start:end])


def run_pytest_command(
    command: list[str],
    repo_root: Path,
    environment: dict[str, str],
    *,
    stream_output: bool,
) -> tuple[int, str]:
    """Run one pytest suite while retaining output for diagnostics."""
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    output = []
    for line in process.stdout:
        output.append(line)
        if stream_output:
            sys.stdout.write(line)
            sys.stdout.flush()
    return process.wait(), "".join(output)


def run_timed_pytest_command(
    command: list[str],
    repo_root: Path,
    environment: dict[str, str],
    *,
    stream_output: bool,
) -> tuple[int, str, float]:
    started_at = time.monotonic()
    returncode, output = run_pytest_command(
        command, repo_root, environment, stream_output=stream_output
    )
    return returncode, output, time.monotonic() - started_at


def load_pytest_duration_cache(path: Path) -> dict[str, dict[str, float]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema") != PYTEST_DURATION_CACHE_SCHEMA:
            raise ValueError("unsupported or missing schema")
        raw_profiles = raw.get("profiles")
        if not isinstance(raw_profiles, dict):
            raise ValueError("profiles must be an object")
        profiles = {}
        for profile_key, raw_durations in raw_profiles.items():
            if not isinstance(profile_key, str) or not isinstance(raw_durations, dict):
                raise ValueError("profile timings must be objects")
            durations = {}
            for suite_id, duration in raw_durations.items():
                if (
                    not isinstance(suite_id, str)
                    or isinstance(duration, bool)
                    or not isinstance(duration, (int, float))
                    or not math.isfinite(duration)
                    or duration < 0
                ):
                    raise ValueError("suite durations must be finite non-negative numbers")
                durations[suite_id] = float(duration)
            profiles[profile_key] = durations
        return profiles
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"WARNING: ignoring invalid pytest duration cache {path}: {exc}", file=sys.stderr)
        return {}


def write_pytest_duration_cache(path: Path, profiles: dict[str, dict[str, float]]) -> None:
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = {"schema": PYTEST_DURATION_CACHE_SCHEMA, "profiles": profiles}
    try:
        temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary_path, path)
    except OSError as exc:
        print(f"WARNING: failed to update pytest duration cache {path}: {exc}", file=sys.stderr)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def updated_pytest_durations(previous: dict[str, float], measured: dict[str, float]) -> dict[str, float]:
    updated = dict(previous)
    for suite_id, duration in measured.items():
        old_duration = previous.get(suite_id)
        updated[suite_id] = duration if old_duration is None else (
            old_duration * (1.0 - PYTEST_DURATION_SMOOTHING)
            + duration * PYTEST_DURATION_SMOOTHING
        )
    return updated


def print_pytest_suite_header(suite_id: str) -> None:
    print("")
    print("----------------------------------------")
    print(f"  {suite_id}")
    print("----------------------------------------")


def pytest_worker_environment(base_environment: dict[str, str], suite_temp: Path) -> dict[str, str]:
    environment = base_environment.copy()
    environment["TEMP"] = str(suite_temp)
    environment["TMP"] = str(suite_temp)
    environment["TMPDIR"] = str(suite_temp)
    for variable in ("BLIS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        environment.setdefault(variable, "1")
    return environment


def report_pytest_suite_result(suite_id: str, returncode: int, output: str, *, print_output: bool) -> bool:
    if print_output:
        print_pytest_suite_header(suite_id)
        sys.stdout.write(output)
        if output and not output.endswith("\n"):
            print("")
        sys.stdout.flush()
    nanobind_excerpt = nanobind_shutdown_diagnostic_excerpt(output)
    if nanobind_excerpt is not None:
        print(f"ERROR: pytest suite {suite_id} emitted nanobind shutdown leak diagnostics:", file=sys.stderr)
        print(nanobind_excerpt, file=sys.stderr)
    return returncode != 0 or nanobind_excerpt is not None
