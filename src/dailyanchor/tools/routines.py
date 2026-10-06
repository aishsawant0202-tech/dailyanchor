import re
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


def step_status(conn: sqlite3.Connection, step: dict, log_date: str, now: datetime) -> dict:
    """A step's state on a given day: done, missed (window passed), due (inside its
    window) or upcoming, with today's effective time and when it was completed."""
    completion = conn.execute(
        "SELECT completed_at FROM completions WHERE step_id = ? AND log_date = ? "
        "ORDER BY completed_at LIMIT 1",
        (step["id"], log_date),
    ).fetchone()
    expected_time = effective_expected_time(conn, step, log_date)

    if completion:
        status = "done"
    elif now > deadline_for(log_date, expected_time, step["window_minutes"]):
        status = "missed"
    elif now >= deadline_for(log_date, expected_time, 0):
        status = "due"
    else:
        status = "upcoming"

    return {
        "id": step["id"],
        "routine_id": step["routine_id"],
        "title": step["title"],
        "description": step["description"],
        "expected_time": expected_time,
        "scheduled_time": step["expected_time"],
        "snoozed": expected_time != step["expected_time"],
        "window_minutes": step["window_minutes"],
        "status": status,
        "completed_at": completion["completed_at"] if completion else None,
    }


# Words people say that don't help pick out a step ("did I take my pill").
_FILLER_WORDS = {
    "a", "an", "the", "my", "i", "did", "do", "have", "has", "already", "today", "yet",
    "take", "taken", "took", "to", "of", "for", "and", "is", "it", "done",
}
# Everyday words for things step titles name more formally.
_SYNONYMS = {
    "pill": "medication", "pills": "medication", "tablet": "medication",
    "tablets": "medication", "meds": "medication", "medicine": "medication",
    "medicines": "medication",
}


def _words(text: str) -> set[str]:
    words = set()
    for word in re.findall(r"[a-z0-9']+", text.lower()):
        word = _SYNONYMS.get(word, word)
        if word not in _FILLER_WORDS:
            words.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return words


def check_step_done(
    conn: sqlite3.Connection, step: str, now: datetime | None = None
) -> dict:
    """Answer "did I already do X today?" from the completion record.

    `step` is a step id or the person's own words ("morning pill"). Words are matched
    against step titles; every step tied for the best match is returned, so "medication"
    gives both the morning and evening doses and the caller can ask which one."""
    now = now or datetime.now()
    log_date = today(now)

    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT s.*, r.name AS routine_name FROM steps s "
            "JOIN routines r ON r.id = s.routine_id WHERE r.active = 1 "
            "ORDER BY r.name, s.order_index"
        ).fetchall()
    ]

    matches = [row for row in rows if row["id"] == step]
    if not matches:
        wanted = _words(step)
        scored = [(len(wanted & _words(row["title"])), row) for row in rows]
        best = max((score for score, _ in scored), default=0)
        matches = [row for score, row in scored if best and score == best]

    if not matches:
        return {
            "status": "not_found",
            "query": step,
            "message": f"No step matching '{step}'.",
            "available_steps": [row["title"] for row in rows],
        }

    results = []
    for row in matches:
        state = step_status(conn, row, log_date, now)
        if state["status"] == "done":
            message = f"Yes, '{row['title']}' was done today at {state['completed_at'][11:16]}."
        else:
            message = (
                f"No, '{row['title']}' has not been done today "
                f"(it is {state['status']}, expected at {state['expected_time']})."
            )
        results.append(
            {
                "step_id": row["id"],
                "routine_id": row["routine_id"],
                "routine": row["routine_name"],
                "title": row["title"],
                "done": state["status"] == "done",
                "completed_at": state["completed_at"],
                "state": state["status"],
                "expected_time": state["expected_time"],
                "message": message,
            }
        )

    return {
        "status": "found" if len(results) == 1 else "ambiguous",
        "date": log_date,
        "matches": results,
    }
