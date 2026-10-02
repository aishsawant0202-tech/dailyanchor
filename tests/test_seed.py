import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import adaptation, reminders, routines

NOW = datetime(2026, 9, 20, 10, 0)


@pytest.fixture(scope="module")
def seed_data():
    path = Path(__file__).resolve().parent.parent / "scripts" / "seed_data.py"
    spec = importlib.util.spec_from_file_location("seed_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn():
    connection = get_db(":memory:")
    init_db(connection)
    return connection


def test_seed_routines_creates_sample_routines(conn, seed_data):
    assert seed_data.seed_routines(conn) == 2

    listed = {r["name"]: r for r in routines.list_routines(conn)}
    assert set(listed) == {"Morning Routine", "Evening Routine"}
    assert [s["title"] for s in listed["Morning Routine"]["steps"]] == [
        "Take morning medication",
        "Eat breakfast",
        "Review today's appointments",
    ]


def test_seed_routines_twice_does_not_duplicate(conn, seed_data):
    seed_data.seed_routines(conn)

    assert seed_data.seed_routines(conn) == 0
    assert len(routines.list_routines(conn)) == 2


def test_seed_history_is_repeatable(conn, seed_data):
    seed_data.seed_routines(conn)

    first = seed_data.seed_history(conn, now=NOW)
    second = seed_data.seed_history(conn, now=NOW)

    assert first == 5 * 7  # 5 steps, 7 past days
    assert second == 0


def test_demo_history_suggests_only_the_late_breakfast(conn, seed_data):
    seed_data.seed_routines(conn)
    seed_data.seed_history(conn, now=NOW)

    suggestions = adaptation.suggest_schedule_adjustments(conn, now=NOW)

    assert [(s["title"], s["current_time"], s["suggested_time"]) for s in suggestions] == [
        ("Eat breakfast", "08:30", "09:15")
    ]


def test_demo_history_leaves_today_clear(conn, seed_data):
    seed_data.seed_routines(conn)
    seed_data.seed_history(conn, now=NOW)
    morning = next(r for r in routines.list_routines(conn) if r["name"] == "Morning Routine")

    step = routines.get_current_step(conn, morning["id"], now=NOW)
    summary = reminders.get_daily_summary(conn, log_date="2026-09-20", now=NOW)

    assert step["title"] == "Take morning medication"
    assert all(not r["completed"] for r in summary["routines"])


def test_reset_clears_everything(conn, seed_data):
    seed_data.seed_routines(conn)
    seed_data.seed_history(conn, now=NOW)

    seed_data.reset(conn)

    assert routines.list_routines(conn, active_only=False) == []
    for table in ("steps", "completions", "step_overrides"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
