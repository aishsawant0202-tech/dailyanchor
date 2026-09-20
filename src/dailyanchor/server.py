import sqlite3

from mcp.server.mcpserver import MCPServer

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import adaptation, reminders, routines, setup

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


@mcp.tool()
def add_routine(name: str, description: str = "") -> dict:
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
) -> dict:
    """Add a step to a routine. expected_time is HH:MM (24h); window_minutes is how long
    after that it still counts as on time. Appended to the end unless position is given."""
    return setup.add_step(
        _connection(), routine_id, title, expected_time, window_minutes, description, position
    )


@mcp.tool()
def update_step_time(step_id: str, expected_time: str) -> dict:
    """Permanently change when a step is expected (HH:MM). Use to accept a schedule
    suggestion; snooze_step only shifts a step for today."""
    return setup.update_step_time(_connection(), step_id, expected_time)


@mcp.tool()
def suggest_schedule_adjustments(lookback_days: int = 7) -> list[dict]:
    """Suggest moving steps the person consistently completes later than scheduled,
    based on recent history. Ask the person or caregiver before applying one with
    update_step_time."""
    return adaptation.suggest_schedule_adjustments(_connection(), lookback_days)


def main() -> None:
    # Streamable HTTP per MCP spec 2025-11-25 -- required transport for Alexa+ integration.
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
