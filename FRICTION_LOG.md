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

## 4. A bare `-> dict` return annotation silently drops structured output

- **Date:** 2026-10-03
- **Task attempted:** Writing an MCP client (`scripts/demo_client.py`) that drives the live
  server and prints each tool's structured JSON result, to use as the hackathon simulation
  script and video spine.
- **Steps taken:**
  1. Called `mark_step_done`, `add_step`, `snooze_step`, `get_daily_summary`, `add_routine`,
     and `update_step_time` via `mcp.Client.call_tool(...)` against the running server.
  2. Read `result.structured_content` on the returned `CallToolResult`.
- **Expected:** The dict the Python function returned (same as `list_routines` -> `list[dict]`
  and `get_current_step` -> `dict | None`, which both came back correctly in
  `structured_content`).
- **Actual:** `structured_content` was `None` for every tool annotated as a bare `-> dict`
  (no type arguments). The data wasn't lost -- it was still JSON-encoded inside the
  unstructured `content[0].text` block -- but a client reading only `structured_content`
  (as MCP's structured-output feature is meant to allow) gets nothing. `dict | None` and
  `list[dict]` on the *same* server, with the *same* mcp package (2.2.0, well above this
  project's `mcp[cli]>=1.2.0` floor), both produced correct `structured_content`; only the
  bare, unparameterized `dict` silently fell back to unstructured-only.
- **Severity:** moderate -- cost real debugging time (an `ExceptionGroup`/`TypeError`
  traceback two levels removed from the actual cause), and would have made Alexa+ itself
  get an opaque JSON-text blob back from 6 of this server's 10 tools instead of structured
  data, defeating the point of typed tool outputs.
- **Workaround:** Changed every bare `-> dict` tool signature in `server.py` to
  `-> dict[str, Any]`, which produces correct `structured_content`. Also made the demo
  client fall back to parsing `content[0].text` as JSON when `structured_content` is `None`,
  so it degrades gracefully if this recurs for a tool we haven't hit yet.
- **Suggestion:** Either make `MCPServer.tool()` build an output schema for a bare `dict`
  return annotation the same way it does for `dict[str, Any]`, or have it warn/log loudly
  when a tool's return type is "object-shaped but un-typed enough to skip structured output"
  rather than silently falling back to text-only content.

## 5. Requests through a tunnel are rejected with `421 Invalid Host header`

- **Date:** 2026-10-05
- **Task attempted:** Prepare the server to be reached through a tunnel (cloudflared/ngrok),
  the usual way to give a cloud agent like Alexa+ a public HTTPS URL for a local server.
- **Steps taken:**
  1. Ran the server as before (`host="127.0.0.1"`, Streamable HTTP).
  2. Sent an MCP `initialize` POST to `/mcp` with the `Host` header a quick tunnel would
     forward (`Host: abc.trycloudflare.com`). Reproduced locally with curl; a real tunnel was
     not set up.
- **Expected:** The request handled like a local one, since the tunnel delivers it to
  127.0.0.1 exactly as a local client would.
- **Actual:** `HTTP/1.1 421 Misdirected Request`, body `Invalid Host header`. The same request
  with `Host: 127.0.0.1:8000` returns 200. Cause: when the host is 127.0.0.1/localhost, the
  SDK (mcp 2.3.0) switches on DNS-rebinding protection by default, allowing only localhost
  `Host` values. Nothing in the startup output says this protection is on, and the only server
  log line is a `WARNING Invalid Host header` without the rejected value or the setting to
  change -- so behind a tunnel, every request from the cloud agent would fail.
- **Severity:** moderate -- found before it cost a live test, but it would fail exactly at the
  first real Alexa+ connection attempt, with an error that doesn't point at the fix.
- **Workaround:** Not applied yet (no public client to test with). The fix is to pass
  `transport_security` with the tunnel hostname added to `allowed_hosts`.
- **Suggestion:** Log the rejected `Host` value and the setting that controls it (e.g.
  "Host 'abc.trycloudflare.com' not in allowed_hosts; see transport_security"), and document
  the tunnel case on the Streamable HTTP page, since tunnelling a local server is a common
  way to test cloud agents.

## 6. `mcp.run()` has no hook for HTTP middleware

- **Date:** 2026-10-05
- **Task attempted:** Log every MCP request (JSON-RPC method, tool name, client, status) to
  see whether a remote client was really calling the server.
- **Steps taken:**
  1. Looked for a way to add Starlette/ASGI middleware through `MCPServer.run(...)`.
  2. Found `MCPServer(middleware=...)`, but it wraps JSON-RPC messages inside the SDK, after
     the transport, so it can't see the HTTP status, `Host` header or client IP -- and so
     can't log requests the transport rejects, such as the 421s in entry 5.
- **Expected:** A way to add HTTP-level middleware while still using `run()`.
- **Actual:** `run(transport="streamable-http")` builds the Starlette app and starts uvicorn
  internally, with no parameter for HTTP middleware.
- **Severity:** minor
- **Workaround:** Call `mcp.streamable_http_app(...)` directly, wrap it in our own ASGI
  middleware (`src/dailyanchor/request_log.py`), and start it with `uvicorn.run(...)`.
- **Suggestion:** Accept an `http_middleware` (list of Starlette `Middleware`) argument on
  `run()` / `streamable_http_app()`, or document the "build the app and wrap it" pattern.

## 7. No documented way to connect a self-hosted MCP server to real Alexa+

- **Date:** 2026-10-06
- **Task attempted:** Validate the server with the real Alexa+ as the MCP client.
- **Steps taken:**
  1. Read the Alexa+ track description, the linked MCP spec pages and the ADBT get-started
     page, looking for how Alexa+ is pointed at a self-hosted Streamable HTTP server.
  2. Planned a public HTTPS endpoint (tunnel, then AWS) on the assumption that Alexa+ would
     need one, which surfaced entry 5.
- **Expected:** A short "connect your MCP server to Alexa+" guide: where to register the URL,
  what auth is supported, and whether a developer/preview account is needed.
- **Actual:** No such path found for hackathon entrants. The official rules later clarified
  that a simulated Alexa+ experience (any agentic tool, via a web app) is acceptable, but
  only after time had gone into planning hosting for a client we couldn't access.
- **Severity:** moderate -- cost planning time and left the core integration unverifiable
  against the real target.
- **Workaround:** Validated the server with another MCP client instead (Claude Code, which
  picked the expected tool for all 8 test utterances, confirmed in the server's request log),
  and plan a web-app simulation per the rules.
- **Suggestion:** State on the track page, up front, that real Alexa+ access isn't available
  to entrants and that simulation is the expected path -- or, if it is available, link the
  steps to register a server URL and the supported auth.

---

## To confirm (not yet hit; turn into entries if they become real problems)

- If real Alexa+ access becomes available: how does it reach a self-hosted server (public
  HTTPS URL, auth, account linking), and are tunnelled URLs accepted? (See entry 7.)
- Which reminder and routine features does Alexa+ already provide natively, so the server
  can add value on top instead of duplicating them?

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
