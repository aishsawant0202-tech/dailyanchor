import sqlite3
import uuid
from datetime import datetime

from dailyanchor.time_utils import deadline_for, effective_expected_time, is_completed, today


def list_routines(conn: sqlite3.Connection, active_only: bool = True) -> list[dict]:
    """List routines, each with its ordered steps."""
    query = "SELECT * FROM routines"
    if active_only:
        query += " WHERE active = 1"

    routines = [dict(row) for row in conn.execute(query).fetchall()]
    for routine in routines:
        steps = conn.execute(
            "SELECT * FROM steps WHERE routine_id = ? ORDER BY order_index",
            (routine["id"],),
        ).fetchall()
        routine["steps"] = [dict(s) for s in steps]
    return routines


def get_current_step(
    conn: sqlite3.Connection, routine_id: str, now: datetime | None = None
) -> dict | None:
    """Return the next not-yet-completed step in a routine, in order. None if the
    routine is fully done for today."""
    now = now or datetime.now()
    log_date = today(now)

    steps = conn.execute(
        "SELECT * FROM steps WHERE routine_id = ? ORDER BY order_index",
        (routine_id,),
    ).fetchall()

    for row in steps:
        step = dict(row)
        if is_completed(conn, step["id"], log_date):
            continue
        step["expected_time"] = effective_expected_time(conn, step, log_date)
        return step

    return None


def mark_step_done(
    conn: sqlite3.Connection, routine_id: str, step_id: str, now: datetime | None = None
) -> dict:
    """Record a step as completed for today."""
    now = now or datetime.now()
    log_date = today(now)

    if is_completed(conn, step_id, log_date):
        return {"status": "already_done", "step_id": step_id}

    conn.execute(
        "INSERT INTO completions (id, step_id, routine_id, completed_at, log_date) "
        "VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), step_id, routine_id, now.isoformat(timespec="seconds"), log_date),
    )
    conn.commit()
    return {"status": "done", "step_id": step_id, "completed_at": now.isoformat(timespec="seconds")}


def get_missed_steps(
    conn: sqlite3.Connection, routine_id: str | None = None, now: datetime | None = None
) -> list[dict]:
    """Steps whose expected_time + window_minutes has passed today without completion."""
    now = now or datetime.now()
    log_date = today(now)

    query = "SELECT * FROM steps"
    params: tuple = ()
    if routine_id:
        query += " WHERE routine_id = ?"
        params = (routine_id,)

    missed = []
    for row in conn.execute(query, params).fetchall():
        step = dict(row)
        if is_completed(conn, step["id"], log_date):
            continue
        expected_time = effective_expected_time(conn, step, log_date)
        if now > deadline_for(log_date, expected_time, step["window_minutes"]):
            step["expected_time"] = expected_time
            missed.append(step)
    return missed
