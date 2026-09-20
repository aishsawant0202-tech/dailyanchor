from datetime import datetime

import pytest

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import adaptation, routines, setup

NOW = datetime(2026, 9, 20, 12, 0)


@pytest.fixture
def conn():
    connection = get_db(":memory:")
    init_db(connection)
    return connection


def _step(conn, title="Eat breakfast", expected_time="08:30"):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]
    step_id = setup.add_step(conn, routine_id, title, expected_time)["step_id"]
    return routine_id, step_id


def _complete(conn, routine_id, step_id, day, at):
    """Record a completion on `day` (e.g. "2026-09-18") at clock time `at` ("09:10")."""
    routines.mark_step_done(
        conn, routine_id, step_id, now=datetime.strptime(f"{day} {at}", "%Y-%m-%d %H:%M")
    )


def test_suggests_later_time_for_consistently_late_step(conn):
    routine_id, step_id = _step(conn)
    # 37, 42 and 46 minutes after 08:30
    for day, at in [("2026-09-17", "09:07"), ("2026-09-18", "09:12"), ("2026-09-19", "09:16")]:
        _complete(conn, routine_id, step_id, day, at)

    suggestions = adaptation.suggest_schedule_adjustments(conn, now=NOW)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["step_id"] == step_id
    assert suggestion["current_time"] == "08:30"
    assert suggestion["suggested_time"] == "09:15"  # median 42 min late -> rounded up to 45
    assert suggestion["median_minutes_late"] == 42
    assert suggestion["days_observed"] == 3
    assert "09:15" in suggestion["message"]


def test_no_suggestion_with_too_few_samples(conn):
    routine_id, step_id = _step(conn)
    for day in ["2026-09-18", "2026-09-19"]:
        _complete(conn, routine_id, step_id, day, "09:30")

    assert adaptation.suggest_schedule_adjustments(conn, now=NOW) == []


def test_no_suggestion_when_step_is_on_time(conn):
    routine_id, step_id = _step(conn)
    for day, at in [("2026-09-17", "08:35"), ("2026-09-18", "08:28"), ("2026-09-19", "08:40")]:
        _complete(conn, routine_id, step_id, day, at)

    assert adaptation.suggest_schedule_adjustments(conn, now=NOW) == []


def test_one_very_late_day_is_not_a_pattern(conn):
    routine_id, step_id = _step(conn)
    for day, at in [("2026-09-17", "08:30"), ("2026-09-18", "08:35"), ("2026-09-19", "11:30")]:
        _complete(conn, routine_id, step_id, day, at)

    assert adaptation.suggest_schedule_adjustments(conn, now=NOW) == []


def test_ignores_completions_outside_lookback_window(conn):
    routine_id, step_id = _step(conn)
    for day in ["2026-08-01", "2026-08-02", "2026-08-03"]:
        _complete(conn, routine_id, step_id, day, "10:00")

    assert adaptation.suggest_schedule_adjustments(conn, lookback_days=7, now=NOW) == []


def test_accepting_suggestion_updates_step_schedule(conn):
    routine_id, step_id = _step(conn)
    for day, at in [("2026-09-17", "09:15"), ("2026-09-18", "09:15"), ("2026-09-19", "09:15")]:
        _complete(conn, routine_id, step_id, day, at)
    suggestion = adaptation.suggest_schedule_adjustments(conn, now=NOW)[0]

    setup.update_step_time(conn, step_id, suggestion["suggested_time"])

    assert routines.get_current_step(conn, routine_id, now=NOW)["expected_time"] == "09:15"


def test_most_late_step_listed_first(conn):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]
    slightly_late = setup.add_step(conn, routine_id, "Meds", "08:00")["step_id"]
    very_late = setup.add_step(conn, routine_id, "Breakfast", "08:30")["step_id"]
    for day in ["2026-09-17", "2026-09-18", "2026-09-19"]:
        _complete(conn, routine_id, slightly_late, day, "08:20")
        _complete(conn, routine_id, very_late, day, "10:00")

    suggestions = adaptation.suggest_schedule_adjustments(conn, now=NOW)

    assert [s["title"] for s in suggestions] == ["Breakfast", "Meds"]
