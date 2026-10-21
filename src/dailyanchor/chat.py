"""Live chat for the web simulator: an OpenAI model stands in for Alexa+ and answers with
the DailyAnchor tools.

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
OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
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


def openai_completer(api_key: str, model: str = DEFAULT_MODEL) -> Complete:
    """Chat Completions over plain urllib (in a thread), to avoid a new dependency."""

    def post(payload: dict) -> dict:
        request = urllib.request.Request(
            OPENAI_URL,
            data=json.dumps({"model": model, **payload}).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
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
