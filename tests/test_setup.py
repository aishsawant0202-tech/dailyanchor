import pytest

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import routines, setup


@pytest.fixture
def conn():
    connection = get_db(":memory:")
    init_db(connection)
    return connection


def _titles(conn, routine_id):
    steps = next(r for r in routines.list_routines(conn) if r["id"] == routine_id)["steps"]
    return [s["title"] for s in steps]


def test_add_routine_shows_up_in_list_routines(conn):
    result = setup.add_routine(conn, "Morning Routine", "Meds and breakfast")

    assert result["status"] == "created"
    listed = routines.list_routines(conn)
    assert [r["name"] for r in listed] == ["Morning Routine"]
    assert listed[0]["steps"] == []


def test_add_routine_rejects_blank_name(conn):
    assert setup.add_routine(conn, "   ")["status"] == "error"


def test_add_step_appends_in_order(conn):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]

    setup.add_step(conn, routine_id, "Take meds", "08:00")
    setup.add_step(conn, routine_id, "Eat breakfast", "08:30")

    assert _titles(conn, routine_id) == ["Take meds", "Eat breakfast"]


def test_add_step_at_position_shifts_later_steps(conn):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]
    setup.add_step(conn, routine_id, "Take meds", "08:00")
    setup.add_step(conn, routine_id, "Eat breakfast", "08:30")

    setup.add_step(conn, routine_id, "Drink water", "07:45", position=0)

    assert _titles(conn, routine_id) == ["Drink water", "Take meds", "Eat breakfast"]


def test_add_step_normalizes_time(conn):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]

    result = setup.add_step(conn, routine_id, "Take meds", "8:00")

    assert result["expected_time"] == "08:00"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_time": "25:00"},
        {"expected_time": "breakfast"},
        {"expected_time": "08:00", "window_minutes": 0},
        {"expected_time": "08:00", "title": "  "},
    ],
)
def test_add_step_rejects_invalid_input(conn, kwargs):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]
    args = {"title": "Take meds", "expected_time": "08:00", **kwargs}

    assert setup.add_step(conn, routine_id, **args)["status"] == "error"
    assert _titles(conn, routine_id) == []


def test_add_step_to_missing_routine_errors(conn):
    result = setup.add_step(conn, "no-such-routine", "Take meds", "08:00")

    assert result["status"] == "error"


def test_update_step_time_changes_schedule_permanently(conn):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]
    step_id = setup.add_step(conn, routine_id, "Eat breakfast", "08:30")["step_id"]

    result = setup.update_step_time(conn, step_id, "9:15")

    assert result == {
        "status": "updated",
        "step_id": step_id,
        "old_expected_time": "08:30",
        "new_expected_time": "09:15",
    }
    assert routines.get_current_step(conn, routine_id)["expected_time"] == "09:15"


def test_update_step_time_rejects_bad_input(conn):
    routine_id = setup.add_routine(conn, "Morning")["routine_id"]
    step_id = setup.add_step(conn, routine_id, "Eat breakfast", "08:30")["step_id"]

    assert setup.update_step_time(conn, step_id, "noon")["status"] == "error"
    assert setup.update_step_time(conn, "missing", "09:00")["status"] == "error"
