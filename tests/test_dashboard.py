import uuid
from datetime import datetime

import pytest

from dailyanchor import dashboard
from dailyanchor.db import get_db, init_db
from dailyanchor.tools import reminders, routines


@pytest.fixture
def conn():
    connection = get_db(":memory:")
    init_db(connection)
    return connection


def _make_routine(conn, steps, name="Morning Routine"):
    routine_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO routines (id, name, description, active) VALUES (?, ?, '', 1)",
        (routine_id, name),
    )
    step_ids = []
    for index, (title, expected_time, window) in enumerate(steps):
        step_id = str(uuid.uuid4())
        step_ids.append(step_id)
        conn.execute(
            "INSERT INTO steps (id, routine_id, order_index, title, description, "
            "expected_time, window_minutes) VALUES (?, ?, ?, ?, '', ?, ?)",
            (step_id, routine_id, index, title, expected_time, window),
        )
    conn.commit()
    return routine_id, step_ids


def _at(hhmm):
    return datetime.strptime(f"2026-09-20 {hhmm}", "%Y-%m-%d %H:%M")


def test_step_statuses_cover_done_missed_due_upcoming(conn):
    routine_id, step_ids = _make_routine(
        conn,
        [
            ("Take meds", "08:00", 60),
            ("Eat breakfast", "08:30", 30),
            ("Review appointments", "09:00", 60),
            ("Walk", "11:00", 60),
        ],
    )
    routines.mark_step_done(conn, routine_id, step_ids[0], now=_at("08:10"))

    data = dashboard.build_dashboard(conn, now=_at("09:15"))

    steps = data["routines"][0]["steps"]
    assert [s["status"] for s in steps] == ["done", "missed", "due", "upcoming"]
    assert steps[0]["completed_at"] == "08:10"
    assert data["routines"][0]["counts"] == {"done": 1, "missed": 1, "due": 1, "upcoming": 1}


def test_snoozed_step_shows_new_time_and_is_not_missed(conn):
    _, step_ids = _make_routine(conn, [("Eat breakfast", "08:30", 30)])
    reminders.snooze_step(conn, step_ids[0], 60, now=_at("09:05"))

    step = dashboard.build_dashboard(conn, now=_at("09:10"))["routines"][0]["steps"][0]

    assert step["expected_time"] == "09:30"
    assert step["scheduled_time"] == "08:30"
    assert step["snoozed"] is True
    assert step["status"] == "upcoming"


def test_render_escapes_user_text(conn):
    _make_routine(conn, [("<script>alert(1)</script>", "08:00", 60)], name="Tom & Jerry")

    page = dashboard.render_dashboard(
        dashboard.build_dashboard(conn, now=_at("07:00")), "http://127.0.0.1:8000/mcp", 10
    )

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "Tom &amp; Jerry" in page
    assert "10 tools" in page


def test_render_with_no_routines(conn):
    page = dashboard.render_dashboard(
        dashboard.build_dashboard(conn, now=_at("07:00")), "http://127.0.0.1:8000/mcp", 10
    )

    assert "No routines yet" in page
