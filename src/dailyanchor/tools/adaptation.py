import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

from dailyanchor.time_utils import today

ROUND_TO_MINUTES = 5


def suggest_schedule_adjustments(
    conn: sqlite3.Connection,
    lookback_days: int = 7,
    min_samples: int = 3,
    min_late_minutes: int = 15,
    now: datetime | None = None,
) -> list[dict]:
    """Suggest moving steps the person consistently completes later than scheduled.

    Looks at completions over the last `lookback_days` days. A step needs at least
    `min_samples` completions, and a median lateness of `min_late_minutes` or more,
    before we suggest anything -- one late morning is not a pattern. Lateness is
    measured against the step's scheduled time, not today's snooze override."""
    now = now or datetime.now()
    end_date = today(now)
    start_date = today(now - timedelta(days=lookback_days - 1))

    rows = conn.execute(
        "SELECT s.id, s.routine_id, s.title, s.expected_time, c.completed_at, c.log_date "
        "FROM completions c "
        "JOIN steps s ON s.id = c.step_id "
        "JOIN routines r ON r.id = s.routine_id "
        "WHERE r.active = 1 AND c.log_date >= ? AND c.log_date <= ?",
        (start_date, end_date),
    ).fetchall()

    steps: dict[str, dict] = {}
    minutes_late: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        steps[row["id"]] = dict(row)
        scheduled = datetime.strptime(f"{row['log_date']} {row['expected_time']}", "%Y-%m-%d %H:%M")
        completed = datetime.fromisoformat(row["completed_at"])
        minutes_late[row["id"]].append((completed - scheduled).total_seconds() / 60)

    suggestions = []
    for step_id, samples in minutes_late.items():
        if len(samples) < min_samples:
            continue
        typical_lateness = median(samples)
        if typical_lateness < min_late_minutes:
            continue

        step = steps[step_id]
        shift = math.ceil(typical_lateness / ROUND_TO_MINUTES) * ROUND_TO_MINUTES
        current = datetime.strptime(step["expected_time"], "%H:%M")
        suggested = current + timedelta(minutes=shift)
        if suggested.date() != current.date():
            continue  # would wrap past midnight; not a sensible suggestion
        suggested_time = suggested.strftime("%H:%M")

        suggestions.append(
            {
                "step_id": step_id,
                "routine_id": step["routine_id"],
                "title": step["title"],
                "current_time": step["expected_time"],
                "suggested_time": suggested_time,
                "days_observed": len(samples),
                "median_minutes_late": round(typical_lateness),
                "message": (
                    f"'{step['title']}' is usually done around {suggested_time} rather than "
                    f"{step['expected_time']} (over the last {len(samples)} days). "
                    f"Move it to {suggested_time}?"
                ),
            }
        )

    return sorted(suggestions, key=lambda s: s["median_minutes_late"], reverse=True)
