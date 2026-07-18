import json
import queue
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPOSITORY_ROOT / "scripts" / "termin-editor-mcp"


class _EditorEndpoint:
    def __init__(self, token: str) -> None:
        self.token = token
        self.requests: list[dict[str, object]] = []
        self._server = self._create_server()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/mcp"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)

    def _create_server(self) -> ThreadingHTTPServer:
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                assert self.headers["Authorization"] == f"Bearer {endpoint.token}"
                length = int(self.headers["Content-Length"])
                request = json.loads(self.rfile.read(length))
                endpoint.requests.append(request)

                method = request["method"]
                if method == "tools/list":
                    result = {
                        "tools": [
                            {
                                "name": "execute_python_script",
                                "description": "Execute Python in the editor.",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"script": {"type": "string"}},
                                    "required": ["script"],
                                },
                            }
                        ]
                    }
                elif method == "tools/call":
                    result = {
                        "content": [{"type": "text", "text": "editor result\n"}],
                        "isError": False,
                    }
                else:
                    self.send_response(204)
                    self.end_headers()
                    return

                body = json.dumps(
                    {"jsonrpc": "2.0", "id": request["id"], "result": result}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: object) -> None:
                pass

        try:
            return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except OSError as exc:
            pytest.skip(f"local loopback listener is unavailable: {exc}")


class _BrokerProcess:
    def __init__(self, session_file: Path) -> None:
        self.process = subprocess.Popen(
            [sys.executable, str(HELPER), "--session", str(session_file), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self._responses: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        line = self._responses.get(timeout=5.0)
        return json.loads(line)

    def notify(self, payload: dict[str, object]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def close(self) -> tuple[str, str]:
        assert self.process.stdin is not None
        self.process.stdin.close()
        return_code = self.process.wait(timeout=5.0)
        assert return_code == 0
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        stdout_tail = self.process.stdout.read()
        stderr = self.process.stderr.read()
        return stdout_tail, stderr

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._responses.put(line)


def _write_session(path: Path, endpoint: _EditorEndpoint) -> None:
    path.write_text(
        json.dumps({"url": endpoint.url, "token": endpoint.token}),
        encoding="utf-8",
    )


def _initialize(broker: _BrokerProcess) -> None:
    response = broker.request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
    )
    assert response["result"]["protocolVersion"] == "2025-11-25"
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    broker.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})


def test_stdio_broker_enforces_lifecycle_and_negotiates_version(tmp_path: Path):
    broker = _BrokerProcess(tmp_path / "missing-session.json")
    try:
        before_initialize = broker.request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        assert before_initialize["error"] == {
            "code": -32002,
            "message": "Server not initialized",
        }

        initialized = broker.request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2099-01-01",
                    "capabilities": {},
                    "clientInfo": {"name": "future-client", "version": "1.0"},
                },
            }
        )
        assert initialized["result"]["protocolVersion"] == "2025-11-25"

        before_ready = broker.request(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        )
        assert before_ready["error"]["code"] == -32002

        broker.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
        unavailable = broker.request(
            {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}}
        )
        assert unavailable["error"]["code"] == -32050

        stdout_tail, stderr = broker.close()
        assert stdout_tail == ""
        assert "Session file not found" in stderr
    finally:
        if broker.process.poll() is None:
            broker.process.terminate()


def test_stdio_broker_proxies_tools_without_polluting_stdout(tmp_path: Path):
    endpoint = _EditorEndpoint("first-token")
    endpoint.start()
    session_file = tmp_path / "editor-session.json"
    _write_session(session_file, endpoint)
    broker = _BrokerProcess(session_file)
    try:
        _initialize(broker)
        listed = broker.request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert listed["result"]["tools"][0]["name"] == "execute_python_script"

        called = broker.request(
            {
                "jsonrpc": "2.0",
                "id": "call",
                "method": "tools/call",
                "params": {
                    "name": "execute_python_script",
                    "arguments": {"script": "print('hello')"},
                },
            }
        )
        assert called["result"]["content"] == [
            {"type": "text", "text": "editor result\n"}
        ]
        assert [request["method"] for request in endpoint.requests] == [
            "tools/list",
            "tools/call",
        ]
        stdout_tail, stderr = broker.close()
        assert stdout_tail == ""
        assert stderr == ""
    finally:
        endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()


def test_stdio_broker_reports_unavailable_and_reconnects(tmp_path: Path):
    session_file = tmp_path / "editor-session.json"
    broker = _BrokerProcess(session_file)
    endpoint = _EditorEndpoint("replacement-token")
    try:
        _initialize(broker)
        unavailable = broker.request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert unavailable["error"]["code"] == -32050
        assert unavailable["error"]["message"] == "Termin Editor is unavailable"
        assert unavailable["error"]["data"]["sessionFile"] == str(session_file)

        endpoint.start()
        _write_session(session_file, endpoint)
        listed = broker.request(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        )
        assert listed["result"]["tools"][0]["name"] == "execute_python_script"

        stdout_tail, stderr = broker.close()
        assert stdout_tail == ""
        assert "Session file not found" in stderr
    finally:
        endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()
