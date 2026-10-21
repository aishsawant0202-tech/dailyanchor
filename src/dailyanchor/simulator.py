"""Browser version of scripts/demo_client.py, served at /simulator.

The scripted demo, like the CLI script, is a SIMULATION: the Alexa+, Margaret and Priya lines are fixed
dialogue, since nothing here can drive the real Alexa+ app. What is real is every fact in
them. The page is its own MCP client: its JavaScript speaks Streamable HTTP to /mcp
(initialize, tools/list, tools/call) exactly as Alexa+ would, and shows each call and the
JSON that came back next to the conversation. A live dashboard sits alongside, so a tool
call made here shows up there a few seconds later.

With OPENAI_API_KEY set on the server the page also has a Live chat mode: what you type (or
say) goes to /simulator/chat, where an OpenAI model standing in for Alexa+ answers using the
same tools (see chat.py). Nothing in that mode is scripted. On the deployed server OpenAI calls
this server's /mcp endpoint itself; locally, where it can't, the server runs the tools.
"""

import json
from datetime import datetime

PERSON = "Margaret"
CAREGIVER = "Priya"


def render_simulator(
    mcp_path: str,
    dashboard_path: str,
    now: datetime | None = None,
    chat_model: str | None = None,
    chat_mcp_url: str | None = None,
) -> str:
    """The simulator page. `now` is the server's local time: the page uses it rather than
    the browser clock to pick a time that is already overdue, since a cloud server's clock
    (often UTC) can be hours away from the viewer's. `chat_model` turns on Live chat;
    `chat_mcp_url` is the public /mcp URL OpenAI calls in that mode, if there is one."""
    now = now or datetime.now()
    config = {
        "mcpPath": mcp_path,
        "dashboardPath": dashboard_path,
        "chatPath": "/simulator/chat",
        "chatModel": chat_model,
        "chatMcpUrl": chat_mcp_url,
        "serverNow": now.isoformat(timespec="seconds"),
        "person": PERSON,
        "caregiver": CAREGIVER,
    }
    # "</" can't appear inside a <script> block, so escape it in the embedded JSON.
    config_json = json.dumps(config).replace("</", "<\\/")
    return _HTML.replace("__CONFIG__", config_json)


_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DailyAnchor Simulator</title>
<style>
:root {
  --bg: #f6f5f1; --card: #ffffff; --text: #1d1d1b; --muted: #6b6a65; --line: #e4e2db;
  --accent: #2b5fab; --accent-bg: #e5edf8; --alexa: #0f7c90; --alexa-bg: #dff1f4;
  --person-bg: #eceef2; --caregiver: #7a4fa3; --caregiver-bg: #efe7f6;
  --ok: #2e7d4f; --err: #b3261e; --err-bg: #fbe4e2; --code-bg: #f1f0ec;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161614; --card: #22221f; --text: #ecebe6; --muted: #a09f98; --line: #34332f;
    --accent: #8ab4f0; --accent-bg: #1f2a3b; --alexa: #6fd3e4; --alexa-bg: #173338;
    --person-bg: #2a2d33; --caregiver: #c9a6ec; --caregiver-bg: #2f2538;
    --ok: #7fd19c; --err: #f2a29b; --err-bg: #3d1f1c; --code-bg: #1b1b19;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1240px; margin: 0 auto; padding: 20px 16px 48px; }
h1 { font-size: 1.6rem; margin: 0 0 2px; }
h2 { font-size: 1.05rem; margin: 0; }
.sub { color: var(--muted); margin: 0 0 14px; font-size: .9rem; }
a { color: var(--accent); }
code { font-size: .85em; background: var(--code-bg); padding: 1px 5px; border-radius: 4px; }
.notice { background: var(--accent-bg); border-radius: 10px; padding: 10px 14px; font-size: .88rem;
  margin-bottom: 16px; }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px;
  align-items: start; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
.card > header { display: flex; justify-content: space-between; align-items: center; gap: 10px;
  margin-bottom: 10px; flex-wrap: wrap; }
.conn { font-size: .82rem; color: var(--muted); display: flex; align-items: center; gap: 6px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); display: inline-block; }
.dot.ok { background: var(--ok); } .dot.err { background: var(--err); }

