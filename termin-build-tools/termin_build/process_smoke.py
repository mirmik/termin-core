"""Cross-platform process-smoke execution with retained diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ProcessSmokeRun:
    selected: tuple[str, ...]
    executed: tuple[str, ...]
    skipped: dict[str, str]
    failed: dict[str, str]
    logs: dict[str, str]

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0


def _safe_suite_directory(suite_id: str) -> str:
    return "".join(
        character if character.isalnum() or character in "_.-" else "-"
        for character in suite_id
    )


def _display_log_path(repo_root: Path, log_path: Path) -> str:
    try:
        return log_path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(log_path)


def _command_line(command: Path, platform: str) -> tuple[list[str] | None, str | None]:
    suffix = command.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(command)], None
    if platform == "windows" and suffix == ".ps1":
        powershell = shutil.which("pwsh")
        if powershell is None:
            return None, "pwsh is unavailable"
        return [powershell, "-NoProfile", "-File", str(command)], None
    if platform == "windows" and suffix in {".bat", ".cmd"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(command)], None
    if not os.access(command, os.X_OK):
        return None, f"process-smoke command is not executable: {command}"
    return [str(command)], None


def execute_process_smoke_suites(
    repo_root: Path,
    suites: Iterable[Mapping[str, object]],
    profile_id: str,
    platform: str,
    capabilities: Iterable[str],
    configuration: str | None,
    timeout_seconds: float,
    log_dir: Path,
) -> ProcessSmokeRun:
    suite_list = list(suites)
    enabled_capabilities = set(capabilities)
    log_dir.mkdir(parents=True, exist_ok=True)
    selected = tuple(str(suite["id"]) for suite in suite_list)
    executed = []
    skipped: dict[str, str] = {}
    failed: dict[str, str] = {}
    logs: dict[str, str] = {}
    print(f"Process-smoke execution plan: {profile_id} / {platform}")
    print(f"Process-smoke suites: {len(suite_list)}")
    print(f"Process-smoke capabilities: {', '.join(sorted(enabled_capabilities)) or '(none)'}")
    print(f"Process-smoke logs: {log_dir}")
    environment = os.environ.copy()
    if configuration:
        environment["TERMIN_TEST_CONFIGURATION"] = configuration

    for suite in suite_list:
        suite_id = str(suite["id"])
        required_capabilities = {
            str(value) for value in suite["required_capabilities"]
        }
        missing_capabilities = sorted(required_capabilities - enabled_capabilities)
        if missing_capabilities:
            reason = "missing capabilities: " + ", ".join(missing_capabilities)
            skipped[suite_id] = reason
            print(f"SKIP {suite_id}: {reason}")
            continue

        log_path = log_dir / f"{_safe_suite_directory(suite_id)}.log"
        displayed_log_path = _display_log_path(repo_root, log_path)
        logs[suite_id] = displayed_log_path
        log_parts = []
        print("")
        print("----------------------------------------")
        print(f"  {suite_id}")
        print("----------------------------------------")
        for root in suite["roots"]:
            command = repo_root / str(root)
            command_line, command_error = _command_line(command, platform)
            if command_error is not None or command_line is None:
                failed[suite_id] = f"{command_error}; log: {displayed_log_path}"
                log_parts.append(f"ERROR: {failed[suite_id]}\n")
                break
            log_parts.append(f"$ {' '.join(command_line)}\n")
            try:
                result = subprocess.run(
                    command_line,
                    cwd=repo_root,
                    env=environment,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout_seconds,
                )
                output = result.stdout or ""
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout or ""
                if isinstance(output, bytes):
                    output = output.decode(errors="replace")
                log_parts.append(output)
                failed[suite_id] = (
                    f"timed out after {timeout_seconds:g}s; log: {displayed_log_path}"
                )
                break
            log_parts.append(output)
            if output:
                sys.stdout.write(output)
                sys.stdout.flush()
            if result.returncode != 0:
                failed[suite_id] = (
                    f"command exited with code {result.returncode}; "
                    f"log: {displayed_log_path}"
                )
                break
        log_path.write_text("".join(log_parts), encoding="utf-8")
        if suite_id not in failed:
            executed.append(suite_id)

    if failed:
        print("", file=sys.stderr)
        print("Process-smoke suite failures:", file=sys.stderr)
        for suite_id, reason in failed.items():
            print(f"  - {suite_id}: {reason}", file=sys.stderr)
    return ProcessSmokeRun(
        selected=selected,
        executed=tuple(executed),
        skipped=skipped,
        failed=failed,
        logs=logs,
    )
