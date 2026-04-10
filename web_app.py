"""
Activity Tracker – Webb-gränssnitt (periodbaserat)
"""

import re
import sqlite3
import threading
import csv
import io
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, Response

VERSION    = "v0.11b"
DB_PATH    = Path.home() / "activity_tracker" / "activity.db"
CONFIG_PATH = Path.home() / "activity_tracker" / "app_config.json"
app = Flask(__name__)


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_feedback (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at  TEXT NOT NULL,
        question    TEXT,
        answer      TEXT,
        provider    TEXT,
        model       TEXT,
        vote        INTEGER NOT NULL
    )""")
    conn.commit()
    return conn


HTML = r"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Activity Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@400;600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ── Dark theme (default) ── */
:root {
  --bg:      #0d0f14;
  --surface: #141720;
  --border:  #1e2330;
  --accent:  #00e5ff;
  --accent2: #ff4d6d;
  --green:   #00ff9d;
  --muted:   #b0b8c8;
  --text:    #e8eaf0;
  --r:       8px;
  --font:    'Plus Jakarta Sans', sans-serif;
  --mono:    'JetBrains Mono', monospace;
  --grid-color: rgba(0,229,255,.03);
}

/* ── Light theme ── */
[data-theme="light"] {
  --bg:      #f4f5f7;
  --surface: #ffffff;
  --border:  #dde1e9;
  --accent:  #404E4F;
  --accent2: #ff4d6d;
  --green:   #2e9e6b;
  --muted:   #6b7280;
  --text:    #1a1f2e;
  --grid-color: rgba(64,78,79,.04);
}

/* ── Oaks theme ── */
[data-theme="oaks"] {
  --bg:      #2c3535;
  --surface: #354040;
  --border:  #404E4F;
  --accent:  #FFCC00;
  --accent2: #F9E9B4;
  --green:   #FFCC00;
  --muted:   #BFC8CE;
  --text:    #ffffff;
  --font:    'Plus Jakarta Sans', sans-serif;
  --mono:    'Plus Jakarta Sans', sans-serif;
  --grid-color: rgba(255,204,0,.03);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--font,'Syne',sans-serif);min-height:100vh;overflow-x:hidden;transition:background .2s,color .2s}
body::before{content:'';position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(var(--grid-color) 1px,transparent 1px),linear-gradient(90deg,var(--grid-color) 1px,transparent 1px);
  background-size:40px 40px;pointer-events:none}
.layout{display:flex;min-height:100vh;position:relative;z-index:1}

/* Sidebar */
.sidebar{width:220px;flex-shrink:0;background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;padding:24px 0;position:sticky;top:0;height:100vh;
  transition:width .2s ease;overflow:visible}
.sidebar.collapsed{width:0;padding:0;border-right:none;overflow:hidden}
.sidebar.collapsed .logo,.sidebar.collapsed .nav-item,.sidebar.collapsed .sidebar-footer{opacity:0;pointer-events:none}
.sidebar-inner{display:flex;flex-direction:column;height:100%;width:220px;overflow:hidden}
#sidebar-toggle{
  position:fixed;top:50%;left:220px;transform:translateY(-50%);
  width:16px;height:56px;background:var(--surface);border:1px solid var(--border);
  border-left:none;border-radius:0 8px 8px 0;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  font-size:10px;color:var(--muted);z-index:100;transition:left .2s,color .15s,border-color .15s;
}
#sidebar-toggle:hover{color:var(--accent);border-color:var(--accent);background:rgba(0,229,255,.06)}
.sidebar.collapsed ~ * #sidebar-toggle, body.sb-collapsed #sidebar-toggle{left:0}
.logo{padding:0 20px 28px;font-size:18px;font-weight:800;letter-spacing:-.5px;color:var(--accent);display:flex;align-items:center;gap:8px}
.logo span{color:var(--text)}
.nav-help{margin-left:auto;opacity:0;font-size:10px;font-weight:400;color:var(--muted);
  background:none;border:1px solid var(--border);border-radius:50%;width:16px;height:16px;
  display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;transition:opacity .15s}
.nav-item:hover .nav-help{opacity:1}
.nav-help:hover{color:var(--accent)!important;border-color:var(--accent)!important;opacity:1!important}
.help-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9100;
  align-items:center;justify-content:center}
.help-overlay.open{display:flex}
.help-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:32px 36px;max-width:480px;width:90%;box-shadow:0 20px 60px #000a;position:relative}
.help-box h3{font-size:16px;margin-bottom:12px;color:var(--accent)}
.help-box p{font-size:13px;color:var(--muted);line-height:1.7;margin-bottom:10px}
.help-box p:last-child{margin-bottom:0}
.help-box ul{font-size:13px;color:var(--muted);line-height:1.8;padding-left:18px}
.help-close{position:absolute;top:14px;right:16px;background:none;border:none;
  color:var(--muted);font-size:18px;cursor:pointer}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 20px;font-size:13px;font-weight:700;
  letter-spacing:.5px;text-transform:uppercase;cursor:pointer;transition:all .15s;
  border-left:3px solid transparent;color:var(--muted)}
.nav-item:hover{color:var(--text);background:rgba(255,255,255,.04)}
.nav-item.active{color:var(--accent);border-left-color:var(--accent);background:rgba(0,229,255,.06)}
.nav-icon{font-size:16px;width:20px;text-align:center}
.sidebar-footer{margin-top:auto;padding:20px;font-size:11px;color:var(--muted);font-family:var(--mono)}
.status-dot{display:inline-block;width:6px;height:6px;background:var(--green);border-radius:50%;margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* Main */
.main{flex:1;overflow:hidden;display:flex;flex-direction:column}
.page{display:none;height:100%;overflow-y:auto;padding:32px}
.page.active{display:flex;flex-direction:column}
h1{font-size:28px;font-weight:800;letter-spacing:-1px;margin-bottom:4px}
.subtitle{color:var(--muted);font-size:13px;margin-bottom:28px}

/* KPIs */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:32px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;position:relative;overflow:hidden}
.kpi::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent)}
.kpi.red::after{background:var(--accent2)}.kpi.green::after{background:var(--green)}
.kpi-label{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.kpi-value{font-size:32px;font-weight:800;font-family:var(--mono);color:var(--accent);line-height:1}
.kpi.red .kpi-value{color:var(--accent2)}.kpi.green .kpi-value{color:var(--green)}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:4px}

/* Filters */
.filters{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;align-items:center}
.sticky-filters{position:sticky;top:0;z-index:10;background:var(--bg);padding:12px 0;margin:0 0 20px;border-bottom:1px solid var(--border)}
.filters label{font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--muted)}
.filters input,.filters select{background:var(--surface);border:1px solid var(--border);border-radius:6px;
  padding:7px 12px;color:var(--text);font-family:var(--mono);font-size:12px;outline:none;transition:border-color .15s}
.filters input:focus,.filters select:focus{border-color:var(--accent)}
.btn{padding:7px 16px;border-radius:6px;border:none;cursor:pointer;font-family:var(--font);
  font-weight:700;font-size:12px;letter-spacing:.5px;text-transform:uppercase;transition:all .15s}
.btn-primary{background:var(--accent);color:#000}.btn-primary:hover{filter:brightness(1.1)}
.btn-ghost{background:var(--surface);color:var(--text);border:1px solid var(--border)}.btn-ghost:hover{border-color:var(--accent);color:var(--accent)}

/* Table */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:24px;max-height:70vh;overflow-y:auto}
table{width:100%;border-collapse:collapse}
thead th{background:var(--surface);padding:10px 14px;text-align:left;font-size:10px;font-weight:700;
  letter-spacing:1px;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);
  cursor:pointer;user-select:none;transition:color .15s;
  position:sticky;top:0;z-index:10}
thead th::after{content:'';position:absolute;left:0;right:0;bottom:0;border-bottom:1px solid var(--border)}
thead th:hover{color:var(--accent)}
tbody tr{border-bottom:1px solid var(--border);transition:background .1s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:rgba(255,255,255,.03)}
td{padding:9px 14px;font-size:13px}
td.mono{font-family:var(--mono);font-size:11px}
td.nowrap{white-space:nowrap}
td.title-cell{max-width:320px}
td.title-cell .title-text{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.badge-active{background:rgba(0,255,157,.15);color:var(--green)}
.badge-bg{background:rgba(90,96,112,.15);color:var(--muted)}

/* Länk-stil */
a.row-link{color:var(--accent);text-decoration:none;font-size:11px;opacity:.7;margin-left:6px;flex-shrink:0}
a.row-link:hover{opacity:1;text-decoration:underline}

/* Tooltip */
.has-tooltip{position:relative;cursor:default}
.has-tooltip .tip{
  display:none;position:fixed;z-index:1000;
  background:#1a1f2e;border:1px solid var(--border);border-radius:6px;
  padding:8px 12px;font-size:11px;font-family:var(--mono);
  color:var(--text);white-space:nowrap;max-width:600px;overflow:hidden;text-overflow:ellipsis;
  box-shadow:0 4px 20px rgba(0,0,0,.4);pointer-events:none;
}
.has-tooltip:hover .tip{display:block}

/* Duration bar */
.dur-bar{display:flex;align-items:center;gap:8px}
.dur-track{width:80px;height:6px;background:var(--border);border-radius:3px;overflow:hidden;flex-shrink:0}
.dur-fill{height:100%;border-radius:3px;background:var(--accent)}
.badge-bg .dur-fill{background:var(--muted)}

/* Bar chart */
.chart-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:24px}
.chart-title{font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--muted);margin-bottom:16px}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:12px}
.bar-label{width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;color:var(--muted);font-family:var(--mono)}
.bar-track{flex:1;height:22px;background:var(--border);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;background:var(--accent);transition:width .6s cubic-bezier(.16,1,.3,1);position:relative;display:flex;align-items:center;justify-content:flex-end;padding-right:6px}
.bar-fill span{font-size:10px;font-family:var(--mono);color:#000;font-weight:700;white-space:nowrap}

/* Timeline canvas */
.timeline-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px}
#timeline-canvas{width:100%;height:200px}

/* Pagination */
.pagination{display:flex;gap:8px;align-items:center;margin-top:16px;justify-content:flex-end}
.page-info{font-size:12px;color:var(--muted);font-family:var(--mono)}

/* Snabbval-knappar */
.quick-dates{display:flex;gap:6px}
.btn-quick{padding:5px 10px;border-radius:6px;border:1px solid var(--border);background:var(--surface);
  color:var(--muted);font-family:var(--mono);font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap}
.btn-quick:hover{border-color:var(--accent);color:var(--accent)}

/* Tema-knappar */
.theme-btn{width:28px;height:28px;border-radius:50%;border:2px solid var(--border);background:var(--surface);
  color:var(--muted);font-size:14px;cursor:pointer;transition:all .15s;display:flex;align-items:center;justify-content:center}
.theme-btn:hover{border-color:var(--accent);color:var(--accent)}
.theme-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(0,0,0,.1)}
.oaks-btn.active{border-color:#FFCC00;color:#FFCC00}

.loading{color:var(--muted);font-size:13px;padding:40px;text-align:center;font-family:var(--mono)}

/* AI-chat */
#page-ai{overflow:hidden;height:100vh;box-sizing:border-box}
.ai-top{flex-shrink:0}
.ai-settings{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:14px 18px;margin-bottom:12px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;flex-shrink:0}
.ai-settings label{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
.ai-provider-badge{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:4px;
  font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.ai-provider-badge.local{background:rgba(0,255,157,.12);color:var(--green)}
.ai-provider-badge.cloud{background:rgba(255,77,109,.12);color:var(--accent2)}
.ai-suggestions-wrap{flex-shrink:0;margin-bottom:10px}
.ai-suggestions-label{font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
  color:var(--muted);margin-bottom:6px;display:flex;align-items:center;justify-content:space-between}
.ai-suggestions{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.ai-suggestion{background:var(--surface);border:1px solid var(--border);border-radius:20px;
  padding:5px 13px;font-size:12px;cursor:pointer;color:var(--muted);transition:all .15s}
.ai-suggestion:hover{border-color:var(--accent);color:var(--accent)}
.ai-suggestion.recent{border-style:dashed}
.ai-layout{display:flex;flex-direction:column;flex:1;min-height:0;overflow:hidden}
.ai-messages{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:12px;
  padding:4px 2px;min-height:0}
.ai-msg{display:flex;flex-direction:column;gap:4px;max-width:90%}
.ai-msg.user{align-self:flex-end;align-items:flex-end}
.ai-msg.assistant{align-self:flex-start;align-items:flex-start}
.ai-bubble{padding:11px 16px;border-radius:12px;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-word}
.ai-msg.user .ai-bubble{background:var(--accent);color:#000;border-bottom-right-radius:3px}
.ai-msg.assistant .ai-bubble{background:var(--surface);border:1px solid var(--border);
  color:var(--text);border-bottom-left-radius:3px}
.ai-msg.assistant .ai-bubble.streaming::after{content:'▌';animation:blink .7s infinite;color:var(--accent)}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
.ai-role{font-size:10px;color:var(--muted);font-family:var(--mono);padding:0 4px}
.ai-feedback{display:flex;gap:6px;padding:2px 4px}
.ai-feedback button{background:none;border:1px solid var(--border);border-radius:20px;
  padding:2px 10px;font-size:14px;cursor:pointer;color:var(--muted);transition:all .15s}
.ai-feedback button:hover:not(:disabled){border-color:var(--accent);color:var(--text)}
.ai-feedback button:disabled{cursor:default}
.ai-feedback button.voted-up{border-color:#4caf50;color:#4caf50;opacity:1!important}
.ai-feedback button.voted-down{border-color:#e57373;color:#e57373;opacity:1!important}
.ai-input-row{display:flex;gap:10px;padding-top:12px;border-top:1px solid var(--border);margin-top:4px;flex-shrink:0}
.ai-input-row textarea{flex:1;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:10px 14px;color:var(--text);font-family:var(--font);font-size:13px;resize:none;
  outline:none;transition:border-color .15s;min-height:44px;max-height:160px;line-height:1.5}
.ai-input-row textarea:focus{border-color:var(--accent)}
.ai-input-row textarea:disabled{opacity:.5}
.ai-send{padding:10px 20px;white-space:nowrap;align-self:flex-end}

::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* Program-filter panel */
.prog-filter-btn{position:relative;display:inline-block}
.prog-filter-panel{position:absolute;top:calc(100% + 6px);left:0;z-index:300;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  min-width:240px;max-width:340px;box-shadow:0 8px 32px rgba(0,0,0,.5)}
.prog-filter-panel-head{padding:10px 14px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;gap:8px}
.prog-filter-panel-title{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
.prog-filter-list{max-height:300px;overflow-y:auto;padding:4px 0}
.prog-filter-item{display:flex;align-items:center;gap:8px;padding:5px 14px;
  font-size:12px;cursor:pointer;transition:background .1s;font-family:var(--mono)}
.prog-filter-item:hover{background:rgba(255,255,255,.04)}
.prog-filter-item input[type=checkbox]{accent-color:var(--accent);cursor:pointer;flex-shrink:0}
.prog-filter-badge{display:inline-block;background:var(--accent2);color:#fff;
  font-size:9px;font-weight:700;border-radius:3px;padding:1px 5px;margin-left:4px;vertical-align:middle}
</style>
</head>
<body>
<div class="layout">
<nav class="sidebar" id="sidebar">
  <div class="sidebar-inner">
    <div class="logo"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAABmUlEQVR4nO2aS5ICIQyGIeXB5AJ6o1nMjZwLkJtpuegqhqKbPIEuzcaFNPl+EkgTDeHkFi0nu97uz94Y/HuY+owjoD3FxNHQ1mJgBXjNvHE2uDYasBo81x+sBs/1CyvCc/xHa/j88zj8Pv3eTfdEtILvgWuF4I6IS1BaDd4D28Zvn0kQkdKiZvVL+BbIEWTvWWoUQAv/di5ZxfK5TEy/Fh+7EpcO3wDc3K8tMUWoBbTgZ4oATvrUOV2mzigR14pTlEItxxTnHgbUgUcnipWIJEglsHpl0J7nHCt5SRHgFp2RUQCxpwPnHACtmQqgVN3lBeyZlwgIJzfwmLR31J4iAqkA9jxiL24zD6oNQGljaN8YOZYJNafk/ZxNnAZEIQuumeDVNfYyrDhZKeQZhSy85LP3gIeIrOhQ/BNATSNLEZkB3+JTNbYkrRHps7izuOrOnLSxRR0vEiC5pXm2FpHbG/XskVr1RDfrbtqZLXYkHCrdY3RWgUOiX1IdGC0CGf7YYJ4phYKFYldir2igcN7P/KV+pf9KfC1MthcwXPwslV6UHwAAAABJRU5ErkJggg==" style="width:32px;height:32px;border-radius:6px" alt=""><div><span>Tracker</span><span id="app-version" style="display:block;font-size:10px;font-weight:400;color:var(--muted);margin-top:1px;letter-spacing:.5px"></span></div></div>
    <div class="nav-item active" data-page="dashboard" onclick="showPage(this)"><span class="nav-icon">⬡</span> Dashboard<button class="nav-help" onclick="event.stopPropagation();showHelp('dashboard')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="live" onclick="showPage(this)"><span class="nav-icon">●</span> Live<button class="nav-help" onclick="event.stopPropagation();showHelp('live')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="periods" onclick="showPage(this)"><span class="nav-icon">◷</span> Perioder<button class="nav-help" onclick="event.stopPropagation();showHelp('periods')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="apps" onclick="showPage(this)"><span class="nav-icon">◫</span> Program<button class="nav-help" onclick="event.stopPropagation();showHelp('apps')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="sessions" onclick="showPage(this)"><span class="nav-icon">≡</span> Sessioner<button class="nav-help" onclick="event.stopPropagation();showHelp('sessions')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="gantt" onclick="showPage(this)"><span class="nav-icon">▤</span> Tidslinje<button class="nav-help" onclick="event.stopPropagation();showHelp('gantt')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="ai" onclick="showPage(this)"><span class="nav-icon">◈</span> Maj-Britt<button class="nav-help" onclick="event.stopPropagation();showHelp('ai')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="feedback" onclick="showPage(this)"><span class="nav-icon">✉</span> Feedback<button class="nav-help" onclick="event.stopPropagation();showHelp('feedback')" title="Hjälp">?</button></div>
    <div class="sidebar-footer"><span class="status-dot"></span>Tracker aktiv</div>
  </div>
</nav>
<div id="sidebar-toggle" onclick="toggleSidebar()">◀</div>

<!-- Gantt canvas tooltip -->
<div id="gantt-tip" style="display:none;position:fixed;z-index:999;background:#1a1f2e;border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:11px;font-family:var(--mono);color:var(--text);pointer-events:none;max-width:400px;white-space:nowrap;box-shadow:0 4px 20px rgba(0,0,0,.5)"></div>

<!-- Theme switcher -->
<div id="theme-switcher" style="position:fixed;top:16px;right:20px;z-index:200;display:flex;gap:6px;align-items:center">
  <button class="theme-btn" data-theme="dark"  onclick="setTheme('dark')"  title="Dark">◑</button>
  <button class="theme-btn" data-theme="light" onclick="setTheme('light')" title="Light">○</button>
  <button class="theme-btn oaks-btn" data-theme="oaks"  onclick="setTheme('oaks')"  title="Oaks">⬡</button>
</div>

<main class="main" id="main-content">

  <!-- Dashboard -->
  <div id="page-dashboard" class="page active">
    <h1>Dashboard</h1><p class="subtitle">Aktivitetsöversikt</p>
    <div class="filters sticky-filters">
      <label>Från</label><input type="date" id="dash-from">
      <label>Till</label><input type="date" id="dash-to">
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('dash-from','dash-to','today',loadDashboard)">Idag</button>
        <button class="btn-quick" onclick="setQuick('dash-from','dash-to','yesterday',loadDashboard)">Igår</button>
        <button class="btn-quick" onclick="stepWeek('dash',-1,loadDashboard)">←</button>
        <button class="btn-quick" id="dash-week-btn" onclick="setQuick('dash-from','dash-to','week',loadDashboard)">V?</button>
        <button class="btn-quick" onclick="stepWeek('dash',1,loadDashboard)">→</button>
      </div>
      <button class="btn btn-primary" onclick="loadDashboard()">Uppdatera</button>
      <div class="prog-filter-btn">
        <button class="btn btn-ghost" onclick="openProgFilter('dashboard')">⊞ Program<span id="prog-filter-count-dashboard"></span></button>
        <div class="prog-filter-panel" id="prog-filter-dashboard" style="display:none">
          <div class="prog-filter-panel-head">
            <span class="prog-filter-panel-title">Visa program</span>
            <div style="display:flex;gap:6px">
              <button class="btn-quick" onclick="selectAllProgs('dashboard',true);event.stopPropagation()">Alla</button>
              <button class="btn-quick" onclick="selectAllProgs('dashboard',false);event.stopPropagation()">Inga</button>
            </div>
          </div>
          <div class="prog-filter-list" id="prog-filter-list-dashboard"></div>
        </div>
      </div>
    </div>
    <div class="kpi-grid" id="kpi-grid"><div class="loading">Laddar</div></div>
    <div class="chart-wrap">
      <div class="chart-title">Topp program – total aktiv tid</div>
      <div id="top-apps-chart"><div class="loading">Laddar</div></div>
    </div>
    <div class="timeline-wrap">
      <div class="chart-title">Aktiv tid per timme (idag)</div>
      <canvas id="timeline-canvas"></canvas>
    </div>
  </div>

  <!-- Live -->
  <div id="page-live" class="page">
    <h1>Live</h1><p class="subtitle">Vad som är öppet just nu – uppdateras var 5:e sekund</p>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <div id="live-updated" style="font-size:11px;color:var(--muted);font-family:var(--mono)"></div>
      <div class="prog-filter-btn">
        <button class="btn btn-ghost" onclick="openProgFilter('live')">⊞ Program<span id="prog-filter-count-live"></span></button>
        <div class="prog-filter-panel" id="prog-filter-live" style="display:none">
          <div class="prog-filter-panel-head">
            <span class="prog-filter-panel-title">Visa program</span>
            <div style="display:flex;gap:6px">
              <button class="btn-quick" onclick="selectAllProgs('live',true);event.stopPropagation()">Alla</button>
              <button class="btn-quick" onclick="selectAllProgs('live',false);event.stopPropagation()">Inga</button>
            </div>
          </div>
          <div class="prog-filter-list" id="prog-filter-list-live"></div>
        </div>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Program</th>
          <th>Fönsterrubrik</th>
          <th>Öppet sedan</th>
          <th>Pågående tid</th>
          <th>Status</th>
        </tr></thead>
        <tbody id="live-body"><tr><td colspan="5" class="loading">Laddar</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Perioder -->
  <div id="page-periods" class="page">
    <h1>Perioder</h1><p class="subtitle">Loggade aktivitetsperioder</p>
    <div class="filters">
      <label>Från</label><input type="date" id="per-from">
      <label>Till</label><input type="date" id="per-to">
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('per-from','per-to','today',()=>loadPeriods(1))">Idag</button>
        <button class="btn-quick" onclick="setQuick('per-from','per-to','yesterday',()=>loadPeriods(1))">Igår</button>
        <button class="btn-quick" onclick="stepWeek('per',-1,()=>loadPeriods(1))">←</button>
        <button class="btn-quick" id="per-week-btn" onclick="setQuick('per-from','per-to','week',()=>loadPeriods(1))">V?</button>
        <button class="btn-quick" onclick="stepWeek('per',1,()=>loadPeriods(1))">→</button>
      </div>
      <label>Sök</label><input type="text" id="per-search" placeholder="program..." style="width:180px">
      <select id="per-active">
        <option value="">Alla</option>
        <option value="1">Aktivt fönster</option>
        <option value="0">Bakgrund</option>
      </select>
      <button class="btn btn-primary" onclick="loadPeriods(1)">Sök</button>
      <button class="btn btn-ghost" onclick="exportCSV()">↓ CSV</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th onclick="sortPer('process_name')">Program ↕</th>
          <th onclick="sortPer('window_title')">Titel / Dokument ↕</th>
          <th onclick="sortPer('started_at')">Start ↕</th>
          <th onclick="sortPer('ended_at')">Slut ↕</th>
          <th onclick="sortPer('duration_sec')">Längd ↕</th>
          <th onclick="sortPer('is_active')">Status ↕</th>
        </tr></thead>
        <tbody id="per-body"><tr><td colspan="6" class="loading">Laddar</td></tr></tbody>
      </table>
    </div>
    <div class="pagination">
      <span class="page-info" id="per-pageinfo"></span>
      <button class="btn btn-ghost" id="per-prev" onclick="loadPeriods(currentPage-1)">← Förra</button>
      <button class="btn btn-ghost" id="per-next" onclick="loadPeriods(currentPage+1)">Nästa →</button>
    </div>
  </div>

  <!-- Program -->
  <div id="page-apps" class="page">
    <h1>Program</h1><p class="subtitle">Total tid per applikation</p>
    <div class="filters">
      <label>Från</label><input type="date" id="apps-from">
      <label>Till</label><input type="date" id="apps-to">
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('apps-from','apps-to','today',loadApps)">Idag</button>
        <button class="btn-quick" onclick="setQuick('apps-from','apps-to','yesterday',loadApps)">Igår</button>
        <button class="btn-quick" onclick="stepWeek('apps',-1,loadApps)">←</button>
        <button class="btn-quick" id="apps-week-btn" onclick="setQuick('apps-from','apps-to','week',loadApps)">V?</button>
        <button class="btn-quick" onclick="stepWeek('apps',1,loadApps)">→</button>
      </div>
      <select id="apps-active">
        <option value="">Aktivt + bakgrund</option>
        <option value="1">Bara aktivt fönster</option>
        <option value="0">Bara bakgrund</option>
      </select>
      <button class="btn btn-primary" onclick="loadApps()">Uppdatera</button>
      <div class="prog-filter-btn">
        <button class="btn btn-ghost" onclick="openProgFilter('apps')">⊞ Program<span id="prog-filter-count-apps"></span></button>
        <div class="prog-filter-panel" id="prog-filter-apps" style="display:none">
          <div class="prog-filter-panel-head">
            <span class="prog-filter-panel-title">Visa program</span>
            <div style="display:flex;gap:6px">
              <button class="btn-quick" onclick="selectAllProgs('apps',true);event.stopPropagation()">Alla</button>
              <button class="btn-quick" onclick="selectAllProgs('apps',false);event.stopPropagation()">Inga</button>
            </div>
          </div>
          <div class="prog-filter-list" id="prog-filter-list-apps"></div>
        </div>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Program</th>
          <th>Total tid</th>
          <th>Antal perioder</th>
          <th>Snitt per period</th>
          <th>Senast aktiv</th>
          <th></th>
        </tr></thead>
        <tbody id="apps-body"><tr><td colspan="6" class="loading">Laddar</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Sessioner -->
  <div id="page-sessions" class="page">
    <h1>Sessioner</h1><p class="subtitle">Datorns aktiva perioder</p>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Start</th><th>Slut</th><th>Längd</th><th>Perioder</th></tr></thead>
        <tbody id="sessions-body"><tr><td colspan="5" class="loading">Laddar</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- Tidslinje -->
  <div id="page-gantt" class="page">
    <h1>Tidslinje</h1><p class="subtitle">Program och aktivitet över tid</p>
    <div class="filters">
      <label>Från</label><input type="datetime-local" id="gantt-from">
      <label>Till</label><input type="datetime-local" id="gantt-to">
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('gantt-from','gantt-to','today',loadGantt,true)">Idag</button>
        <button class="btn-quick" onclick="setQuick('gantt-from','gantt-to','yesterday',loadGantt,true)">Igår</button>
        <button class="btn-quick" onclick="stepWeek('gantt',-1,loadGantt,true)">←</button>
        <button class="btn-quick" id="gantt-week-btn" onclick="setQuick('gantt-from','gantt-to','week',loadGantt,true)">V?</button>
        <button class="btn-quick" onclick="stepWeek('gantt',1,loadGantt,true)">→</button>
      </div>
      <button class="btn btn-primary" onclick="loadGantt()">Uppdatera</button>
      <div class="prog-filter-btn">
        <button class="btn btn-ghost" onclick="openProgFilter('gantt')">⊞ Program<span id="prog-filter-count-gantt"></span></button>
        <div class="prog-filter-panel" id="prog-filter-gantt" style="display:none">
          <div class="prog-filter-panel-head">
            <span class="prog-filter-panel-title">Visa program</span>
            <div style="display:flex;gap:6px">
              <button class="btn-quick" onclick="selectAllProgs('gantt',true);event.stopPropagation()">Alla</button>
              <button class="btn-quick" onclick="selectAllProgs('gantt',false);event.stopPropagation()">Inga</button>
            </div>
          </div>
          <div class="prog-filter-list" id="prog-filter-list-gantt"></div>
        </div>
      </div>
    </div>
    <div id="gantt-outer" style="border:1px solid var(--border);border-radius:var(--r);background:var(--surface);overflow:hidden">
      <!-- Sticky tidsaxel -->
      <div style="position:sticky;top:0;z-index:10;background:var(--surface)">
        <canvas id="gantt-header" style="display:block"></canvas>
      </div>
      <!-- Scrollbar rad-innehåll -->
      <div id="gantt-wrap" style="overflow-y:auto;overflow-x:hidden;max-height:60vh">
        <canvas id="gantt-canvas" style="display:block;cursor:grab"></canvas>
      </div>
    </div>
    <div style="margin-top:12px;font-size:11px;color:var(--muted);font-family:var(--mono)">
      Klicka på en rad för att expandera titlar &nbsp;·&nbsp; Dra för att panorera &nbsp;·&nbsp;
      <span style="display:inline-block;width:12px;height:8px;background:var(--accent);border-radius:2px;vertical-align:middle"></span> Aktivt &nbsp;
      <span style="display:inline-block;width:12px;height:8px;background:var(--muted);border-radius:2px;vertical-align:middle;opacity:.5"></span> Bakgrund
    </div>
    <div id="gantt-detail" style="margin-top:16px"></div>
  </div>

  <!-- AI-chat -->
  <div id="page-ai" class="page">
    <div class="ai-top">
      <h1>Maj-Britt</h1><p class="subtitle">Ställ frågor om din aktivitetsdata</p>

      <!-- Inställningar -->
      <div class="ai-settings">
        <div style="display:flex;align-items:center;gap:10px">
          <label>Källa</label>
          <select id="ai-provider" onchange="onProviderChange()" style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 10px;color:var(--text);font-size:12px;outline:none">
            <option value="ollama">Ollama (lokalt)</option>
            <option value="anthropic">Anthropic API (moln)</option>
          </select>
          <span id="ai-privacy-badge" class="ai-provider-badge local">🔒 Lokalt</span>
        </div>
        <div style="display:flex;align-items:center;gap:10px">
          <label>Modell</label>
          <select id="ai-model" style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 10px;color:var(--text);font-size:12px;outline:none;min-width:160px">
            <option value="llama3.2">llama3.2</option>
          </select>
          <button class="btn-quick" onclick="refreshOllamaModels()" id="ai-refresh-btn" title="Hämta tillgängliga Ollama-modeller">↺</button>
        </div>
        <div id="ai-apikey-wrap" style="display:none;align-items:center;gap:10px">
          <label>API-nyckel</label>
          <input id="ai-api-key" type="password" placeholder="sk-ant-..." autocomplete="off"
            style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 12px;color:var(--text);font-family:var(--mono);font-size:12px;outline:none;width:280px">
        </div>
        <button class="btn btn-ghost" onclick="saveAiSettings()" style="margin-left:auto">Spara inställningar</button>
      </div>

      <!-- Förslag – alltid synliga -->
      <div class="ai-suggestions-wrap">
        <div class="ai-suggestions-label">
          <span>Förslag</span>
        </div>
        <div class="ai-suggestions" id="ai-suggestions-builtin">
          <button class="ai-suggestion" onclick="aiSuggest(this)">Vad jobbade jag med igår?</button>
          <button class="ai-suggestion" onclick="aiSuggest(this)">Sammanfatta min dag idag</button>
          <button class="ai-suggestion" onclick="aiSuggest(this)">Vilket program använde jag mest den här veckan?</button>
          <button class="ai-suggestion" onclick="aiSuggest(this)">Hur ser min arbetsvecka ut?</button>
        </div>
        <div id="ai-suggestions-recent-wrap" style="display:none">
          <div class="ai-suggestions-label" style="margin-top:8px">
            <span>Senast frågat</span>
            <button class="btn-quick" onclick="clearAiHistory()" style="font-size:10px">Rensa</button>
          </div>
          <div class="ai-suggestions" id="ai-suggestions-recent"></div>
        </div>
      </div>
    </div>

    <div class="ai-layout">
      <!-- Meddelanden -->
      <div class="ai-messages" id="ai-messages"></div>

      <!-- Input -->
      <div class="ai-input-row">
        <textarea id="ai-input" rows="1" placeholder="Skriv en fråga... (Enter skickar, Shift+Enter ny rad)"
          onkeydown="aiKeydown(event)" oninput="autoGrow(this)"></textarea>
        <button class="btn btn-primary ai-send" id="ai-send-btn" onclick="sendAiMessage()">Skicka</button>
      </div>
    </div>
  </div>

  <!-- ── Feedback-sida ─────────────────────────────────────────── -->
  <div id="page-feedback" class="page">
    <div class="page-header"><h2>Feedback</h2></div>
    <div style="max-width:560px">
      <p style="color:var(--muted);font-size:13px;margin-bottom:20px">
        Har du en idé, hittat ett fel eller vill ge beröm? Skriv här – det går direkt till utvecklaren.
      </p>
      <div style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Kategori</label>
        <select id="fb-category" style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
          padding:8px 12px;color:var(--text);font-size:13px;width:100%">
          <option value="idé">💡 Idé / förbättring</option>
          <option value="fel">🐛 Fel / bugg</option>
          <option value="beröm">👏 Beröm</option>
          <option value="övrigt">💬 Övrigt</option>
        </select>
      </div>
      <div style="margin-bottom:14px">
        <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Meddelande</label>
        <textarea id="fb-message" rows="5" placeholder="Beskriv din feedback…"
          style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
          padding:10px 14px;color:var(--text);font-size:13px;resize:vertical;font-family:var(--font);
          box-sizing:border-box;outline:none"></textarea>
      </div>
      <!-- Diagnostikpaket -->
      <div style="margin-bottom:18px">
        <button onclick="toggleDiag()" style="background:none;border:none;color:var(--muted);
          font-size:12px;cursor:pointer;padding:0;display:flex;align-items:center;gap:6px">
          <span id="diag-arrow">▶</span> Vad som skickas med (diagnostik)
        </button>
        <div id="diag-box" style="display:none;margin-top:10px;background:var(--bg);border:1px solid var(--border);
          border-radius:var(--r);padding:12px 14px;font-size:11px;color:var(--muted);
          font-family:var(--mono);line-height:1.8">
          <div id="diag-content">Laddar…</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        <button onclick="submitFeedback()" class="btn-primary" style="padding:10px 24px">Skicka</button>
        <span id="fb-status" style="font-size:12px;color:var(--muted)"></span>
      </div>
      <div id="fb-user-info" style="margin-top:20px;font-size:12px;color:var(--muted)"></div>
      <div id="fb-not-registered" style="display:none;margin-top:20px;padding:14px 16px;
        background:var(--bg);border:1px solid var(--border);border-radius:var(--r);font-size:13px">
        Du är inte registrerad än.
        <button onclick="showRegistration()" style="background:none;border:none;color:var(--accent);
          cursor:pointer;font-size:13px;padding:0;margin-left:6px;text-decoration:underline">
          Registrera dig här →
        </button>
      </div>
    </div>
  </div>
</main>
</div>

<!-- ── Hjälp-overlay ─────────────────────────────────────────── -->
<div id="help-overlay" class="help-overlay" onclick="if(event.target===this)closeHelp()">
  <div class="help-box">
    <button class="help-close" onclick="closeHelp()">✕</button>
    <h3 id="help-title"></h3>
    <div id="help-body"></div>
  </div>
</div>

<!-- ── Registreringsmodal ────────────────────────────────────── -->
<div id="reg-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);
  z-index:9000;align-items:center;justify-content:center" onclick="if(event.target===this)dismissRegistration()">
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;
    padding:36px 40px;max-width:420px;width:90%;box-shadow:0 20px 60px #000a;position:relative">
    <button onclick="dismissRegistration()" style="position:absolute;top:14px;right:16px;background:none;
      border:none;color:var(--muted);font-size:18px;cursor:pointer;line-height:1">✕</button>
    <h2 style="margin:0 0 6px;font-size:18px">Tack för att du vill prova ActivityTracker!</h2>
    <p style="color:var(--muted);font-size:13px;margin:0 0 24px">
      Registrera dig för att aktivera feedback och automatiska uppdateringar.
    </p>
    <div style="margin-bottom:14px">
      <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Ditt namn</label>
      <input id="reg-name" type="text" placeholder="Förnamn Efternamn"
        style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);
        padding:10px 14px;color:var(--text);font-size:13px;box-sizing:border-box;outline:none">
    </div>
    <div style="margin-bottom:20px">
      <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">E-post</label>
      <input id="reg-email" type="email" placeholder="namn@foretag.se"
        style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:var(--r);
        padding:10px 14px;color:var(--text);font-size:13px;box-sizing:border-box;outline:none">
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <button onclick="submitRegistration()" class="btn-primary" style="padding:10px 24px">Registrera</button>
      <button onclick="dismissRegistration()" style="background:none;border:none;color:var(--muted);
        font-size:12px;cursor:pointer;padding:0">Påminn mig senare</button>
      <span id="reg-status" style="font-size:12px;color:var(--muted)"></span>
    </div>
  </div>
</div>

<script>
let currentPage = 1;
let perSort = 'started_at';
let perDir  = 'desc';

function today()   { return new Date().toISOString().slice(0,10); }
function daysAgo(n){ const d=new Date(); d.setDate(d.getDate()-n); return d.toISOString().slice(0,10); }
function fmtTs(ts) { return ts ? ts.replace('T',' ').slice(0,19) : '—'; }
function fmtDur(s) {
  if (!s) return '—';
  if (s < 60)   return s + 's';
  if (s < 3600) return Math.floor(s/60) + 'm ' + (s%60) + 's';
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60);
  return h + 'h ' + m + 'm';
}

// ── Snabbval datum ─────────────────────────────────────────────
function weekNumber(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay()||7));
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(),0,1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

function getWeekBounds() {
  const now = new Date();
  const day = now.getDay();
  const daysSinceMon = (day + 6) % 7;
  const mon = new Date(now); mon.setDate(now.getDate() - daysSinceMon); mon.setHours(0,0,0,0);
  const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
  const localDate = d => {
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,'0');
    const dd = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${dd}`;
  };
  return {
    from: localDate(mon),
    to:   localDate(sun),
    week: weekNumber(mon)
  };
}

function setQuick(fromId, toId, preset, loadFn, isDatetime) {
  const section = fromId.replace('-from','');

  if (preset === 'today') {
    document.getElementById(fromId).value = isDatetime ? today()+'T00:00' : today();
    document.getElementById(toId).value   = isDatetime ? today()+'T23:59' : today();
    loadFn();
  } else if (preset === 'yesterday') {
    const y = daysAgo(1);
    document.getElementById(fromId).value = isDatetime ? y+'T00:00' : y;
    document.getElementById(toId).value   = isDatetime ? y+'T23:59' : y;
    loadFn();
  } else if (preset === 'week') {
    weekOffset[section] = 0;
    applyWeek(section, 0, loadFn, isDatetime);
  }
}

function weekLabel() {
  return 'V' + getWeekBounds().week;
}

// Spåra vecko-offset per sektion (0 = innevarande vecka)
const weekOffset = { 'dash': 0, 'per': 0, 'apps': 0, 'gantt': 0 };

function applyWeek(section, offset, loadFn, isDatetime) {
  const now = new Date();
  const day = now.getDay();
  const daysSinceMon = (day + 6) % 7;
  const mon = new Date(now);
  mon.setDate(now.getDate() - daysSinceMon + offset * 7);
  mon.setHours(0,0,0,0);
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);

  const fmt = d => {
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,'0');
    const dd = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${dd}`;
  };
  const fromId = section + '-from';
  const toId   = section + '-to';
  document.getElementById(fromId).value = isDatetime ? fmt(mon)+'T00:00' : fmt(mon);
  document.getElementById(toId).value   = isDatetime ? fmt(sun)+'T23:59' : fmt(sun);

  const wn = weekNumber(mon);
  const btn = document.getElementById(section + '-week-btn');
  if (btn) btn.textContent = 'V' + wn;

  loadFn();
}

function stepWeek(section, dir, loadFn, isDatetime) {
  weekOffset[section] = (weekOffset[section] || 0) + dir;
  applyWeek(section, weekOffset[section], loadFn, isDatetime);
}

function showPage(el) {
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('page-'+el.dataset.page).classList.add('active');
  if (liveInterval) { clearInterval(liveInterval); liveInterval=null; }
  if(el.dataset.page==='dashboard') loadDashboard();
  if(el.dataset.page==='live')      { loadLive(); liveInterval=setInterval(loadLive,5000); }
  if(el.dataset.page==='periods')   loadPeriods(1);
  if(el.dataset.page==='apps')      loadApps();
  if(el.dataset.page==='sessions')  loadSessions();
  if(el.dataset.page==='gantt')     loadGantt();
  if(el.dataset.page==='ai')        loadAiSettings();
}

// ── Temabyte ───────────────────────────────────────────────────
function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme === 'dark' ? '' : theme);
  localStorage.setItem('at-theme', theme);
  document.querySelectorAll('.theme-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.theme === theme);
  });
  // Rita om Gantt om det är aktivt (färger i canvas)
  if (ganttData) setTimeout(drawGantt, 50);
}

// ── Kollapsbar sidebar ─────────────────────────────────────────
function toggleSidebar() {
  const sb  = document.getElementById('sidebar');
  const btn = document.getElementById('sidebar-toggle');
  const collapsed = sb.classList.toggle('collapsed');
  btn.textContent = collapsed ? '▶' : '◀';
  btn.style.left  = collapsed ? '0px' : '220px';
  setTimeout(() => { if (ganttData) drawGantt(); }, 220);
}

// ── Tooltip-positionering ──────────────────────────────────────
document.addEventListener('mousemove', e => {
  const tip = e.target.closest('.has-tooltip')?.querySelector('.tip');
  if (tip) {
    tip.style.left = (e.clientX + 12) + 'px';
    tip.style.top  = (e.clientY + 12) + 'px';
  }
});

// ── Live ───────────────────────────────────────────────────────
let liveInterval = null;

async function loadLive() {
  const r = await fetch('/api/live');
  const d = await r.json();

  if (d.updated_at) {
    document.getElementById('live-updated').textContent = 'Senast uppdaterad: ' + fmtTs(d.updated_at);
  }

  if (!d.entries || d.entries.length === 0) {
    document.getElementById('live-body').innerHTML = '<tr><td colspan="5" style="color:var(--muted);padding:20px;text-align:center">Ingen data – trackern kanske inte körs?</td></tr>';
    return;
  }

  const visEntries = d.entries.filter(e => isProgVisible('live', e.process_name));
  if (!visEntries.length) {
    document.getElementById('live-body').innerHTML = '<tr><td colspan="5" style="color:var(--muted);padding:20px;text-align:center">Alla program är filtrerade bort</td></tr>';
    return;
  }

  document.getElementById('live-body').innerHTML = visEntries.map(e => `
    <tr>
      <td class="nowrap">${e.process_name}</td>
      ${titleCell(e.window_title, e.url, null, e.process_name)}
      <td class="mono nowrap">${fmtTs(e.started_at)}</td>
      <td class="mono nowrap" style="color:${e.is_active?'var(--green)':'var(--text)'}">${fmtDur(e.duration_sec)}</td>
      <td><span class="badge ${e.is_active?'badge-active':'badge-bg'}">${e.is_active?'Aktivt':'Bakgrund'}</span></td>
    </tr>`).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  // Återställ sparat tema
  const savedTheme = localStorage.getItem('at-theme') || 'dark';
  setTheme(savedTheme);

  ['dash-from','per-from','apps-from'].forEach(id => { const e=document.getElementById(id); if(e) e.value=daysAgo(6); });
  ['dash-to','per-to','apps-to'].forEach(id => { const e=document.getElementById(id); if(e) e.value=today(); });
  // Sätt veckonummer på alla vecko-knappar
  const wl = weekLabel();
  ['dash-week-btn','per-week-btn','apps-week-btn','gantt-week-btn'].forEach(id => {
    const el = document.getElementById(id); if(el) el.textContent = wl;
  });
  initGanttDates();
  FILTER_VIEWS.forEach(updateProgFilterBadge);
  loadDashboard();
  initRegistration();
});

// ── Hjälp ──────────────────────────────────────────────────
const HELP = {
  dashboard: {
    title: '⬡ Dashboard',
    body: `
      <p>Ger dig en snabb överblick över din aktivitet för vald tidsperiod.</p>
      <ul>
        <li><strong>KPI-kort</strong> – total aktiv tid, antal program och sessioner</li>
        <li><strong>Tidsfördelning</strong> – stapeldiagram per program</li>
        <li><strong>Datumväljare</strong> – filtrera på dag, vecka eller eget intervall</li>
        <li><strong>Program-filter</strong> – dölj program du inte vill räkna med</li>
      </ul>`,
  },
  live: {
    title: '● Live',
    body: `
      <p>Visar vad som händer på din dator just nu i realtid.</p>
      <ul>
        <li>Uppdateras automatiskt var 5:e sekund</li>
        <li>Visar aktivt fönster och alla öppna program</li>
        <li>Tiden räknas upp löpande för varje program</li>
      </ul>`,
  },
  periods: {
    title: '◷ Perioder',
    body: `
      <p>Detaljerad lista över alla registrerade aktivitetsperioder.</p>
      <ul>
        <li>Sök på programnamn eller fönstertext</li>
        <li>Filtrera på datum, program och aktiv/inaktiv</li>
        <li>Sortera på valfri kolumn</li>
        <li>Exportera till CSV via knappen uppe till höger</li>
      </ul>`,
  },
  apps: {
    title: '◫ Program',
    body: `
      <p>Sammanställning av total tid per program för vald period.</p>
      <ul>
        <li>Visar procentandel av total aktiv tid</li>
        <li>Använd program-filtret för att exkludera bakgrundsprogram</li>
        <li>Bra för att förstå var arbetstiden faktiskt tar vägen</li>
      </ul>`,
  },
  sessions: {
    title: '≡ Sessioner',
    body: `
      <p>En session är en sammanhängande arbetsperiod – från att du sätter dig vid datorn till att du låser den eller stänger av.</p>
      <ul>
        <li>Visar start, slut och total tid per session</li>
        <li>Hjälper dig se hur länge du jobbade utan avbrott</li>
        <li>Nya sessioner skapas automatiskt efter viloläge</li>
      </ul>`,
  },
  gantt: {
    title: '▤ Tidslinje',
    body: `
      <p>Visar din aktivitet som ett Gantt-diagram över dagen.</p>
      <ul>
        <li>Varje rad är ett program, varje block är en period</li>
        <li>Hovra över ett block för att se detaljer</li>
        <li>Bra för att se mönster och pauser under dagen</li>
        <li>Filtrera bort program du inte vill se</li>
      </ul>`,
  },
  ai: {
    title: '◈ Maj-Britt',
    body: `
      <p>Din personliga AI-assistent som känner till din aktivitetsdata.</p>
      <ul>
        <li>Ställ frågor om din arbetstid, projekt och vanor</li>
        <li>Använder lokal AI (Ollama) eller Anthropic Claude</li>
        <li>All data stannar på din dator vid lokal AI</li>
        <li>Ge tumme upp/ner på svaren för att hjälpa Maj-Britt bli bättre</li>
      </ul>
      <p>Välj leverantör och modell i inställningarna överst på sidan.</p>`,
  },
  feedback: {
    title: '✉ Feedback',
    body: `
      <p>Skicka synpunkter, felrapporter eller idéer direkt till utvecklaren.</p>
      <ul>
        <li>Välj kategori – idé, fel, beröm eller övrigt</li>
        <li>Din mailapp öppnas med ett färdigifyllt meddelande</li>
        <li>Diagnostikinformation bifogas automatiskt för att underlätta felsökning</li>
        <li>Inget skickas utan att du godkänner det i din mailapp</li>
      </ul>`,
  },
};

function showHelp(page) {
  const h = HELP[page];
  if (!h) return;
  document.getElementById('help-title').textContent = h.title;
  document.getElementById('help-body').innerHTML = h.body;
  document.getElementById('help-overlay').classList.add('open');
}

function closeHelp() {
  document.getElementById('help-overlay').classList.remove('open');
}

// ── Registrering ───────────────────────────────────────────────
async function initRegistration() {
  const r = await fetch('/api/config');
  const cfg = await r.json();
  const verEl = document.getElementById('app-version');
  if (verEl && cfg.version) verEl.textContent = cfg.version;
  if (cfg.token) {
    const info = document.getElementById('fb-user-info');
    if (info) info.textContent = `Inloggad som: ${cfg.user_name || ''} (${cfg.user_email || ''})`;
    const notReg = document.getElementById('fb-not-registered');
    if (notReg) notReg.style.display = 'none';
  } else if (cfg.backend_ready) {
    document.getElementById('fb-not-registered').style.display = 'block';
    const dismissed = localStorage.getItem('at-reg-dismissed');
    const today = new Date().toISOString().slice(0, 10);
    if (dismissed !== today) {
      document.getElementById('reg-overlay').style.display = 'flex';
    }
  }
}

function dismissRegistration() {
  document.getElementById('reg-overlay').style.display = 'none';
  localStorage.setItem('at-reg-dismissed', new Date().toISOString().slice(0, 10));
  document.getElementById('fb-not-registered').style.display = 'block';
}

function showRegistration() {
  document.getElementById('reg-overlay').style.display = 'flex';
}

async function submitRegistration() {
  const name  = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const status = document.getElementById('reg-status');
  if (!name || !email) { status.textContent = 'Fyll i namn och e-post.'; return; }
  status.textContent = 'Registrerar… (kan ta upp till 60s första gången)';
  try {
    const r = await fetch('/api/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, email}),
    });
    const d = await r.json();
    if (d.ok) {
      document.getElementById('reg-overlay').style.display = 'none';
      document.getElementById('fb-not-registered').style.display = 'none';
      const info = document.getElementById('fb-user-info');
      if (info) info.textContent = `Inloggad som: ${name} (${email})`;
    } else {
      status.textContent = d.error || 'Fel vid registrering.';
    }
  } catch(e) {
    status.textContent = 'Kunde inte nå servern.';
  }
}

let _diagData = null;

async function loadDiag() {
  if (_diagData) return _diagData;
  try {
    const r = await fetch('/api/diagnostics');
    _diagData = await r.json();
  } catch(e) {
    _diagData = {error: 'Kunde inte hämta diagnostik'};
  }
  return _diagData;
}

async function toggleDiag() {
  const box   = document.getElementById('diag-box');
  const arrow = document.getElementById('diag-arrow');
  const shown = box.style.display !== 'none';
  if (shown) {
    box.style.display = 'none';
    arrow.textContent = '▶';
  } else {
    box.style.display = 'block';
    arrow.textContent = '▼';
    const d = await loadDiag();
    const content = document.getElementById('diag-content');
    if (d.error) {
      content.textContent = d.error;
    } else {
      content.innerHTML = [
        `App-version:    ${d.app_version}`,
        `OS:             ${d.os_version}`,
        `Python:         ${d.python_version}`,
        `RAM totalt:     ${d.ram_total_gb} GB`,
        `RAM ledigt:     ${d.ram_free_gb} GB`,
        `Ollama:         ${d.ollama_running ? 'Installerat och igång' : 'Ej igång'}`,
        `Tracker status: ${d.tracker_running ? 'Aktiv' : 'Ej aktiv'}`,
        `Senaste fel:    ${d.last_error || 'inga'}`,
      ].map(escHtml).join('<br>');
    }
  }
}

async function submitFeedback() {
  const category = document.getElementById('fb-category').value;
  const message  = document.getElementById('fb-message').value.trim();
  const status   = document.getElementById('fb-status');
  if (!message) { status.textContent = 'Skriv ett meddelande.'; return; }

  const cfg = await fetch('/api/config').then(r => r.json());
  const diag = await loadDiag();

  const diagText = diag && !diag.error ? [
    '',
    '── Diagnostik ───────────────────',
    `App-version:    ${diag.app_version}`,
    `OS:             ${diag.os_version}`,
    `Python:         ${diag.python_version}`,
    `RAM totalt:     ${diag.ram_total_gb} GB`,
    `RAM ledigt:     ${diag.ram_free_gb} GB`,
    `Ollama:         ${diag.ollama_running ? 'Igång' : 'Ej igång'}`,
    `Tracker:        ${diag.tracker_running ? 'Aktiv' : 'Ej aktiv'}`,
    `Senaste fel:    ${diag.last_error || 'inga'}`,
  ].join('\n') : '';

  const subject = encodeURIComponent(`[AT Feedback] ${category}`);
  const body = encodeURIComponent(
    `Från: ${cfg.user_name || ''} (${cfg.user_email || ''})\nVersion: ${cfg.version}\nKategori: ${category}\n\n${message}${diagText}`
  );

  window.location.href = `mailto:${cfg.feedback_email}?subject=${subject}&body=${body}`;

  document.getElementById('fb-message').value = '';
  status.style.color = 'var(--accent)';
  status.textContent = '✓ Din mailapp öppnas – skicka därifrån';
  setTimeout(() => { status.textContent = ''; status.style.color = ''; }, 5000);
}

// ── Dashboard ──────────────────────────────────────────────────
async function loadDashboard() {
  const from=document.getElementById('dash-from').value, to=document.getElementById('dash-to').value;
  const r = await fetch(`/api/dashboard?from=${from}&to=${to}`);
  const d = await r.json();

  document.getElementById('kpi-grid').innerHTML = `
    <div class="kpi"><div class="kpi-label">Total aktiv tid</div><div class="kpi-value">${fmtDur(d.total_active_sec)}</div><div class="kpi-sub">aktivt fönster</div></div>
    <div class="kpi green"><div class="kpi-label">Total öppen tid</div><div class="kpi-value">${fmtDur(d.total_open_sec)}</div><div class="kpi-sub">inkl. bakgrund</div></div>
    <div class="kpi red"><div class="kpi-label">Program</div><div class="kpi-value">${d.unique_apps}</div><div class="kpi-sub">unika applikationer</div></div>
    <div class="kpi"><div class="kpi-label">Perioder</div><div class="kpi-value">${d.total_periods}</div><div class="kpi-sub">loggade aktiviteter</div></div>
  `;

  const visApps = d.top_apps.filter(a => isProgVisible('dashboard', a.process_name));
  const max = visApps[0]?.total_sec || 1;
  document.getElementById('top-apps-chart').innerHTML = visApps.map(a => `
    <div class="bar-row">
      <div class="bar-label">${a.process_name}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${(a.total_sec/max*100).toFixed(1)}%"><span>${fmtDur(a.total_sec)}</span></div></div>
    </div>`).join('');

  drawTimeline(d.hourly);
}

function drawTimeline(hourly) {
  const canvas = document.getElementById('timeline-canvas');
  const W = canvas.offsetWidth||700, H = 200;
  canvas.width=W; canvas.height=H;
  const ctx = canvas.getContext('2d');
  const hours = Array.from({length:24},(_,i)=>i);
  const vals  = hours.map(h=>(hourly.find(x=>x.hour===h)||{total_sec:0}).total_sec);
  const max   = Math.max(...vals,1);
  const pad   = {l:36,r:12,t:12,b:28};
  const bw    = (W-pad.l-pad.r)/24-2;

  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle='#1e2330'; ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const y=pad.t+(H-pad.t-pad.b)*(1-i/4);
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(W-pad.r,y); ctx.stroke();
  }
  hours.forEach((h,i)=>{
    const bh=vals[i]/max*(H-pad.t-pad.b);
    const x=pad.l+i*((W-pad.l-pad.r)/24);
    const y=H-pad.b-bh;
    const g=ctx.createLinearGradient(0,y,0,H-pad.b);
    g.addColorStop(0,'#00e5ff'); g.addColorStop(1,'rgba(0,229,255,.2)');
    ctx.fillStyle=g;
    ctx.beginPath(); ctx.roundRect(x+1,y,bw,bh,[3,3,0,0]); ctx.fill();
  });
  ctx.fillStyle='#5a6070'; ctx.font=`10px ${getComputedStyle(document.body).getPropertyValue('--mono').trim()}`; ctx.textAlign='center';
  [0,6,12,18,23].forEach(h=>{
    const x=pad.l+h*((W-pad.l-pad.r)/24)+bw/2;
    ctx.fillText(h+':00',x,H-8);
  });
}

// ── Perioder ───────────────────────────────────────────────────
function truncatePath(path, maxLen = 60) {
  if (!path || path.length <= maxLen) return path;
  return '… ' + path.slice(-(maxLen - 2));
}

function titleCell(title, url, exe, procName) {
  const tip = url || exe || '';
  const tipShort = truncatePath(tip);

  return `<td class="title-cell">
    <span class="title-text has-tooltip" style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
      ${title||'—'}
      ${tipShort ? `<span class="tip">${tipShort}</span>` : ''}
    </span>
  </td>`;
}

async function loadPeriods(page) {
  if(page<1) return;
  currentPage=page;
  const from=document.getElementById('per-from').value, to=document.getElementById('per-to').value;
  const search=document.getElementById('per-search').value, active=document.getElementById('per-active').value;
  const params=new URLSearchParams({from,to,search,active,sort:perSort,dir:perDir,page,limit:50});
  const r=await fetch('/api/periods?'+params);
  const d=await r.json();

  document.getElementById('per-body').innerHTML = d.rows.map(row=>`
    <tr>
      <td class="nowrap">${row.process_name||'—'}</td>
      ${titleCell(row.window_title, row.url, row.exe_path, row.process_name)}
      <td class="mono nowrap">${fmtTs(row.started_at)}</td>
      <td class="mono nowrap">${fmtTs(row.ended_at)}</td>
      <td class="mono nowrap">${fmtDur(row.duration_sec)}</td>
      <td><span class="badge ${row.is_active?'badge-active':'badge-bg'}">${row.is_active?'Aktivt':'Bakgrund'}</span></td>
    </tr>`).join('') || '<tr><td colspan="6" style="color:var(--muted);padding:20px;text-align:center">Inga resultat</td></tr>';

  const pages=Math.ceil(d.total/50);
  document.getElementById('per-pageinfo').textContent=`Sida ${page} / ${pages} (${d.total.toLocaleString()} perioder)`;
  document.getElementById('per-prev').disabled=page<=1;
  document.getElementById('per-next').disabled=page>=pages;
}

function sortPer(col) {
  if(perSort===col) perDir=perDir==='asc'?'desc':'asc';
  else { perSort=col; perDir='desc'; }
  loadPeriods(1);
}

async function exportCSV() {
  const from=document.getElementById('per-from').value, to=document.getElementById('per-to').value;
  const search=document.getElementById('per-search').value, active=document.getElementById('per-active').value;
  window.location=`/api/export?from=${from}&to=${to}&search=${search}&active=${active}`;
}

// ── Program ────────────────────────────────────────────────────
async function loadApps() {
  const from=document.getElementById('apps-from').value, to=document.getElementById('apps-to').value;
  const active=document.getElementById('apps-active').value;
  const r=await fetch(`/api/apps?from=${from}&to=${to}&active=${active}`);
  const d=await r.json();
  const visRows = d.filter(row => isProgVisible('apps', row.process_name));
  const maxSec = visRows[0]?.total_sec||1;

  document.getElementById('apps-body').innerHTML = visRows.map((row,i)=>`
    <tr>
      <td>${row.process_name||'—'}</td>
      <td>
        <div class="dur-bar">
          <div class="dur-track"><div class="dur-fill" style="width:${(row.total_sec/maxSec*100).toFixed(1)}%"></div></div>
          <span class="mono">${fmtDur(row.total_sec)}</span>
        </div>
      </td>
      <td class="mono">${row.period_count}</td>
      <td class="mono">${fmtDur(Math.round(row.total_sec/row.period_count))}</td>
      <td class="mono">${fmtTs(row.last_seen)}</td>
      <td><button class="btn btn-ghost" style="padding:3px 10px;font-size:10px" onclick="toggleTitles(this,'${encodeURIComponent(row.process_name)}','${from}','${to}','${active}')">▶ Titlar</button></td>
    </tr>
    <tr id="titles-${i}" style="display:none">
      <td colspan="6" style="padding:0 14px 12px 32px;background:rgba(0,0,0,.2)">
        <div id="titles-content-${i}" style="font-size:12px;color:var(--muted)"></div>
      </td>
    </tr>`).join('');
}

async function toggleTitles(btn, procEncoded, from, to, active) {
  const proc = decodeURIComponent(procEncoded);
  const row = btn.closest('tr');
  const idx = [...document.querySelectorAll('#apps-body tr')].indexOf(row);
  const titleRow = document.getElementById('titles-'+Math.floor(idx/2));
  const content  = document.getElementById('titles-content-'+Math.floor(idx/2));

  if (titleRow.style.display !== 'none') {
    titleRow.style.display = 'none';
    btn.textContent = '▶ Titlar';
    return;
  }

  btn.textContent = '▼ Titlar';
  titleRow.style.display = '';
  content.textContent = 'Laddar...';

  const r = await fetch(`/api/app_titles?proc=${encodeURIComponent(proc)}&from=${from}&to=${to}&active=${active}`);
  const titles = await r.json();

  if (!titles.length) { content.textContent = 'Inga titlar hittades.'; return; }
  content.innerHTML = titles.map(t => {
    const tip = truncatePath(t.url || t.exe_path || '');
    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--border)">
      <span class="has-tooltip" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">
        ${t.window_title||'—'}
        ${tip ? `<span class="tip">${tip}</span>` : ''}
      </span>
      <span class="mono" style="margin-left:16px;flex-shrink:0;color:var(--accent)">${fmtDur(t.total_sec)}</span>
    </div>`;
  }).join('');
}

// ── Tidslinje (Gantt) ──────────────────────────────────────────
let ganttData     = null;
let ganttOffsetX  = 0;
let ganttScale    = 1;      // px per sekund
let ganttDragging = false;
let ganttDragStartX = 0;
let ganttDragStartOffset = 0;
let ganttExpandedRows = new Set();

const ROW_H      = 28;
const LABEL_W    = 200;
const HEADER_H   = 36;
const SECTION_GAP = 14;
const COLORS = {
  active:     '#00e5ff',
  activeDim:  'rgba(0,229,255,0.18)',
  bg:         '#5a6070',
  bgDim:      'rgba(90,96,112,0.25)',
  subActive:  'rgba(0,229,255,0.55)',
  subBg:      'rgba(90,96,112,0.45)',
};

function ganttDatetimeLocal(date) {
  const d = new Date(date);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0,16);
}

function initGanttDates() {
  const now = new Date();
  const ago = new Date(now - 24*3600*1000);
  document.getElementById('gantt-to').value   = ganttDatetimeLocal(now);
  document.getElementById('gantt-from').value = ganttDatetimeLocal(ago);
}

async function loadGantt() {
  const from = document.getElementById('gantt-from').value;
  const to   = document.getElementById('gantt-to').value;
  if (!from || !to) return;
  const r = await fetch(`/api/gantt?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
  ganttData = (await r.json()).filter(g => isProgVisible('gantt', g.process_name));
  ganttExpandedRows.clear();
  ganttOffsetX = 0;
  drawGantt();
}

function ganttZoom(factor) {} // borttagen – behålls tom för bakåtkompatibilitet

function drawGantt() {
  if (!ganttData) return;
  const canvas  = document.getElementById('gantt-canvas');
  const hCanvas = document.getElementById('gantt-header');
  const wrap    = document.getElementById('gantt-wrap');
  const from    = new Date(document.getElementById('gantt-from').value);
  const to      = new Date(document.getElementById('gantt-to').value);
  const totalSec = (to - from) / 1000;

  const wrapW = wrap.clientWidth - 4;
  ganttScale = Math.max(0.001, (wrapW - LABEL_W) / totalSec);

  // Bygg radlista
  const activeProcs = ganttData.filter(g => g.has_active);
  const bgProcs     = ganttData.filter(g => !g.has_active);
  let rows = [];
  if (activeProcs.length) {
    rows.push({type:'header', label:'AKTIVT FÖNSTER'});
    activeProcs.forEach(g => {
      rows.push({type:'proc', data:g, mode:'active'});
      if (ganttExpandedRows.has(g.process_name))
        g.titles.filter(t=>t.is_active).forEach(t => rows.push({type:'title', data:t, proc:g.process_name, mode:'active'}));
    });
  }
  if (bgProcs.length) {
    if (activeProcs.length) rows.push({type:'gap'});
    rows.push({type:'header', label:'BAKGRUND'});
    bgProcs.forEach(g => {
      rows.push({type:'proc', data:g, mode:'bg'});
      if (ganttExpandedRows.has(g.process_name))
        g.titles.filter(t=>!t.is_active).forEach(t => rows.push({type:'title', data:t, proc:g.process_name, mode:'bg'}));
    });
  }

  const DAYS_SV = ['Sön','Mån','Tis','Ons','Tor','Fre','Lör'];
  const showDayLabels = totalSec > 3600 * 20;
  const axisH = showDayLabels ? HEADER_H + 18 : HEADER_H;
  const totalW = Math.max(wrapW, LABEL_W + totalSec * ganttScale + 40);
  const bodyH  = rows.reduce((s,r) => s + (r.type==='header'?22 : r.type==='gap'?SECTION_GAP : ROW_H), 0) + 20;

  // Läs CSS-variabler
  const cs = getComputedStyle(document.documentElement);
  const C = {
    bg:      cs.getPropertyValue('--bg').trim(),
    surface: cs.getPropertyValue('--surface').trim(),
    border:  cs.getPropertyValue('--border').trim(),
    accent:  cs.getPropertyValue('--accent').trim(),
    muted:   cs.getPropertyValue('--muted').trim(),
    text:    cs.getPropertyValue('--text').trim(),
    accent2: cs.getPropertyValue('--accent2').trim(),
  };

  const timelineX = x => LABEL_W + ganttOffsetX + x * ganttScale;

  // ── Rita header-canvas ────────────────────────────────────────
  hCanvas.width  = totalW;
  hCanvas.height = axisH;
  const hCtx = hCanvas.getContext('2d');
  hCtx.clearRect(0, 0, totalW, axisH);

  hCtx.fillStyle = C.surface;
  hCtx.fillRect(0, 0, LABEL_W, axisH);
  hCtx.fillStyle = C.border;
  hCtx.fillRect(LABEL_W, 0, totalW - LABEL_W, axisH);

  const tickIntervals = [60,300,600,1800,3600,7200,14400,21600,43200,86400];
  const tickSec = tickIntervals.find(t => t * ganttScale >= 60) || 86400;

  hCtx.font = '10px JetBrains Mono';
  hCtx.textAlign = 'center';
  for (let s = 0; s <= totalSec + tickSec; s += tickSec) {
    const x = timelineX(s);
    if (x < LABEL_W || x > totalW) continue;
    hCtx.strokeStyle = C.muted + '44'; hCtx.lineWidth = 1;
    hCtx.beginPath(); hCtx.moveTo(x, 0); hCtx.lineTo(x, axisH); hCtx.stroke();
    hCtx.fillStyle = C.muted;
    hCtx.fillText(new Date(from.getTime() + s*1000).toTimeString().slice(0,5), x, HEADER_H - 6);
  }

  if (showDayLabels) {
    const startDay = new Date(from); startDay.setHours(0,0,0,0);
    for (let d = new Date(startDay); d <= to; d.setDate(d.getDate()+1)) {
      const sec = (d - from) / 1000;
      const x = timelineX(sec);
      if (x >= LABEL_W && x <= totalW) {
        hCtx.strokeStyle = C.muted + '88'; hCtx.lineWidth = 1.5;
        hCtx.beginPath(); hCtx.moveTo(x, 0); hCtx.lineTo(x, axisH); hCtx.stroke();
      }
      const midX = timelineX(sec + 43200);
      if (midX >= LABEL_W && midX <= totalW) {
        hCtx.fillStyle = C.accent;
        hCtx.font = 'bold 10px JetBrains Mono';
        hCtx.textAlign = 'center';
        hCtx.fillText(DAYS_SV[d.getDay()] + ' ' + d.getDate() + '/' + (d.getMonth()+1), midX, HEADER_H + 13);
      }
    }
  }

  // Nulinje i header
  const nowSec = (new Date() - from) / 1000;
  if (nowSec > 0 && nowSec < totalSec) {
    const nx = timelineX(nowSec);
    hCtx.strokeStyle = C.accent2; hCtx.lineWidth = 1.5;
    hCtx.setLineDash([4,3]);
    hCtx.beginPath(); hCtx.moveTo(nx, 0); hCtx.lineTo(nx, axisH); hCtx.stroke();
    hCtx.setLineDash([]);
  }

  // ── Rita body-canvas ──────────────────────────────────────────
  canvas.width  = totalW;
  canvas.height = bodyH;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, totalW, bodyH);

  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, totalW, bodyH);
  ctx.fillStyle = C.surface;
  ctx.fillRect(0, 0, LABEL_W, bodyH);

  // Tick-linjer nedåt i body
  for (let s = 0; s <= totalSec + tickSec; s += tickSec) {
    const x = timelineX(s);
    if (x < LABEL_W || x > totalW) continue;
    ctx.strokeStyle = C.muted + '22'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, bodyH); ctx.stroke();
  }

  // Dag-separatorer i body
  if (showDayLabels) {
    const startDay = new Date(from); startDay.setHours(0,0,0,0);
    for (let d = new Date(startDay); d <= to; d.setDate(d.getDate()+1)) {
      const x = timelineX((d - from) / 1000);
      if (x >= LABEL_W && x <= totalW) {
        ctx.strokeStyle = C.muted + '44'; ctx.lineWidth = 1.5;
        ctx.setLineDash([3,3]);
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, bodyH); ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  }

  // Nulinje i body
  if (nowSec > 0 && nowSec < totalSec) {
    const nx = timelineX(nowSec);
    ctx.strokeStyle = C.accent2; ctx.lineWidth = 1.5;
    ctx.setLineDash([4,3]);
    ctx.beginPath(); ctx.moveTo(nx, 0); ctx.lineTo(nx, bodyH); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Rita rader
  let y = 0;
  rows.forEach(row => {
    if (row.type === 'gap') { y += SECTION_GAP; return; }
    if (row.type === 'header') {
      ctx.fillStyle = C.border;
      ctx.fillRect(LABEL_W, y, totalW-LABEL_W, 20);
      ctx.fillStyle = C.muted;
      ctx.font = '9px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(row.label, LABEL_W + 8, y + 14);
      y += 22; return;
    }

    const isProc   = row.type === 'proc';
    const isActive = row.mode === 'active';
    const periods  = row.data.periods;
    const barColor = isActive ? (isProc ? C.accent : C.accent+'99')
                              : (isProc ? C.muted+'aa' : C.muted+'55');

    ctx.fillStyle = 'rgba(128,128,128,0.04)';
    ctx.fillRect(0, y, totalW, ROW_H);
    ctx.strokeStyle = C.border; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(totalW,y); ctx.stroke();

    ctx.fillStyle = isActive ? C.text : C.muted;
    ctx.font = isProc ? '12px Syne' : '11px JetBrains Mono';
    ctx.textAlign = 'left';

    let displayLabel;
    if (row.type === 'title') {
      const raw = row.data.window_title || '';
      const cutAt = raw.search(/ [-–|] [A-Z]/);
      const clean = cutAt > 0 ? raw.slice(0, cutAt) : raw;
      displayLabel = '  ' + (clean.length > 24 ? clean.slice(0,23)+'…' : clean);
    } else {
      const lbl = row.data.process_name;
      displayLabel = lbl.length > 26 ? lbl.slice(0,25)+'…' : lbl;
    }
    ctx.fillText(displayLabel, 8, y + ROW_H/2 + 4);

    if (isProc && row.data.titles && row.data.titles.length > 0) {
      ctx.fillStyle = C.muted;
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(ganttExpandedRows.has(row.data.process_name) ? '▼' : '▶', LABEL_W - 6, y + ROW_H/2 + 4);
    }

    periods.forEach(p => {
      const ps = (new Date(p.started_at) - from) / 1000;
      const pe = (new Date(p.ended_at)   - from) / 1000;
      const bx = timelineX(ps);
      const bw = Math.max(2, (pe - ps) * ganttScale);
      if (bx + bw < LABEL_W || bx > totalW) return;
      const bh = isProc ? 14 : 10;
      const by = y + (ROW_H - bh) / 2;
      ctx.fillStyle = barColor;
      ctx.beginPath();
      ctx.roundRect(Math.max(LABEL_W, bx), by, bw - Math.max(0, LABEL_W - bx), bh, 3);
      ctx.fill();
    });

    y += ROW_H;
  });

  // Spara radpositioner för klick/tooltip
  canvas._rows = rows;
  canvas._rowY = (() => {
    let yy = 0, ys = [];
    rows.forEach(r => { ys.push(yy); yy += r.type==='header'?22 : r.type==='gap'?SECTION_GAP : ROW_H; });
    return ys;
  })();
  canvas._from = from;
  canvas._totalSec = totalSec;
}

// Klick – expandera proc-rad
document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('gantt-canvas');
  const tip    = document.getElementById('gantt-tip');

  // ── Tooltip vid hovring ──────────────────────────────────────
  canvas.addEventListener('mousemove', e => {
    if (ganttDragging || !canvas._rows) { tip.style.display='none'; return; }
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const from = new Date(document.getElementById('gantt-from').value);

    let found = null;
    canvas._rows.forEach((row, i) => {
      if (row.type === 'header' || row.type === 'gap') return;
      const ry = canvas._rowY[i];
      if (my < ry || my >= ry + ROW_H) return;

      if (mx <= LABEL_W) {
        // Hovring på label
        const d = row.data;
        if (row.type === 'proc') {
          found = d.process_name + (d.total_sec ? ' · ' + fmtDur(d.total_sec) : '');
        } else {
          const path = truncatePath(d.url || d.exe_path || '');
          found = d.window_title + (path ? '\n' + path : '');
        }
      } else {
        // Hovring på stapel
        const timelineX = x => LABEL_W + ganttOffsetX + x * ganttScale;
        const periods = row.data.periods || [];
        for (const p of periods) {
          const ps = (new Date(p.started_at) - from) / 1000;
          const pe = (new Date(p.ended_at)   - from) / 1000;
          const bx = timelineX(ps);
          const bw = Math.max(2, (pe - ps) * ganttScale);
          if (mx >= Math.max(LABEL_W, bx) && mx <= bx + bw) {
            const st = new Date(p.started_at).toTimeString().slice(0,5);
            const en = new Date(p.ended_at).toTimeString().slice(0,5);
            found = `${st} – ${en}  (${fmtDur(p.duration_sec)})`;
            if (row.type === 'title') found = row.data.window_title + '\n' + found;
            break;
          }
        }
      }
    });

    if (found) {
      tip.style.display = 'block';
      tip.style.left = (e.clientX + 14) + 'px';
      tip.style.top  = (e.clientY + 14) + 'px';
      tip.innerText  = found;
    } else {
      tip.style.display = 'none';
    }
  });

  canvas.addEventListener('mouseleave', () => { tip.style.display = 'none'; });

  canvas.addEventListener('click', e => {
    if (!canvas._rows) return;
    const rect = canvas.getBoundingClientRect();
    const my = e.clientY - rect.top;
    const mx = e.clientX - rect.left;
    if (mx > LABEL_W) return;
    canvas._rows.forEach((row, i) => {
      const ry = canvas._rowY[i];
      if (row.type === 'proc' && my >= ry && my < ry + ROW_H) {
        const pn = row.data.process_name;
        if (ganttExpandedRows.has(pn)) ganttExpandedRows.delete(pn);
        else ganttExpandedRows.add(pn);
        drawGantt();
      }
    });
  });

  // Drag för panorering (horisontellt) – behålls men offset nollställs vid loadGantt
  canvas.addEventListener('mousedown', e => {
    if (e.clientX - canvas.getBoundingClientRect().left <= LABEL_W) return;
    ganttDragging = true;
    ganttDragStartX = e.clientX;
    ganttDragStartOffset = ganttOffsetX;
    canvas.style.cursor = 'grabbing';
  });
  window.addEventListener('mousemove', e => {
    if (!ganttDragging) return;
    ganttOffsetX = ganttDragStartOffset + (e.clientX - ganttDragStartX);
    drawGantt();
  });
  window.addEventListener('mouseup', () => {
    ganttDragging = false;
    const canvas = document.getElementById('gantt-canvas');
    if (canvas) canvas.style.cursor = 'grab';
  });

});


// ── AI-chat ────────────────────────────────────────────────────
let aiChatHistory = [];
let aiStreaming   = false;

const AI_HISTORY_KEY = 'at-ai-questions';
const AI_HISTORY_MAX = 12;

function loadAiQuestionHistory() {
  try { return JSON.parse(localStorage.getItem(AI_HISTORY_KEY) || '[]'); }
  catch(e) { return []; }
}

function saveAiQuestion(text) {
  const q = text.trim();
  if (!q || q.length < 5) return;
  let hist = loadAiQuestionHistory().filter(h => h !== q);
  hist.unshift(q);
  if (hist.length > AI_HISTORY_MAX) hist = hist.slice(0, AI_HISTORY_MAX);
  localStorage.setItem(AI_HISTORY_KEY, JSON.stringify(hist));
  renderAiRecentSuggestions();
}

function renderAiRecentSuggestions() {
  const hist = loadAiQuestionHistory();
  const wrap = document.getElementById('ai-suggestions-recent-wrap');
  const list = document.getElementById('ai-suggestions-recent');
  if (!hist.length) { wrap.style.display = 'none'; return; }
  wrap.style.display = 'block';
  list.innerHTML = hist.slice(0, 6).map(q =>
    `<button class="ai-suggestion recent" onclick="aiSuggest(this)">${escHtml(q)}</button>`
  ).join('');
}

function clearAiHistory() {
  localStorage.removeItem(AI_HISTORY_KEY);
  renderAiRecentSuggestions();
}

function loadAiSettings() {
  try {
    const s = JSON.parse(localStorage.getItem('at-ai-settings') || '{}');
    if (s.provider) document.getElementById('ai-provider').value = s.provider;
    if (s.model)    document.getElementById('ai-model').value    = s.model;
    if (s.api_key)  document.getElementById('ai-api-key').value  = s.api_key;
    onProviderChange(false);
  } catch(e) {}
  renderAiRecentSuggestions();
}

function saveAiSettings() {
  const s = {
    provider: document.getElementById('ai-provider').value,
    model:    document.getElementById('ai-model').value,
    api_key:  document.getElementById('ai-api-key').value,
  };
  localStorage.setItem('at-ai-settings', JSON.stringify(s));
  const btn = document.querySelector('[onclick="saveAiSettings()"]');
  const orig = btn.textContent;
  btn.textContent = '✓ Sparat';
  setTimeout(() => btn.textContent = orig, 1500);
}

function onProviderChange(save) {
  const p = document.getElementById('ai-provider').value;
  const badge = document.getElementById('ai-privacy-badge');
  const keyWrap = document.getElementById('ai-apikey-wrap');
  const refreshBtn = document.getElementById('ai-refresh-btn');
  if (p === 'ollama') {
    badge.className = 'ai-provider-badge local'; badge.textContent = '🔒 Lokalt';
    keyWrap.style.display = 'none';
    refreshBtn.style.display = '';
    refreshOllamaModels();
  } else {
    badge.className = 'ai-provider-badge cloud'; badge.textContent = '☁ Moln';
    keyWrap.style.display = 'flex';
    refreshBtn.style.display = 'none';
    const modelSel = document.getElementById('ai-model');
    modelSel.innerHTML = `
      <option value="claude-haiku-4-5-20251001">Haiku 4.5 (snabb/billig)</option>
      <option value="claude-sonnet-4-6">Sonnet 4.6 (bäst)</option>`;
  }
}

async function refreshOllamaModels() {
  const sel = document.getElementById('ai-model');
  const saved = localStorage.getItem('at-ai-settings');
  const savedModel = saved ? JSON.parse(saved).model : '';
  const r = await fetch('/api/ai/models');
  const d = await r.json();
  if (d.ok && d.models.length) {
    sel.innerHTML = d.models.map(m =>
      `<option value="${m}" ${m===savedModel?'selected':''}>${m}</option>`).join('');
  } else {
    sel.innerHTML = '<option value="llama3.2">llama3.2</option><option value="llama3.1:8b">llama3.1:8b</option><option value="mistral">mistral</option>';
    if (savedModel) sel.value = savedModel;
  }
}

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function aiKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAiMessage(); }
}

function aiSuggest(btn) {
  document.getElementById('ai-input').value = btn.textContent.trim();
  sendAiMessage();
}

function appendAiMessage(role, text, streaming) {
  const wrap = document.getElementById('ai-messages');
  const div = document.createElement('div');
  div.className = `ai-msg ${role}`;
  const label = role === 'user' ? 'Du' : 'Maj-Britt';
  div.innerHTML = `<span class="ai-role">${label}</span><div class="ai-bubble${streaming?' streaming':''}">${escHtml(text)}</div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  return div.querySelector('.ai-bubble');
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

const aiFeedbackData = [];

async function sendFeedback(id, vote, btn) {
  const data = aiFeedbackData[id];
  if (!data) return;
  const wrap = btn.closest('.ai-feedback');
  const btns = wrap.querySelectorAll('button');
  btns.forEach(b => { b.disabled = true; b.style.opacity = '0.3'; });
  btn.style.opacity = '1';
  btn.classList.add(vote === 1 ? 'voted-up' : 'voted-down');
  try {
    await fetch('/api/ai/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...data, vote}),
    });
  } catch(e) {}
}

async function sendAiMessage() {
  if (aiStreaming) return;
  const input = document.getElementById('ai-input');
  const text  = input.value.trim();
  if (!text) return;

  const settings = JSON.parse(localStorage.getItem('at-ai-settings') || '{}');
  const provider = document.getElementById('ai-provider').value;
  const model    = document.getElementById('ai-model').value;
  const api_key  = document.getElementById('ai-api-key').value;

  if (provider === 'anthropic' && !api_key) {
    alert('Ange din Anthropic API-nyckel i inställningarna ovan.');
    return;
  }

  input.value = ''; input.style.height = 'auto';
  saveAiQuestion(text);
  aiChatHistory.push({role: 'user', content: text});
  appendAiMessage('user', text, false);

  aiStreaming = true;
  document.getElementById('ai-send-btn').disabled = true;
  input.disabled = true;

  const bubble = appendAiMessage('assistant', 'Tänker\u2026', true);
  let fullText = '';

  try {
    const resp = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider, model, api_key, messages: aiChatHistory}),
    });

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const chunk = JSON.parse(line.slice(6));
          if (chunk.text) {
            if (!fullText) bubble.innerHTML = '';
            fullText += chunk.text;
            bubble.innerHTML = escHtml(fullText);
            document.getElementById('ai-messages').scrollTop = 9999;
          }
        } catch(e) {}
      }
    }
  } catch(e) {
    fullText = '⚠️ Fel: ' + e.message;
    bubble.innerHTML = escHtml(fullText);
  }

  bubble.classList.remove('streaming');
  aiChatHistory.push({role: 'assistant', content: fullText});

  // Lägg till 👍👎 om vi fick ett svar (inte ett felmeddelande)
  if (fullText && !fullText.startsWith('⚠️')) {
    const exchangeId = aiFeedbackData.length;
    aiFeedbackData.push({question: text, answer: fullText, provider, model});
    const fb = document.createElement('div');
    fb.className = 'ai-feedback';
    fb.innerHTML =
      `<button onclick="sendFeedback(${exchangeId},1,this)" title="Bra svar">👍</button>` +
      `<button onclick="sendFeedback(${exchangeId},-1,this)" title="D\u00e5ligt svar">👎</button>`;
    bubble.parentElement.appendChild(fb);
  }

  aiStreaming = false;
  document.getElementById('ai-send-btn').disabled = false;
  input.disabled = false;
  input.focus();
}

// ── Program-filter ─────────────────────────────────────────────
let allPrograms = null;
const FILTER_VIEWS = ['dashboard','live','apps','gantt'];
const progFilters = {};
FILTER_VIEWS.forEach(v => {
  try {
    const saved = localStorage.getItem('at-prog-filter-' + v);
    progFilters[v] = saved ? new Set(JSON.parse(saved)) : new Set();
  } catch(e) { progFilters[v] = new Set(); }
});

function saveProgFilter(v) {
  localStorage.setItem('at-prog-filter-' + v, JSON.stringify([...progFilters[v]]));
  updateProgFilterBadge(v);
}

function updateProgFilterBadge(v) {
  const el = document.getElementById('prog-filter-count-' + v);
  if (!el) return;
  const n = progFilters[v].size;
  el.innerHTML = n > 0 ? `<span class="prog-filter-badge">-${n}</span>` : '';
}

function isProgVisible(v, name) {
  return !progFilters[v].has(name);
}

async function openProgFilter(view) {
  document.querySelectorAll('.prog-filter-panel').forEach(p => {
    if (p.id !== 'prog-filter-' + view) p.style.display = 'none';
  });
  const panel = document.getElementById('prog-filter-' + view);
  if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  if (!allPrograms) {
    const r = await fetch('/api/all_programs');
    allPrograms = await r.json();
  }
  renderProgFilterList(view);
  panel.style.display = 'block';
}

function renderProgFilterList(view) {
  const list = document.getElementById('prog-filter-list-' + view);
  if (!list || !allPrograms) return;
  list.innerHTML = allPrograms.map(p => {
    const checked = !progFilters[view].has(p);
    const safe = p.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
    return `<label class="prog-filter-item">
      <input type="checkbox" ${checked?'checked':''} onchange="onProgFilterChange(event,'${view}','${safe}')">
      <span>${p}</span>
    </label>`;
  }).join('');
}

function onProgFilterChange(e, view, prog) {
  e.stopPropagation();
  if (e.target.checked) progFilters[view].delete(prog);
  else progFilters[view].add(prog);
  saveProgFilter(view);
  reloadView(view);
}

function selectAllProgs(view, show) {
  if (show) progFilters[view] = new Set();
  else if (allPrograms) progFilters[view] = new Set(allPrograms);
  saveProgFilter(view);
  renderProgFilterList(view);
  reloadView(view);
}

function reloadView(view) {
  const fns = { dashboard: loadDashboard, live: loadLive, apps: loadApps, gantt: loadGantt };
  if (fns[view]) fns[view]();
}

document.addEventListener('click', e => {
  if (!e.target.closest('.prog-filter-btn'))
    document.querySelectorAll('.prog-filter-panel').forEach(p => p.style.display = 'none');
});

async function loadSessions() {
  const r=await fetch('/api/sessions');
  const d=await r.json();
  document.getElementById('sessions-body').innerHTML = d.map(s=>{
    const dur=s.started_at&&s.ended_at?Math.round((new Date(s.ended_at)-new Date(s.started_at))/1000):null;
    return `<tr>
      <td class="mono">${s.id}</td>
      <td class="mono">${fmtTs(s.started_at)}</td>
      <td class="mono">${s.ended_at?fmtTs(s.ended_at):'<span style="color:var(--green)">● Aktiv</span>'}</td>
      <td class="mono">${fmtDur(dur)}</td>
      <td class="mono">${s.period_count.toLocaleString()}</td>
    </tr>`;
  }).join('');
}
</script>
</body>
</html>"""


