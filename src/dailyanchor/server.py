import logging
import sqlite3
import sys
from typing import Any

# Importing the MCP SDK can take several seconds on a slow filesystem (e.g. WSL2 reading a
# project on /mnt/d), so say something before it starts rather than looking hung.
print("DailyAnchor: starting (loading dependencies, this can take a few seconds)...",
      file=sys.stderr, flush=True)

from mcp.server.mcpserver import MCPServer  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import HTMLResponse, RedirectResponse, Response  # noqa: E402

from dailyanchor import dashboard  # noqa: E402
from dailyanchor.db import get_db, init_db  # noqa: E402
from dailyanchor.request_log import RequestLogMiddleware  # noqa: E402
from dailyanchor.tools import adaptation, reminders, routines, setup  # noqa: E402

HOST = "127.0.0.1"
PORT = 8000
MCP_PATH = "/mcp"

mcp = MCPServer("DailyAnchor")

_conn: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = get_db()
        init_db(_conn)
    return _conn


@mcp.tool()
def list_routines() -> list[dict]:
    """List all active daily routines and their ordered steps."""
    return routines.list_routines(_connection())


@mcp.tool()
def get_current_step(routine_id: str) -> dict[str, Any] | None:
    """Get the next step the person should do right now in a given routine."""
    return routines.get_current_step(_connection(), routine_id)


@mcp.tool()
def mark_step_done(routine_id: str, step_id: str) -> dict[str, Any]:
    """Mark a routine step as completed for today."""
    return routines.mark_step_done(_connection(), routine_id, step_id)


@mcp.tool()
def check_step_done(step: str) -> dict[str, Any]:
    """Check whether a step was already done today, and when -- use this whenever the
    person asks "did I take my pill?", "have I eaten?" or similar, especially before
    medication, so nothing is taken twice. `step` can be their own words ("morning pill")
    or a step id. If several steps match (status "ambiguous"), ask which one they mean."""
    return routines.check_step_done(_connection(), step)


@mcp.tool()
def get_missed_steps(routine_id: str | None = None) -> list[dict]:
    """List steps that were expected today but are now overdue and not completed."""
    return routines.get_missed_steps(_connection(), routine_id)


@mcp.tool()
def snooze_step(step_id: str, minutes: int) -> dict[str, Any]:
    """Push a step's expected time later today, for a gentler re-prompt after a miss."""
    return reminders.snooze_step(_connection(), step_id, minutes)


@mcp.tool()
def get_daily_summary(log_date: str | None = None) -> dict[str, Any]:
    """Caregiver-facing summary of completed/missed/pending steps for a day."""
    return reminders.get_daily_summary(_connection(), log_date)


@mcp.tool()
def add_routine(name: str, description: str = "") -> dict[str, Any]:
    """Create a new, empty routine (e.g. "Morning Routine"). Add steps with add_step."""
    return setup.add_routine(_connection(), name, description)


@mcp.tool()
def add_step(
    routine_id: str,
    title: str,
    expected_time: str,
    window_minutes: int = 60,
    description: str = "",
    position: int | None = None,
) -> dict[str, Any]:
    """Add a step to a routine. expected_time is HH:MM (24h); window_minutes is how long
    after that it still counts as on time. Appended to the end unless position is given."""
    return setup.add_step(
        _connection(), routine_id, title, expected_time, window_minutes, description, position
    )


@mcp.tool()
def update_step_time(step_id: str, expected_time: str) -> dict[str, Any]:
    """Permanently change when a step is expected (HH:MM). Use to accept a schedule
    suggestion; snooze_step only shifts a step for today."""
    return setup.update_step_time(_connection(), step_id, expected_time)


@mcp.tool()
def suggest_schedule_adjustments(lookback_days: int = 7) -> list[dict]:
    """Suggest moving steps the person consistently completes later than scheduled,
    based on recent history. Ask the person or caregiver before applying one with
    update_step_time."""
    return adaptation.suggest_schedule_adjustments(_connection(), lookback_days)


@mcp.custom_route("/", methods=["GET"])
async def root(request: Request) -> Response:
    # Opening the server URL in a browser used to show a bare "Not Found".
    return RedirectResponse("/dashboard")


@mcp.custom_route("/dashboard", methods=["GET"])
async def dashboard_page(request: Request) -> Response:
    """Read-only caregiver view of today's routines, for a browser rather than an agent."""
    # Its own short-lived connection: sync tools run in worker threads, and a sqlite3
    # connection can only be used from the thread that created it.
    conn = get_db()
    try:
        init_db(conn)
        data = dashboard.build_dashboard(conn)
    finally:
        conn.close()
    tool_count = len(await mcp.list_tools())
    return HTMLResponse(
        dashboard.render_dashboard(data, f"http://{HOST}:{PORT}{MCP_PATH}", tool_count)
    )


def main() -> None:
    # Streamable HTTP per MCP spec 2025-11-25 -- required transport for Alexa+ integration.
    # The MCP endpoint is only at MCP_PATH; the root URL returns "Not Found", so print it.
    print(f"DailyAnchor MCP endpoint: http://{HOST}:{PORT}{MCP_PATH}", file=sys.stderr, flush=True)
    print(f"Caregiver dashboard:      http://{HOST}:{PORT}/dashboard", file=sys.stderr, flush=True)
    # Built by hand rather than mcp.run() so every MCP request gets a log line (method, tool,
    # client) -- the quickest way to see whether Alexa+ is actually calling the server.
    import uvicorn

    # Own plain handler: the SDK's rich log handler wraps these lines across several rows.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s MCP %(message)s", datefmt="%H:%M:%S"))
    request_logger = logging.getLogger("dailyanchor.requests")
    request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)
    request_logger.propagate = False
    app = mcp.streamable_http_app(streamable_http_path=MCP_PATH, host=HOST)
    uvicorn.run(RequestLogMiddleware(app, MCP_PATH), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
