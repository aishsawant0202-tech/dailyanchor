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

The demo follows **Margaret**, 78, who lives alone with early-stage memory loss, and her
daughter **Priya**, who checks in by phone as her caregiver. The seed data gives Margaret a
Morning, Midday and Evening routine (meds, meals, water, a short walk, locking up).

1. Morning: Margaret asks Alexa+ what's next → `get_current_step` returns "Take morning medication."
2. She confirms → `mark_step_done`.
3. A step is missed → `get_missed_steps` flags it; Alexa+ gently re-prompts and calls
   `snooze_step` to push it back 30 minutes instead of just marking it failed.
4. Priya asks Alexa+ "how is Mum's day going?" → `get_daily_summary` reports
   completed/missed/pending across all routines.
5. Priya asks if anything should change → `suggest_schedule_adjustments` notices breakfast
   is consistently ~40 minutes late and offers to move it; on confirmation, `update_step_time`
   applies it.
6. Priya adds the exercises Margaret's physiotherapist prescribed, by voice → `add_routine`
   creates "Physio Exercises" and `add_step` adds leg stretches (10:30) and balance practice (16:00).

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

### Web simulator

The same scenario also runs in the browser at **http://127.0.0.1:8000/simulator** (linked from
the dashboard). It shows the session on an Echo Show-style screen, with an optional *Read lines
aloud* toggle, and adds one beat the CLI script doesn't have: Margaret asks "did I take my
medication?", `check_step_done` finds three matches, and Alexa+ asks which one she means before
answering. Play the whole demo or one beat at a time.

The page is a real MCP client. Its JavaScript speaks Streamable HTTP to `/mcp`
(`initialize`, `tools/list`, `tools/call`), and the *MCP tool calls* tab lists every call
with the JSON it returned. The *Live dashboard* tab shows the dashboard updating as the
calls land. As with the script, the dialogue is scripted and the facts in it come from the
server. On a server with `DAILYANCHOR_API_KEY` set, the page asks for the key and keeps it
in that browser tab only.

**Live chat.** With `OPENAI_API_KEY` set on the server, the simulator's *Live chat* tab drops
the script: you type (or, in Chrome and Edge, say) what Margaret or Priya says, and an OpenAI
model standing in for Alexa+ answers. It gets the 11 DailyAnchor tools and the
care-assistant skill as its instructions, decides which tools to call, and the server runs
them for real; the calls show in the *MCP tool calls* tab as before. The browser posts to
`/simulator/chat`, which takes the same API key as `/mcp`, so a public server doesn't spend
its OpenAI credit on strangers.

On the deployed server (https on a `DAILYANCHOR_ALLOWED_HOSTS` hostname) the chat uses
OpenAI's Responses API with a remote MCP tool: **OpenAI's servers connect to this server's
`/mcp` endpoint themselves**, with the API key, list the tools and call them, just as Alexa+
would. Locally OpenAI can't reach `127.0.0.1`, so the server runs the model's tool calls
itself (Chat Completions with function tools). The page says which one is in use.

```bat
:: Windows cmd
set OPENAI_API_KEY=sk-...
python -m dailyanchor.server
```

## Project structure

