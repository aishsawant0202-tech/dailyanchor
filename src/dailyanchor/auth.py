"""Shared-secret check for the MCP endpoint, so a public deployment isn't writable by anyone
who finds the URL. Clients send `Authorization: Bearer <key>`; the dashboard stays open."""

import hmac

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def bearer_matches(authorization: str | bytes, api_key: str) -> bool:
    """Whether an Authorization header value carries this API key, compared in constant time."""
    if isinstance(authorization, str):
        authorization = authorization.encode()
    return hmac.compare_digest(authorization, f"Bearer {api_key}".encode())


class ApiKeyMiddleware:
    """ASGI middleware that rejects requests under `path` without the right bearer token."""

    def __init__(self, app: ASGIApp, path: str, api_key: str) -> None:
        self.app = app
        self.path = path
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.path):
            await self.app(scope, receive, send)
            return
        provided = dict(scope.get("headers", [])).get(b"authorization", b"")
        if not bearer_matches(provided, self.api_key):
            response = PlainTextResponse(
                "Missing or invalid API key", status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
