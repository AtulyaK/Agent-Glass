"""
Frontend service — serves the Agent Glass real-time monitoring dashboard.

The dashboard:
- Fetches sessions from trace-gateway via the browser (localhost:8002)
- Streams live events via SSE from trace-gateway /stream
- Polls critic decisions for each session (localhost:8003)
- Shows green/yellow/red flag indicators per session
- Shows expandable event+decision timelines
"""
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

TRACE_GATEWAY_EXT = os.getenv("TRACE_GATEWAY_EXT_URL", "http://localhost:8002")
CRITIC_EXT = os.getenv("CRITIC_EXT_URL", "http://localhost:8003")

app = FastAPI(title="Agent Glass Dashboard", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "frontend"}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE.replace("__TRACE_URL__", TRACE_GATEWAY_EXT).replace("__CRITIC_URL__", CRITIC_EXT)


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Agent Glass — Observability Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  :root{
    --bg:#0d0f14;--surface:#13161e;--surface2:#1a1e28;--surface3:#212536;
    --border:#2a2e3f;--border2:#363b52;
    --text:#e2e8f0;--text2:#94a3b8;--text3:#64748b;
    --green:#22c55e;--green-dim:#16a34a22;
    --yellow:#f59e0b;--yellow-dim:#d9770622;
    --red:#ef4444;--red-dim:#dc262622;
    --blue:#3b82f6;--blue-dim:#2563eb22;
    --glow-green:0 0 12px #22c55e55;
    --glow-yellow:0 0 12px #f59e0b55;
    --glow-red:0 0 12px #ef444455;
    --radius:10px;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh;overflow-x:hidden}

  /* ── Header ── */
  header{
    display:flex;align-items:center;gap:14px;
    padding:18px 28px;
    background:var(--surface);
    border-bottom:1px solid var(--border);
    position:sticky;top:0;z-index:100;
    backdrop-filter:blur(12px);
  }
  .logo{
    width:38px;height:38px;border-radius:10px;
    background:linear-gradient(135deg,#3b82f6,#8b5cf6);
    display:flex;align-items:center;justify-content:center;
    font-size:18px;font-weight:700;color:#fff;
    box-shadow:0 0 16px #3b82f655;
  }
  .brand{font-size:18px;font-weight:700;letter-spacing:-0.3px}
  .brand span{color:var(--blue)}
  .status-pill{
    margin-left:auto;display:flex;align-items:center;gap:7px;
    background:var(--surface2);border:1px solid var(--border);
    padding:5px 12px;border-radius:20px;font-size:12px;color:var(--text2);
  }
  .pulse{
    width:8px;height:8px;border-radius:50%;background:var(--green);
    animation:pulse 2s infinite;
  }
  @keyframes pulse{0%,100%{opacity:1;box-shadow:var(--glow-green)}50%{opacity:.5;box-shadow:none}}

  /* ── Layout ── */
  .layout{display:grid;grid-template-columns:340px 1fr;height:calc(100vh - 65px)}

  /* ── Left panel ── */
  .left-panel{
    background:var(--surface);border-right:1px solid var(--border);
    display:flex;flex-direction:column;overflow:hidden;
  }
  .panel-header{
    padding:16px 18px;border-bottom:1px solid var(--border);
    display:flex;align-items:center;justify-content:space-between;
  }
  .panel-header-actions{display:flex;align-items:center;gap:8px;}
  .panel-title{font-size:13px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.8px}
  .badge{
    background:var(--surface2);border:1px solid var(--border);
    padding:2px 8px;border-radius:10px;font-size:11px;color:var(--text3);
    font-variant-numeric:tabular-nums;
  }
  .sessions-list{flex:1;overflow-y:auto;padding:10px 0}
  .sessions-list::-webkit-scrollbar{width:4px}
  .sessions-list::-webkit-scrollbar-track{background:transparent}
  .sessions-list::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px}

  .session-card{
    margin:4px 10px;padding:14px;
    border-radius:var(--radius);border:1px solid var(--border);
    cursor:pointer;transition:all 0.18s ease;
    background:var(--surface2);
    position:relative;overflow:hidden;
  }
  .session-card::before{
    content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
    border-radius:3px 0 0 3px;background:var(--border2);transition:all 0.18s;
  }
  .session-card.flag-green::before{background:var(--green);box-shadow:var(--glow-green)}
  .session-card.flag-yellow::before{background:var(--yellow);box-shadow:var(--glow-yellow)}
  .session-card.flag-red::before{background:var(--red);box-shadow:var(--glow-red)}
  .session-card.active,
  .session-card:hover{background:var(--surface3);border-color:var(--border2)}
  .session-card.active{border-color:var(--blue)}

  .session-id{
    font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:500;
    color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  }
  .session-meta{
    display:flex;align-items:center;gap:8px;margin-top:7px;flex-wrap:wrap;
  }
  .flag-chip{
    display:inline-flex;align-items:center;gap:4px;
    padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;
  }
  .chip-green{background:var(--green-dim);color:var(--green);border:1px solid #22c55e33}
  .chip-yellow{background:var(--yellow-dim);color:var(--yellow);border:1px solid #f59e0b33}
  .chip-red{background:var(--red-dim);color:var(--red);border:1px solid #ef444433}
  .chip-grey{background:var(--surface);color:var(--text3);border:1px solid var(--border)}
  .events-count{font-size:11px;color:var(--text3)}

  .empty-state{
    padding:40px 20px;text-align:center;color:var(--text3);font-size:13px;line-height:1.6;
  }
  .empty-state .icon{font-size:32px;margin-bottom:10px;opacity:.5}

  /* ── Right panel ── */
  .right-panel{display:flex;flex-direction:column;overflow:hidden}
  .right-header{
    padding:18px 24px;border-bottom:1px solid var(--border);
    display:flex;align-items:flex-start;gap:14px;
    background:var(--surface);
  }
  .right-header-info{flex:1}
  .session-full-id{
    font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:500;color:var(--text);
    word-break:break-all;
  }
  .session-stats{display:flex;gap:12px;margin-top:8px;flex-wrap:wrap}
  .stat{font-size:12px;color:var(--text2)}
  .stat strong{color:var(--text)}

  /* Live feed */
  .feed{flex:1;overflow-y:auto;padding:16px 24px;display:flex;flex-direction:column;gap:12px}
  .feed::-webkit-scrollbar{width:4px}
  .feed::-webkit-scrollbar-track{background:transparent}
  .feed::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px}

  .event-row{
    background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
    overflow:hidden;transition:border-color 0.15s;
  }
  .event-row:hover{border-color:var(--border2)}
  .event-header{
    display:flex;align-items:center;gap:10px;padding:12px 16px;cursor:pointer;
  }
  .event-type-badge{
    padding:3px 9px;border-radius:8px;font-size:11px;font-weight:600;font-family:'JetBrains Mono',monospace;
    background:var(--blue-dim);color:var(--blue);border:1px solid #3b82f633;
  }
  .event-node{font-size:12px;color:var(--text2)}
  .event-time{margin-left:auto;font-size:11px;color:var(--text3);font-family:'JetBrains Mono',monospace}
  .chevron{color:var(--text3);font-size:12px;transition:transform 0.2s;margin-left:4px}
  .chevron.open{transform:rotate(90deg)}
  .event-body{
    padding:0 16px;max-height:0;overflow:hidden;transition:max-height 0.25s ease,padding 0.25s;
    font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text2);line-height:1.5;
  }
  .event-body.open{max-height:600px;padding:0 16px 14px}
  pre{white-space:pre-wrap;word-break:break-word;background:var(--surface2);
      border:1px solid var(--border);border-radius:6px;padding:10px;margin-top:8px}

  /* Critic panel */
  .critic-panel{
    width:300px;background:var(--surface);border-left:1px solid var(--border);
    padding:18px;overflow-y:auto;flex-shrink:0;display:flex;flex-direction:column;gap:14px;
  }
  .critic-panel::-webkit-scrollbar{width:4px}
  .critic-panel::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px}
  .critic-title{font-size:12px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:2px}
  .decision-card{
    background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);
    padding:14px;transition:border-color 0.15s;
  }
  .decision-card.flag-green{border-color:#22c55e33;background:var(--green-dim)}
  .decision-card.flag-yellow{border-color:#f59e0b33;background:var(--yellow-dim)}
  .decision-card.flag-red{border-color:#ef444433;background:var(--red-dim)}
  .decision-header{display:flex;align-items:center;gap:8px;margin-bottom:8px}
  .decision-turn{font-size:11px;color:var(--text3)}
  .halt-badge{
    margin-left:auto;font-size:10px;font-weight:700;padding:2px 7px;
    border-radius:8px;background:#ef444430;color:var(--red);border:1px solid #ef444444;
  }
  .rationale{font-size:12px;color:var(--text2);line-height:1.55}
  .threat-tag{
    display:inline-block;margin-top:7px;
    font-size:10px;font-weight:600;padding:2px 8px;border-radius:8px;
    font-family:'JetBrains Mono',monospace;
  }

  /* Live feed indicator */
  .live-bar{
    display:flex;align-items:center;gap:8px;padding:9px 24px;
    background:var(--surface2);border-bottom:1px solid var(--border);
    font-size:12px;color:var(--text2);
  }
  .live-dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
  .content-area{display:flex;flex:1;overflow:hidden}

  /* Feedback modal */
  .modal-overlay{
    display:none;position:fixed;inset:0;background:#00000099;backdrop-filter:blur(4px);z-index:200;
    align-items:center;justify-content:center;
  }
  .modal-overlay.open{display:flex}
  .modal{
    background:var(--surface);border:1px solid var(--border2);border-radius:14px;
    padding:28px;width:480px;max-width:95vw;
  }
  .modal h3{font-size:16px;font-weight:600;margin-bottom:14px}
  .modal textarea{
    width:100%;height:100px;background:var(--surface2);border:1px solid var(--border2);
    border-radius:8px;color:var(--text);font-family:'Inter',sans-serif;font-size:13px;
    padding:10px;resize:vertical;
  }
  .modal-actions{display:flex;gap:10px;margin-top:14px;justify-content:flex-end}
  .btn{
    padding:8px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;
    border:none;transition:all 0.15s;
  }
  .btn-primary{background:var(--blue);color:#fff}
  .btn-primary:hover{background:#2563eb}
  .btn-ghost{background:var(--surface2);color:var(--text2);border:1px solid var(--border2)}
  .btn-ghost:hover{background:var(--surface3)}
  .feedback-btn{
    margin-left:auto;padding:6px 14px;border-radius:8px;
    background:var(--surface2);border:1px solid var(--border);
    color:var(--text2);font-size:12px;cursor:pointer;transition:all 0.15s;
  }
  .feedback-btn:hover{background:var(--surface3);border-color:var(--border2)}

  /* Welcome screen */
  .welcome{
    flex:1;display:flex;align-items:center;justify-content:center;
    flex-direction:column;gap:16px;color:var(--text3);font-size:14px;
  }
  .welcome .big-icon{font-size:48px;opacity:.3}
  
  /* UMAP View styling */
  .umap-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:var(--surface);z-index:10;color:var(--text2);font-size:14px}
</style>
</head>
<body>
<header>
  <div class="logo">🔭</div>
  <div>
    <div class="brand">Agent <span>Glass</span></div>
  </div>
  <div class="status-pill">
    <div class="pulse"></div>
    <span id="status-text">Connecting…</span>
  </div>
</header>

<div class="layout">
  <!-- Left: sessions list -->
  <div class="left-panel">
    <div class="panel-header">
      <span class="panel-title">Sessions</span>
      <div class="panel-header-actions">
        <span class="badge" id="session-count">0</span>
        <button class="btn btn-ghost" style="padding:2px 8px;font-size:11px" onclick="showUmap()">🌌 UMAP 3D</button>
      </div>
    </div>
    <div class="sessions-list" id="sessions-list">
      <div class="empty-state">
        <div class="icon">📭</div>
        <div>No sessions yet.<br>Run <code>POST /plan</code> to start one.</div>
      </div>
    </div>
  </div>

  <!-- Right: detail view -->
  <div class="right-panel">
    <div id="welcome" class="welcome">
      <div class="big-icon">🔭</div>
      <div>Select a session to view its trace and critic decisions.</div>
    </div>
    <div id="detail-view" style="display:none;flex:1;flex-direction:column;overflow:hidden;display:flex">
      <div class="right-header" id="right-header">
        <div class="right-header-info" style="flex:1">
          <div class="session-full-id" id="detail-session-id">—</div>
          <div class="session-stats" id="detail-stats"></div>
        </div>
        <button class="feedback-btn" onclick="openFeedback()">💬 Human Feedback</button>
      </div>
      <div class="live-bar">
        <div class="live-dot"></div>
        <span>Live event stream</span>
        <span id="event-count-label" style="margin-left:auto;color:var(--text3)"></span>
      </div>
      <div class="content-area">
        <div class="feed" id="events-feed"></div>
        <div class="critic-panel" id="critic-panel">
          <div class="critic-title">Critic Decisions</div>
          <div id="decisions-list" style="display:flex;flex-direction:column;gap:10px"></div>
        </div>
      </div>
    </div>
    <div id="umap-view" style="display:none;flex:1;flex-direction:column;position:relative">
      <div class="right-header">
        <div class="right-header-info">
          <div class="session-full-id">🌌 Vector Embedding Space (UMAP 3D)</div>
        </div>
        <button class="btn btn-ghost" onclick="loadUmap()">🔄 Refresh</button>
      </div>
      <div id="umap-loading" class="umap-loading" style="display:none">Computing 3D Projection...</div>
      <div id="umap-plot" style="flex:1;width:100%"></div>
    </div>
  </div>
</div>

<!-- Feedback modal -->
<div class="modal-overlay" id="feedback-modal">
  <div class="modal">
    <h3>💬 Human Operator Feedback</h3>
    <p style="font-size:13px;color:var(--text2);margin-bottom:12px">Your note will be injected into the next critic call for this session.</p>
    <textarea id="feedback-text" placeholder="e.g. The file_reader tool is unavailable — use api_caller instead."></textarea>
    <div class="modal-actions">
      <button class="btn btn-ghost" onclick="closeFeedback()">Cancel</button>
      <button class="btn btn-primary" onclick="submitFeedback()">Submit Feedback</button>
    </div>
  </div>
</div>

<script>
const TRACE_URL = '__TRACE_URL__';
const CRITIC_URL = '__CRITIC_URL__';
let activeSession = null;
let eventSseSource = null;
let lastEventId = 0;
const sessionFlags = {};  // session_id → latest flag
const sessionEventCounts = {};
const renderedEventIds = new Set();

// ── Helpers ──────────────────────────────────────────────────────────────────
function flagChip(flag, decision) {
  const cls = {green:'chip-green',yellow:'chip-yellow',red:'chip-red'}[flag] || 'chip-grey';
  const icon = {green:'✅',yellow:'⚠️',red:'🛑'}[flag] || '⬜';
  return `<span class="flag-chip ${cls}">${icon} ${decision||flag}</span>`;
}
function threatTag(tc) {
  if (!tc || tc==='none') return '';
  const colours = {malicious:'#ef4444',roadblock:'#f59e0b',loop:'#8b5cf6'};
  const c = colours[tc]||'#64748b';
  return `<span class="threat-tag" style="background:${c}22;color:${c};border:1px solid ${c}44">${tc}</span>`;
}
function timeAgo(ts) {
  if (!ts) return '';
  const d = new Date(ts), now = new Date();
  const s = Math.round((now - d) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  return d.toLocaleTimeString();
}

// ── Sessions ─────────────────────────────────────────────────────────────────
async function refreshSessions() {
  try {
    const r = await fetch(`${TRACE_URL}/sessions?limit=50`);
    const data = await r.json();
    renderSessions(data.sessions || []);
    document.getElementById('status-text').textContent = 'Live';
  } catch(e) {
    document.getElementById('status-text').textContent = 'Disconnected';
  }
}

function renderSessions(sessions) {
  const list = document.getElementById('sessions-list');
  document.getElementById('session-count').textContent = sessions.length;
  if (!sessions.length) {
    list.innerHTML = `<div class="empty-state"><div class="icon">📭</div><div>No sessions yet.<br>Run <code>POST /plan</code> to start one.</div></div>`;
    return;
  }
  list.innerHTML = sessions.map(s => {
    const flag = sessionFlags[s.session_id] || 'grey';
    const flagClass = {green:'flag-green',yellow:'flag-yellow',red:'flag-red'}[flag] || '';
    const activeClass = s.session_id === activeSession ? 'active' : '';
    return `
      <div class="session-card ${flagClass} ${activeClass}" onclick="selectSession('${s.session_id}')">
        <div class="session-id">${s.session_id}</div>
        <div class="session-meta">
          ${flagChip(flag, flag)}
          <span class="events-count">📊 ${s.event_count} events</span>
          <span class="events-count">${timeAgo(s.last_event)}</span>
        </div>
      </div>`;
  }).join('');
}

// ── Session Detail ────────────────────────────────────────────────────────────
async function selectSession(sid) {
  activeSession = sid;
  document.getElementById('welcome').style.display = 'none';
  document.getElementById('umap-view').style.display = 'none';
  document.getElementById('detail-view').style.display = 'flex';
  document.getElementById('detail-session-id').textContent = sid;
  document.getElementById('events-feed').innerHTML = '';
  document.getElementById('decisions-list').innerHTML = '';
  renderedEventIds.clear();
  lastEventId = 0;

  await loadEvents(sid);
  await loadDecisions(sid);
  refreshSessions();
}

async function loadEvents(sid) {
  try {
    const r = await fetch(`${TRACE_URL}/events/${sid}?limit=100`);
    const data = await r.json();
    const events = (data.events || []).reverse();
    events.forEach(e => renderEvent(e));
    const cnt = events.length;
    document.getElementById('event-count-label').textContent = `${cnt} event${cnt!==1?'s':''}`;
  } catch(e) {}
}

function renderEvent(ev) {
  if (renderedEventIds.has(ev.id)) return;
  renderedEventIds.add(ev.id);
  if (ev.id > lastEventId) lastEventId = ev.id;
  const feed = document.getElementById('events-feed');
  const div = document.createElement('div');
  div.className = 'event-row';
  div.id = `ev-${ev.id}`;
  const payloadStr = JSON.stringify(ev.payload, null, 2);
  div.innerHTML = `
    <div class="event-header" onclick="toggleEvent(${ev.id})">
      <span class="event-type-badge">${ev.event_type||'unknown'}</span>
      <span class="event-node">${ev.node||''}</span>
      <span class="event-time">${timeAgo(ev.timestamp)}</span>
      <span class="chevron" id="chev-${ev.id}">▶</span>
    </div>
    <div class="event-body" id="body-${ev.id}">
      <pre>${escHtml(payloadStr)}</pre>
    </div>`;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

function toggleEvent(id) {
  const body = document.getElementById(`body-${id}`);
  const chev = document.getElementById(`chev-${id}`);
  const open = body.classList.toggle('open');
  chev.classList.toggle('open', open);
}

async function loadDecisions(sid) {
  try {
    const r = await fetch(`${CRITIC_URL}/decisions/${sid}?limit=20`);
    const data = await r.json();
    const items = (data.items || []).reverse();
    const list = document.getElementById('decisions-list');
    list.innerHTML = '';
    items.forEach(d => {
      sessionFlags[sid] = d.flag;  // use latest
      const div = document.createElement('div');
      div.className = `decision-card flag-${d.flag}`;
      div.innerHTML = `
        <div class="decision-header">
          <span class="decision-turn">Turn ${d.turn}</span>
          ${flagChip(d.flag, d.decision)}
          ${d.halt ? '<span class="halt-badge">HALT</span>' : ''}
        </div>
        <div class="rationale">${escHtml((d.rationale||'').substring(0,300))}</div>
        ${threatTag(d.threat_class)}`;
      list.appendChild(div);
    });
    refreshSessions();
  } catch(e) {}
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── SSE Listener (global — picks up events across all sessions) ───────────────
function startSSE() {
  if (eventSseSource) eventSseSource.close();
  try {
    eventSseSource = new EventSource(`${TRACE_URL}/stream`);
    eventSseSource.addEventListener('trace', async (e) => {
      const ev = JSON.parse(e.data);
      sessionEventCounts[ev.session_id] = (sessionEventCounts[ev.session_id]||0)+1;
      if (ev.session_id === activeSession) {
        renderEvent(ev);
        const cnt = renderedEventIds.size;
        document.getElementById('event-count-label').textContent = `${cnt} event${cnt!==1?'s':''}`;
        await loadDecisions(ev.session_id);
      }
      refreshSessions();
    });
    eventSseSource.addEventListener('connected', () => {
      document.getElementById('status-text').textContent = 'Live';
    });
    eventSseSource.onerror = () => {
      document.getElementById('status-text').textContent = 'Reconnecting…';
      setTimeout(startSSE, 5000);
    };
  } catch(e) { setTimeout(startSSE, 5000); }
}

// ── Human Feedback ────────────────────────────────────────────────────────────
function openFeedback() {
  if (!activeSession) return;
  document.getElementById('feedback-modal').classList.add('open');
  document.getElementById('feedback-text').focus();
}
function closeFeedback() {
  document.getElementById('feedback-modal').classList.remove('open');
}
async function submitFeedback() {
  const note = document.getElementById('feedback-text').value.trim();
  if (!note) return;
  try {
    await fetch(`${CRITIC_URL}/feedback`, {
      method:'POST',
      headers:{'content-type':'application/json'},
      body: JSON.stringify({session_id: activeSession, turn: 99, human_note: note}),
    });
    closeFeedback();
    document.getElementById('feedback-text').value = '';
    alert('Feedback stored ✅ It will be injected on the next critic call for this session.');
  } catch(e) { alert('Failed to store feedback: '+e); }
}

// ── UMAP Visualization ─────────────────────────────────────────────────────────
function showUmap() {
  document.getElementById('welcome').style.display = 'none';
  document.getElementById('detail-view').style.display = 'none';
  document.getElementById('umap-view').style.display = 'flex';
  activeSession = null;
  loadUmap();
}

async function loadUmap() {
  document.getElementById('umap-loading').style.display = 'flex';
  try {
    const r = await fetch(`${TRACE_URL}/visualization/umap`);
    const data = await r.json();
    const points = data.points || [];
    
    if (points.length < 3) {
      document.getElementById('umap-plot').innerHTML = '<div class="empty-state">Not enough traces with embeddings yet.</div>';
      return;
    }

    const threatColors = {
      'malicious': '#ef4444',
      'roadblock': '#f59e0b',
      'loop': '#8b5cf6',
      'none': '#22c55e',
      'unknown': '#94a3b8'
    };

    // Group by threat_class to create traces
    const traces = {};
    points.forEach(p => {
      const t = p.threat_class || 'unknown';
      if (!traces[t]) {
        traces[t] = {
          x: [], y: [], z: [],
          text: [],
          mode: 'markers',
          type: 'scatter3d',
          name: t,
          marker: { size: 5, color: threatColors[t] || threatColors['unknown'], opacity: 0.8 }
        };
      }
      traces[t].x.push(p.x);
      traces[t].y.push(p.y);
      traces[t].z.push(p.z);
      traces[t].text.push(`Turn: ${p.turn}<br>Preview: ${JSON.stringify(p.payload).substring(0, 50)}...`);
    });

    const layout = {
      margin: { l: 0, r: 0, b: 0, t: 0 },
      paper_bgcolor: '#13161e',
      plot_bgcolor: '#13161e',
      scene: {
        xaxis: { title: 'UMAP 1', showbackground: false, color:'#64748b' },
        yaxis: { title: 'UMAP 2', showbackground: false, color:'#64748b' },
        zaxis: { title: 'UMAP 3', showbackground: false, color:'#64748b' },
      },
      legend: { font: { color: '#e2e8f0' } }
    };

    document.getElementById('umap-loading').style.display = 'none';
    Plotly.newPlot('umap-plot', Object.values(traces), layout, {responsive: true});
  } catch(e) {
    document.getElementById('umap-plot').innerHTML = `<div class="empty-state">Failed to load UMAP: ${e}</div>`;
  } finally {
    document.getElementById('umap-loading').style.display = 'none';
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────
startSSE();
refreshSessions();
setInterval(refreshSessions, 10000);
</script>
</body>
</html>"""
