import sqlite3

from mcp.server.mcpserver import MCPServer

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import reminders, routines

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
def get_current_step(routine_id: str) -> dict | None:
    """Get the next step the person should do right now in a given routine."""
    return routines.get_current_step(_connection(), routine_id)


@mcp.tool()
def mark_step_done(routine_id: str, step_id: str) -> dict:
    """Mark a routine step as completed for today."""
    return routines.mark_step_done(_connection(), routine_id, step_id)


@mcp.tool()
def get_missed_steps(routine_id: str | None = None) -> list[dict]:
    """List steps that were expected today but are now overdue and not completed."""
    return routines.get_missed_steps(_connection(), routine_id)


@mcp.tool()
def snooze_step(step_id: str, minutes: int) -> dict:
    """Push a step's expected time later today, for a gentler re-prompt after a miss."""
    return reminders.snooze_step(_connection(), step_id, minutes)


@mcp.tool()
def get_daily_summary(log_date: str | None = None) -> dict:
    """Caregiver-facing summary of completed/missed/pending steps for a day."""
    return reminders.get_daily_summary(_connection(), log_date)


def main() -> None:
    # Streamable HTTP per MCP spec 2025-11-25 -- required transport for Alexa+ integration.
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
