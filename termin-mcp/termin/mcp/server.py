"""Shared MCP-compatible JSON-RPC server for Termin processes."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tcbase import log

from termin.mcp.python_executor import PythonExecutionResult, PythonScriptExecutor


@dataclass(frozen=True)
class TerminMcpConfig:
    host: str
    port: int
    token: str
    session_file: Path


def create_secure_mcp_config(
    *,
    host: object,
    port: object,
    token: object,
    session_file: str | Path,
    default_host: str,
    default_port: int,
    log_prefix: str,
) -> TerminMcpConfig:
    resolved_host = host.strip() if isinstance(host, str) else ""
    if not resolved_host:
        log.error(f"[{log_prefix}] invalid empty MCP host; using {default_host}")
        resolved_host = default_host

    try:
        resolved_port = int(port)
    except (TypeError, ValueError):
        resolved_port = default_port
        log.error(f"[{log_prefix}] invalid MCP port {port!r}; using {default_port}")
    if not 1 <= resolved_port <= 65535:
        log.error(f"[{log_prefix}] MCP port {resolved_port} is outside 1..65535; using {default_port}")
        resolved_port = default_port

    resolved_token = token.strip() if isinstance(token, str) else ""
    if not resolved_token:
        resolved_token = secrets.token_urlsafe(24)
        log.warning(
            f"[{log_prefix}] empty or invalid MCP token replaced with a generated token; "
            "unauthenticated execution is disabled"
        )

    return TerminMcpConfig(
        host=resolved_host,
        port=resolved_port,
        token=resolved_token,
        session_file=Path(session_file),
    )


class TerminMcpServer:
    def __init__(
        self,
        executor: PythonScriptExecutor,
        config: TerminMcpConfig,
        *,
        log_prefix: str = "TerminMCP",
        server_name: str = "termin",
        server_version: str = "TerminMCP/0.1",
        thread_name: str = "termin-mcp",
    ) -> None:
        self._executor = executor
        self._config = config
        self._log_prefix = log_prefix
        self._server_name = server_name
        self._server_version = server_version
        self._thread_name = thread_name
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        server = self._httpd
        if server is None:
            return f"http://{self._config.host}:{self._config.port}/mcp"
        host, port = server.server_address
        return f"http://{host}:{port}/mcp"

    def start(self) -> None:
        handler_class = self._make_handler()
        self._httpd = ThreadingHTTPServer(
            (self._config.host, self._config.port),
            handler_class,
        )
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name=self._thread_name,
            daemon=True,
        )
        self._thread.start()
        self._write_session_file()
        log.info(f"[{self._log_prefix}] listening on {self.url}")

    def stop(self) -> None:
        server = self._httpd
        if server is not None:
            server.shutdown()
            server.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            self._config.session_file.unlink(missing_ok=True)
        except OSError as exc:
            log.error(f"[{self._log_prefix}] failed to remove session file: {exc}")

    def _write_session_file(self) -> None:
        path = self._config.session_file
        payload = {
            "pid": os.getpid(),
            "url": self.url,
            "token": self._config.token,
            "started_at": time.time(),
            "server": self._server_name,
            "tools": [schema["name"] for schema in self._tool_schemas()],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(path)
        except OSError as exc:
            log.error(f"[{self._log_prefix}] failed to write session file '{path}': {exc}")

    def _make_handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = owner._server_version

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._send_json({"ok": True, "server": owner._server_name})
                    return
                self.send_error(404)

            def do_POST(self) -> None:
                if self.path not in ("/mcp", "/jsonrpc"):
                    self.send_error(404)
                    return
                if not self._is_authorized():
                    self._send_json(
                        self._error_response(None, -32001, "Unauthorized"),
                        status=401,
                    )
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(length).decode("utf-8")
                    request = json.loads(body)
                except Exception as exc:
                    log.error(f"[{owner._log_prefix}] invalid JSON-RPC request: {exc}")
                    self._send_json(self._error_response(None, -32700, "Parse error"))
                    return

                if isinstance(request, list):
                    if not request:
                        self._send_json(self._error_response(None, -32600, "Invalid Request"))
                        return
                    responses = [
                        response
                        for item in request
                        if (response := owner._handle_rpc(item)) is not None
                    ]
                    if not responses:
                        self.send_response(204)
                        self.end_headers()
                        return
                    self._send_json(responses)
                    return

                response = owner._handle_rpc(request)
                if response is None:
                    self.send_response(204)
                    self.end_headers()
                    return
                self._send_json(response)

            def log_message(self, fmt: str, *args: object) -> None:
                log.debug(f"[{owner._log_prefix}] {fmt % args}")

            def _is_authorized(self) -> bool:
                token = owner._config.token
                if not token:
                    log.error(f"[{owner._log_prefix}] refusing request because MCP token is empty")
                    return False
                header = self.headers.get("Authorization", "")
                if header == f"Bearer {token}":
                    return True
                return self.headers.get("X-Termin-MCP-Token", "") == token

            def _send_json(self, payload: Any, *, status: int = 200) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _error_response(
                self,
                request_id: object,
                code: int,
                message: str,
            ) -> dict[str, object]:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": code, "message": message},
                }

        return Handler

    def _handle_rpc(self, request: Any) -> dict[str, object] | None:
        if not isinstance(request, dict):
            return self._rpc_error(None, -32600, "Invalid Request")
        if request.get("jsonrpc") != "2.0":
            return self._rpc_error(None, -32600, "Invalid Request")
        method = request.get("method")
        if not isinstance(method, str) or not method:
            return self._rpc_error(None, -32600, "Invalid Request")

        is_notification = "id" not in request
        request_id = request.get("id")
        if not is_notification and (isinstance(request_id, bool) or not isinstance(request_id, (str, int, float, type(None)))):
            return self._rpc_error(None, -32600, "Invalid Request")

        try:
            if method == "initialize":
                response = self._rpc_result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": self._server_name,
                            "version": "0.1.0",
                        },
                    },
                )
            elif method == "ping":
                response = self._rpc_result(request_id, {})
            elif method == "tools/list":
                response = self._rpc_result(request_id, {"tools": self._tool_schemas()})
            elif method == "tools/call":
                response = self._handle_tool_call(request_id, request.get("params"))
            elif method == "termin/execute_python":
                params = request.get("params")
                if not isinstance(params, dict):
                    response = self._rpc_error(request_id, -32602, "Invalid params")
                else:
                    response = self._rpc_result(
                        request_id,
                        self._execute_python_result(
                            str(params.get("script", "")),
                            timeout=float(params.get("timeout", 30.0)),
                        ),
                    )
            else:
                response = self._rpc_error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            log.error(f"[{self._log_prefix}] request handling failed: {exc}")
            response = self._rpc_error(request_id, -32603, f"Internal error: {exc}")

        return None if is_notification else response

    def _handle_tool_call(
        self,
        request_id: object,
        params: object,
    ) -> dict[str, object]:
        if not isinstance(params, dict):
            return self._rpc_error(request_id, -32602, "Invalid params")
        name = params.get("name")
        if name != "execute_python_script":
            return self._rpc_error(request_id, -32602, f"Unknown tool: {name}")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            return self._rpc_error(request_id, -32602, "Tool arguments must be an object")

        script = str(arguments.get("script", ""))
        timeout = float(arguments.get("timeout", 30.0))
        result = self._execute_python(script, timeout=timeout)
        return self._rpc_result(
            request_id,
            {
                "content": [{"type": "text", "text": result.output or ""}],
                "isError": not result.ok,
                "structuredContent": self._result_payload(result),
            },
        )

    def _execute_python_result(self, script: str, *, timeout: float) -> dict[str, object]:
        return self._result_payload(self._execute_python(script, timeout=timeout))

    def _execute_python(self, script: str, *, timeout: float) -> PythonExecutionResult:
        return self._executor.execute_script_from_any_thread(script, timeout=timeout)

    def _tool_schemas(self) -> list[dict[str, object]]:
        return [self._execute_python_tool_schema()]

    def _execute_python_tool_schema(self) -> dict[str, object]:
        return {
            "name": "execute_python_script",
            "description": "Execute a Python script inside the running Termin process.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Python source code to execute in the process namespace.",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the runtime thread to run the script.",
                        "default": 30,
                    },
                },
                "required": ["script"],
                "additionalProperties": False,
            },
        }

    def _result_payload(self, result: PythonExecutionResult) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": result.ok,
            "output": result.output,
            "wants_more": result.wants_more,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def _rpc_result(self, request_id: object, result: object) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _rpc_error(self, request_id: object, code: int, message: str) -> dict[str, object]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