```
src/dailyanchor/
  server.py       # MCP server entrypoint (FastMCP, Streamable HTTP transport)
  db.py           # SQLite schema + connection helper
  time_utils.py   # shared time/deadline/override logic
  dashboard.py    # caregiver web page served at /dashboard
  simulator.py    # browser Alexa+ simulation served at /simulator (an MCP client in JS)
  chat.py         # the simulator's live chat: OpenAI model + DailyAnchor tools loop
  models.py       # dataclasses for Routine, Step, Completion
  tools/
    routines.py   # list_routines, get_current_step, mark_step_done, check_step_done, get_missed_steps
    reminders.py  # snooze_step, get_daily_summary
    setup.py      # add_routine, add_step, update_step_time
    adaptation.py # suggest_schedule_adjustments
skills/
  dailyanchor-care-assistant/SKILL.md  # Agent Skill: how an agent should use these tools
scripts/
  seed_data.py    # seeds sample Morning/Midday/Evening routines for demoing
  demo_client.py  # scripted Alexa+-session simulation over real MCP calls (see below)
tests/
  test_tools.py       # routine/reminder logic (in-memory SQLite)
  test_setup.py       # add_routine / add_step / update_step_time
  test_adaptation.py  # schedule adjustment suggestions
  test_seed.py        # seed script: idempotent, demo history, reset
  test_dashboard.py   # dashboard step statuses and HTML rendering
  test_simulator.py   # simulator page config embedding
  test_chat.py        # live chat tool loop, with a fake model
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

Then open http://127.0.0.1:8000/dashboard (or /simulator) in a browser, and point MCP clients (e.g. the
MCP Inspector, transport "Streamable HTTP") at http://127.0.0.1:8000/mcp.

Run tests:

```bash
pip install pytest
pytest
```

## Configuration & container

Defaults suit running locally. Environment variables change them for a cloud host:

| Variable | Default | Purpose |
|---|---|---|
| `DAILYANCHOR_HOST` | `127.0.0.1` | Interface to listen on; `0.0.0.0` in a container. |
| `PORT` | `8000` | Port to listen on. |
| `DAILYANCHOR_ALLOWED_HOSTS` | *(none)* | Comma-separated public hostnames (e.g. `dailyanchor.example.com`) the MCP endpoint accepts in the `Host` header, in addition to localhost. Without it, requests through a tunnel or proxy to a server bound to 127.0.0.1 get `421 Invalid Host header`, and a server bound to `0.0.0.0` does no Host/Origin checks. |
| `DAILYANCHOR_DB` | `data/dailyanchor.db` | SQLite file location, e.g. on a mounted volume. |
| `DAILYANCHOR_API_KEY` | *(none)* | When set, MCP clients must send `Authorization: Bearer <key>`; others get 401. The dashboard stays open. Set it on any public deployment. |
| `OPENAI_API_KEY` | *(none)* | Turns on the simulator's live chat. |
| `OPENAI_MODEL` | `gpt-5-mini` | Model for the live chat; any Chat Completions model with tool calling. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Another OpenAI-compatible endpoint. |
| `TZ` | system (UTC in the container) | Timezone the routine times are in, e.g. `Europe/Berlin`. `deploy/ec2-user-data.sh` sets it from `TIMEZONE`. |

The `Dockerfile` listens on `0.0.0.0:8000`, seeds the sample routines and demo history on
start (idempotent), then runs the server:

```bash
docker build -t dailyanchor .
docker run -p 8000:8000 -e DAILYANCHOR_ALLOWED_HOSTS=dailyanchor.example.com \
    -e DAILYANCHOR_API_KEY=<long-random-key> dailyanchor

# run the demo against it
python scripts/demo_client.py --url https://dailyanchor.example.com/mcp --api-key <long-random-key>
```

The database lives inside the container, so it resets on each redeploy unless
`/app/data` is mounted as a volume.

### AWS EC2

`deploy/ec2-user-data.sh` deploys to a single free-tier EC2 instance (Amazon Linux 2023)
with no SSH needed: set `API_KEY` in it and paste it into *User data* when launching, with
ports 80 and 443 open. On first boot it builds the image from this repo and runs it behind
Caddy, which serves HTTPS at `https://<public-ip-with-dashes>.sslip.io`. The hostname comes
from the public IP, which changes if the instance is stopped and started.

## Status / next steps

- [ ] Confirm actual Alexa+ ↔ MCP server invocation flow via hackathon office hours (docs are minimal as of this writing) and adjust transport/auth if needed.
- [x] Add a caregiver-side "add routine" / "add step" tool so routines can be configured conversationally rather than only via `scripts/seed_data.py`.
- [x] Adaptive behavior: suggest schedule changes from completion history.
- [x] Seed some demo history so `suggest_schedule_adjustments` has something to show in the video.
- [x] Scripted simulation client (`scripts/demo_client.py`) exercising the full demo scenario over real MCP calls.
- [x] Record demo video (<3 min) walking through the scenario above.
- [x] Write up product feedback (MCP SDK / Alexa+ docs / Devpost) as required by the submission.

## License

MIT — see [LICENSE](LICENSE).