LIVE_PATH = Path.home() / "activity_tracker" / "live.json"


@app.route("/api/live")
def api_live():
    try:
        data = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
        return jsonify(data)
    except Exception:
        return jsonify({"updated_at": None, "entries": []})


def date_filter(from_date, to_date):
    f = from_date or "1970-01-01"
    t = to_date   or "2099-12-31"
    return "p.started_at >= ? AND p.started_at < date(?, '+1 day')", (f, t)


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/dashboard")
def api_dashboard():
    from_date = request.args.get("from","")
    to_date   = request.args.get("to","")
    df, params = date_filter(from_date, to_date)
    db = get_db()

    total_active = db.execute(f"SELECT COALESCE(SUM(p.duration_sec),0) FROM periods p WHERE {df} AND p.is_active=1", params).fetchone()[0]
    total_open   = db.execute(f"SELECT COALESCE(SUM(p.duration_sec),0) FROM periods p WHERE {df}", params).fetchone()[0]
    unique_apps  = db.execute(f"SELECT COUNT(DISTINCT p.process_name) FROM periods p WHERE {df}", params).fetchone()[0]
    total_per    = db.execute(f"SELECT COUNT(*) FROM periods p WHERE {df}", params).fetchone()[0]

    top_apps = db.execute(
        f"SELECT p.process_name, SUM(p.duration_sec) as total_sec FROM periods p WHERE {df} AND p.is_active=1 GROUP BY p.process_name ORDER BY total_sec DESC LIMIT 15",
        params
    ).fetchall()

    hourly = db.execute(
        f"""SELECT CAST(strftime('%H', p.started_at) AS INTEGER) as hour,
            SUM(p.duration_sec) as total_sec
            FROM periods p WHERE {df} AND date(p.started_at)=date('now','localtime')
            GROUP BY hour ORDER BY hour""",
        params
    ).fetchall()

    db.close()
    return jsonify({
        "total_active_sec": total_active,
        "total_open_sec":   total_open,
        "unique_apps":      unique_apps,
        "total_periods":    total_per,
        "top_apps":         [dict(r) for r in top_apps],
        "hourly":           [dict(r) for r in hourly],
    })


