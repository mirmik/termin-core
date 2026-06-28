"""Main-thread Python execution service for MCP diagnostics."""

from __future__ import annotations

import code
import contextlib
import io
import queue
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from tcbase import log


@dataclass(frozen=True)
class PythonExecutionResult:
    ok: bool
    output: str
    wants_more: bool = False
    error: str | None = None


@dataclass
class _ExecutionRequest:
    script: str
    done: threading.Event
    result: PythonExecutionResult | None = None


class PythonScriptExecutor:
    """Executes Python snippets against a live process namespace.

    External callers enqueue work from their own threads. The owner loop calls
    ``process_pending()`` on the main thread, keeping scene/UI/native access in
    the same thread as the rest of the runtime.
    """

    def __init__(
        self,
        context_provider: Callable[[], dict[str, object | None]],
        *,
        log_prefix: str = "PythonScriptExecutor",
        compile_filename: str = "<termin-mcp>",
    ) -> None:
        self._context_provider = context_provider
        self._log_prefix = log_prefix
        self._compile_filename = compile_filename
        self._console = code.InteractiveConsole(locals={})
        self._main_thread_id = threading.get_ident()
        self._pending: queue.Queue[_ExecutionRequest] = queue.Queue()

    def execute_repl_line(self, text: str) -> PythonExecutionResult:
        if not text.strip():
            return PythonExecutionResult(ok=True, output="")

        self._refresh_context()
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
                wants_more = self._console.push(text)
        except Exception:
            log.error(f"[{self._log_prefix}] internal console execution failure", exc_info=True)
            return PythonExecutionResult(
                ok=False,
                output=stdout.getvalue(),
                error="Internal console error; see log.",
            )

        return PythonExecutionResult(
            ok=True,
            output=stdout.getvalue(),
            wants_more=wants_more,
        )

    def execute_script(self, script: str) -> PythonExecutionResult:
        if not script.strip():
            return PythonExecutionResult(ok=True, output="")

        self._refresh_context()
        stdout = io.StringIO()
        try:
            compiled = compile(script, self._compile_filename, "exec")
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
                exec(compiled, self._console.locals)
        except BaseException as exc:
            tb = traceback.format_exc()
            log.error(f"[{self._log_prefix}] script execution failed: {exc}")
            output = stdout.getvalue()
            if output and not output.endswith("\n"):
                output += "\n"
            return PythonExecutionResult(
                ok=False,
                output=output + tb,
                error=f"{type(exc).__name__}: {exc}",
            )

        return PythonExecutionResult(ok=True, output=stdout.getvalue())

    def execute_script_from_any_thread(
        self,
        script: str,
        *,
        timeout: float | None = 30.0,
    ) -> PythonExecutionResult:
        if threading.get_ident() == self._main_thread_id:
            return self.execute_script(script)

        request = _ExecutionRequest(script=script, done=threading.Event())
        self._pending.put(request)
        if not request.done.wait(timeout=timeout):
            log.error(f"[{self._log_prefix}] script execution timed out waiting for main thread")
            return PythonExecutionResult(
                ok=False,
                output="",
                error="Timed out waiting for main thread",
            )
        if request.result is None:
            log.error(f"[{self._log_prefix}] script execution completed without a result")
            return PythonExecutionResult(
                ok=False,
                output="",
                error="Execution completed without a result",
            )
        return request.result

    def process_pending(self, *, limit: int = 8) -> int:
        processed = 0
        while processed < limit:
            try:
                request = self._pending.get_nowait()
            except queue.Empty:
                break
            try:
                request.result = self.execute_script(request.script)
            finally:
                request.done.set()
            processed += 1
        return processed

    def _refresh_context(self) -> None:
        namespace = self._console.locals
        namespace.update(self._context_provider())
        self._add_common_context(namespace)
        self._add_runtime_context(namespace)

    def _add_common_context(self, namespace: dict[str, object | None]) -> None:
        try:
            import termin
            from termin.geombase import GeneralPose3, Pose3, Quat, Vec3, Vec4
            from termin.scene import GeneralTransform3
            from termin_assets import get_resource_manager
        except Exception as exc:
            log.warning(f"[{self._log_prefix}] common Termin MCP context is incomplete: {exc}")
            return

        namespace["rm"] = get_resource_manager()
        namespace["resource_manager"] = namespace["rm"]
        namespace["termin"] = termin
        namespace["Vec3"] = Vec3
        namespace["Vec4"] = Vec4
        namespace["Quat"] = Quat
        namespace["Pose3"] = Pose3
        namespace["GeneralPose3"] = GeneralPose3
        namespace["GeneralTransform3"] = GeneralTransform3

    def _add_runtime_context(self, namespace: dict[str, object | None]) -> None:
        del namespace
