# DailyAnchor

An MCP server that turns Alexa+ into a patient step-by-step guide for daily
routines — meds, appointments, hygiene — adapting in real time for people with
memory impairment, ADHD, or cognitive fatigue.

Built for the [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/) — Alexa+ track.

## What it does

DailyAnchor tracks one or more daily **routines** (e.g. "Morning Routine"),
each made of ordered **steps** with an expected time and a completion window
(e.g. "Take medication, 08:00, within 60 minutes"). It exposes this as an MCP
server over Streamable HTTP so an Alexa+ agent can:

- ask what the person should be doing right now
- mark a step done when the person confirms it
- notice when a step was missed and needs a gentler re-prompt
- give a caregiver a daily summary of what got done, missed, or is still pending

## MCP tools

| Tool | Description |
|---|---|
| `list_routines` | List all active routines with their ordered steps. |
| `get_current_step` | The next not-yet-completed step in a routine — "what should I do now?" |
| `mark_step_done` | Record a step as completed for today. |
| `get_missed_steps` | Steps that are overdue (past expected time + window) and not completed. |
| `snooze_step` | Push a step's expected time later today — a gentler re-prompt after a miss. |
| `get_daily_summary` | Caregiver-facing rollup of completed / missed / pending steps for a day. |

## Demo scenario (for the video)

1. Morning: person asks Alexa+ what's next → `get_current_step` returns "Take morning medication."
2. They confirm → `mark_step_done`.
3. Time passes, breakfast step is missed → `get_missed_steps` flags it; Alexa+ gently re-prompts and, if needed, calls `snooze_step` to push it back 30 minutes instead of just marking it failed.
4. A remote caregiver asks Alexa+ "how did today go?" → `get_daily_summary` reports completed/missed/pending across all routines.

## Project structure

```
src/dailyanchor/
  server.py       # MCP server entrypoint (FastMCP, Streamable HTTP transport)
  db.py           # SQLite schema + connection helper
  time_utils.py   # shared time/deadline/override logic
  models.py       # dataclasses for Routine, Step, Completion
  tools/
    routines.py   # list_routines, get_current_step, mark_step_done, get_missed_steps
    reminders.py  # snooze_step, get_daily_summary
scripts/
  seed_data.py    # seeds sample Morning/Evening routines for demoing
tests/
  test_tools.py   # unit tests for the routine/reminder logic (in-memory SQLite)
```

Business logic in `tools/` takes a plain `sqlite3.Connection` and has no MCP
dependency, so it's tested directly (see `tests/test_tools.py`) without
spinning up a server.

## Setup & running

Requires Python 3.10+.

```bash
# from the project root
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .

# seed sample routines into data/dailyanchor.db
python scripts/seed_data.py

# run the MCP server (Streamable HTTP, per MCP spec 2025-11-25)
python -m dailyanchor.server
```

Run tests:

```bash
pip install pytest
pytest
```

## Status / next steps

- [ ] Confirm actual Alexa+ ↔ MCP server invocation flow via hackathon office hours (docs are minimal as of this writing) and adjust transport/auth if needed.
- [ ] Add a caregiver-side "add routine" / "add step" tool so routines can be configured conversationally rather than only via `scripts/seed_data.py`.
- [ ] Record demo video (<3 min) walking through the scenario above.
- [ ] Write up product feedback (MCP SDK / Alexa+ docs / Devpost) as required by the submission.

## License

MIT — see [LICENSE](LICENSE).
