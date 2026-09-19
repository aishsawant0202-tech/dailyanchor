import sqlite3
from datetime import datetime, timedelta


def today(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def effective_expected_time(conn: sqlite3.Connection, step: dict, log_date: str) -> str:
    """A step's expected time for a given day, accounting for any snooze override."""
    override = conn.execute(
        "SELECT expected_time FROM step_overrides WHERE step_id = ? AND log_date = ?",
        (step["id"], log_date),
    ).fetchone()
    return override["expected_time"] if override else step["expected_time"]


def is_completed(conn: sqlite3.Connection, step_id: str, log_date: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM completions WHERE step_id = ? AND log_date = ?",
        (step_id, log_date),
    ).fetchone()
    return row is not None


def deadline_for(log_date: str, expected_time: str, window_minutes: int) -> datetime:
    return datetime.strptime(f"{log_date} {expected_time}", "%Y-%m-%d %H:%M") + timedelta(
        minutes=window_minutes
    )
