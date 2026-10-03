"""Scripted simulation of an Alexa+ session talking to DailyAnchor over MCP.

This is a SIMULATION, not a live Alexa+ integration: Alexa+ chooses which tools to
call and narrates results in its own voice, and this repo has no way to drive the
real Alexa+ app. The lines marked "Alexa+:" and "Person:" below are fixed dialogue,
written to read the way a real session would sound.

What is NOT faked: every fact inside those lines -- step names, times, which steps
are missed, the adaptive suggestion -- comes back from a real MCP tool call against
a running DailyAnchor server. Each beat prints the exact tool call it made and the
JSON it got back ([tool call] / [result] lines), so the gap between "scripted
dialogue" and "real server response" stays visible rather than being smoothed over.

Setup (two terminals):

    # terminal 1
    python scripts/seed_data.py --reset --history
    python -m dailyanchor.server

    # terminal 2
    python scripts/demo_client.py

Beat 2 (the missed-step demo) adds one throwaway step scheduled a few minutes in
the past, via a real add_step call, so there is reliably something overdue to show
regardless of what time of day this is run -- see the comment at that beat.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta

from mcp import Client

DEFAULT_URL = "http://127.0.0.1:8000/mcp"

PAUSE_SECONDS = 1.5  # overridden by --pause / --no-pause; set per-run in main()


def pause() -> None:
    if PAUSE_SECONDS:
        time.sleep(PAUSE_SECONDS)


def banner(text: str) -> None:
    print()
    print(f"-- {text} " + "-" * max(1, 60 - len(text)))
    pause()


def says(speaker: str, line: str) -> None:
    # Plain ASCII on purpose: Windows terminals (cp1252/cp437) choke on emoji/box
    # drawing characters, and this script needs to run cleanly for a screen recording.
    print(f"[{speaker.upper()}] {line}")
    pause()


async def call(client: Client, tool: str, **arguments):
    """Call an MCP tool, printing the call and the (unwrapped) JSON result."""
    print(f"   [tool call] {tool}({', '.join(f'{k}={v!r}' for k, v in arguments.items())})")
    result = await client.call_tool(tool, arguments)
    if result.is_error:
        text = "; ".join(getattr(block, "text", str(block)) for block in result.content)
        print(f"   [error] {text}")
        return None

    payload = result.structured_content
    # Tools that return a bare list get wrapped on the wire as {"result": [...]}
    # because structured content must be a JSON object; unwrap that here so callers
    # just see the list or dict their Python function actually returned.
    if isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
    if payload is None and result.content:
        # Fallback for servers/tools where structured_content comes back empty even
        # though the function returned a plain dict/list (see FRICTION_LOG.md: a bare
        # "-> dict" return annotation, with no type args, was silently dropped by this
        # SDK version -- "-> dict[str, Any]" fixed it). The JSON is still in the
        # unstructured text block, so recover it from there rather than failing.
        text = "".join(getattr(block, "text", "") for block in result.content)
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            payload = text
    print(f"   [result] {payload}")
    return payload


def find_routine(routine_list: list[dict], name: str) -> dict | None:
    return next((r for r in routine_list if r["name"] == name), None)


def find_step(routine: dict, title: str) -> dict | None:
    return next((s for s in routine["steps"] if s["title"] == title), None)


async def run_demo(url: str) -> None:
    print("=" * 70)
    print("DailyAnchor -- simulated Alexa+ session (see module docstring: this is")
    print("scripted dialogue over real MCP tool calls, not a live Alexa+ connection)")
    print("=" * 70)
    pause()

    async with Client(url) as client:
        banner("Setup: what routines does DailyAnchor know about?")
        all_routines = await call(client, "list_routines")
        if not all_routines:
            print("\nNo routines found. Run `python scripts/seed_data.py --reset --history`")
            print("against this server's database first, then re-run this script.")
            return

        morning = find_routine(all_routines, "Morning Routine") or all_routines[0]
        print(f"\nUsing routine: {morning['name']} ({len(morning['steps'])} steps)")

        # --- Beat 1: morning check-in -----------------------------------------
        banner("Beat 1 - Morning check-in")
        says("Person", "Alexa, what's next on my morning routine?")
        step = await call(client, "get_current_step", routine_id=morning["id"])
        if step:
            says("Alexa+", f"Time to {step['title'].lower()}. It's set for {step['expected_time']}.")
            says("Person", "Done, thanks.")
            await call(client, "mark_step_done", routine_id=morning["id"], step_id=step["id"])
            says("Alexa+", "Nice work -- I've checked that off.")
        else:
            says("Alexa+", "Looks like this routine is already fully done for today.")

        # --- Beat 2: a missed step gets a gentle re-prompt ---------------------
        banner("Beat 2 - A missed step, caught and softened")
        # Add one throwaway step scheduled a few minutes in the past with a short
        # window, via a real add_step call. That makes it deterministically overdue
        # the moment we check -- so this beat demonstrates get_missed_steps/snooze_step
        # reliably no matter what time of day the demo is actually recorded.
        past_time = (datetime.now() - timedelta(minutes=20)).strftime("%H:%M")
        demo_step = await call(
            client,
            "add_step",
            routine_id=morning["id"],
            title="Take out recycling",
            expected_time=past_time,
            window_minutes=5,
            description="(demo-only step, added a few minutes in the past so it's overdue now)",
        )
        missed = await call(client, "get_missed_steps", routine_id=morning["id"])
        missed_step = next((m for m in (missed or []) if m["id"] == demo_step["step_id"]), None)
        if missed_step:
            says("Alexa+", f"Looks like '{missed_step['title']}' got missed earlier -- want me to push it back half an hour instead?")
            says("Person", "Yes, please.")
            await call(client, "snooze_step", step_id=missed_step["id"], minutes=30)
            says("Alexa+", "Done -- I'll check back with you then, no harm done.")
        else:
            says("Alexa+", "(unexpected: the demo step wasn't flagged as missed)")

        # --- Beat 3: caregiver summary ------------------------------------------
        banner("Beat 3 - A caregiver checks in remotely")
        says("Person", "(caregiver, by phone) Alexa, how did Mom's day go?")
        summary = await call(client, "get_daily_summary")
        for r in summary["routines"]:
            says(
                "Alexa+",
                f"{r['routine']}: {len(r['completed'])} done, "
                f"{len(r['missed'])} missed, {len(r['pending'])} still to go.",
            )

        # --- Beat 4: adaptive suggestion ----------------------------------------
        banner("Beat 4 - Adapting to how mornings actually go")
        says("Person", "Alexa, any changes I should make to the routine?")
        suggestions = await call(client, "suggest_schedule_adjustments")
        if suggestions:
            top = suggestions[0]
            says("Alexa+", top["message"])
            says("Person", "Sure, go ahead.")
            await call(client, "update_step_time", step_id=top["step_id"], expected_time=top["suggested_time"])
            says("Alexa+", f"Done -- '{top['title']}' is now scheduled for {top['suggested_time']}.")
        else:
            says(
                "Alexa+",
                "Nothing to adjust yet -- I need a few more days of history before I "
                "suggest a change. (Run `seed_data.py --history` for demo data.)",
            )

    print()
    print("=" * 70)
    print("End of simulation.")
    print("=" * 70)


def main() -> None:
    global PAUSE_SECONDS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL, help=f"MCP server URL (default: {DEFAULT_URL})")
    parser.add_argument("--pause", type=float, default=1.5, help="seconds to pause between lines (default: 1.5)")
    parser.add_argument("--no-pause", action="store_true", help="run without pauses, e.g. for a quick smoke test")
    args = parser.parse_args()

    PAUSE_SECONDS = 0.0 if args.no_pause else args.pause

    try:
        asyncio.run(run_demo(args.url))
    except ConnectionError as exc:
        print(f"\nCouldn't reach the DailyAnchor server at {args.url}: {exc}")
        print("Start it first with: python -m dailyanchor.server")
        sys.exit(1)


if __name__ == "__main__":
    main()
