import uuid

from dailyanchor.db import get_db, init_db

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


def seed() -> None:
    conn = get_db()
    init_db(conn)

    for routine_data in ROUTINES:
        routine_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO routines (id, name, description, active) VALUES (?, ?, ?, 1)",
            (routine_id, routine_data["name"], routine_data["description"]),
        )
        for index, step_data in enumerate(routine_data["steps"]):
            conn.execute(
                "INSERT INTO steps (id, routine_id, order_index, title, description, "
                "expected_time, window_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    routine_id,
                    index,
                    step_data["title"],
                    step_data["description"],
                    step_data["expected_time"],
                    step_data["window_minutes"],
                ),
            )

    conn.commit()
    conn.close()
    print("Seeded DailyAnchor with sample routines.")


if __name__ == "__main__":
    seed()
