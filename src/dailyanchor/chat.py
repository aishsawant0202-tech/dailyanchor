"""Live chat for the web simulator: an OpenAI model stands in for Alexa+ and answers with
the DailyAnchor tools. There are two ways the model reaches the tools:

- chat_via_remote_mcp(): OpenAI's Responses API connects to this server's public /mcp
  endpoint itself, as Alexa+ would. Needs a URL OpenAI can reach (the deployed server).
- chat(): for a server OpenAI can't reach (localhost), the tool loop runs here instead.

chat() runs the tool loop: send the conversation and the tool list to the model, run any
tools it asks for, send the results back, repeat until it answers in words. The model call
and the tool call are both passed in, so the loop is tested without a network or an MCP
server; server.py wires them to the OpenAI API and to the MCP tools in-process.
"""

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

# OPENAI_BASE_URL points at another OpenAI-compatible endpoint (or a local fake for testing).
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
DEFAULT_MODEL = "gpt-5-mini"
MAX_TOOL_ROUNDS = 6
MAX_HISTORY = 20
MAX_MESSAGE_CHARS = 2000

SKILL_FILE = Path("skills") / "dailyanchor-care-assistant" / "SKILL.md"
FALLBACK_REPLY = "Sorry, I got a bit muddled there. Could you ask me again?"

Complete = Callable[[dict], Awaitable[dict]]
CallTool = Callable[[str, dict], Awaitable[Any]]


class ChatError(Exception):
    """The model call failed; the message is safe to show on the page."""


def load_skill() -> str:
    """The care-assistant Agent Skill without its frontmatter, so the model follows the same
    workflow as an agent with the skill installed. Looked up from the working directory
    (the repo root locally, /app in the container), then next to the source tree."""
    for path in (Path.cwd() / SKILL_FILE, Path(__file__).resolve().parents[2] / SKILL_FILE):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                text = text.split("---", 2)[2]
            return text.strip()
    return ""


def system_prompt(now: datetime, skill: str) -> str:
    return (
        "You are Alexa+, the voice assistant in Margaret's home, connected to the DailyAnchor "
        "tools. Margaret is 78 and lives alone with early-stage memory loss. Her daughter "
        "Priya is her caregiver and checks in by phone.\n"
        "Each user message starts with who is speaking, e.g. 'Margaret: ...' or 'Priya: ...'. "
        "Answer that person.\n"
        f"It is {now:%A %d %B %Y, %H:%M} where Margaret lives.\n"
        "Your replies are spoken aloud: one to three short sentences, plain text, no lists, "
        "markdown or emoji. Get every fact about routines from the tools, never from memory.\n\n"
        + skill
    )


def openai_tools(tools: list) -> list[dict]:
    """MCP tool definitions (name, description, input_schema) as OpenAI function tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def clean_history(raw: Any) -> list[dict]:
    """The browser's conversation, reduced to the last few user/assistant text turns."""
    if not isinstance(raw, list):
        return []
    history = [
        {"role": item["role"], "content": item["content"][:MAX_MESSAGE_CHARS]}
        for item in raw
        if isinstance(item, dict)
        and item.get("role") in ("user", "assistant")
        and isinstance(item.get("content"), str)
        and item["content"].strip()
    ]
    return history[-MAX_HISTORY:]


async def chat(
    history: list[dict],
    *,
    tools: list[dict],
    call_tool: CallTool,
    complete: Complete,
    now: datetime | None = None,
    skill: str = "",
) -> dict:
    """Run one turn. Returns the spoken reply and every tool call made for it."""
    messages = [{"role": "system", "content": system_prompt(now or datetime.now(), skill)}]
    messages += history
    calls = []
    for _ in range(MAX_TOOL_ROUNDS):
        response = await complete({"messages": messages, "tools": tools})
        message = response["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return {"reply": (message.get("content") or "").strip() or FALLBACK_REPLY, "tool_calls": calls}

        messages.append(message)
        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            started = time.monotonic()
            arguments: Any = tool_call["function"].get("arguments") or "{}"
            try:
                arguments = json.loads(arguments)
                result = await call_tool(name, arguments)
                error = False
            except Exception as exc:  # reported back to the model, which explains it
                result = {"status": "error", "message": str(exc)}
                error = True
            calls.append(
                {
                    "name": name,
                    "arguments": arguments,
                    "result": result,
                    "ms": round((time.monotonic() - started) * 1000),
                    "error": error,
                }
            )
            messages.append(
                {"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(result, default=str)}
            )
    return {"reply": FALLBACK_REPLY, "tool_calls": calls}


def _parse_json(text: Any) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


async def chat_via_remote_mcp(
    history: list[dict],
    *,
    server_url: str,
    mcp_api_key: str,
    respond: Complete,
    now: datetime | None = None,
    skill: str = "",
) -> dict:
    """Run one turn with OpenAI calling `server_url` over MCP. Returns the same shape as chat();
    the tool calls are the mcp_call items OpenAI reports, since it made them, not us."""
    tool = {
        "type": "mcp",
        "server_label": "dailyanchor",
        "server_description": "Margaret's daily routines, reminders and caregiver summary.",
        "server_url": server_url,
        # The care-assistant skill already says when to ask before changing anything.
        "require_approval": "never",
    }
    if mcp_api_key:
        tool["authorization"] = mcp_api_key  # sent as "Authorization: Bearer <key>"
    response = await respond(
        {"instructions": system_prompt(now or datetime.now(), skill), "input": history, "tools": [tool]}
    )

    calls, texts = [], []
    for item in response.get("output") or []:
        kind = item.get("type")
        if kind == "mcp_call":
            error = item.get("error")
            calls.append(
                {
                    "name": item.get("name", "?"),
                    "arguments": _parse_json(item.get("arguments") or "{}"),
                    "result": error if error else _parse_json(item.get("output")),
                    "ms": None,
                    "error": bool(error),
                }
            )
        elif kind == "mcp_list_tools" and item.get("error"):
            calls.append({"name": "tools/list", "arguments": {}, "result": item["error"], "ms": None, "error": True})
        elif kind == "message":
            texts += [part.get("text", "") for part in item.get("content") or [] if part.get("type") == "output_text"]
    reply = " ".join(text.strip() for text in texts if text.strip())
    return {"reply": reply or FALLBACK_REPLY, "tool_calls": calls}


def openai_completer(api_key: str, model: str = DEFAULT_MODEL) -> Complete:
    """Chat Completions, for chat()."""
    return _openai_poster(f"{OPENAI_BASE_URL}/chat/completions", api_key, model)


def openai_responder(api_key: str, model: str = DEFAULT_MODEL) -> Complete:
    """The Responses API, for chat_via_remote_mcp()."""
    return _openai_poster(f"{OPENAI_BASE_URL}/responses", api_key, model)


def _openai_poster(url: str, api_key: str, model: str) -> Complete:
    """POST to an OpenAI endpoint over plain urllib (in a thread), to avoid a new dependency."""

    def post(payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps({"model": model, **payload}).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            # Long enough for OpenAI to list this server's tools and make several calls.
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc)["error"]["message"]
            except Exception:
                detail = exc.reason
            raise ChatError(f"OpenAI returned {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ChatError(f"Couldn't reach OpenAI: {exc}") from exc

    async def complete(payload: dict) -> dict:
        return await asyncio.to_thread(post, payload)

    return complete
