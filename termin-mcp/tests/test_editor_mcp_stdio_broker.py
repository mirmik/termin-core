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
                if method == "tools/call":
                    result = {
                        "content": [{"type": "text", "text": "editor result\n"}],
                        "isError": False,
                    }
                elif method == "ping":
                    result = {}
                else:
                    self.send_response(204)
                    self.end_headers()
                    return

                body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()
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
    def __init__(
        self,
        session_file: Path | None = None,
        *,
        registry_dir: Path | None = None,
        project: Path | None = None,
        instance_id: str | None = None,
    ) -> None:
        args = [sys.executable, str(HELPER)]
        if session_file is not None:
            args.extend(["--session", str(session_file)])
        if registry_dir is not None:
            args.extend(["--registry", str(registry_dir)])
        if project is not None:
            args.extend(["--project", str(project)])
        if instance_id is not None:
            args.extend(["--instance", instance_id])
        args.append("serve")
        self.process = subprocess.Popen(
            args,
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


def _write_session(
    path: Path,
    endpoint: _EditorEndpoint,
    *,
    instance_id: str = "test-instance",
    project_path: Path | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "instance_id": instance_id,
                "pid": 123,
                "project_path": str(project_path) if project_path is not None else None,
                "started_at": 1.0,
                "url": endpoint.url,
                "token": endpoint.token,
            }
        ),
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


def _call_execute(broker: _BrokerProcess, request_id: str, marker: str) -> dict[str, object]:
    return broker.request(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "execute_python_script",
                "arguments": {"script": f"print({marker!r})"},
            },
        }
    )


def test_two_brokers_keep_explicit_editor_sessions_isolated(tmp_path: Path):
    first_endpoint = _EditorEndpoint("first-token")
    second_endpoint = _EditorEndpoint("second-token")
    first_endpoint.start()
    second_endpoint.start()
    first_session = tmp_path / "first" / "session.json"
    second_session = tmp_path / "second" / "session.json"
    first_session.parent.mkdir()
    second_session.parent.mkdir()
    _write_session(first_session, first_endpoint)
    _write_session(second_session, second_endpoint)
    first_broker = _BrokerProcess(first_session)
    second_broker = _BrokerProcess(second_session)
    try:
        _initialize(first_broker)
        _initialize(second_broker)

        assert _call_execute(first_broker, "first-call", "first")["result"]["isError"] is False
        assert _call_execute(second_broker, "second-call", "second")["result"]["isError"] is False
        assert first_endpoint.requests[0]["params"]["arguments"]["script"] == "print('first')"
        assert second_endpoint.requests[0]["params"]["arguments"]["script"] == "print('second')"

        assert first_broker.close() == ("", "")
        assert second_broker.close() == ("", "")
    finally:
        first_endpoint.stop()
        second_endpoint.stop()
        if first_broker.process.poll() is None:
            first_broker.process.terminate()
        if second_broker.process.poll() is None:
            second_broker.process.terminate()


def test_registry_broker_selects_user_editor_by_project(tmp_path: Path):
    first_endpoint = _EditorEndpoint("first-token")
    second_endpoint = _EditorEndpoint("second-token")
    first_endpoint.start()
    second_endpoint.start()
    registry = tmp_path / "registry"
    first_project = tmp_path / "first-project"
    second_project = tmp_path / "second-project"
    first_project.mkdir()
    second_project.mkdir()
    _write_session(
        registry / "first.json",
        first_endpoint,
        instance_id="first-instance",
        project_path=first_project,
    )
    _write_session(
        registry / "second.json",
        second_endpoint,
        instance_id="second-instance",
        project_path=second_project,
    )
    broker = _BrokerProcess(registry_dir=registry, project=first_project)
    try:
        _initialize(broker)

        called = _call_execute(broker, "project-call", "selected-project")

        assert called["result"]["isError"] is False
        assert first_endpoint.requests[0]["params"]["arguments"]["script"] == ("print('selected-project')")
        assert second_endpoint.requests == []
        assert broker.close() == ("", "")
    finally:
        first_endpoint.stop()
        second_endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()


def test_registry_broker_reports_ambiguity_for_two_live_editors_of_one_project(
    tmp_path: Path,
):
    first_endpoint = _EditorEndpoint("first-token")
    second_endpoint = _EditorEndpoint("second-token")
    first_endpoint.start()
    second_endpoint.start()
    registry = tmp_path / "registry"
    project = tmp_path / "project"
    project.mkdir()
    _write_session(
        registry / "first.json",
        first_endpoint,
        instance_id="first-instance",
        project_path=project,
    )
    _write_session(
        registry / "second.json",
        second_endpoint,
        instance_id="second-instance",
        project_path=project,
    )
    broker = _BrokerProcess(registry_dir=registry, project=project)
    try:
        _initialize(broker)

        unavailable = _call_execute(broker, "ambiguous-call", "ambiguous")

        assert unavailable["error"]["code"] == -32050
        assert "Multiple editor instances" in unavailable["error"]["data"]["detail"]
        assert "first-instance" in unavailable["error"]["data"]["detail"]
        assert "second-instance" in unavailable["error"]["data"]["detail"]
        assert [request["method"] for request in first_endpoint.requests] == ["ping"]
        assert [request["method"] for request in second_endpoint.requests] == ["ping"]
        _, stderr = broker.close()
        assert "Multiple editor instances" in stderr
    finally:
        first_endpoint.stop()
        second_endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()