@app.route("/api/periods")
def api_periods():
    from_date = request.args.get("from","")
    to_date   = request.args.get("to","")
    search    = request.args.get("search","")
    active    = request.args.get("active","")
    sort_col  = request.args.get("sort","started_at")
    sort_dir  = request.args.get("dir","desc")
    page      = max(1, int(request.args.get("page",1)))
    limit     = int(request.args.get("limit",50))
    offset    = (page-1)*limit

    allowed = {"started_at","ended_at","duration_sec","process_name","is_active"}
    if sort_col not in allowed: sort_col="started_at"
    if sort_dir not in ("asc","desc"): sort_dir="desc"

    df, base = date_filter(from_date, to_date)
    clauses=[df]; p=list(base)

    if search:
        clauses.append("p.process_name LIKE ?")
        p.append(f"%{search}%")
    if active in ("0","1"):
        clauses.append("p.is_active=?"); p.append(int(active))

    where=" AND ".join(clauses)
    db=get_db()
    total = db.execute(f"SELECT COUNT(*) FROM periods p WHERE {where}", p).fetchone()[0]
    rows  = db.execute(
        f"SELECT p.process_name, p.window_title, p.url, p.exe_path, p.started_at, p.ended_at, p.duration_sec, p.is_active FROM periods p WHERE {where} ORDER BY {sort_col} {sort_dir} LIMIT {limit} OFFSET {offset}",
        p
    ).fetchall()
    db.close()
    return jsonify({"total": total, "rows": [dict(r) for r in rows]})


