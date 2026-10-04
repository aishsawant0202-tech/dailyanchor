"""Read-only caregiver dashboard, served next to the MCP endpoint.

build_dashboard() gathers today's per-step status from the same tables the MCP tools
use; render_dashboard() turns that into a self-refreshing HTML page. Like the tools,
neither depends on MCP, so they're tested directly against an in-memory database.
"""

import sqlite3
from datetime import datetime
from html import escape

from dailyanchor.time_utils import deadline_for, effective_expected_time, today
from dailyanchor.tools.adaptation import suggest_schedule_adjustments

REFRESH_SECONDS = 5

# status -> (label shown on the page, CSS class)
STATUS_LABELS = {
    "done": "Done",
    "missed": "Missed",
    "due": "Due now",
    "upcoming": "Upcoming",
}


def _step_status(conn: sqlite3.Connection, step: dict, log_date: str, now: datetime) -> dict:
    completion = conn.execute(
        "SELECT completed_at FROM completions WHERE step_id = ? AND log_date = ? "
        "ORDER BY completed_at LIMIT 1",
        (step["id"], log_date),
    ).fetchone()
    expected_time = effective_expected_time(conn, step, log_date)
    deadline = deadline_for(log_date, expected_time, step["window_minutes"])
    start = deadline_for(log_date, expected_time, 0)

    if completion:
        status = "done"
    elif now > deadline:
        status = "missed"
    elif now >= start:
        status = "due"
    else:
        status = "upcoming"

    return {
        "id": step["id"],
        "title": step["title"],
        "description": step["description"],
        "expected_time": expected_time,
        "scheduled_time": step["expected_time"],
        "snoozed": expected_time != step["expected_time"],
        "window_minutes": step["window_minutes"],
        "status": status,
        "completed_at": completion["completed_at"][11:16] if completion else None,
    }


def build_dashboard(conn: sqlite3.Connection, now: datetime | None = None) -> dict:
    """Today's status for every step of every active routine, plus schedule suggestions."""
    now = now or datetime.now()
    log_date = today(now)

    routines = []
    for routine_row in conn.execute("SELECT * FROM routines WHERE active = 1").fetchall():
        routine = dict(routine_row)
        steps = [
            _step_status(conn, dict(row), log_date, now)
            for row in conn.execute(
                "SELECT * FROM steps WHERE routine_id = ? ORDER BY order_index",
                (routine["id"],),
            ).fetchall()
        ]
        counts = {status: 0 for status in STATUS_LABELS}
        for step in steps:
            counts[step["status"]] += 1
        routines.append(
            {
                "name": routine["name"],
                "description": routine["description"],
                "steps": steps,
                "counts": counts,
            }
        )

    return {
        "date": log_date,
        "generated_at": now.strftime("%H:%M:%S"),
        "routines": routines,
        "suggestions": suggest_schedule_adjustments(conn, now=now),
    }


def _step_row(step: dict) -> str:
    when = escape(step["expected_time"])
    if step["snoozed"]:
        when = f'{when} <span class="note">snoozed from {escape(step["scheduled_time"])}</span>'
    detail = f'<div class="desc">{escape(step["description"])}</div>' if step["description"] else ""
    status = step["status"]
    label = STATUS_LABELS[status]
    if status == "done" and step["completed_at"]:
        label = f"Done at {escape(step['completed_at'])}"
    return (
        f'<li class="step {status}">'
        f'<div class="time">{when}</div>'
        f'<div class="what"><div class="title">{escape(step["title"])}</div>{detail}</div>'
        f'<span class="badge {status}">{label}</span>'
        "</li>"
    )


def _routine_card(routine: dict) -> str:
    counts = routine["counts"]
    total = len(routine["steps"])
    tally = " · ".join(
        f'<span class="count {status}">{counts[status]} {STATUS_LABELS[status].lower()}</span>'
        for status in STATUS_LABELS
        if counts[status]
    )
    steps = "".join(_step_row(step) for step in routine["steps"]) or (
        '<li class="empty">No steps yet. Add some with the add_step tool.</li>'
    )
    return (
        '<section class="card">'
        f'<header><h2>{escape(routine["name"])}</h2>'
        f'<div class="progress">{counts["done"]} of {total} done</div></header>'
        f'<p class="routine-desc">{escape(routine["description"])}</p>'
        f'<div class="tally">{tally}</div>'
        f'<ul class="steps">{steps}</ul>'
        "</section>"
    )


