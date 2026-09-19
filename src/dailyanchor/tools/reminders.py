import sqlite3
from datetime import datetime, timedelta

from dailyanchor.time_utils import deadline_for, effective_expected_time, is_completed, today


def snooze_step(
    conn: sqlite3.Connection, step_id: str, minutes: int, now: datetime | None = None
) -> dict:
    """Push a step's expected time later today by `minutes`. Used to give a gentler
    re-prompt instead of letting a missed step just sit as a hard failure."""
    now = now or datetime.now()
    log_date = today(now)

    row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
    if row is None:
        return {"status": "error", "message": f"step {step_id} not found"}
    step = dict(row)

    current_expected = effective_expected_time(conn, step, log_date)
    new_time = (
        datetime.strptime(current_expected, "%H:%M") + timedelta(minutes=minutes)
    ).strftime("%H:%M")

    conn.execute(
        "INSERT INTO step_overrides (step_id, log_date, expected_time) VALUES (?, ?, ?) "
        "ON CONFLICT(step_id, log_date) DO UPDATE SET expected_time = excluded.expected_time",
        (step_id, log_date, new_time),
    )
    conn.commit()
    return {"status": "snoozed", "step_id": step_id, "new_expected_time": new_time}


def get_daily_summary(
    conn: sqlite3.Connection, log_date: str | None = None, now: datetime | None = None
) -> dict:
    """Caregiver-facing rollup: which steps across all active routines were completed,
    missed, or are still pending for a given day (defaults to today)."""
    now = now or datetime.now()
    log_date = log_date or today(now)

    routines = conn.execute("SELECT * FROM routines WHERE active = 1").fetchall()
    summary: dict = {"date": log_date, "routines": []}

    for routine_row in routines:
        routine = dict(routine_row)
        steps = conn.execute(
            "SELECT * FROM steps WHERE routine_id = ? ORDER BY order_index",
            (routine["id"],),
        ).fetchall()

        completed, missed, pending = [], [], []
        for step_row in steps:
            step = dict(step_row)
            if is_completed(conn, step["id"], log_date):
                completed.append(step["title"])
                continue
            expected_time = effective_expected_time(conn, step, log_date)
            deadline = deadline_for(log_date, expected_time, step["window_minutes"])
            (missed if now > deadline else pending).append(step["title"])

        summary["routines"].append(
            {
                "routine": routine["name"],
                "completed": completed,
                "missed": missed,
                "pending": pending,
            }
        )

    return summary
