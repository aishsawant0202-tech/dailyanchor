import uuid
from datetime import datetime

import pytest

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import reminders, routines


@pytest.fixture
def conn():
    connection = get_db(":memory:")
    init_db(connection)
    return connection


def _make_routine(conn, steps):
    routine_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO routines (id, name, description, active) VALUES (?, 'Test Routine', '', 1)",
        (routine_id,),
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


def test_get_current_step_returns_first_incomplete(conn):
    routine_id, step_ids = _make_routine(
        conn, [("Take meds", "08:00", 60), ("Eat breakfast", "08:30", 60)]
    )
    now = datetime.strptime("2026-09-20 07:30", "%Y-%m-%d %H:%M")

    step = routines.get_current_step(conn, routine_id, now=now)

    assert step["title"] == "Take meds"


def test_mark_step_done_advances_to_next_step(conn):
    routine_id, step_ids = _make_routine(
        conn, [("Take meds", "08:00", 60), ("Eat breakfast", "08:30", 60)]
    )
    now = datetime.strptime("2026-09-20 08:10", "%Y-%m-%d %H:%M")

    result = routines.mark_step_done(conn, routine_id, step_ids[0], now=now)
    assert result["status"] == "done"

    next_step = routines.get_current_step(conn, routine_id, now=now)
    assert next_step["title"] == "Eat breakfast"


def test_mark_step_done_twice_is_idempotent(conn):
    routine_id, step_ids = _make_routine(conn, [("Take meds", "08:00", 60)])
    now = datetime.strptime("2026-09-20 08:10", "%Y-%m-%d %H:%M")

    routines.mark_step_done(conn, routine_id, step_ids[0], now=now)
    result = routines.mark_step_done(conn, routine_id, step_ids[0], now=now)

    assert result["status"] == "already_done"


def test_get_missed_steps_flags_overdue_incomplete_steps(conn):
    routine_id, step_ids = _make_routine(conn, [("Take meds", "08:00", 60)])
    now = datetime.strptime("2026-09-20 09:30", "%Y-%m-%d %H:%M")  # past 08:00 + 60min window

    missed = routines.get_missed_steps(conn, routine_id, now=now)

    assert len(missed) == 1
    assert missed[0]["title"] == "Take meds"


def test_snooze_step_pushes_deadline_later(conn):
    routine_id, step_ids = _make_routine(conn, [("Take meds", "08:00", 60)])
    now = datetime.strptime("2026-09-20 09:30", "%Y-%m-%d %H:%M")

    reminders.snooze_step(conn, step_ids[0], minutes=90, now=now)
    missed = routines.get_missed_steps(conn, routine_id, now=now)

    assert missed == []  # no longer overdue: new deadline is 09:30 + 60min window


def test_get_daily_summary_buckets_steps_correctly(conn):
    routine_id, step_ids = _make_routine(
        conn, [("Take meds", "08:00", 60), ("Eat breakfast", "08:30", 60), ("Walk", "12:00", 30)]
    )
    now = datetime.strptime("2026-09-20 09:00", "%Y-%m-%d %H:%M")
    routines.mark_step_done(conn, routine_id, step_ids[0], now=now)

    summary = reminders.get_daily_summary(conn, log_date="2026-09-20", now=now)

    routine_summary = summary["routines"][0]
    assert routine_summary["completed"] == ["Take meds"]
    assert routine_summary["missed"] == []
    assert "Eat breakfast" in routine_summary["pending"]
    assert "Walk" in routine_summary["pending"]
