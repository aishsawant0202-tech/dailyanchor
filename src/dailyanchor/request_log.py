"""One log line per MCP request: who called, which JSON-RPC method/tool, and the status.

Used to confirm a real client (e.g. Alexa+) is reaching the server, not just a local test
client. Behind a tunnel (cloudflared, ngrok) the TCP peer is always 127.0.0.1, so the
Host and forwarded-for headers are what tell tunnelled traffic apart from local calls.
"""

import json
import logging
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("dailyanchor.requests")


def describe_rpc(body: bytes) -> str:
    """Summarise a JSON-RPC body as e.g. "tools/call mark_step_done", or "-" if not JSON-RPC."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return "-"
    messages = payload if isinstance(payload, list) else [payload]
    parts = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        method = msg.get("method")
        if method is None:
            parts.append("response" if "result" in msg or "error" in msg else "?")
            continue
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if method == "tools/call":
            parts.append(f"tools/call {params.get('name', '?')}")
        elif method == "initialize":
            client = params.get("clientInfo") or {}
            parts.append(f"initialize client={client.get('name', '?')}/{client.get('version', '?')}")
        else:
            parts.append(method)
    return ", ".join(parts) or "-"


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return ""


class RequestLogMiddleware:
    """ASGI middleware that logs requests under `path`; everything else passes through."""

    def __init__(self, app: ASGIApp, path: str) -> None:
        self.app = app
        self.path = path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.path):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        body = b""
        replay: list[Message] = []
        if scope["method"] == "POST":
            # Read the whole body to parse it, then hand the same messages to the app.
            while True:
                message = await receive()
                replay.append(message)
                if message["type"] != "http.request":
                    break
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break

        async def replay_receive() -> Message:
            return replay.pop(0) if replay else await receive()

        status: dict[str, Any] = {"code": "?"}

        async def logging_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, replay_receive, logging_send)
        finally:
            peer = scope.get("client") or ("?", 0)
            forwarded = _header(scope, b"cf-connecting-ip") or _header(scope, b"x-forwarded-for")
            logger.info(
                "%s %s %s -> %s (%.0f ms) host=%s peer=%s%s%s",
                scope["method"],
                scope["path"],
                describe_rpc(body) if body else "",
                status["code"],
                (time.monotonic() - start) * 1000,
                _header(scope, b"host") or "-",
                peer[0],
                f" forwarded={forwarded}" if forwarded else "",
                f" session={sid[:8]}" if (sid := _header(scope, b"mcp-session-id")) else "",
            )