/* Echo Show-style screen */
.device { background: #101418; border-radius: 18px; padding: 14px; }
.screen { background: #0b0f13; color: #e9eef2; border-radius: 10px; height: 430px; overflow-y: auto;
  padding: 14px; display: flex; flex-direction: column; gap: 8px; scroll-behavior: smooth; }
.ring { height: 6px; border-radius: 3px; margin-top: 12px; background: #24303a;
  transition: background .2s; }
.ring.listening { background: linear-gradient(90deg, #0b5f73, #36c5e0, #0b5f73);
  background-size: 200% 100%; animation: sweep 1.2s linear infinite; }
@keyframes sweep { from { background-position: 0 0; } to { background-position: 200% 0; } }
@media (prefers-reduced-motion: reduce) { .ring.listening { animation: none; background: #36c5e0; } }
.empty-screen { color: #8b98a3; margin: auto; text-align: center; font-size: .95rem; max-width: 300px; }
.beat-title { color: #8b98a3; font-size: .75rem; text-transform: uppercase; letter-spacing: .06em;
  margin-top: 8px; }
.line { max-width: 85%; padding: 8px 12px; border-radius: 14px; font-size: .95rem; }
.line .who { display: block; font-size: .7rem; font-weight: 700; letter-spacing: .04em;
  text-transform: uppercase; opacity: .75; }
.line.alexa { background: #13414b; color: #e6fbff; align-self: flex-start; border-bottom-left-radius: 4px; }
.line.person { background: #2d333b; align-self: flex-end; border-bottom-right-radius: 4px; }
.line.caregiver { background: #3d2f4c; align-self: flex-end; border-bottom-right-radius: 4px; }
.line.aside { background: none; color: #8b98a3; font-size: .8rem; align-self: center; padding: 0; }

.controls { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.row-label { font-size: .78rem; color: var(--muted); width: 100%; }
button { font: inherit; font-size: .88rem; border-radius: 999px; padding: 6px 14px; cursor: pointer;
  border: 1px solid var(--line); background: var(--card); color: var(--text); }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .5; cursor: default; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--card); font-weight: 600; }
label.toggle { font-size: .85rem; display: flex; gap: 6px; align-items: center; color: var(--muted); }
.key-row { display: none; }
.key-row.show { display: flex; }
.key-row input { font: inherit; font-size: .88rem; padding: 6px 10px; border-radius: 8px;
  border: 1px solid var(--line); background: var(--bg); color: var(--text); flex: 1; min-width: 0; }

/* Right column */
.tabs { display: flex; gap: 4px; }
.tab { border-radius: 8px; padding: 4px 12px; }
.tab[aria-selected="true"] { background: var(--accent-bg); border-color: var(--accent); color: var(--accent); font-weight: 600; }
.panel { display: none; }
.panel.active { display: block; }
.log { height: 560px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.log .hint { color: var(--muted); font-size: .9rem; }
.call { border: 1px solid var(--line); border-radius: 8px; font-size: .82rem; }
.call summary { padding: 7px 10px; cursor: pointer; display: flex; gap: 8px; align-items: baseline;
  list-style: none; }
.call summary::-webkit-details-marker { display: none; }
.call .name { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-weight: 600; }
.call .args { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; color: var(--muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.call .ms { color: var(--muted); white-space: nowrap; }
.call.error { border-color: var(--err); background: var(--err-bg); }
.call pre { margin: 0; padding: 8px 10px; background: var(--code-bg); border-top: 1px solid var(--line);
  font-size: .78rem; overflow-x: auto; max-height: 260px; }
.chat-form { flex-wrap: nowrap; }
.chat-form input, select { font: inherit; font-size: .9rem; padding: 6px 10px; border-radius: 8px;
  border: 1px solid var(--line); background: var(--bg); color: var(--text); }
.chat-form input { flex: 1; min-width: 0; }
button.recording { border-color: var(--err); color: var(--err); }
.chat-off { color: var(--muted); font-size: .88rem; margin: 0; }
.line.typing { background: #13414b; color: #9fd6e0; align-self: flex-start; }
[hidden] { display: none !important; }
iframe { width: 100%; height: 560px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); }
@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .screen { height: 380px; }
  .log, iframe { height: 440px; }
}
</style>
</head>
<body>
<main>
  <h1>DailyAnchor &middot; Alexa+ simulator</h1>
  <p class="sub">Margaret, 78, lives alone with early memory loss. Her daughter Priya checks in by phone.
    <a href="/dashboard">Open the caregiver dashboard</a></p>
  <div class="notice" id="notice-chat" hidden><strong>Live chat, nothing scripted.</strong> An OpenAI
    model (<code id="chat-model"></code>) stands in for Alexa+ and follows the DailyAnchor
    care-assistant skill. It decides which tools to call, and they run on this server for real,
    listed under <em>MCP tool calls</em>. <span id="chat-via"></span> What you type is sent to OpenAI.</div>
  <div class="notice" id="notice-scripted"><strong>This is a simulation.</strong> The spoken lines are scripted, because
    this page can't drive the real Alexa+ app. Every fact in them (step names, times, what was
    missed, the suggested change) comes from a real MCP tool call this page makes to
    <code id="mcp-url"></code>. Each call and its JSON result is listed under <em>MCP tool calls</em>.</div>

  <div class="layout">
    <section class="card">
      <header>
        <div class="tabs" role="tablist">
          <button class="tab" role="tab" aria-selected="true" data-mode="scripted">Scripted demo</button>
          <button class="tab" role="tab" aria-selected="false" data-mode="chat">Live chat</button>
        </div>
        <span class="conn"><span class="dot" id="conn-dot"></span><span id="conn-text">Not connected</span></span>
      </header>
      <div class="device">
        <div class="screen" id="screen" aria-live="polite">
          <p class="empty-screen" id="empty-screen">Press <strong>Play full demo</strong>, or pick one
            moment from Margaret's day below.</p>
        </div>
        <div class="ring" id="ring"></div>
      </div>
      <div class="controls" id="scripted-controls">
        <div class="row">
          <button class="primary" id="play-all">Play full demo</button>
          <button id="clear">Clear screen</button>
          <label class="toggle"><input type="checkbox" id="speak"> Read lines aloud</label>
        </div>
        <div class="row" id="beats">
          <span class="row-label">Or play one moment:</span>
        </div>
      </div>
      <div class="controls" id="chat-controls" hidden>
        <p class="chat-off" id="chat-off" hidden>Live chat isn't set up on this server. Start it with
          <code>OPENAI_API_KEY</code> set (and optionally <code>OPENAI_MODEL</code>).</p>
        <div class="row">
          <label class="toggle">Speaking as
            <select id="speaker"><option>Margaret</option><option>Priya</option></select></label>
          <label class="toggle"><input type="checkbox" id="speak-chat"> Read replies aloud</label>
          <button id="clear-chat">New conversation</button>
        </div>
        <form class="row chat-form" id="chat-form">
          <button type="button" id="mic" hidden>Mic</button>
          <input id="chat-input" placeholder="Type what Margaret or Priya says" autocomplete="off">
          <button class="primary" type="submit" id="send">Send</button>
        </form>
        <div class="row" id="chat-ideas"><span class="row-label">Try:</span></div>
      </div>
      <div class="controls">
        <div class="row key-row" id="key-row">
          <span class="row-label">This server needs its API key (<code>DAILYANCHOR_API_KEY</code>). It stays in this browser tab.</span>
          <input type="password" id="api-key" placeholder="API key" autocomplete="off">
          <button id="save-key">Connect</button>
        </div>
      </div>
    </section>

    <section class="card">
      <header>
        <div class="tabs" role="tablist">
          <button class="tab" role="tab" aria-selected="true" data-panel="log-panel">MCP tool calls</button>
          <button class="tab" role="tab" aria-selected="false" data-panel="dash-panel">Live dashboard</button>
        </div>
        <span class="conn" id="tool-count"></span>
      </header>
      <div class="panel active" id="log-panel">
        <div class="log" id="log"><p class="hint">Tool calls show up here as the session runs.
          Click one to see the JSON the server returned.</p></div>
      </div>
      <div class="panel" id="dash-panel">
        <iframe id="dashboard" title="Caregiver dashboard" loading="lazy"></iframe>
      </div>
    </section>
  </div>
</main>

<script>
const CONFIG = __CONFIG__;
const PERSON = CONFIG.person, CAREGIVER = CONFIG.caregiver;
const $ = id => document.getElementById(id);

function storageGet(key) { try { return sessionStorage.getItem(key) || ""; } catch { return ""; } }
function storageSet(key, value) { try { sessionStorage.setItem(key, value); } catch {} }

// The server's clock, not the browser's: a cloud server's local time is often UTC.
const loadedAt = Date.now();
const serverNow = () => new Date(new Date(CONFIG.serverNow).getTime() + (Date.now() - loadedAt));
const hhmm = d => String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");

// ---- Minimal MCP client over Streamable HTTP --------------------------------------------
class AuthError extends Error {}
const session = { id: null, protocolVersion: null, connected: false, nextId: 1 };
let apiKey = storageGet("dailyanchor.apiKey");

function parseSse(text) {
  return text.split(/\\r?\\n\\r?\\n/)
    .map(event => event.split(/\\r?\\n/).filter(l => l.startsWith("data:"))
      .map(l => l.slice(5).replace(/^ /, "")).join("\\n"))
    .filter(Boolean)
    .map(data => { try { return JSON.parse(data); } catch { return null; } })
    .filter(Boolean);
}

async function post(message) {
  const headers = { "Content-Type": "application/json", "Accept": "application/json, text/event-stream" };
  if (session.id) headers["Mcp-Session-Id"] = session.id;
  if (session.protocolVersion) headers["MCP-Protocol-Version"] = session.protocolVersion;
  if (apiKey) headers["Authorization"] = "Bearer " + apiKey;
  const res = await fetch(CONFIG.mcpPath, { method: "POST", headers, body: JSON.stringify(message) });
  if (res.status === 401) throw new AuthError("Missing or invalid API key");
  if (res.status === 404 && session.id) {
    const err = new Error("MCP session expired");
    err.expired = true;
    throw err;
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const sid = res.headers.get("mcp-session-id");
  if (sid) session.id = sid;
  if (message.id === undefined) return null;  // a notification: no reply expected
  const text = await res.text();
  const type = res.headers.get("content-type") || "";
  const replies = type.includes("text/event-stream") ? parseSse(text) : [JSON.parse(text)];
  const reply = replies.find(r => r.id === message.id);
  if (!reply) throw new Error("The server sent no reply to " + message.method);
  if (reply.error) throw new Error(reply.error.message);
  return reply.result;
}

const request = (method, params) => post({ jsonrpc: "2.0", id: session.nextId++, method, params });

async function connect() {
  Object.assign(session, { id: null, protocolVersion: null, connected: false });
  setConn("", "Connecting...");
  const init = await request("initialize", {
    protocolVersion: "2025-11-25",
    capabilities: {},
    clientInfo: { name: "dailyanchor-web-simulator", version: "0.1.0" },
  });
  session.protocolVersion = init.protocolVersion;
  await post({ jsonrpc: "2.0", method: "notifications/initialized" });
  const { tools } = await request("tools/list", {});
  session.connected = true;
  setConn("ok", `Connected to ${init.serverInfo?.name || "server"} over MCP`);
  $("tool-count").textContent = `${tools.length} tools`;
}

// Tools that return a bare list (or None) come back wrapped as {"result": ...}, because
// structured content has to be a JSON object. Unwrap it, as scripts/demo_client.py does.
function unwrap(result) {
  let payload = result.structuredContent;
  if (payload && !Array.isArray(payload) && typeof payload === "object"
      && Object.keys(payload).length === 1 && "result" in payload) payload = payload.result;
  if (payload === undefined) {
    const text = (result.content || []).map(block => block.text || "").join("");
    try { payload = JSON.parse(text); } catch { payload = text || null; }
  }
  return payload ?? null;
}

async function callTool(name, args = {}) {
  const started = performance.now();
  const entry = logCall(name, args);
  try {
    if (!session.connected) await connect();
    let result;
    try {
      result = await request("tools/call", { name, arguments: args });
    } catch (err) {
      if (!err.expired) throw err;
      await connect();
      result = await request("tools/call", { name, arguments: args });
    }
    if (result.isError) {
      throw new Error((result.content || []).map(block => block.text || "").join("; ") || "Tool error");
    }
    const payload = unwrap(result);
    finishCall(entry, payload, performance.now() - started);
    return payload;
  } catch (err) {
    finishCall(entry, String(err.message || err), performance.now() - started, true);
    throw err;
  }
}

// ---- Rendering ---------------------------------------------------------------------------
function setConn(state, text) {
  $("conn-dot").className = "dot " + state;
  $("conn-text").textContent = text;
}

function logCall(name, args) {
  const log = $("log");
  log.querySelector(".hint")?.remove();
  const details = document.createElement("details");
  details.className = "call";
  const summary = document.createElement("summary");
  const argText = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
  summary.innerHTML = '<span class="name"></span><span class="args"></span><span class="ms">...</span>';
  summary.querySelector(".name").textContent = name;
  summary.querySelector(".args").textContent = "(" + argText + ")";
  summary.querySelector(".args").title = argText;
  const pre = document.createElement("pre");
  details.append(summary, pre);
  log.append(details);
  log.scrollTop = log.scrollHeight;
  return details;
}

function finishCall(entry, payload, ms, isError = false) {
  // ms is null for calls OpenAI made to /mcp itself: we only see them afterwards.
  entry.querySelector(".ms").textContent = isError ? "error" : ms == null ? "by OpenAI" : `${Math.round(ms)} ms`;
  entry.querySelector("pre").textContent =
    typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  if (isError) { entry.classList.add("error"); entry.open = true; }
}

const ROLE = { "Alexa+": "alexa", [PERSON]: "person", [CAREGIVER]: "caregiver" };
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

function addToScreen(el) {
  $("empty-screen")?.remove();
  $("screen").append(el);
  $("screen").scrollTop = $("screen").scrollHeight;
}

let mode = "scripted";

function speak(speaker, text) {
  const toggle = mode === "chat" ? $("speak-chat") : $("speak");
  if (!toggle.checked || !("speechSynthesis" in window)) return Promise.resolve(false);
  return new Promise(resolve => {
    const utterance = new SpeechSynthesisUtterance(text);
    // Give the three speakers audibly different voices with pitch, as voice lists vary by browser.
    utterance.pitch = speaker === "Alexa+" ? 1.05 : speaker === PERSON ? 0.8 : 1.3;
    utterance.rate = speaker === PERSON ? 0.9 : 1;
    utterance.onend = utterance.onerror = () => resolve(true);
    speechSynthesis.speak(utterance);
  });
}

function addLine(speaker, text) {
  const line = document.createElement("div");
  line.className = "line " + (ROLE[speaker] || "person");
  line.innerHTML = '<span class="who"></span>';
  line.querySelector(".who").textContent = speaker;
  line.append(text);
  addToScreen(line);
}

// Shows a line and reads it aloud if that's on. `paced` waits a reading-length pause when
// not speaking, so the scripted demo doesn't flash past.
async function say(speaker, text, paced = true) {
  addLine(speaker, text);
  const ring = $("ring");
  if (speaker === "Alexa+") ring.classList.add("listening");
  const spoke = await speak(speaker, text);
  if (!spoke && paced) await pause(Math.min(2600, 700 + text.length * 22));
  ring.classList.remove("listening");
}

function aside(text) {
  const line = document.createElement("div");
  line.className = "line aside";
  line.textContent = text;
  addToScreen(line);
}

function beatTitle(text) {
  const el = document.createElement("div");
  el.className = "beat-title";
  el.textContent = text;
  addToScreen(el);
}

// ---- The scenario (the same beats as scripts/demo_client.py, plus the pill check) -------
const findRoutine = (list, name) => (list || []).find(r => r.name === name);

async function routinesOrStop() {
  const all = await callTool("list_routines");
  if (!all || !all.length) {
    aside("No routines found. Run scripts/seed_data.py --reset --history on the server, then try again.");
    throw new Error("no routines");
  }
  return all;
}

const BEATS = [
  {
    label: "Morning check-in",
    async run() {
      const all = await routinesOrStop();
      const morning = findRoutine(all, "Morning Routine") || all[0];
      await say(PERSON, "Alexa, what's next on my morning routine?");
      const step = await callTool("get_current_step", { routine_id: morning.id });
      if (!step) {
        await say("Alexa+", "You've finished everything on your morning routine today. Well done.");
        return;
      }
      await say("Alexa+", `Good morning, ${PERSON}. Time to ${step.title.toLowerCase()}. It's set for ${step.expected_time}.`);
      if (step.description) await say("Alexa+", step.description);
      await say(PERSON, "Done, thanks.");
      await callTool("mark_step_done", { routine_id: morning.id, step_id: step.id });
      await say("Alexa+", "Nice work. I've checked that off.");
    },
  },
  {
    label: "Did I take my pill?",
    async run() {
      await say(PERSON, "Alexa, did I take my medication?");
      let check = await callTool("check_step_done", { step: "medication" });
      if (check.status === "ambiguous") {
        const names = [...check.matches].sort((a, b) => a.expected_time.localeCompare(b.expected_time))
          .map(m => m.title.replace(/^Take /, "").toLowerCase());
        await say("Alexa+", `You have ${names.length} medications today: ${names.slice(0, -1).join(", ")} and ${names.at(-1)}. Which one do you mean?`);
        await say(PERSON, "The morning one.");
        check = await callTool("check_step_done", { step: "morning medication" });
      }
      const match = check.matches?.[0];
      if (!match) {
        await say("Alexa+", "I couldn't find a medication step in your routines.");
      } else if (match.done) {
        await say("Alexa+", `Yes, you took it at ${match.completed_at.slice(11, 16)}, so there's no need to take another one today.`);
      } else {
        await say("Alexa+", `Not yet. It was due at ${match.expected_time}. Would you like to take it now?`);
      }
    },
  },
  {
    label: "A missed step",
    async run() {
      const all = await routinesOrStop();
      const morning = findRoutine(all, "Morning Routine") || all[0];
      // A throwaway step scheduled 20 minutes ago with a 5-minute window, added with a real
      // add_step call, so there is always something overdue whatever time this runs.
      const past = new Date(serverNow().getTime() - 20 * 60000);
      const added = await callTool("add_step", {
        routine_id: morning.id, title: "Take out recycling", expected_time: hhmm(past), window_minutes: 5,
        description: "(demo-only step, added a few minutes in the past so it's overdue now)",
      });
      const missed = await callTool("get_missed_steps", { routine_id: morning.id });
      const step = (missed || []).find(m => m.id === added.step_id);
      if (!step) {
        aside("(unexpected: the demo step wasn't flagged as missed)");
        return;
      }
      await say("Alexa+", `${PERSON}, it looks like '${step.title}' got missed earlier. Want me to push it back half an hour?`);
      await say(PERSON, "Oh, I forgot. Yes, please.");
      const snoozed = await callTool("snooze_step", { step_id: step.id, minutes: 30 });
      await say("Alexa+", `Done. I'll remind you again at ${snoozed.new_expected_time}. No harm done.`);
    },
  },
  {
    label: "Priya checks in",
    async run() {
      await say(CAREGIVER, "Alexa, how is Mum's day going?");
      const summary = await callTool("get_daily_summary");
      for (const r of summary.routines) {
        let line = `${r.routine}: ${r.completed.length} done, ${r.missed.length} missed, ${r.pending.length} still to go.`;
        if (r.missed.length) line += ` Missed: ${r.missed.join(", ").toLowerCase()}.`;
        await say("Alexa+", line);
      }
    },
  },
  {
    label: "Adjust the schedule",
    async run() {
      await say(CAREGIVER, "Is there anything in her routine we should change?");
      const suggestions = await callTool("suggest_schedule_adjustments");
      if (!suggestions || !suggestions.length) {
        await say("Alexa+", "Nothing to change yet. I need a few more days of history before I suggest anything.");
        return;
      }
      const top = suggestions[0];
      await say("Alexa+", top.message);
      await say(CAREGIVER, "That makes sense. Go ahead.");
      await callTool("update_step_time", { step_id: top.step_id, expected_time: top.suggested_time });
      await say("Alexa+", `Done. '${top.title}' is now scheduled for ${top.suggested_time}.`);
    },
  },
  {
    label: "Set up physio by voice",
    async run() {
      const name = "Physio Exercises";
      await say(CAREGIVER, `Alexa, ${PERSON}'s physio gave her two exercises to do every day. Can you add them?`);
      await say("Alexa+", "Of course. What should I call the routine, and when should she do them?");
      await say(CAREGIVER, "Call it Physio Exercises. Leg stretches at half ten, balance practice at four.");
      const all = await callTool("list_routines");
      if (findRoutine(all, name)) {
        await say("Alexa+", `${PERSON} already has a '${name}' routine, so I've left it as it is.`);
        aside("(Reseed with seed_data.py --reset --history for a clean take.)");
        return;
      }
      const created = await callTool("add_routine", { name, description: "Daily exercises from the physiotherapist." });
      const steps = [
        { title: "Leg stretches", expected_time: "10:30", window_minutes: 60,
          description: "Three slow stretches per leg, holding the kitchen counter." },
        { title: "Balance practice", expected_time: "16:00", window_minutes: 60,
          description: "Stand on one foot for ten seconds each side, next to a chair." },
      ];
      const added = [];
      for (const step of steps) added.push(await callTool("add_step", { routine_id: created.routine_id, ...step }));
      const schedule = added.map(a => `${a.title.toLowerCase()} at ${a.expected_time}`).join(" and ");
      await say("Alexa+", `All set. I'll remind ${PERSON} about ${schedule}, and let you know if one gets missed.`);
      await say(CAREGIVER, "Perfect, thank you.");
    },
  },
];

// ---- Controls ----------------------------------------------------------------------------
let running = false;

function setRunning(value) {
  running = value;
  document.querySelectorAll(".controls button").forEach(b => { if (b.id !== "save-key") b.disabled = value; });
}

function showError(err) {
  if (err instanceof AuthError) {
    setConn("err", "API key needed");
    $("key-row").classList.add("show");
    $("api-key").focus();
    aside("The server asked for an API key. Enter it below, then try again.");
  } else if (err.message !== "no routines") {
    setConn("err", "Error");
    aside("Something went wrong: " + err.message);
  }
}

async function run(beats) {
  if (running) return;
  setRunning(true);
  try {
    for (const beat of beats) {
      beatTitle(beat.label);
      await beat.run();
    }
  } catch (err) {
    showError(err);
  } finally {
    setRunning(false);
    $("ring").classList.remove("listening");
  }
}

// ---- Live chat ---------------------------------------------------------------------------
// The conversation lives here and is sent whole each turn; the server keeps no chat state.
const chatHistory = [];
const CHAT_IDEAS = [
  [PERSON, "What should I do now?"],
  [PERSON, "Did I take my pill?"],
  [PERSON, "I've just taken my morning tablet."],
  [CAREGIVER, "How is Mum's day going?"],
  [CAREGIVER, "Should anything in her routine change?"],
];

async function sendChat(text) {
  text = text.trim();
  if (running || !text || !CONFIG.chatModel) return;
  const speaker = $("speaker").value;
  setRunning(true);
  $("chat-input").value = "";
  addLine(speaker, text);
  chatHistory.push({ role: "user", content: `${speaker}: ${text}` });
  const typing = document.createElement("div");
  typing.className = "line typing";
  typing.textContent = "...";
  addToScreen(typing);
  $("ring").classList.add("listening");
  try {
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["Authorization"] = "Bearer " + apiKey;
    const res = await fetch(CONFIG.chatPath, { method: "POST", headers, body: JSON.stringify({ messages: chatHistory }) });
    if (res.status === 401) throw new AuthError("Missing or invalid API key");
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    for (const call of data.tool_calls) {
      finishCall(logCall(call.name, call.arguments || {}), call.result, call.ms, call.error);
    }
    chatHistory.push({ role: "assistant", content: data.reply });
    typing.remove();
    await say("Alexa+", data.reply, false);
  } catch (err) {
    chatHistory.pop();  // not answered, so don't send it again as if it had been
    typing.remove();
    showError(err);
  } finally {
    setRunning(false);
    $("ring").classList.remove("listening");
    $("chat-input").focus();
  }
}

function setMode(next) {
  mode = next;
  document.querySelectorAll("[data-mode]").forEach(t => t.setAttribute("aria-selected", String(t.dataset.mode === mode)));
  $("scripted-controls").hidden = mode !== "scripted";
  $("chat-controls").hidden = mode !== "chat";
  $("notice-scripted").hidden = mode !== "scripted";
  $("notice-chat").hidden = mode !== "chat" || !CONFIG.chatModel;
  if (mode === "chat" && CONFIG.chatModel) $("chat-input").focus();
}

for (const beat of BEATS) {
  const button = document.createElement("button");
  button.textContent = beat.label;
  button.addEventListener("click", () => run([beat]));
  $("beats").append(button);
}
$("play-all").addEventListener("click", () => run(BEATS));
document.querySelectorAll("[data-mode]").forEach(tab => tab.addEventListener("click", () => setMode(tab.dataset.mode)));
$("chat-form").addEventListener("submit", event => { event.preventDefault(); sendChat($("chat-input").value); });
$("clear-chat").addEventListener("click", () => {
  chatHistory.length = 0;
  $("screen").replaceChildren();
});
for (const [speaker, text] of CHAT_IDEAS) {
  const button = document.createElement("button");
  button.textContent = `${speaker}: "${text}"`;
  button.addEventListener("click", () => { $("speaker").value = speaker; sendChat(text); });
  $("chat-ideas").append(button);
}
if (CONFIG.chatModel) {
  $("chat-model").textContent = CONFIG.chatModel;
  $("chat-via").textContent = CONFIG.chatMcpUrl
    ? `OpenAI connects to this server's MCP endpoint (${CONFIG.chatMcpUrl}) itself, the way Alexa+ would.`
    : "This server isn't public, so OpenAI can't reach its MCP endpoint; the server runs the tool calls the model asks for.";
} else {
  $("chat-off").hidden = false;
  $("chat-form").hidden = $("chat-ideas").hidden = true;
}
// Speech input where the browser has it (Chrome, Edge): one utterance, then send.
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (Recognition && CONFIG.chatModel) {
  const mic = $("mic");
  mic.hidden = false;
  mic.addEventListener("click", () => {
    const recognition = new Recognition();
    recognition.lang = "en-GB";
    recognition.onstart = () => { mic.classList.add("recording"); mic.textContent = "Listening..."; };
    recognition.onend = () => { mic.classList.remove("recording"); mic.textContent = "Mic"; };
    recognition.onresult = event => sendChat(event.results[0][0].transcript);
    recognition.start();
  });
}
$("clear").addEventListener("click", () => {
  $("screen").replaceChildren();
  $("log").replaceChildren();
});
$("save-key").addEventListener("click", async () => {
  apiKey = $("api-key").value.trim();
  storageSet("dailyanchor.apiKey", apiKey);
  try {
    await connect();
    $("key-row").classList.remove("show");
  } catch (err) {
    setConn("err", err instanceof AuthError ? "That key didn't work" : "Couldn't connect");
  }
});
if (!("speechSynthesis" in window)) {
  $("speak").closest("label").hidden = true;
  $("speak-chat").closest("label").hidden = true;
}

document.querySelectorAll("[data-panel]").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll("[data-panel]").forEach(t => t.setAttribute("aria-selected", String(t === tab)));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === tab.dataset.panel));
  if (tab.dataset.panel === "dash-panel" && !$("dashboard").src) $("dashboard").src = CONFIG.dashboardPath;
}));

$("mcp-url").textContent = new URL(CONFIG.mcpPath, location.href).href;
connect().catch(err => {
  if (err instanceof AuthError) {
    setConn("err", "API key needed");
    $("key-row").classList.add("show");
  } else {
    setConn("err", "Couldn't connect: " + err.message);
  }
});
</script>
</body>
</html>
"""
