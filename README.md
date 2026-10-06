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
| `check_step_done` | "Did I already take my pill?" — whether a step was done today and at what time, matched from the person's own words. Returns every match if ambiguous (e.g. morning and evening meds). Guards against double-dosing. |
| `get_missed_steps` | Steps that are overdue (past expected time + window) and not completed. |
| `snooze_step` | Push a step's expected time later today — a gentler re-prompt after a miss. |
| `get_daily_summary` | Caregiver-facing rollup of completed / missed / pending steps for a day. |
| `add_routine` | Create a new, empty routine — lets a caregiver set things up by voice. |
| `add_step` | Add a step (title, `HH:MM` time, on-time window) to a routine, at the end or at a given position. |
| `update_step_time` | Permanently change when a step is expected (`snooze_step` only shifts it for today). |
| `suggest_schedule_adjustments` | Looks at recent history and suggests moving steps the person consistently does late, e.g. "breakfast is usually done around 09:15 rather than 08:30 — move it?" |

## Agent Skill

`skills/dailyanchor-care-assistant/SKILL.md` is an [Agent Skill](https://agentskills.io) that
teaches any agent using these tools how to act as the assistant, not just which tools exist:
always check `check_step_done` before talking about medication and ask when the match is
ambiguous, re-prompt gently with `snooze_step` instead of scolding, and ask before applying
a schedule suggestion. The MCP server provides the memory; the skill provides the care workflow.

To use it with Claude Code, copy or link the folder into a project's `.claude/skills/`.

## Caregiver dashboard

The server also serves a read-only web page at **http://127.0.0.1:8000/dashboard**
(`/` redirects there). It shows each routine's steps for today as *Done* (with the time),
*Due now*, *Upcoming* or *Missed*, marks snoozed steps, and lists the current schedule
suggestions. It refreshes every 5 seconds, so a step marked done through an MCP tool shows up
on the page a moment later.

`http://127.0.0.1:8000/mcp` is for MCP clients only; opening it in a browser gives a
"Missing session ID" error, which is expected.

### How the adaptive suggestion works

`suggest_schedule_adjustments` compares each step's completion times over the last
7 days to its scheduled time. It only suggests a change when a step has at least
3 completions and a median lateness of 15+ minutes, so one bad morning isn't
treated as a pattern. The suggested time is the median lateness rounded up to the
next 5 minutes. Alexa+ should ask before applying one with `update_step_time`.

## Demo scenario (for the video)

1. Morning: person asks Alexa+ what's next → `get_current_step` returns "Take morning medication."
2. They confirm → `mark_step_done`.
3. A step is missed → `get_missed_steps` flags it; Alexa+ gently re-prompts and calls
   `snooze_step` to push it back 30 minutes instead of just marking it failed.
4. A remote caregiver asks Alexa+ "how did today go?" → `get_daily_summary` reports
   completed/missed/pending across all routines.
5. Alexa+ asks if anything should change → `suggest_schedule_adjustments` notices breakfast
   is consistently ~40 minutes late and offers to move it; on confirmation, `update_step_time`
   applies it.

`scripts/demo_client.py` runs this whole scenario against a live DailyAnchor server as a
**scripted simulation**: the "Alexa+ says" / "Person says" lines are fixed dialogue (there is
no real Alexa+ connection here), but every fact in them — step names, times, which step is
missed, the suggested new time — comes back from real MCP tool calls, printed alongside the
dialogue so the two stay distinguishable. This is the Alexa+-track simulation the hackathon
rules ask the repo to include; the demo video should make clear it's simulated.

```bash
# terminal 1
python scripts/seed_data.py --reset --history
python -m dailyanchor.server

# terminal 2
python scripts/demo_client.py            # paced for recording (1.5s between lines)
python scripts/demo_client.py --no-pause # fast run, e.g. to sanity-check before recording
```

## Project structure

```
src/dailyanchor/
  server.py       # MCP server entrypoint (FastMCP, Streamable HTTP transport)
  db.py           # SQLite schema + connection helper
  time_utils.py   # shared time/deadline/override logic
  dashboard.py    # caregiver web page served at /dashboard
  models.py       # dataclasses for Routine, Step, Completion
  tools/
    routines.py   # list_routines, get_current_step, mark_step_done, check_step_done, get_missed_steps
    reminders.py  # snooze_step, get_daily_summary
    setup.py      # add_routine, add_step, update_step_time
    adaptation.py # suggest_schedule_adjustments
skills/
  dailyanchor-care-assistant/SKILL.md  # Agent Skill: how an agent should use these tools
scripts/
  seed_data.py    # seeds sample Morning/Evening routines for demoing
  demo_client.py  # scripted Alexa+-session simulation over real MCP calls (see below)
tests/
  test_tools.py       # routine/reminder logic (in-memory SQLite)
  test_setup.py       # add_routine / add_step / update_step_time
  test_adaptation.py  # schedule adjustment suggestions
  test_seed.py        # seed script: idempotent, demo history, reset
  test_dashboard.py   # dashboard step statuses and HTML rendering
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

# seed sample routines into data/dailyanchor.db (safe to re-run)
python scripts/seed_data.py

# demo setup: also add a week of past completions, so the adaptive
# suggestion ("breakfast is usually ~09:15, move it?") has history to learn from
python scripts/seed_data.py --history

# start a clean demo take: wipe all data, then reseed
python scripts/seed_data.py --reset --history

# run the MCP server (Streamable HTTP, per MCP spec 2025-11-25)
python -m dailyanchor.server
```

Then open http://127.0.0.1:8000/dashboard in a browser, and point MCP clients (e.g. the
MCP Inspector, transport "Streamable HTTP") at http://127.0.0.1:8000/mcp.

Run tests:

```bash
pip install pytest
pytest
```

## Status / next steps

- [ ] Confirm actual Alexa+ ↔ MCP server invocation flow via hackathon office hours (docs are minimal as of this writing) and adjust transport/auth if needed.
- [x] Add a caregiver-side "add routine" / "add step" tool so routines can be configured conversationally rather than only via `scripts/seed_data.py`.
- [x] Adaptive behavior: suggest schedule changes from completion history.
- [x] Seed some demo history so `suggest_schedule_adjustments` has something to show in the video.
- [x] Scripted simulation client (`scripts/demo_client.py`) exercising the full demo scenario over real MCP calls.
- [ ] Record demo video (<3 min) walking through the scenario above.
- [ ] Write up product feedback (MCP SDK / Alexa+ docs / Devpost) as required by the submission.

## License

MIT — see [LICENSE](LICENSE).
