import json
from pathlib import Path
from urllib.request import Request, urlopen

from termin.mcp.server import TerminMcpConfig, TerminMcpServer


class _Executor:
    def execute_script_from_any_thread(self, script: str, *, timeout: float):
        raise AssertionError(f"notification should not execute test script: {script!r}")


def _server(tmp_path: Path) -> TerminMcpServer:
    return TerminMcpServer(
        _Executor(),
        TerminMcpConfig("127.0.0.1", 0, "token", tmp_path / "session.json"),
    )


def test_jsonrpc_requests_and_notifications_follow_the_contract(tmp_path: Path):
    server = _server(tmp_path)
    assert server._handle_rpc({"jsonrpc": "2.0", "method": "ping", "id": "request"}) == {
        "jsonrpc": "2.0", "id": "request", "result": {}
    }
    assert server._handle_rpc({"jsonrpc": "2.0", "method": "ping"}) is None
    assert server._handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server._handle_rpc({"method": "ping", "id": 1})["error"]["code"] == -32600
    assert server._handle_rpc({"jsonrpc": "2.0", "method": "ping", "id": True})["error"]["code"] == -32600
    assert server._handle_rpc({"jsonrpc": "2.0", "method": "missing", "id": None})["error"]["code"] == -32601


def test_jsonrpc_batches_omit_notification_responses(tmp_path: Path):
    server = _server(tmp_path)
    server.start()
    try:
        def post(payload: object):
            request = Request(
                server.url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "X-Termin-MCP-Token": "token"},
            )
            with urlopen(request) as response:
                return response.status, response.read()

        status, body = post([])
        assert status == 200
        assert json.loads(body)["error"]["code"] == -32600

        status, body = post([{"jsonrpc": "2.0", "method": "ping"}])
        assert status == 204
        assert body == b""

        status, body = post([
            {"jsonrpc": "2.0", "method": "ping"},
            {"jsonrpc": "2.0", "method": "ping", "id": 1},
        ])
        assert status == 200
        assert json.loads(body) == [{"jsonrpc": "2.0", "id": 1, "result": {}}]
    finally:
        server.stop()