def test_registry_broker_can_select_one_instance_explicitly(tmp_path: Path):
    first_endpoint = _EditorEndpoint("first-token")
    second_endpoint = _EditorEndpoint("second-token")
    first_endpoint.start()
    second_endpoint.start()
    registry = tmp_path / "registry"
    project = tmp_path / "project"
    project.mkdir()
    _write_session(
        registry / "first.json",
        first_endpoint,
        instance_id="first-instance",
        project_path=project,
    )
    _write_session(
        registry / "second.json",
        second_endpoint,
        instance_id="second-instance",
        project_path=project,
    )
    broker = _BrokerProcess(
        registry_dir=registry,
        project=project,
        instance_id="second-instance",
    )
    try:
        _initialize(broker)

        called = _call_execute(broker, "instance-call", "second")

        assert called["result"]["isError"] is False
        assert first_endpoint.requests == []
        assert second_endpoint.requests[0]["params"]["arguments"]["script"] == "print('second')"
        assert broker.close() == ("", "")
    finally:
        first_endpoint.stop()
        second_endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()


def test_sessions_command_lists_reachability_without_tokens(tmp_path: Path):
    endpoint = _EditorEndpoint("secret-token")
    endpoint.start()
    registry = tmp_path / "registry"
    project = tmp_path / "project"
    _write_session(
        registry / "editor.json",
        endpoint,
        instance_id="listed-instance",
        project_path=project,
    )
    try:
        completed = subprocess.run(
            [sys.executable, str(HELPER), "--registry", str(registry), "sessions"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        sessions = json.loads(completed.stdout)
        assert sessions == [
            {
                "instanceId": "listed-instance",
                "pid": 123,
                "projectPath": str(project),
                "startedAt": 1.0,
                "sessionFile": str(registry / "editor.json"),
                "reachable": True,
            }
        ]
        assert "secret-token" not in completed.stdout
    finally:
        endpoint.stop()


def test_registry_broker_ignores_stale_descriptor_when_one_match_is_live(tmp_path: Path):
    endpoint = _EditorEndpoint("live-token")
    endpoint.start()
    registry = tmp_path / "registry"
    project = tmp_path / "project"
    project.mkdir()
    stale = registry / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(
        json.dumps(
            {
                "instance_id": "stale-instance",
                "pid": 999999,
                "project_path": str(project),
                "started_at": 0.0,
                "url": "http://127.0.0.1:1/mcp",
                "token": "stale-token",
            }
        ),
        encoding="utf-8",
    )
    _write_session(
        registry / "live.json",
        endpoint,
        instance_id="live-instance",
        project_path=project,
    )
    broker = _BrokerProcess(registry_dir=registry, project=project)
    try:
        _initialize(broker)

        called = _call_execute(broker, "live-call", "live")

        assert called["result"]["isError"] is False
        assert [request["method"] for request in endpoint.requests] == ["ping", "tools/call"]
        assert stale.exists()
        assert broker.close() == ("", "")
    finally:
        endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()


def test_stdio_broker_enforces_lifecycle_and_negotiates_version(tmp_path: Path):
    broker = _BrokerProcess(tmp_path / "missing-session.json")
    try:
        before_initialize = broker.request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
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

        before_ready = broker.request({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
        assert before_ready["error"]["code"] == -32002

        broker.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
        listed = broker.request({"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}})
        assert [tool["name"] for tool in listed["result"]["tools"]] == [
            "execute_python_script",
            "capture_editor_screenshot",
            "inspect_framegraph",
            "capture_framegraph_resource",
            "capture_framegraph_pass_symbol",
        ]

        stdout_tail, stderr = broker.close()
        assert stdout_tail == ""
        assert stderr == ""
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
        listed = broker.request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
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
        assert called["result"]["content"] == [{"type": "text", "text": "editor result\n"}]
        assert [request["method"] for request in endpoint.requests] == ["tools/call"]
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
    endpoint = _EditorEndpoint("initial-token")
    replacement_endpoint = _EditorEndpoint("replacement-token")
    try:
        _initialize(broker)
        listed = broker.request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert listed["result"]["tools"][0]["name"] == "execute_python_script"

        unavailable = broker.request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "execute_python_script",
                    "arguments": {"script": "print('before editor')"},
                },
            }
        )
        assert unavailable["error"]["code"] == -32050
        assert unavailable["error"]["message"] == "Termin Editor is unavailable"
        assert unavailable["error"]["data"]["sessionFile"] == str(session_file)

        endpoint.start()
        _write_session(session_file, endpoint)
        called = broker.request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "execute_python_script",
                    "arguments": {"script": "print('after editor')"},
                },
            }
        )
        assert called["result"]["content"] == [{"type": "text", "text": "editor result\n"}]
        assert [request["method"] for request in endpoint.requests] == ["tools/call"]

        endpoint.stop()
        unavailable_after_stop = broker.request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "execute_python_script",
                    "arguments": {"script": "print('during restart')"},
                },
            }
        )
        assert unavailable_after_stop["error"]["code"] == -32050
        assert unavailable_after_stop["error"]["message"] == "Termin Editor is unavailable"

        replacement_endpoint.start()
        _write_session(session_file, replacement_endpoint)
        called_after_restart = broker.request(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "execute_python_script",
                    "arguments": {"script": "print('after restart')"},
                },
            }
        )
        assert called_after_restart["result"]["content"] == [{"type": "text", "text": "editor result\n"}]
        assert [request["method"] for request in replacement_endpoint.requests] == ["tools/call"]

        stdout_tail, stderr = broker.close()
        assert stdout_tail == ""
        assert "Session file not found" in stderr
    finally:
        endpoint.stop()
        replacement_endpoint.stop()
        if broker.process.poll() is None:
            broker.process.terminate()
