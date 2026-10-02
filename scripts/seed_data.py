"""Seed sample routines (and optionally demo history) into the DailyAnchor database.

    python scripts/seed_data.py              # add sample routines (safe to re-run)
    python scripts/seed_data.py --history    # ...plus a week of past completions
    python scripts/seed_data.py --reset --history   # wipe everything first (clean demo take)
"""

import argparse
import sqlite3
from datetime import datetime, timedelta

from dailyanchor.db import get_db, init_db
from dailyanchor.tools import routines, setup

ROUTINES = [
    {
        "name": "Morning Routine",
        "description": "Medication, breakfast, and daily check-in.",
        "steps": [
            {
                "title": "Take morning medication",
                "description": "One tablet with water.",
                "expected_time": "08:00",
                "window_minutes": 60,
            },
            {
                "title": "Eat breakfast",
                "description": "",
                "expected_time": "08:30",
                "window_minutes": 60,
            },
            {
                "title": "Review today's appointments",
                "description": "Alexa+ reads out the day's schedule.",
                "expected_time": "09:00",
                "window_minutes": 90,
            },
        ],
    },
    {
        "name": "Evening Routine",
        "description": "Evening medication and wind-down.",
        "steps": [
            {
                "title": "Take evening medication",
                "description": "One tablet with water.",
                "expected_time": "19:00",
                "window_minutes": 60,
            },
            {
                "title": "Lock the front door",
                "description": "",
                "expected_time": "21:00",
                "window_minutes": 60,
            },
        ],
    },
]

# Minutes after the scheduled time that each step was completed, one entry per past day
# (most recent first). Fixed values, not random, so every demo take behaves the same.
# Breakfast is consistently ~40 minutes late, so suggest_schedule_adjustments proposes
# moving it to 09:15. Everything else is close to on time, so nothing else is suggested.
DEMO_HISTORY_MINUTES_LATE = {
    "Take morning medication": [3, 5, 2, 6, 4, 3, 5],
    "Eat breakfast": [37, 42, 46, 40, 44, 38, 45],
    "Review today's appointments": [4, 8, 6, 5, 7, 9, 5],
    "Take evening medication": [5, 3, 8, 4, 6, 2, 7],
    "Lock the front door": [10, 12, 8, 15, 9, 11, 10],
}


def reset(conn: sqlite3.Connection) -> None:
    """Delete all routines, steps and history. Children first because of foreign keys."""
    for table in ("completions", "step_overrides", "steps", "routines"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def seed_routines(conn: sqlite3.Connection) -> int:
    """Add the sample routines, skipping any whose name already exists. Returns how many
    were added, so running this twice doesn't duplicate them."""
    added = 0
    for routine_data in ROUTINES:
        exists = conn.execute(
            "SELECT 1 FROM routines WHERE name = ?", (routine_data["name"],)
        ).fetchone()
        if exists:
            continue

        routine_id = setup.add_routine(conn, routine_data["name"], routine_data["description"])[
            "routine_id"
        ]
        for step_data in routine_data["steps"]:
            setup.add_step(conn, routine_id, **step_data)
        added += 1
    return added


def seed_history(conn: sqlite3.Connection, days: int = 7, now: datetime | None = None) -> int:
    """Record past completions (yesterday and earlier; today is left clear so the demo
    starts fresh). Returns how many completions were recorded."""
    now = now or datetime.now()
    recorded = 0

    for routine in routines.list_routines(conn):
        for step in routine["steps"]:
            offsets = DEMO_HISTORY_MINUTES_LATE.get(step["title"])
            if not offsets:
                continue
            scheduled_time = datetime.strptime(step["expected_time"], "%H:%M").time()
            for days_ago in range(1, days + 1):
                minutes_late = offsets[(days_ago - 1) % len(offsets)]
                completed_at = datetime.combine(
                    (now - timedelta(days=days_ago)).date(), scheduled_time
                ) + timedelta(minutes=minutes_late)
                result = routines.mark_step_done(conn, routine["id"], step["id"], now=completed_at)
                recorded += result["status"] == "done"
    return recorded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--history", action="store_true", help="also add a week of past completions")
    parser.add_argument("--reset", action="store_true", help="delete all existing data first")
    args = parser.parse_args()

    conn = get_db()
    init_db(conn)

    if args.reset:
        reset(conn)
        print("Cleared existing data.")

    print(f"Added {seed_routines(conn)} routine(s).")
    if args.history:
        print(f"Recorded {seed_history(conn)} past completion(s).")

    conn.close()


if __name__ == "__main__":
    main()
