from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from dailyanchor.auth import ApiKeyMiddleware


def _client():
    async def ok(request: Request):
        return PlainTextResponse("ok")

    inner = Starlette(routes=[Route("/mcp", ok, methods=["POST"]), Route("/dashboard", ok)])
    return TestClient(ApiKeyMiddleware(inner, "/mcp", "s3cret"))


def test_mcp_requires_key():
    client = _client()
    assert client.post("/mcp").status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_dashboard_stays_open():
    assert _client().get("/dashboard").status_code == 200
