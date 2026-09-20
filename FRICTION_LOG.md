# Friction Log

Problems hit while building DailyAnchor (Alexa+ track, self-hosted MCP server).
Entry format follows the hackathon rules: task attempted, steps taken, expected vs.
actual, severity, workaround, actionable suggestion.

**Severity scale:** `minor` = annoying, no lost time to speak of · `moderate` = cost real
time or forced a guess · `blocker` = could not proceed without outside help.

Add an entry as soon as something gets in the way; details are hard to recall later.

---

## 1. No hint of the MCP endpoint path when the server starts

- **Date:** 2026-09-19
- **Task attempted:** Check that the locally running MCP server was up.
- **Steps taken:**
  1. Ran `python -m dailyanchor.server` (FastMCP, Streamable HTTP).
  2. Saw `Uvicorn running on http://127.0.0.1:8000` in the log.
  3. Opened `http://127.0.0.1:8000` in a browser.
- **Expected:** Some sign the server was up, or a pointer to where the MCP endpoint lives.
- **Actual:** A bare `Not Found`. The endpoint is at `/mcp`, but the startup log never
  mentions that path, so it looked like the server might be broken.
- **Severity:** minor
- **Workaround:** Knew from the code that the endpoint was `/mcp`, then verified with the
  MCP Inspector (Streamable HTTP, `http://127.0.0.1:8000/mcp`). In this repo, `server.py`
  now prints `DailyAnchor MCP endpoint: http://127.0.0.1:8000/mcp` at startup.
- **Suggestion:** Have the SDK print the full MCP endpoint URL in the startup log (e.g.
  `MCP endpoint: http://127.0.0.1:8000/mcp`), and/or return a short plain-text hint at `/`.

## 2. Server is silent for several seconds at startup

- **Date:** 2026-09-19
- **Task attempted:** Start the server in the background and confirm it was listening.
- **Steps taken:**
  1. Started `python -m dailyanchor.server` with output redirected to a log file.
  2. Checked the log and open ports after ~4 seconds.
- **Expected:** Listening within a couple of seconds, or at least some startup output.
- **Actual:** Empty log and nothing on port 8000 at ~4 s; the `Uvicorn running` line and the
  listening socket appeared several seconds later (roughly 5-10 s after launch).
  Measured afterwards: `import dailyanchor.server` took ~9.7 s wall-clock but only ~1 s of
  CPU, with `import mcp` the largest single cost. That points to slow disk access: the
  project and its `.venv` live on a Windows drive mounted in WSL2 (`/mnt/d`). Moving the
  venv to the Linux filesystem is the likely cure, but that was not tested.
- **Severity:** minor
- **Workaround:** Waited and re-checked the port. In this repo, `server.py` now prints a
  "starting" line before importing the SDK so the wait doesn't look like a hang.
- **Suggestion:** Note in the docs that first start can be slow on WSL2 `/mnt/*` drives and
  recommend keeping the venv on the Linux filesystem.

## 3. `init-context` for the Amazon Devices Builder Tools MCP did not register the server

- **Date:** recorded from a note in the project's `CLAUDE.md` (since deleted); not re-run this session
- **Task attempted:** Set up the Amazon Devices Builder Tools MCP server for use with Claude Code.
- **Steps taken:** Ran `npx @amazon-devices/amazon-devices-buildertools-mcp@latest init-context`.
- **Expected:** The MCP server registered with Claude Code and listed by `claude mcp list`.
- **Actual:** The command wrote a `CLAUDE.md` and `.adbt-config.json`, but the server did not
  appear in `claude mcp list`.
- **Severity:** minor (the tools are for Fire TV/Vega work, which this project doesn't do)
- **Workaround:** Left it unregistered and deleted the generated `CLAUDE.md`.
- **Suggestion:** Have `init-context` say clearly whether registration succeeded, and print
  the exact command to register the server manually if it did not.

---

## To confirm (not yet hit; turn into entries if they become real problems)

- How does real Alexa+ reach a self-hosted server: public HTTPS URL, auth, account linking?
  Are local/tunnelled URLs accepted?
- Which reminder and routine features does Alexa+ already provide natively, so the server
  can add value on top instead of duplicating them?
- Is the MCP spec version (2025-11-25) stable in the SDK version used here, or did the
  transport/API change between releases?

## Entry template

```
## N. Short title

- **Date:**
- **Task attempted:**
- **Steps taken:**
- **Expected:**
- **Actual:**
- **Severity:** minor | moderate | blocker
- **Workaround:**
- **Suggestion:**
```
