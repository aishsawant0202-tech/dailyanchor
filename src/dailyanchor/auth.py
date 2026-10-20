"""Shared-secret check for the MCP endpoint, so a public deployment isn't writable by anyone
who finds the URL. Clients send `Authorization: Bearer <key>`; the dashboard stays open."""

import hmac

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ApiKeyMiddleware:
    """ASGI middleware that rejects requests under `path` without the right bearer token."""

    def __init__(self, app: ASGIApp, path: str, api_key: str) -> None:
        self.app = app
        self.path = path
        self.expected = f"Bearer {api_key}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.path):
            await self.app(scope, receive, send)
            return
        provided = dict(scope.get("headers", [])).get(b"authorization", b"")
        if not hmac.compare_digest(provided, self.expected):
            response = PlainTextResponse(
                "Missing or invalid API key", status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
