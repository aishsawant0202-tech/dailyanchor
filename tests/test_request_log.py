import json
import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from dailyanchor.request_log import RequestLogMiddleware, describe_rpc


def test_describe_rpc_tool_call():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "mark_step_done", "arguments": {}}})
    assert describe_rpc(body.encode()) == "tools/call mark_step_done"


def test_describe_rpc_initialize_names_client():
    body = json.dumps({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                       "params": {"clientInfo": {"name": "alexa", "version": "1.0"}}})
    assert describe_rpc(body.encode()) == "initialize client=alexa/1.0"


def test_describe_rpc_batch_and_garbage():
    batch = [{"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    assert describe_rpc(json.dumps(batch).encode()) == "notifications/initialized, tools/list"
    assert describe_rpc(b"not json") == "-"


def _app():
    async def echo(request: Request):
        return JSONResponse(await request.json(), status_code=202)

    async def other(request: Request):
        return JSONResponse({})

    inner = Starlette(routes=[Route("/mcp", echo, methods=["POST"]), Route("/other", other)])
    return RequestLogMiddleware(inner, "/mcp")


def test_middleware_logs_and_passes_body_through(caplog):
    client = TestClient(_app())
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_routines"}}
    with caplog.at_level(logging.INFO, logger="dailyanchor.requests"):
        resp = client.post("/mcp", json=body, headers={"X-Forwarded-For": "203.0.113.7"})
    assert resp.status_code == 202
    assert resp.json() == body  # the app still sees the full body after the middleware read it
    [line] = [r.getMessage() for r in caplog.records]
    assert "POST /mcp tools/call list_routines -> 202" in line
    assert "forwarded=203.0.113.7" in line


def test_middleware_ignores_other_paths(caplog):
    with caplog.at_level(logging.INFO, logger="dailyanchor.requests"):
        TestClient(_app()).get("/other")
    assert caplog.records == []