@app.route("/api/app_titles")
def api_app_titles():
    proc      = request.args.get("proc","")
    from_date = request.args.get("from","")
    to_date   = request.args.get("to","")
    active    = request.args.get("active","")
    df, params = date_filter(from_date, to_date)
    clauses = [df, "p.process_name = ?"]
    p = list(params) + [proc]
    if active in ("0","1"):
        clauses.append("p.is_active=?"); p.append(int(active))
    where = " AND ".join(clauses)
    db = get_db()
    rows = db.execute(
        f"SELECT p.window_title, MAX(p.url) as url, MAX(p.exe_path) as exe_path, SUM(p.duration_sec) as total_sec, COUNT(*) as cnt FROM periods p WHERE {where} AND p.window_title IS NOT NULL AND p.window_title != '' GROUP BY p.window_title ORDER BY total_sec DESC LIMIT 50",
        p
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/apps")
def api_apps():
    from_date = request.args.get("from","")
    to_date   = request.args.get("to","")
    active    = request.args.get("active","")
    df, params = date_filter(from_date, to_date)
    clauses=[df]; p=list(params)
    if active in ("0","1"):
        clauses.append("p.is_active=?"); p.append(int(active))
    where=" AND ".join(clauses)
    db=get_db()
    rows=db.execute(
        f"SELECT p.process_name, SUM(p.duration_sec) as total_sec, COUNT(*) as period_count, MAX(p.ended_at) as last_seen FROM periods p WHERE {where} GROUP BY p.process_name ORDER BY total_sec DESC",
        p
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/gantt")
def api_gantt():
    from_str = request.args.get("from","")
    to_str   = request.args.get("to","")
    if not from_str or not to_str:
        return jsonify([])

    db = get_db()
    # Hämta alla perioder inom intervallet
    rows = db.execute(
        "SELECT process_name, window_title, url, exe_path, started_at, ended_at, duration_sec, is_active "
        "FROM periods WHERE started_at >= ? AND ended_at <= ? ORDER BY started_at",
        (from_str, to_str)
    ).fetchall()
    db.close()

    # Gruppera per process_name
    from collections import defaultdict
    procs = defaultdict(lambda: {"periods":[], "titles": defaultdict(lambda: {"periods":[],"is_active":0}), "has_active":0})

    for r in rows:
        pn = r["process_name"]
        period = {"started_at": r["started_at"], "ended_at": r["ended_at"], "duration_sec": r["duration_sec"]}
        procs[pn]["periods"].append(period)
        if r["is_active"]:
            procs[pn]["has_active"] = 1
        title = r["window_title"] or ""
        if title:
            procs[pn]["titles"][title]["periods"].append(period)
            procs[pn]["titles"][title]["is_active"] = max(
                procs[pn]["titles"][title]["is_active"], r["is_active"]
            )
            if r["url"]:
                procs[pn]["titles"][title]["url"] = r["url"]
            if r["exe_path"]:
                procs[pn]["titles"][title]["exe_path"] = r["exe_path"]

    result = []
    for pn, data in sorted(procs.items(), key=lambda x: -sum(p["duration_sec"] for p in x[1]["periods"])):
        titles = [{"window_title": t, "periods": v["periods"],
                   "is_active": v["is_active"],
                   "url": v.get("url"), "exe_path": v.get("exe_path"),
                   "total_sec": sum(p["duration_sec"] for p in v["periods"])}
                  for t, v in data["titles"].items()]
        titles.sort(key=lambda x: -x["total_sec"])
        result.append({
            "process_name": pn,
            "periods":      data["periods"],
            "titles":       titles,
            "has_active":   data["has_active"],
            "total_sec":    sum(p["duration_sec"] for p in data["periods"]),
        })
    return jsonify(result)


@app.route("/api/all_programs")
def api_all_programs():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT process_name FROM periods WHERE process_name IS NOT NULL AND process_name != '' ORDER BY process_name"
    ).fetchall()
    db.close()
    return jsonify([r["process_name"] for r in rows])


@app.route("/api/sessions")
def api_sessions():
    db=get_db()
    rows=db.execute("""
        SELECT s.id, s.started_at, s.ended_at, COUNT(p.id) as period_count
        FROM sessions s LEFT JOIN periods p ON p.session_id=s.id
        GROUP BY s.id ORDER BY s.id DESC LIMIT 100
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/export")
def api_export():
    from_date=request.args.get("from","")
    to_date=request.args.get("to","")
    search=request.args.get("search","")
    active=request.args.get("active","")
    df,base=date_filter(from_date,to_date)
    clauses=[df]; p=list(base)
    if search: clauses.append("p.process_name LIKE ?"); p.append(f"%{search}%")
    if active in ("0","1"): clauses.append("p.is_active=?"); p.append(int(active))
    where=" AND ".join(clauses)
    db=get_db()
    rows=db.execute(f"SELECT p.process_name, p.started_at, p.ended_at, p.duration_sec, p.is_active, p.exe_path FROM periods p WHERE {where} ORDER BY p.started_at DESC", p).fetchall()
    db.close()
    out=io.StringIO()
    w=csv.writer(out)
    w.writerow(["Program","Start","Slut","Längd (sek)","Aktivt fönster","EXE-sökväg"])
    for r in rows: w.writerow(list(r))
    return Response(out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=perioder_{from_date}_{to_date}.csv"})


# System-processer som inte representerar faktiskt arbete
_NOISE_PROCS = {
    "lockapp.exe", "startmenuexperiencehost.exe", "applicationframehost.exe",
    "shellhost.exe", "searchhost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "sihost.exe", "runtimebroker.exe", "ctfmon.exe",
    "dwm.exe", "taskhostw.exe", "svchost.exe", "unknown",
}

# Läsvänliga namn för vanliga processer
_FRIENDLY = {
    "chrome.exe":            "Chrome",
    "msedge.exe":            "Edge",
    "firefox.exe":           "Firefox",
    "code.exe":              "VS Code",
    "windowsterminal.exe":   "Terminal",
    "explorer.exe":          "Utforskaren",
    "ms-teams.exe":          "Teams",
    "teams.exe":             "Teams",
    "outlook.exe":           "Outlook",
    "olk.exe":               "Outlook",
    "winword.exe":           "Word",
    "excel.exe":             "Excel",
    "powerpnt.exe":          "PowerPoint",
    "visio.exe":             "Visio",
    "onenote.exe":           "OneNote",
    "foxitpdfreader.exe":    "Foxit PDF",
    "acrord32.exe":          "Adobe PDF",
    "slack.exe":             "Slack",
    "discord.exe":           "Discord",
    "zoom.exe":              "Zoom",
    "mstsc.exe":             "Remote Desktop",
    "devenv.exe":            "Visual Studio",
    "rider64.exe":           "Rider",
    "pycharm64.exe":         "PyCharm",
    "idea64.exe":            "IntelliJ",
    "notepad++.exe":         "Notepad++",
    "notepad.exe":           "Notepad",
    "chatgpt.exe":           "ChatGPT",
    "githubdesktop.exe":     "GitHub Desktop",
    "tcxaeshell.exe":        "TwinCAT/TcXaeShell",
    "nacvpn.exe":            "VPN",
}

DAYS_SV = ["Måndag","Tisdag","Onsdag","Torsdag","Fredag","Lördag","Söndag"]


def friendly_name(proc):
    return _FRIENDLY.get(proc.lower(), proc)


def _clean_title(title, proc):
    """Tar bort onödigt suffix från fönsterrubrik."""
    if not title:
        return None
    suffixes = [
        " - Google Chrome", " - Mozilla Firefox", " - Microsoft Edge",
        " - Visual Studio Code", " - Foxit PDF Reader",
        " - Visio Professional", " - Visio",
        " - Word", " - Excel", " - PowerPoint",
        " | Microsoft Teams",
    ]
    t = title.strip()
    for s in suffixes:
        if t.endswith(s):
            t = t[:-len(s)]
            break
    # Skippa titlar som är identiska med programnamnet eller är ointressanta
    skip = {"", "microsoft teams", "chatt", "standardlåsskärm för windows",
            "activity tracker"}
    if t.lower() in skip:
        return None
    return t


_PROJECT_RE = re.compile(r'P\d{4,6}', re.IGNORECASE)


def extract_projects(db, since_days=7):
    """Identifierar projektnummer ur sökvägar och fönsterrubriker."""
    from collections import defaultdict
    two_weeks_ago = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
    rows = db.execute("""
        SELECT url, window_title, SUM(duration_sec) as secs
        FROM periods
        WHERE date(started_at) >= ? AND is_active=1
          AND (url IS NOT NULL OR window_title IS NOT NULL)
        GROUP BY url, window_title
    """, (two_weeks_ago,)).fetchall()

    projects = defaultdict(lambda: {"secs": 0, "names": set()})
    for r in rows:
        found = set()
        for text in [r["url"] or "", r["window_title"] or ""]:
            for m in _PROJECT_RE.findall(text):
                found.add(m.upper())
        for proj in found:
            projects[proj]["secs"] += r["secs"]
            # Försök extrahera projektnamn ur sökvägen (mappen efter projektnumret)
            if r["url"]:
                m = re.search(rf'{proj}[,\s_-]+([^\\\/]+)', r["url"], re.IGNORECASE)
                if m:
                    name = m.group(1).strip().rstrip(',').strip()
                    if name:
                        projects[proj]["names"].add(name)

    return sorted(projects.items(), key=lambda x: -x[1]["secs"])


def build_ai_context(db):
    today = datetime.now()
    two_weeks_ago = (today - timedelta(days=6)).strftime("%Y-%m-%d")

    # Programtid per dag
    rows = db.execute("""
        SELECT date(started_at) as day, process_name, SUM(duration_sec) as secs
        FROM periods
        WHERE date(started_at) >= ? AND is_active=1 AND process_name IS NOT NULL
        GROUP BY day, process_name
        ORDER BY day DESC, secs DESC
    """, (two_weeks_ago,)).fetchall()

    from collections import defaultdict
    by_day = defaultdict(list)
    for r in rows:
        if r["process_name"].lower() not in _NOISE_PROCS:
            by_day[r["day"]].append((r["process_name"], r["secs"]))

    # Fönsterrubriker per dag+program
    title_rows = db.execute("""
        SELECT date(started_at) as day, process_name, window_title,
               MAX(url) as url, SUM(duration_sec) as secs
        FROM periods
        WHERE date(started_at) >= ? AND is_active=1
          AND window_title IS NOT NULL AND window_title != ''
        GROUP BY day, process_name, window_title
        ORDER BY day DESC, secs DESC
    """, (two_weeks_ago,)).fetchall()

    # by_titles[day][proc] = [(title, secs, path), ...]
    by_titles = defaultdict(lambda: defaultdict(list))
    for r in title_rows:
        if r["process_name"].lower() in _NOISE_PROCS:
            continue
        t = _clean_title(r["window_title"], r["process_name"])
        if t:
            # Extrahera meningsfull sökväg (skippa exe-sökvägar och tomma)
            path = r["url"] or ""
            if path and "\\Program Files" in path:
                path = ""
            if path and "\\AppData\\Local\\Temp" in path:
                path = ""
            by_titles[r["day"]][r["process_name"]].append((t, r["secs"], path))

    today_str = today.strftime("%Y-%m-%d")
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday  = this_monday - timedelta(days=1)

    def week_summary(start, end):
        """Summerar arbetsdagar (mån–fre) i ett datumintervall."""
        totals = defaultdict(int)
        day_count = 0
        cur = start
        while cur <= end:
            day_str = cur.strftime("%Y-%m-%d")
            if cur.weekday() < 5 and day_str in by_day:
                day_count += 1
                for proc, secs in by_day[day_str]:
                    totals[friendly_name(proc)] += secs
            cur += timedelta(days=1)
        if not totals:
            return None, 0
        ranked = sorted(totals.items(), key=lambda x: -x[1])
        total_min = round(sum(totals.values()) / 60)
        parts = [f"{p}: {round(s/60)}min" for p, s in ranked[:8]]
        return parts, total_min

    this_week_parts, this_week_total = week_summary(this_monday, today)
    last_week_parts, last_week_total = week_summary(last_monday, last_sunday)

    # Projektsummering
    projects = extract_projects(db, since_days=6)

    lines = [
        "=== KONTEXT FÖR MAJ-BRITT ===",
        f"Idag: {today_str} ({DAYS_SV[today.weekday()]})",
        "",
    ]

    if projects:
        lines.append("PROJEKT (senaste 7 dagarna, identifierade ur sökvägar och titlar):")
        for proj_id, data in projects:
            names = ", ".join(sorted(data["names"])[:2])
            name_str = f" – {names}" if names else ""
            lines.append(f"  {proj_id}{name_str}: {round(data['secs']/60)}min")
        lines.append("")

    # Sammanfattning idag
    today_apps = by_day.get(today_str, [])
    if today_apps:
        today_total = round(sum(s for _, s in today_apps) / 60)
        today_parts = [f"{friendly_name(a[0])}: {round(a[1]/60)}min" for a in today_apps[:10]]
        lines += [
            f"IDAG ({today_str}, {DAYS_SV[today.weekday()]}, {today_total}min aktivt):",
            "  " + ", ".join(today_parts),
            "",
        ]
    else:
        lines += ["IDAG: ingen data ännu.", ""]

    # Sammanfattning innevarande vecka (mån–idag, exkl. helg)
    if this_week_parts:
        lines += [
            f"INNEVARANDE VECKA ({this_monday.strftime('%Y-%m-%d')} – {today_str}, arbetsdagar, {this_week_total}min totalt):",
            "  " + ", ".join(this_week_parts),
            "",
        ]

    # Sammanfattning förra veckan (mån–fre)
    if last_week_parts:
        lines += [
            f"FÖRRA VECKAN ({last_monday.strftime('%Y-%m-%d')} – {last_sunday.strftime('%Y-%m-%d')}, {last_week_total}min totalt):",
            "  " + ", ".join(last_week_parts),
            "",
        ]

    # Daglig rådata med fönsterrubriker
    lines.append("DAGLIG RÅDATA MED DOKUMENT/TITLAR (inkl. helger):")
    for day in sorted(by_day.keys(), reverse=True):
        apps = by_day[day]
        if not apps:
            continue
        total_min = round(sum(s for _, s in apps) / 60)
        d = datetime.strptime(day, "%Y-%m-%d")
        weekday = DAYS_SV[d.weekday()]
        is_weekend = d.weekday() >= 5
        weekend_note = " [helg]" if is_weekend else ""
        label = " <- IDAG" if day == today_str else ""
        lines.append(f"  {day} ({weekday}{weekend_note}, {total_min}min){label}:")
        for proc, secs in apps[:10]:
            fname = friendly_name(proc)
            proc_min = round(secs / 60)
            titles = by_titles[day].get(proc, [])
            # Topp 5 titlar, skippa dubletter (samma titel, mer tid)
            seen = set()
            top_titles = []
            for t, ts, path in sorted(titles, key=lambda x: -x[1]):
                key = t.lower()[:60]
                if key not in seen:
                    seen.add(key)
                    entry = f"{t} ({round(ts/60)}min)"
                    if path:
                        entry += f" [sökväg: {path}]"
                    top_titles.append(entry)
                if len(top_titles) >= 5:
                    break
            if top_titles:
                lines.append(f"    {fname} ({proc_min}min):")
                for tt in top_titles:
                    lines.append(f"      - {tt}")
            else:
                lines.append(f"    {fname} ({proc_min}min)")

    return "\n".join(lines)


SYSTEM_PROMPT = """Du heter Maj-Britt och är en personlig produktivitetsassistent som analyserar datoranvändning.

Data du får visar hur många minuter per dag användaren haft olika program AKTIVT I FÖRGRUNDEN på sin Windows-dator.

VIKTIGA REGLER:
1. Svara ALLTID på svenska.
2. Datumet märkt "← IDAG" är dagens datum. Använd BARA den raden när du svarar på frågor om "idag".
3. "Innevarande vecka" = dagarna från och med den markerade veckomåndagen t.o.m. idag.
4. Dagar märkta [helg] är lördag/söndag – räkna dem INTE som arbetsdagar om inte användaren frågar specifikt.
5. Var konkret – nämn faktiska programnamn och tider.
6. Håll svaren korta (3–6 meningar) om inte mer detaljer efterfrågas.
7. Om data saknas för en dag eller period, säg det rakt ut.

PROGRAMTOLKNING:
- Chrome/Edge/Firefox = webbläsare (research, webbappar, mail-i-browser)
- Teams/Zoom/Slack = möten och kommunikation
- VS Code/Terminal/Visual Studio = programmering/kodning
- Excel/Word/PowerPoint/Visio/OneNote = Office-arbete
- Foxit PDF/Adobe PDF = läser dokument
- Outlook/olk.exe = e-post
- TwinCAT/TcXaeShell = industriell automationsprogrammering
- Remote Desktop/mstsc = arbete på annan dator
- ChatGPT = AI-assistans
- GitHub Desktop = versionshantering
- Utforskaren = filhantering

PROJEKTNUMMER: I kontexten finns en PROJEKT-sektion med projektnummer (t.ex. P25080) och tid.
Använd dessa när du svarar på frågor om projekt. Om användaren frågar vilket projekt de jobbat
med, referera till projektnumret och dess namn om det finns."""


def stream_ollama(messages, model, context):
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}] + messages
    payload = json.dumps({"model": model, "messages": full_messages, "stream": True}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                try:
                    chunk = json.loads(line.decode())
                    text = chunk.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if chunk.get("done"):
                        break
                except Exception:
                    pass
    except urllib.error.URLError:
        yield "\n\n⚠️ Kunde inte ansluta till Ollama. Kör `ollama serve` i terminalen."


def stream_anthropic(messages, model, api_key, context):
    payload = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT + "\n\n" + context,
        "messages": messages,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line = line.decode().strip()
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content_block_delta":
                            text = chunk.get("delta", {}).get("text", "")
                            if text:
                                yield text
                    except Exception:
                        pass
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        yield f"\n\n⚠️ Anthropic-fel: {msg}"
    except urllib.error.URLError as e:
        yield f"\n\n⚠️ Nätverksfel: {e.reason}"


@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    data      = request.get_json()
    provider  = data.get("provider", "ollama")
    model     = data.get("model", "llama3.2")
    api_key   = data.get("api_key", "")
    messages  = data.get("messages", [])

    db = get_db()
    context = build_ai_context(db)
    db.close()

    def generate():
        if provider == "anthropic":
            gen = stream_anthropic(messages, model, api_key, context)
        else:
            gen = stream_ollama(messages, model, context)
        for text in gen:
            yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: {\"done\": true}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


BACKEND_URL    = "https://activity-tracker-lyyh.onrender.com"
FEEDBACK_EMAIL = "activity.testapp@gmail.com"


@app.route("/api/diagnostics")
def api_diagnostics():
    import sys
    import platform

    # RAM via psutil
    ram_total_gb = ram_free_gb = "okänd"
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        ram_total_gb = f"{vm.total / 1_073_741_824:.1f}"
        ram_free_gb  = f"{vm.available / 1_073_741_824:.1f}"
    except Exception:
        pass

    # Ollama igång?
    ollama_running = False
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        ollama_running = True
    except Exception:
        pass

    # Tracker aktiv?
    tracker_running = False
    try:
        live = Path.home() / "activity_tracker" / "live.json"
        import time
        if live.exists() and (time.time() - live.stat().st_mtime) < 30:
            tracker_running = True
    except Exception:
        pass

    # Senaste fel ur tray.log
    last_error = None
    try:
        log_path = Path.home() / "activity_tracker" / "tray.log"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            errors = [l for l in lines if "ERROR" in l or "CRITICAL" in l]
            last_error = errors[-1] if errors else None
    except Exception:
        pass

    return jsonify({
        "app_version":     VERSION,
        "os_version":      platform.version(),
        "python_version":  sys.version.split()[0],
        "ram_total_gb":    ram_total_gb,
        "ram_free_gb":     ram_free_gb,
        "ollama_running":  ollama_running,
        "tracker_running": tracker_running,
        "last_error":      last_error,
    })


@app.route("/api/config")
def api_config():
    cfg = load_config()
    return jsonify({
        "token":         cfg.get("token", ""),
        "user_name":     cfg.get("user_name", ""),
        "user_email":    cfg.get("user_email", ""),
        "version":        VERSION,
        "backend_ready":  bool(BACKEND_URL),
        "feedback_email": FEEDBACK_EMAIL,
    })


@app.route("/api/register", methods=["POST"])
def api_register():
    if not BACKEND_URL:
        return jsonify({"ok": False, "error": "Backend inte konfigurerad ännu"}), 503
    data  = request.get_json()
    name  = data.get("name", "").strip()
    email = data.get("email", "").strip()
    try:
        payload = json.dumps({"name": name, "email": email}).encode()
        req = urllib.request.Request(
            f"{BACKEND_URL}/register",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502
    if result.get("ok"):
        cfg = load_config()
        cfg.update({"token": result["token"], "user_name": name, "user_email": email})
        save_config(cfg)
    return jsonify(result)



@app.route("/api/ai/feedback", methods=["POST"])
def api_ai_feedback():
    data = request.get_json()
    vote = data.get("vote")
    if vote not in (1, -1):
        return jsonify({"ok": False, "error": "invalid vote"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO ai_feedback (created_at, question, answer, provider, model, vote) VALUES (?,?,?,?,?,?)",
        (datetime.now().isoformat(),
         data.get("question", ""),
         data.get("answer", ""),
         data.get("provider", ""),
         data.get("model", ""),
         vote)
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/api/ai/models")
def api_ai_models():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            return jsonify({"ok": True, "models": models})
    except Exception:
        return jsonify({"ok": False, "models": []})


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


def _wake_backend():
    """Pingatar backenden tyst så att Render hinner vakna innan användaren registrerar sig."""
    if not BACKEND_URL:
        return
    try:
        urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=60)
    except Exception:
        pass


def run(port=5757):
    print(f"[Activity Tracker] Webb-gränssnitt: http://localhost:{port}")
    threading.Thread(target=_wake_backend, daemon=True, name="backend-wake").start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