def _suggestions(suggestions: list[dict]) -> str:
    if not suggestions:
        return ""
    items = "".join(f"<li>{escape(s['message'])}</li>" for s in suggestions)
    return (
        '<section class="card suggestions">'
        "<header><h2>Schedule suggestions</h2></header>"
        '<p class="routine-desc">Based on the last 7 days. Alexa+ asks before applying '
        "one with update_step_time.</p>"
        f"<ul>{items}</ul>"
        "</section>"
    )


def render_dashboard(data: dict, mcp_url: str, tool_count: int) -> str:
    routines = "".join(_routine_card(r) for r in data["routines"]) or (
        '<section class="card"><p>No routines yet. Run <code>scripts/seed_data.py</code> '
        "or add one with the add_routine tool.</p></section>"
    )
    date_label = datetime.strptime(data["date"], "%Y-%m-%d").strftime("%A %d %B %Y")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>DailyAnchor Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<main>
  <div class="status">
    <span class="dot"></span> MCP server running · endpoint <code>{escape(mcp_url)}</code>
    · {tool_count} tools
  </div>
  <h1>Today's routines</h1>
  <p class="sub">{escape(date_label)} · updated {escape(data["generated_at"])},
    refreshes every {REFRESH_SECONDS}s</p>
  {routines}
  {_suggestions(data["suggestions"])}
</main>
</body>
</html>"""


_CSS = """
:root {
  --bg: #f6f5f1; --card: #ffffff; --text: #1d1d1b; --muted: #6b6a65; --line: #e4e2db;
  --done: #2e7d4f; --done-bg: #e3f2e8; --missed: #b3261e; --missed-bg: #fbe4e2;
  --due: #8a5a00; --due-bg: #fdf0d5; --upcoming: #4a5568; --upcoming-bg: #eceef2;
  --accent: #2b5fab;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161614; --card: #22221f; --text: #ecebe6; --muted: #a09f98; --line: #34332f;
    --done: #7fd19c; --done-bg: #1d3326; --missed: #f2a29b; --missed-bg: #3d1f1c;
    --due: #f0c46b; --due-bg: #3a2f17; --upcoming: #b8c0cc; --upcoming-bg: #2a2d33;
    --accent: #8ab4f0;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.75rem; margin: 16px 0 2px; }
h2 { font-size: 1.15rem; margin: 0; }
.sub { color: var(--muted); margin: 0 0 20px; font-size: .9rem; }
code { font-size: .85em; background: var(--upcoming-bg); padding: 1px 5px; border-radius: 4px; }
.status { font-size: .85rem; color: var(--muted); display: flex; align-items: center;
  gap: 6px; flex-wrap: wrap; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--done); display: inline-block; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 18px 18px 8px; margin-bottom: 16px; }
.card header { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.progress { color: var(--muted); font-size: .9rem; white-space: nowrap; }
.routine-desc { color: var(--muted); margin: 2px 0 8px; font-size: .9rem; }
.tally { font-size: .85rem; margin-bottom: 6px; }
.count.done { color: var(--done); } .count.missed { color: var(--missed); }
.count.due { color: var(--due); } .count.upcoming { color: var(--upcoming); }
.steps { list-style: none; margin: 0; padding: 0; }
.step { display: grid; grid-template-columns: 92px 1fr auto; gap: 12px; align-items: start;
  padding: 12px 0; border-top: 1px solid var(--line); }
.time { font-variant-numeric: tabular-nums; font-weight: 600; }
.note { display: block; font-weight: 400; font-size: .75rem; color: var(--due); }
.title { font-weight: 500; }
.step.done .title { color: var(--muted); text-decoration: line-through; }
.desc { color: var(--muted); font-size: .85rem; }
.badge { font-size: .78rem; font-weight: 600; padding: 3px 10px; border-radius: 999px;
  white-space: nowrap; }
.badge.done { color: var(--done); background: var(--done-bg); }
.badge.missed { color: var(--missed); background: var(--missed-bg); }
.badge.due { color: var(--due); background: var(--due-bg); }
.badge.upcoming { color: var(--upcoming); background: var(--upcoming-bg); }
.empty { padding: 12px 0; color: var(--muted); border-top: 1px solid var(--line); }
.suggestions ul { margin: 0 0 10px; padding-left: 20px; }
.suggestions li { margin-bottom: 6px; }
@media (max-width: 480px) {
  .step { grid-template-columns: 64px 1fr; }
  .badge { grid-column: 2; justify-self: start; }
}
"""
