import sqlite3
import uuid
from datetime import datetime


def _normalize_time(value: str) -> str | None:
    """Normalize a time like "8:00" to "08:00". None if it isn't a valid HH:MM."""
    try:
        return datetime.strptime(value.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def add_routine(conn: sqlite3.Connection, name: str, description: str = "") -> dict:
    """Create a new, empty routine. Steps are added afterwards with add_step."""
    name = name.strip()
    if not name:
        return {"status": "error", "message": "routine name cannot be empty"}

    routine_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO routines (id, name, description, active) VALUES (?, ?, ?, 1)",
        (routine_id, name, description.strip()),
    )
    conn.commit()
    return {"status": "created", "routine_id": routine_id, "name": name}


def add_step(
    conn: sqlite3.Connection,
    routine_id: str,
    title: str,
    expected_time: str,
    window_minutes: int = 60,
    description: str = "",
    position: int | None = None,
) -> dict:
    """Add a step to a routine. Appended to the end unless `position` (0-based) is
    given, in which case later steps shift down by one."""
    title = title.strip()
    if not title:
        return {"status": "error", "message": "step title cannot be empty"}

    normalized_time = _normalize_time(expected_time)
    if normalized_time is None:
        return {"status": "error", "message": f"expected_time must be HH:MM, got {expected_time!r}"}

    if window_minutes <= 0:
        return {"status": "error", "message": "window_minutes must be greater than 0"}

    if conn.execute("SELECT 1 FROM routines WHERE id = ?", (routine_id,)).fetchone() is None:
        return {"status": "error", "message": f"routine {routine_id} not found"}

    step_count = conn.execute(
        "SELECT COUNT(*) FROM steps WHERE routine_id = ?", (routine_id,)
    ).fetchone()[0]
    order_index = step_count if position is None else max(0, min(position, step_count))

    conn.execute(
        "UPDATE steps SET order_index = order_index + 1 WHERE routine_id = ? AND order_index >= ?",
        (routine_id, order_index),
    )
    step_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO steps (id, routine_id, order_index, title, description, "
        "expected_time, window_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (step_id, routine_id, order_index, title, description.strip(), normalized_time, window_minutes),
    )
    conn.commit()
    return {
        "status": "created",
        "step_id": step_id,
        "routine_id": routine_id,
        "title": title,
        "expected_time": normalized_time,
        "order_index": order_index,
    }


def update_step_time(conn: sqlite3.Connection, step_id: str, expected_time: str) -> dict:
    """Permanently change when a step is expected (unlike snooze_step, which only
    shifts it for today). Used to accept a schedule adjustment suggestion."""
    normalized_time = _normalize_time(expected_time)
    if normalized_time is None:
        return {"status": "error", "message": f"expected_time must be HH:MM, got {expected_time!r}"}

    row = conn.execute("SELECT expected_time FROM steps WHERE id = ?", (step_id,)).fetchone()
    if row is None:
        return {"status": "error", "message": f"step {step_id} not found"}

    conn.execute("UPDATE steps SET expected_time = ? WHERE id = ?", (normalized_time, step_id))
    conn.commit()
    return {
        "status": "updated",
        "step_id": step_id,
        "old_expected_time": row["expected_time"],
        "new_expected_time": normalized_time,
    }
