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
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, Response

try:
    import tracker as _tracker
except ImportError:
    _tracker = None

try:
    import planner as _planner
except ImportError:
    _planner = None

try:
    import geotracker as _geotracker
except ImportError:
    _geotracker = None

try:
    import screenshot_watcher as _screenshot_watcher
except ImportError:
    _screenshot_watcher = None

# Projektkodsmönster: Göteborg (P/S + 5 siffror) och Stockholm (I/SI/SP + 5 siffror)
_PS_CODE_RE = re.compile(r'\b(?:SI|SP|[IPS])\d{5}(?!\d)')

# Webbläsarprocesser – synkroniserat med tracker.py
BROWSER_PROCS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}

VERSION         = "v0.31b"
DB_PATH         = Path.home() / "activity_tracker" / "activity.db"
CONFIG_PATH     = Path.home() / "activity_tracker" / "app_config.json"
PLAN_CACHE_PATH = Path.home() / "activity_tracker" / "planning_cache.json"
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

/* ── Light theme (Oaks warm) ── */
[data-theme="light"] {
  --bg:      #F5EFE0;
  --surface: #FBF8F0;
  --border:  #DDD3BE;
  --accent:  #9A7400;
  --accent2: #C0392B;
  --green:   #4A7C59;
  --muted:   #7A6F5C;
  --text:    #2C3535;
  --grid-color: rgba(154,116,0,.05);
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
  background:var(--surface);border:1px solid var(--border);border-radius:6px;
  padding:8px 12px;font-size:11px;font-family:var(--mono);
  color:var(--text);white-space:nowrap;max-width:600px;overflow:hidden;text-overflow:ellipsis;
  box-shadow:0 4px 20px rgba(0,0,0,.2);pointer-events:none;
}
.has-tooltip:hover .tip{display:block}

/* Projektsammanfattning */
.proj-summary{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:14px 18px;margin-bottom:20px;display:none}
.proj-summary.visible{display:block}
.proj-summary-header{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}
.proj-summary-title{font-size:13px;font-weight:700;color:var(--accent)}
.proj-summary-total{font-size:20px;font-weight:800;color:var(--accent)}
.proj-summary-sub{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-left:6px}
.proj-summary-row{display:flex;align-items:center;gap:10px;padding:3px 0}
.proj-summary-label{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.proj-summary-bar{flex:1.2;height:4px;background:var(--border);border-radius:2px;overflow:hidden}
.proj-summary-fill{height:100%;background:var(--accent);border-radius:2px;transition:width .3s}
.proj-summary-dur{font-size:11px;font-family:var(--mono);color:var(--text);white-space:nowrap;width:52px;text-align:right}

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

/* Veckoetiketter bredvid datumfält */
.wk-hint{font-size:11px;color:var(--muted);font-family:var(--mono);margin-left:3px;white-space:nowrap}

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
    <!-- Maj-Britt dold tills AI-motor är beslutad -->
    <div class="nav-item" data-page="feedback" onclick="showPage(this)"><span class="nav-icon">✉</span> Feedback<button class="nav-help" onclick="event.stopPropagation();showHelp('feedback')" title="Hjälp">?</button></div>
    <div class="nav-item" data-page="plansettings" onclick="showPage(this)"><span class="nav-icon">⚙</span> Inställningar<button class="nav-help" onclick="event.stopPropagation();showHelp('plansettings')" title="Hjälp">?</button></div>
    <div class="sidebar-footer"><span class="status-dot"></span>Tracker aktiv</div>
  </div>
</nav>
<div id="sidebar-toggle" onclick="toggleSidebar()">◀</div>

<!-- Gantt canvas tooltip -->
<div id="gantt-tip" style="display:none;position:fixed;z-index:999;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:11px;font-family:var(--mono);color:var(--text);pointer-events:none;max-width:400px;white-space:nowrap;box-shadow:0 4px 20px rgba(0,0,0,.2)"></div>

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
      <label>Från</label><input type="date" id="dash-from"><span class="wk-hint" id="dash-from-wk"></span>
      <label>Till</label><input type="date" id="dash-to"><span class="wk-hint" id="dash-to-wk"></span>
      <button class="btn btn-primary" onclick="loadDashboard()">Uppdatera</button>
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('dash-from','dash-to','today',loadDashboard)">Idag</button>
        <button class="btn-quick" onclick="setQuick('dash-from','dash-to','yesterday',loadDashboard)">Igår</button>
        <button class="btn-quick" onclick="stepRange('dash',-1,loadDashboard)">←</button>
        <button class="btn-quick" id="dash-week-btn" onclick="setQuick('dash-from','dash-to','week',loadDashboard)">V?</button>
        <button class="btn-quick" onclick="stepRange('dash',1,loadDashboard)">→</button>
      </div>
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
      <label>Från</label><input type="date" id="per-from"><span class="wk-hint" id="per-from-wk"></span>
      <label>Till</label><input type="date" id="per-to"><span class="wk-hint" id="per-to-wk"></span>
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('per-from','per-to','today',()=>loadPeriods(1))">Idag</button>
        <button class="btn-quick" onclick="setQuick('per-from','per-to','yesterday',()=>loadPeriods(1))">Igår</button>
        <button class="btn-quick" onclick="stepRange('per',-1,()=>loadPeriods(1))">←</button>
        <button class="btn-quick" id="per-week-btn" onclick="setQuick('per-from','per-to','week',()=>loadPeriods(1))">V?</button>
        <button class="btn-quick" onclick="stepRange('per',1,()=>loadPeriods(1))">→</button>
      </div>
      <label>Sök</label><input type="text" id="per-search" placeholder="program..." style="width:180px">
      <select id="per-active">
        <option value="">Alla</option>
        <option value="1">Aktivt fönster</option>
        <option value="0">Bakgrund</option>
      </select>
      <select id="per-project" onchange="loadPeriods(1)" title="Filtrera på projekt">
        <option value="">Alla projekt</option>
      </select>
      <button class="btn btn-primary" onclick="loadPeriods(1)">Sök</button>
      <button class="btn btn-ghost" onclick="exportCSV()">↓ CSV</button>
    </div>
    <div class="proj-summary" id="per-proj-summary"></div>
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
      <label>Från</label><input type="date" id="apps-from"><span class="wk-hint" id="apps-from-wk"></span>
      <label>Till</label><input type="date" id="apps-to"><span class="wk-hint" id="apps-to-wk"></span>
      <button class="btn btn-primary" onclick="loadApps()">Uppdatera</button>
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('apps-from','apps-to','today',loadApps)">Idag</button>
        <button class="btn-quick" onclick="setQuick('apps-from','apps-to','yesterday',loadApps)">Igår</button>
        <button class="btn-quick" onclick="stepRange('apps',-1,loadApps)">←</button>
        <button class="btn-quick" id="apps-week-btn" onclick="setQuick('apps-from','apps-to','week',loadApps)">V?</button>
        <button class="btn-quick" onclick="stepRange('apps',1,loadApps)">→</button>
      </div>
      <select id="apps-active" onchange="loadApps()">
        <option value="">Aktivt + bakgrund</option>
        <option value="1">Bara aktivt fönster</option>
        <option value="0">Bara bakgrund</option>
      </select>
      <select id="apps-project" onchange="loadApps()" title="Filtrera på projekt">
        <option value="">Alla projekt</option>
      </select>
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
    <div class="proj-summary" id="apps-proj-summary"></div>
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
      <label>Från</label><input type="datetime-local" id="gantt-from"><span class="wk-hint" id="gantt-from-wk"></span>
      <label>Till</label><input type="datetime-local" id="gantt-to"><span class="wk-hint" id="gantt-to-wk"></span>
      <button class="btn btn-primary" onclick="loadGantt()">Uppdatera</button>
      <div class="quick-dates">
        <button class="btn-quick" onclick="setQuick('gantt-from','gantt-to','today',loadGantt,true)">Idag</button>
        <button class="btn-quick" onclick="setQuick('gantt-from','gantt-to','yesterday',loadGantt,true)">Igår</button>
        <button class="btn-quick" onclick="stepGantt(-1)">←</button>
        <button class="btn-quick" id="gantt-week-btn" onclick="setQuick('gantt-from','gantt-to','week',loadGantt,true)">V?</button>
        <button class="btn-quick" onclick="stepGantt(1)">→</button>
      </div>
      <select id="gantt-project" onchange="loadGantt(); if(teamPlanningData) renderTeamPlanning(teamPlanningData, this.value);" title="Filtrera på projekt">
        <option value="">Alla projekt</option>
      </select>
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
    <div class="proj-summary" id="gantt-proj-summary"></div>
    <div id="gantt-outer" style="border:1px solid var(--border);border-radius:var(--r);background:var(--surface);overflow:hidden">
      <!-- Sticky tidsaxel -->
      <div style="position:sticky;top:0;z-index:10;background:var(--surface)">
        <svg id="gantt-header" style="display:block;overflow:hidden"></svg>
      </div>
      <!-- Scrollbar rad-innehåll -->
      <div id="gantt-wrap" style="overflow-y:auto;overflow-x:hidden;max-height:60vh">
        <svg id="gantt-svg" style="display:block;cursor:grab;overflow:hidden"></svg>
      </div>
    </div>
    <div style="margin-top:12px;font-size:11px;color:var(--muted);font-family:var(--mono)">
      Klicka på en rad för att expandera titlar &nbsp;·&nbsp; Dra för att panorera &nbsp;·&nbsp;
      <span style="display:inline-block;width:12px;height:8px;background:var(--accent);border-radius:2px;vertical-align:middle"></span> Aktivt &nbsp;
      <span style="display:inline-block;width:12px;height:8px;background:var(--muted);border-radius:2px;vertical-align:middle;opacity:.5"></span> Bakgrund
    </div>
    <div id="gantt-detail" style="margin-top:16px"></div>

    <!-- Tidsredovisningsförslag -->
    <div id="time-report-section" style="display:none;margin-top:32px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;cursor:pointer" onclick="toggleSection('time-report')">
        <span id="time-report-arrow" style="font-size:11px;color:var(--muted);transition:transform .2s">▶</span>
        <h3 style="margin:0;font-size:15px">Tidsredovisning</h3>
        <span style="font-size:11px;color:var(--muted)">Förslag baserat på aktiv och passiv tid – upprundat till närmaste halvtimme</span>
      </div>
      <div id="time-report-body" style="display:none">
        <div id="time-report-table"></div>
      </div>
    </div>

    <!-- Teamplanering -->
    <div id="team-section" style="display:none;margin-top:32px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;cursor:pointer" onclick="toggleSection('team')">
        <span id="team-arrow" style="font-size:11px;color:var(--muted);transition:transform .2s">▶</span>
        <h3 id="team-section-title" style="margin:0;font-size:15px">Planering</h3>
        <button onclick="event.stopPropagation();loadTeamPlanning()" class="btn-secondary" style="padding:5px 14px;font-size:12px">⟳ Ladda</button>
      </div>
      <div id="team-body" style="display:none">
        <div id="team-gantt"></div>
      </div>
    </div>

    <!-- Besökta platser -->
    <div id="geo-section" style="display:none;margin-top:32px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;cursor:pointer" onclick="toggleSection('geo')">
        <span id="geo-arrow" style="font-size:11px;color:var(--muted);transition:transform .2s">▶</span>
        <h3 style="margin:0;font-size:15px">Besökta platser</h3>
        <span id="geo-section-status" style="font-size:11px;color:var(--muted)"></span>
      </div>
      <div id="geo-body" style="display:none">
        <div id="geo-locations"></div>
      </div>
    </div>
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
            <option value="openai">OpenAI / ChatGPT</option>
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

      <!-- Varning: ingen AI konfigurerad -->
      <div id="ai-no-source" style="display:none;margin-top:12px;padding:14px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);font-size:13px">
        <div style="font-weight:600;margin-bottom:6px;color:var(--text)">Ingen AI-källa konfigurerad</div>
        <div style="color:var(--muted);line-height:1.6">
          Välj ett av alternativen för att använda Maj-Britt:<br>
          <b>Ollama (lokalt)</b> – gratis, kör på din dator.
          Ladda ner på <a href="https://ollama.com" target="_blank" style="color:var(--accent)">ollama.com</a>,
          installera och kör sedan <code style="font-family:var(--mono);background:var(--bg);padding:1px 5px;border-radius:3px">ollama pull llama3.2</code>.<br>
          <b>OpenAI / ChatGPT</b> – kräver API-nyckel från
          <a href="https://platform.openai.com/api-keys" target="_blank" style="color:var(--accent)">platform.openai.com</a>.
          Välj OpenAI i listan ovan och klistra in nyckeln.
        </div>
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

  <!-- ── Inställningar ─────────────────────────────────────────── -->
  <div id="page-plansettings" class="page">
    <h1>Inställningar</h1><p class="subtitle">Anpassa Activity Tracker</p>
    <div style="max-width:560px">

      <h3 style="margin:0 0 8px;font-size:15px">Kontor</h3>
      <p style="color:var(--muted);font-size:13px;margin:0 0 14px">
        Välj vilket kontor du tillhör. Inställningen används för att anpassa projektigenkänning.
      </p>
      <div style="margin-bottom:8px">
        <select id="office-select" onchange="saveOfficeSettings()"
          style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
          padding:8px 12px;color:var(--text);font-size:13px">
          <option value="goteborg">Göteborg</option>
          <option value="stockholm">Stockholm</option>
        </select>
      </div>
      <span id="office-save-status" style="font-size:12px;color:var(--muted)"></span>

      <hr style="border:none;border-top:1px solid var(--border);margin:32px 0">

      <h3 style="margin:0 0 8px;font-size:15px">Resursplanering</h3>
      <p style="color:var(--muted);font-size:13px;margin:0 0 20px">
        Koppla Activity Tracker mot Oaks Resursplanering för att se planerade aktiviteter
        i Tidslinje-fliken. Filen hämtas automatiskt från din OneDrive-synk baserat på kontorsvalet ovan.
      </p>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
        <label class="toggle-label">
          <input type="checkbox" id="plan-enabled" onchange="savePlanSettings()">
          <span>Aktivera resursplanering</span>
        </label>
      </div>
      <div id="plan-fields">
        <input id="plan-file" type="hidden">

        <div id="plan-file-found" style="display:none;margin-bottom:14px">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Planeringsfil</label>
          <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg);
            border:1px solid var(--border);border-radius:var(--r)">
            <span style="color:#4caf50;flex-shrink:0">✓</span>
            <span id="plan-file-path" style="font-size:12px;color:var(--muted);overflow:hidden;
              text-overflow:ellipsis;white-space:nowrap"></span>
          </div>
        </div>

        <div id="plan-file-missing" style="display:none;margin-bottom:14px">
          <div style="padding:10px 14px;background:var(--bg);border:1px solid var(--border);
            border-radius:var(--r);font-size:12px;color:var(--muted);margin-bottom:10px">
            ⚠ Planeringsfil hittades inte – kontrollera att SharePoint-biblioteket är synkat i OneDrive.
          </div>
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Ange sökväg manuellt</label>
          <input id="plan-file-manual" type="text" placeholder="C:\Users\...\Oaks Resursplanering.xlsm"
            style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
            padding:8px 12px;color:var(--text);font-size:13px;box-sizing:border-box">
        </div>

        <div style="margin-bottom:14px">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Ditt namn i filen (RESURS-kolumnen)</label>
          <input id="plan-resource" type="text" placeholder="Förnamn Efternamn"
            style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
            padding:8px 12px;color:var(--text);font-size:13px;box-sizing:border-box">
        </div>
        <button onclick="savePlanSettings()" class="btn-primary" style="padding:8px 20px">Spara</button>
        <span id="plan-status" style="font-size:12px;color:var(--muted)"></span>
      </div>

      <hr style="border:none;border-top:1px solid var(--border);margin:32px 0">

      <h3 style="margin:0 0 8px;font-size:15px">Skärmklipp – automatisk namngivning</h3>
      <p style="color:var(--muted);font-size:13px;margin:0 0 20px">
        Döper automatiskt om nya skärmdumpar i din Screenshots-mapp med det aktiva fönstrets namn och en tidsstämpel.
      </p>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
        <label class="toggle-label">
          <input type="checkbox" id="screenshot-enabled" onchange="saveScreenshotSettings()">
          <span>Aktivera automatisk namngivning av skärmdumpar</span>
        </label>
      </div>
      <span id="screenshot-save-status" style="font-size:12px;color:var(--muted)"></span>

      <hr style="border:none;border-top:1px solid var(--border);margin:32px 0">

      <h3 style="margin:0 0 8px;font-size:15px">Platsloggning</h3>
      <p style="color:var(--muted);font-size:13px;margin:0 0 6px">
        Loggar din position med jämna mellanrum och visar en reslinje i Tidslinje-fliken.
        Kan hjälpa till med registrering av resor och utgifter.
      </p>
      <p style="color:var(--muted);font-size:12px;margin:0 0 20px;padding:10px 14px;
        background:var(--bg);border:1px solid var(--border);border-radius:var(--r)">
        🔒 Platser lagras bara lokalt på din dator. Inget skickas någonstans.
        Ny position loggas bara när du förflyttat dig mer än ~150 meter.
      </p>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
        <label class="toggle-label">
          <input type="checkbox" id="geo-enabled" onchange="saveGeoSettings()">
          <span>Aktivera platsloggning</span>
        </label>
        <span id="geo-status-dot" style="font-size:12px;color:var(--muted)"></span>
      </div>
      <div id="geo-fields">
        <div style="margin-bottom:14px">
          <label style="font-size:12px;color:var(--muted);display:block;margin-bottom:6px">Loggningsintervall</label>
          <select id="geo-interval" onchange="saveGeoSettings()"
            style="background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
            padding:8px 12px;color:var(--text);font-size:13px">
            <option value="1">Var 1:e minut</option>
            <option value="5" selected>Var 5:e minut</option>
            <option value="15">Var 15:e minut</option>
            <option value="30">Var 30:e minut</option>
          </select>
        </div>
        <span id="geo-save-status" style="font-size:12px;color:var(--muted)"></span>
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
    savePref(fromId, document.getElementById(fromId).value);
    savePref(toId,   document.getElementById(toId).value);
    updateWkHint(fromId); updateWkHint(toId);
    loadFn();
  } else if (preset === 'yesterday') {
    const y = daysAgo(1);
    document.getElementById(fromId).value = isDatetime ? y+'T00:00' : y;
    document.getElementById(toId).value   = isDatetime ? y+'T23:59' : y;
    savePref(fromId, document.getElementById(fromId).value);
    savePref(toId,   document.getElementById(toId).value);
    updateWkHint(fromId); updateWkHint(toId);
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
  savePref(fromId, document.getElementById(fromId).value);
  savePref(toId,   document.getElementById(toId).value);
  updateWkHint(fromId); updateWkHint(toId);

  const wn = weekNumber(mon);
  const btn = document.getElementById(section + '-week-btn');
  if (btn) btn.textContent = 'V' + wn;

  loadFn();
}

function stepWeek(section, dir, loadFn, isDatetime) {
  weekOffset[section] = (weekOffset[section] || 0) + dir;
  applyWeek(section, weekOffset[section], loadFn, isDatetime);
}

function stepRange(section, dir, loadFn) {
  const fromEl = document.getElementById(section + '-from');
  const toEl   = document.getElementById(section + '-to');
  const from   = new Date(fromEl.value);
  const to     = new Date(toEl.value);
  const isSingleDay = (to - from) <= 3600 * 25 * 1000;
  const days = isSingleDay ? 1 : 7;
  from.setDate(from.getDate() + dir * days);
  to.setDate(to.getDate()   + dir * days);
  const isDatetime = fromEl.type === 'datetime-local';
  fromEl.value = isDatetime ? ganttDatetimeLocal(from) : from.toISOString().slice(0, 10);
  toEl.value   = isDatetime ? ganttDatetimeLocal(to)   : to.toISOString().slice(0, 10);
  savePref(section + '-from', fromEl.value);
  savePref(section + '-to',   toEl.value);
  updateWkHint(section + '-from'); updateWkHint(section + '-to');
  weekOffset[section] = isSingleDay ? 0 : (weekOffset[section] || 0) + dir;
  const [wFrom] = isoWeek(from);
  const [wTo]   = isoWeek(to);
  const wkBtn = document.getElementById(section + '-week-btn');
  if (wkBtn) wkBtn.textContent = wFrom === wTo ? 'V' + wFrom : 'V' + wFrom + '–' + wTo;
  loadFn();
}

function stepGantt(dir) { stepRange('gantt', dir, loadGantt); }

function showPage(el) {
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('page-'+el.dataset.page).classList.add('active');
  localStorage.setItem('at-page', el.dataset.page);
  if (liveInterval) { clearInterval(liveInterval); liveInterval=null; }
  if(el.dataset.page==='dashboard') loadDashboard();
  if(el.dataset.page==='live')      { loadLive(); liveInterval=setInterval(loadLive,5000); }
  if(el.dataset.page==='periods')   loadPeriods(1);
  if(el.dataset.page==='apps')      loadApps();
  if(el.dataset.page==='sessions')  loadSessions();
  if(el.dataset.page==='gantt')     { loadGantt(); autoLoadPlanning(); }
  if(el.dataset.page==='ai')        loadAiSettings();
}

// ── Veckoetiketter bredvid datumfält ──────────────────────────
function updateWkHint(inputId) {
  const el = document.getElementById(inputId);
  const sp = document.getElementById(inputId + '-wk');
  if (!el || !sp || !el.value) { if (sp) sp.textContent = ''; return; }
  const [w] = isoWeek(new Date(el.value));
  sp.textContent = 'V' + w;
}
function updateAllWkHints() {
  ['dash-from','dash-to','per-from','per-to','apps-from','apps-to','gantt-from','gantt-to']
    .forEach(updateWkHint);
}

// ── Inställningspersistens ─────────────────────────────────────
function savePref(k, v) { try { localStorage.setItem('at-pref-' + k, v); } catch(e) {} }
function loadPref(k)    { return localStorage.getItem('at-pref-' + k); }

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
    const tipW = tip.offsetWidth || 200;
    const overflowsRight = (e.clientX + 12 + tipW) > window.innerWidth;
    tip.style.left = overflowsRight ? (e.clientX - tipW - 8) + 'px' : (e.clientX + 12) + 'px';
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
  // Återställ sparade vyinställningar (override defaults ovan)
  ['dash-from','dash-to','per-from','per-to','per-search','per-active','per-project',
   'apps-from','apps-to','apps-active','apps-project','gantt-from','gantt-to','gantt-project'
  ].forEach(id => {
    const v = loadPref(id);
    const el = document.getElementById(id);
    if (v !== null && el) el.value = v;
  });
  // Spara vid framtida ändringar (dropdowns + sökfält)
  ['per-active','per-project','apps-active','apps-project','gantt-project'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => savePref(id, el.value));
  });
  document.getElementById('per-search')?.addEventListener('input', e => savePref('per-search', e.target.value));
  // Datumfält: spara och uppdatera vecko­etikett vid manuell redigering
  ['dash-from','dash-to','per-from','per-to','apps-from','apps-to','gantt-from','gantt-to'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => { savePref(id, el.value); updateWkHint(id); });
  });
  updateAllWkHints();
  FILTER_VIEWS.forEach(updateProgFilterBadge);
  // Återställ senast besökta sida (annars dashboard)
  const savedPage = localStorage.getItem('at-page') || 'dashboard';
  const savedNav = document.querySelector(`.nav-item[data-page="${savedPage}"]`);
  if (savedNav) showPage(savedNav); else loadDashboard();
  initRegistration();
  initPlanSettings();
  initOfficeSettings();
  initScreenshotSettings();
  initGeoSettings();
  initProjectDropdowns();
});

// ── Hjälp ──────────────────────────────────────────────────
const HELP = {
  dashboard: {
    title: '⬡ Dashboard',
    body: `
      <p>Ger dig en snabb överblick över din aktivitet för vald tidsperiod.</p>
      <ul>
        <li><strong>KPI-kort</strong> – total aktiv tid, antal program och sessioner</li>
        <li><strong>Topp program</strong> – stapeldiagram med mest använda program</li>
        <li><strong>Aktiv tid per timme</strong> – visar när på dagen du var aktiv</li>
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
        <li>Visar aktivt fönster och alla öppna program med pågående tid</li>
        <li>Program-filter döljer program du inte vill följa</li>
      </ul>`,
  },
  periods: {
    title: '◷ Perioder',
    body: `
      <p>Detaljerad lista över alla registrerade aktivitetsperioder.</p>
      <ul>
        <li>Sök på programnamn eller fönstertext</li>
        <li>Filtrera på datum, projekt, program och aktiv/bakgrund</li>
        <li>Sortera på valfri kolumn</li>
        <li>Exportera till CSV via knappen uppe till höger</li>
        <li>Projektsammanfattningskort visas när ett projekt är valt</li>
      </ul>`,
  },
  apps: {
    title: '◫ Program',
    body: `
      <p>Sammanställning av total tid per program för vald period.</p>
      <ul>
        <li>Filtrera på projekt för att se tid kopplad till ett specifikt projekt</li>
        <li>Växla mellan aktivt fönster, bakgrund eller båda</li>
        <li>Expandera en rad för att se fönsterrubriker och klickbara URL:er</li>
        <li>Program-filter exkluderar program du inte vill räkna med</li>
      </ul>`,
  },
  sessions: {
    title: '≡ Sessioner',
    body: `
      <p>En session är en sammanhängande arbetsperiod – från att du sätter dig vid datorn till att du låser den eller stänger av.</p>
      <ul>
        <li>Visar start, slut, total tid och antal perioder per session</li>
        <li>Hjälper dig se hur länge du jobbade utan avbrott</li>
        <li>Nya sessioner skapas automatiskt efter viloläge</li>
      </ul>`,
  },
  gantt: {
    title: '▤ Tidslinje',
    body: `
      <p>Visar din aktivitet som ett Gantt-diagram. Nedanför diagrammet finns tre kollapsbara sektioner.</p>
      <ul>
        <li>Varje rad är ett program, varje block är en period – hovra för detaljer</li>
        <li>Klicka på en rad för att se fönsterrubriker</li>
        <li>Dra i diagrammet för att panorera; klicka på ett datum i tidsaxeln för att zooma till den dagen</li>
        <li>Filtrera på projekt eller program</li>
      </ul>
      <p><strong>Tidsredovisning</strong> – förslag på tid per projekt och dag, upprundat till närmaste halvtimme.</p>
      <p><strong>Planering</strong> – teamets resursplanering från Oaks Excel-fil.</p>
      <p><strong>Besökta platser</strong> – GPS-loggning om platsspårning är aktiverat i Inställningar.</p>`,
  },
  ai: {
    title: '◈ Maj-Britt',
    body: `
      <p>Din personliga AI-assistent som känner till din aktivitetsdata.</p>
      <ul>
        <li>Ställ frågor om din arbetstid, projekt och vanor</li>
        <li><strong>Ollama</strong> – lokal AI, gratis, all data stannar på datorn</li>
        <li><strong>OpenAI / ChatGPT</strong> – kräver API-nyckel, data skickas till OpenAI</li>
        <li><strong>Anthropic Claude</strong> – kräver API-nyckel, data skickas till Anthropic</li>
        <li>Ge tumme upp/ner på svaren för att hjälpa Maj-Britt bli bättre</li>
      </ul>
      <p>Välj källa och modell i inställningarna överst på sidan.</p>`,
  },
  feedback: {
    title: '✉ Feedback',
    body: `
      <p>Skicka synpunkter, felrapporter eller idéer direkt till utvecklaren.</p>
      <ul>
        <li>Välj kategori – idé, fel, beröm eller övrigt</li>
        <li>Feedback skickas direkt via e-post utan att öppna din mailapp</li>
        <li>Diagnostikinformation bifogas automatiskt för att underlätta felsökning</li>
      </ul>`,
  },
  plansettings: {
    title: '⚙ Inställningar',
    body: `
      <p>Anpassa Activity Tracker efter dina behov.</p>
      <ul>
        <li><strong>Resursplanering</strong> – koppla mot Oaks Resursplanering.xlsm för att se planerade aktiviteter i Tidslinje-fliken. Ange sökväg och ditt namn i RESURS-kolumnen</li>
        <li><strong>Platsloggning</strong> – loggar din position via Windows Location API och visar besökta platser i Tidslinje-fliken. All data stannar lokalt på din dator</li>
      </ul>
      <p>Tema väljer du med knapparna uppe till höger. AI-källa väljer du i Maj-Britt-fliken.</p>`,
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

  const cfg  = await fetch('/api/config').then(r => r.json());
  const diag = await fetch('/api/diagnostics').then(r => r.json()).catch(() => null);

  status.textContent = 'Skickar…';

  if (cfg.backend_ready) {
    try {
      const resp = await fetch(`${BACKEND_URL}/feedback`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          token:       cfg.token || '',
          name:        cfg.user_name || '',
          email:       cfg.user_email || '',
          category,
          message,
          version:     cfg.version,
          diagnostics: diag || {},
        }),
      });
      const data = await resp.json();
      if (!data.ok) throw new Error(data.error || 'Okänt fel');
      document.getElementById('fb-message').value = '';
      status.style.color = 'var(--accent)';
      status.textContent = '✓ Feedback skickad – tack!';
      setTimeout(() => { status.textContent = ''; status.style.color = ''; }, 5000);
      return;
    } catch(e) {
      status.style.color = 'var(--accent2)';
      status.textContent = `Kunde inte nå servern (${e.message}) – öppnar mailapp istället`;
      setTimeout(() => { status.textContent = ''; status.style.color = ''; }, 6000);
    }
  }

  // Fallback: mailto
  const diagText = diag && !diag.error ? [
    '', '── Diagnostik ───────────────────',
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
  const body    = encodeURIComponent(
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
    <div class="kpi green"><div class="kpi-label">Tid vid datorn</div><div class="kpi-value">${fmtDur(d.total_unique_sec)}</div><div class="kpi-sub">unik tid, inkl. bakgrund</div></div>
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
  const _dpr = window.devicePixelRatio || 1;
  canvas.width = W * _dpr; canvas.height = H * _dpr;
  canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(_dpr, _dpr);
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
  const isUrl = url && (url.startsWith('http://') || url.startsWith('https://'));
  const tip   = isUrl ? url : truncatePath(exe || '');

  const linkIcon = isUrl
    ? ` <a href="${url}" target="_blank" rel="noopener"
           title="${url}"
           style="color:var(--accent);text-decoration:none;font-size:12px;flex-shrink:0"
           onclick="event.stopPropagation()">🔗</a>`
    : '';

  return `<td class="title-cell">
    <span class="has-tooltip" style="display:flex;align-items:center;gap:4px;overflow:hidden">
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${title||'—'}</span>
      ${linkIcon}
      ${tip && !isUrl ? `<span class="tip">${tip}</span>` : ''}
    </span>
  </td>`;
}

const BROWSER_PROCS = new Set(['chrome.exe','msedge.exe','firefox.exe','brave.exe','opera.exe']);

async function loadPeriods(page) {
  if(page<1) return;
  currentPage=page;
  const from=document.getElementById('per-from').value, to=document.getElementById('per-to').value;
  const search=document.getElementById('per-search').value, active=document.getElementById('per-active').value;
  const project=document.getElementById('per-project').value;
  const params=new URLSearchParams({from,to,search,active,project,sort:perSort,dir:perDir,page,limit:50});
  const [perResp, histResp] = await Promise.all([
    fetch('/api/periods?'+params),
    fetch(`/api/browser-history?from=${from}&to=${to}`),
  ]);
  const d    = await perResp.json();
  const hist = await histResp.json().catch(()=>({urls:[]}));

  // Bygg ett lookup: visited_at (sekund) → url för snabb matchning
  const urlByTime = {};
  for (const h of (hist.urls||[])) {
    const sec = h.visited_at.slice(0,19);
    urlByTime[sec] = h.url;
  }

  function browserUrl(row) {
    if (!BROWSER_PROCS.has((row.process_name||'').toLowerCase())) return null;
    const start = new Date(row.started_at).getTime();
    const end   = row.ended_at ? new Date(row.ended_at).getTime() : start;
    // Matcha URL:er besökta inom perioden (±30s marginal)
    const match = (hist.urls||[]).filter(h => {
      const t = new Date(h.visited_at).getTime();
      return t >= (start - 30000) && t <= (end + 30000);
    });
    if (!match.length) return null;
    return match[match.length-1].url;
  }

  document.getElementById('per-body').innerHTML = d.rows.map(row=>{
    const url = row.url || browserUrl(row);
    return `<tr>
      <td class="nowrap">${row.process_name||'—'}</td>
      ${titleCell(row.window_title, url, row.exe_path, row.process_name)}
      <td class="mono nowrap">${fmtTs(row.started_at)}</td>
      <td class="mono nowrap">${fmtTs(row.ended_at)}</td>
      <td class="mono nowrap">${fmtDur(row.duration_sec)}</td>
      <td><span class="badge ${row.is_active?'badge-active':'badge-bg'}">${row.is_active?'Aktivt':'Bakgrund'}</span></td>
    </tr>`;
  }).join('') || '<tr><td colspan="6" style="color:var(--muted);padding:20px;text-align:center">Inga resultat</td></tr>';

  const pages=Math.ceil(d.total/50);
  document.getElementById('per-pageinfo').textContent=`Sida ${page} / ${pages} (${d.total.toLocaleString()} perioder)`;
  document.getElementById('per-prev').disabled=page<=1;
  document.getElementById('per-next').disabled=page>=pages;
  if (page === 1) {
    refreshProjectDropdown('per-project', from, to);
    updateProjectSummary('per-proj-summary', document.getElementById('per-project').value, from, to);
  }
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

// ── Projektdropdown ────────────────────────────────────────────
async function updateProjectSummary(cardId, project, from, to) {
  const card = document.getElementById(cardId);
  if (!card) return;
  if (!project) { card.classList.remove('visible'); return; }
  const r = await fetch(`/api/project-summary?project=${encodeURIComponent(project)}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
  const d = await r.json();
  if (!d.ok || !d.total_sec) { card.classList.remove('visible'); return; }
  const maxSec = d.top_titles[0]?.sec || 1;
  const label = d.project_name ? `${d.project_num} – ${d.project_name}` : d.project_num;

  // Planerad tid: visa endast om exakt en hel vecka är vald och vi har planeringsdata
  let plannedHtml = '';
  const weekCode = selectedFullWeek();
  if (weekCode && planningData) {
    const plannedHours = planningData
      .filter(row => row.project.startsWith(project) && row.week === weekCode)
      .reduce((s, row) => s + row.hours, 0);
    if (plannedHours > 0) {
      const weekLabel = 'V ' + parseInt(weekCode.slice(3));
      plannedHtml = `
    <div class="proj-summary-row" style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">
      <span class="proj-summary-label" style="color:var(--muted)">Planerad tid ${weekLabel}</span>
      <div class="proj-summary-bar"><div class="proj-summary-fill" style="width:100%;background:var(--accent);opacity:0.4"></div></div>
      <span class="proj-summary-dur" style="color:var(--accent)">${plannedHours}h</span>
    </div>`;
    }
  }

  card.innerHTML = `
    <div class="proj-summary-header">
      <span class="proj-summary-title">${label}</span>
      <span><span class="proj-summary-total">${fmtDur(d.total_sec)}</span><span class="proj-summary-sub">förgrundstid</span></span>
    </div>
    ${d.top_titles.map(t => `
    <div class="proj-summary-row">
      <span class="proj-summary-label" title="${t.title}">${t.title}</span>
      <div class="proj-summary-bar"><div class="proj-summary-fill" style="width:${(t.sec/maxSec*100).toFixed(1)}%"></div></div>
      <span class="proj-summary-dur">${fmtDur(t.sec)}</span>
    </div>`).join('')}${plannedHtml}`;
  card.classList.add('visible');
}

async function refreshProjectDropdown(dropdownId, from, to) {
  const url = (from && to)
    ? `/api/active-projects?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
    : '/api/active-projects';
  const d = await fetch(url).then(r => r.json()).catch(() => null);
  if (!d?.ok) return;
  const sel = document.getElementById(dropdownId);
  if (!sel) return;
  const current = sel.value;
  while (sel.options.length > 1) sel.remove(1);
  for (const p of d.projects) {
    const opt = document.createElement('option');
    opt.value = p.number;
    opt.textContent = p.number;
    opt.title = p.name ? `${p.number} – ${p.name}` : p.number;
    sel.appendChild(opt);
  }
  // Återställ val om projektet fortfarande finns i listan
  if (current && [...sel.options].some(o => o.value === current)) sel.value = current;
}

async function initProjectDropdowns() {
  // Initialt: ladda alla kända projekt (utan datumfilter)
  await Promise.all([
    refreshProjectDropdown('per-project',  '', ''),
    refreshProjectDropdown('apps-project', '', ''),
    refreshProjectDropdown('gantt-project','', ''),
  ]);
}

// ── Program ────────────────────────────────────────────────────
async function loadApps() {
  const from=document.getElementById('apps-from').value, to=document.getElementById('apps-to').value;
  const active=document.getElementById('apps-active').value;
  const project=document.getElementById('apps-project').value;
  const r=await fetch(`/api/apps?from=${from}&to=${to}&active=${active}&project=${project}`);
  const d=await r.json();
  refreshProjectDropdown('apps-project', from, to);
  updateProjectSummary('apps-proj-summary', project, from, to);
  const visRows = d.filter(row => isProgVisible('apps', row.process_name));
  const maxSec = visRows[0]?.total_sec||1;

  document.getElementById('apps-body').innerHTML = visRows.map((row,i)=>`
    <tr>
      <td>${row.process_name||'—'}</td>
      <td>
        <div class="dur-bar">
          <div class="dur-track"><div class="dur-fill" style="width:${(row.total_sec/maxSec*100).toFixed(1)}%"></div></div>
          <span class="mono has-tooltip">${fmtDur(row.total_sec)}<span class="tip">Tid i förgrunden + bakgrunden</span></span>
        </div>
      </td>
      <td class="mono">${row.period_count}</td>
      <td class="mono has-tooltip">${fmtDur(Math.round(row.total_sec/row.period_count))}<span class="tip">Genomsnittlig period-längd</span></td>
      <td class="mono">${fmtTs(row.last_seen)}</td>
      <td><button class="btn btn-ghost" style="padding:3px 10px;font-size:10px" onclick="toggleTitles(this,'${encodeURIComponent(row.process_name)}','${from}','${to}','${active}','${project}')">▶ Titlar</button></td>
    </tr>
    <tr id="titles-${i}" style="display:none">
      <td colspan="6" style="padding:0 14px 12px 32px;background:rgba(0,0,0,.2)">
        <div id="titles-content-${i}" style="font-size:12px;color:var(--muted)"></div>
      </td>
    </tr>`).join('');
}

async function toggleTitles(btn, procEncoded, from, to, active, project='') {
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

  const isBrowser = BROWSER_PROCS.has(proc.toLowerCase());
  const [titlesResp, histResp] = await Promise.all([
    fetch(`/api/app_titles?proc=${encodeURIComponent(proc)}&from=${from}&to=${to}&active=${active}&project=${project}`),
    isBrowser ? fetch(`/api/browser-history?from=${from}&to=${to}`) : Promise.resolve(null),
  ]);
  const titles = await titlesResp.json();
  const hist   = histResp ? await histResp.json().catch(()=>({urls:[]})) : {urls:[]};

  if (!titles.length) { content.textContent = 'Inga titlar hittades.'; return; }
  content.innerHTML = titles.map(t => {
    // Hitta URL som matchar titeln eller tidsintervallet
    let url = t.url;
    if (!url && isBrowser && hist.urls.length) {
      const match = hist.urls.find(h => h.title === t.window_title) ||
                    hist.urls.find(h => t.window_title && h.title && h.title.includes(t.window_title.replace(/ - Google Chrome| - Microsoft Edge/,'')));
      if (match) url = match.url;
    }
    const isUrl = url && (url.startsWith('http://') || url.startsWith('https://'));
    const tip   = isUrl ? '' : truncatePath(t.exe_path || '');

    return `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--border)">
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;display:flex;align-items:center;gap:6px">
        <span class="has-tooltip" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${t.window_title||'—'}
          ${tip ? `<span class="tip">${tip}</span>` : ''}
        </span>
        ${isUrl ? `<a href="${url}" target="_blank" rel="noopener" title="${url}"
             style="color:var(--accent);text-decoration:none;font-size:12px;flex-shrink:0"
             onclick="event.stopPropagation()">🔗</a>` : ''}
      </span>
      <span class="mono has-tooltip" style="margin-left:16px;flex-shrink:0;color:var(--accent)">${fmtDur(t.total_sec)}<span class="tip">${t.active_sec ? 'Förgrund: ' + fmtDur(t.active_sec) + (t.total_sec - t.active_sec > 0 ? ' / Bakgrund: ' + fmtDur(t.total_sec - t.active_sec) : '') : 'Tid i bakgrunden'}</span></span>
    </div>`;
  }).join('');
}

// ── Resursplanering ────────────────────────────────────────────

function _renderPlanFileUI(suggestedPath, savedFile) {
  const foundEl   = document.getElementById('plan-file-found');
  const missingEl = document.getElementById('plan-file-missing');
  const pathEl    = document.getElementById('plan-file-path');
  const hiddenEl  = document.getElementById('plan-file');
  if (!foundEl) return;
  if (suggestedPath) {
    hiddenEl.value          = suggestedPath;
    pathEl.textContent      = suggestedPath;
    foundEl.style.display   = 'block';
    missingEl.style.display = 'none';
  } else {
    foundEl.style.display   = 'none';
    missingEl.style.display = 'block';
    if (savedFile) document.getElementById('plan-file-manual').value = savedFile;
  }
}

async function initPlanSettings() {
  const [planCfg, officeCfg] = await Promise.all([
    fetch('/api/planning-config').then(r => r.json()),
    fetch('/api/office-config').then(r => r.json()),
  ]);
  document.getElementById('plan-enabled').checked = planCfg.enabled;
  document.getElementById('plan-resource').value  = planCfg.resource;
  _renderPlanFileUI(officeCfg.suggested_path, planCfg.file);
}

async function savePlanSettings() {
  const enabled  = document.getElementById('plan-enabled').checked;
  const resource = document.getElementById('plan-resource').value.trim();
  const status   = document.getElementById('plan-status');
  const manualEl = document.getElementById('plan-file-manual');
  const file = (manualEl && manualEl.closest('#plan-file-missing').style.display !== 'none')
    ? manualEl.value.trim()
    : document.getElementById('plan-file').value;
  await fetch('/api/planning-config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({enabled, file, resource}),
  });
  status.textContent = 'Sparat ✓';
  setTimeout(() => status.textContent = '', 2000);
}

async function autoLoadPlanning() {
  const cfg = await fetch('/api/planning-config').then(r => r.json());
  document.getElementById('team-section').style.display = cfg.enabled ? '' : 'none';
  if (cfg.enabled) {
    loadPlanning();
    if (!teamPlanningData) {
      loadTeamPlanning();
    } else {
      renderTeamPlanning(teamPlanningData, document.getElementById('gantt-project')?.value || '');
    }
  }

  const geoCfg = await fetch('/api/geo-config').then(r => r.json());
  document.getElementById('geo-section').style.display = geoCfg.enabled ? '' : 'none';
  if (geoCfg.enabled) loadGeoLocations();
}

function toggleSection(name) {
  const body  = document.getElementById(name + '-body');
  const arrow = document.getElementById(name + '-arrow');
  const open  = body.style.display === 'none';
  body.style.display  = open ? '' : 'none';
  arrow.style.transform = open ? 'rotate(90deg)' : '';
}

async function loadGeoLocations() {
  const from = document.getElementById('gantt-from').value?.slice(0, 10);
  const to   = document.getElementById('gantt-to').value?.slice(0, 10);
  const el   = document.getElementById('geo-locations');
  const status = document.getElementById('geo-section-status');
  el.textContent = 'Laddar…';

  const url = (from && to)
    ? `/api/geo-locations?from=${from}&to=${to}`
    : '/api/geo-locations';
  const d = await fetch(url).then(r => r.json()).catch(() => null);

  if (!d?.ok || !d.locations.length) {
    el.textContent = 'Inga loggade platser för perioden.';
    status.textContent = '';
    return;
  }

  const MAX_ACCURACY_M = 300;
  const locations = d.locations.filter(l => l.accuracy_m <= MAX_ACCURACY_M);
  const filtered  = d.locations.length - locations.length;
  status.textContent = `${locations.length} platser${filtered ? ` (${filtered} filtrerade)` : ''}`;

  const rows = [];
  let lastDay = null;
  const dayNames = ['sön','mån','tis','ons','tor','fre','lör'];

  locations.forEach((loc, i) => {
    const next   = locations[i + 1];
    const stayed = next
      ? fmtDur(Math.round((new Date(next.logged_at) - new Date(loc.logged_at)) / 1000))
      : '–';
    const t = new Date(loc.logged_at);
    const dayKey = t.toDateString();
    const time = String(t.getHours()).padStart(2,'0') + ':' + String(t.getMinutes()).padStart(2,'0');

    if (dayKey !== lastDay) {
      lastDay = dayKey;
      const dayLabel = `${dayNames[t.getDay()]} ${t.getDate()}/${t.getMonth()+1}`;
      rows.push(`<div style="font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.5px;padding:10px 0 4px">${dayLabel}</div>`);
    }

    rows.push(`<div style="display:flex;align-items:baseline;gap:12px;padding:6px 0;border-bottom:1px solid var(--border)">
      <span style="font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap">${time}</span>
      <span style="flex:1;font-size:13px">${(() => {
        if (!loc.address) return '(' + loc.latitude.toFixed(4) + ', ' + loc.longitude.toFixed(4) + ')';
        const parts = loc.address.split(',');
        const postcode = parts.length > 1 ? parts.pop().trim() : null;
        const main = parts.join(',').trim();
        return main + (postcode ? `<span style="font-size:11px;color:var(--muted);margin-left:5px">${postcode}</span>` : '');
      })()}</span>
      <span style="font-family:var(--mono);font-size:11px;color:var(--muted);white-space:nowrap" title="Tid till nästa position">${stayed}</span>
      <span style="font-size:10px;color:var(--muted);white-space:nowrap">±${Math.round(loc.accuracy_m)}m</span>
    </div>`);
  });

  el.innerHTML = `<div style="margin-top:8px">${rows.join('')}</div>`;
}

// ── Skärmklipp ─────────────────────────────────────────────────

async function initScreenshotSettings() {
  const cfg = await fetch('/api/screenshot-config').then(r => r.json());
  document.getElementById('screenshot-enabled').checked = cfg.enabled;
}

async function saveScreenshotSettings() {
  const enabled = document.getElementById('screenshot-enabled').checked;
  const status  = document.getElementById('screenshot-save-status');
  await fetch('/api/screenshot-config', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ enabled })
  });
  status.textContent = 'Sparat';
  setTimeout(() => status.textContent = '', 2000);
}

// ── Kontor ─────────────────────────────────────────────────────

function _applyOfficeSuggestedPath(cfg) {
  _renderPlanFileUI(cfg.suggested_path, null);
}

async function initOfficeSettings() {
  const cfg = await fetch('/api/office-config').then(r => r.json());
  document.getElementById('office-select').value = cfg.office || 'goteborg';
  _applyOfficeSuggestedPath(cfg);
}

async function saveOfficeSettings() {
  const office = document.getElementById('office-select').value;
  const status = document.getElementById('office-save-status');
  const cfg = await fetch('/api/office-config', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ office })
  }).then(r => r.json());
  _applyOfficeSuggestedPath(cfg);
  status.textContent = 'Sparat';
  setTimeout(() => status.textContent = '', 2000);
}

// ── Platsloggning ──────────────────────────────────────────────

async function initGeoSettings() {
  const cfg = await fetch('/api/geo-config').then(r => r.json());
  document.getElementById('geo-enabled').checked = cfg.enabled;
  document.getElementById('geo-interval').value  = cfg.interval || 5;
  _updateGeoStatusDot(cfg.enabled);
}

async function saveGeoSettings() {
  const enabled  = document.getElementById('geo-enabled').checked;
  const interval = parseInt(document.getElementById('geo-interval').value);
  const status   = document.getElementById('geo-save-status');
  await fetch('/api/geo-config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({enabled, interval}),
  });
  status.textContent = 'Sparat ✓';
  setTimeout(() => status.textContent = '', 2000);
  _updateGeoStatusDot(enabled);
}

function _updateGeoStatusDot(enabled) {
  const dot = document.getElementById('geo-status-dot');
  if (!dot) return;
  dot.textContent = enabled ? '● Aktiv' : '○ Inaktiv';
  dot.style.color = enabled ? 'var(--green)' : 'var(--muted)';
}

function isoWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return [Math.ceil(((d - yearStart) / 86400000 + 1) / 7), d.getUTCFullYear()];
}

function weekCodeFromDate(date) {
  const [w, y] = isoWeek(date);
  return 'V' + String(y % 100).padStart(2,'0') + String(w).padStart(2,'0');
}

// Returnerar veckkoden (t.ex. "V2615") om from–to är exakt en hel ISO-vecka, annars null.
function selectedFullWeek() {
  const fromVal = document.getElementById('gantt-from')?.value;
  const toVal   = document.getElementById('gantt-to')?.value;
  if (!fromVal || !toVal) return null;
  const f = new Date(fromVal), t = new Date(toVal);
  if (f.getDay() !== 1) return null;           // måste börja på måndag
  const days = (t - f) / (1000 * 3600 * 24);
  if (days < 6.9 || days > 7.1) return null;  // måste vara ~7 dagar
  return weekCodeFromDate(f);
}



async function loadPlanning() {
  const now  = new Date();
  const mon  = new Date(now); mon.setDate(now.getDate() - ((now.getDay()+6)%7));
  const from = new Date(mon); from.setDate(mon.getDate() - 14);
  const to   = new Date(mon); to.setDate(mon.getDate() + 62);
  const fmt  = d => d.toISOString().slice(0,10);

  const r = await fetch(`/api/planning?from=${fmt(from)}&to=${fmt(to)}`);
  const d = await r.json();
  if (!d.ok) return;
  planningData = d.rows;
}

async function loadTeamPlanning() {
  const gantt = document.getElementById('team-gantt');
  gantt.textContent = 'Laddar…';

  const now  = new Date();
  const mon  = new Date(now); mon.setDate(now.getDate() - ((now.getDay()+6)%7));
  const from = new Date(mon); from.setDate(mon.getDate() - 14);
  const to   = new Date(mon); to.setDate(mon.getDate() + 62);
  const fmt  = d => d.toISOString().slice(0,10);

  const r = await fetch(`/api/team-planning?from=${fmt(from)}&to=${fmt(to)}`);
  const d = await r.json();
  if (!d.ok) { gantt.textContent = d.error || 'Kunde inte ladda teamplanering'; return; }

  // Sätt dynamisk rubrik med gruppnamn
  const title = document.getElementById('team-section-title');
  if (title && d.group) title.textContent = 'Planering Grupp ' + d.group;

  teamPlanningData = d.rows;
  renderTeamPlanning(teamPlanningData, document.getElementById('gantt-project')?.value || '');
}

function renderTeamPlanning(rows, selectedProject) {
  const gantt = document.getElementById('team-gantt');
  if (!rows || !rows.length) { gantt.textContent = 'Inga planerade aktiviteter för teamet.'; return; }

  const workRows = selectedProject ? rows.filter(r => r.project.startsWith(selectedProject)) : rows;
  if (selectedProject && !workRows.length) {
    gantt.textContent = 'Inga planerade aktiviteter för valt projekt.';
    return;
  }

  const [curWeek, curISOYear] = isoWeek(new Date());
  const curWeekStr = 'V' + String(curISOYear % 100).padStart(2,'0') + String(curWeek).padStart(2,'0');
  const weeks   = [...new Set(workRows.map(r => r.week))].sort();
  const members = [...new Set(workRows.map(r => r.resource))].sort();
  const colW    = 70;

  const thWeeks = weeks.map(w => {
    const isCur = w === curWeekStr;
    return `<th style="padding:6px 4px;border-bottom:1px solid var(--border);text-align:center;width:${colW}px;white-space:nowrap;${isCur?'color:var(--accent);font-weight:700':'color:var(--muted);font-weight:400'}">V ${parseInt(w.slice(3))}${isCur?' ◀':''}</th>`;
  }).join('');

  // ── En samlad tabell: summerad rubrikrad per person + kollapsara detaljrader ──
  let html = `<div style="overflow-x:auto"><table style="border-collapse:collapse;font-size:12px;width:100%">
    <thead><tr>
      <th style="text-align:left;padding:6px 10px;border-bottom:2px solid var(--border);min-width:220px">Person / Projekt</th>
      ${thWeeks}
    </tr></thead><tbody>`;

  for (const member of members) {
    const memberRows = workRows.filter(r => r.resource === member);
    if (!memberRows.length) continue;
    const safeId = member.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-]/g, '');

    // Summerings­rad (klickbar)
    html += `<tr onclick="toggleTeamMember('${safeId}')" style="cursor:pointer;background:var(--surface)">
      <td style="padding:7px 10px;border-top:2px solid var(--border);border-bottom:1px solid var(--border);font-weight:700">
        <span id="team-arrow-${safeId}" style="font-size:10px;color:var(--muted);transition:transform .2s;display:inline-block;margin-right:6px">▶</span>${member}
      </td>
      ${weeks.map(w => {
        const tot = memberRows.filter(r => r.week === w).reduce((s, r) => s + r.hours, 0);
        const isCur = w === curWeekStr;
        return tot
          ? `<td style="padding:7px 4px;text-align:center;border-top:2px solid var(--border);border-bottom:1px solid var(--border)">
               <div style="background:${isCur?'var(--accent)':'var(--border)'};color:${tot>40?'#c0392b':isCur?'#000':'var(--muted)'};border-radius:4px;padding:2px 6px;font-weight:700;font-family:var(--mono)">${tot}h</div></td>`
          : `<td style="border-top:2px solid var(--border);border-bottom:1px solid var(--border)"></td>`;
      }).join('')}
    </tr>`;

    // Detaljrader (kollapsade)
    const grouped = {};
    for (const row of memberRows) {
      const key = row.project + '|||' + row.activity;
      if (!grouped[key]) grouped[key] = {project: row.project, activity: row.activity, weeks: {}};
      grouped[key].weeks[row.week] = row.hours;
    }

    for (const [, g] of Object.entries(grouped)) {
      html += `<tr class="team-detail-${safeId}" style="display:none">
        <td style="padding:5px 10px 5px 28px;border-bottom:1px solid var(--border)">
          <span style="color:${selectedProject?'var(--accent)':'var(--muted)'};font-size:11px">${g.project}</span><br>
          <span>${g.activity}</span>
        </td>
        ${weeks.map(w => {
          const h = g.weeks[w] || 0;
          const isCur = w === curWeekStr;
          return h
            ? `<td style="padding:5px 4px;text-align:center;border-bottom:1px solid var(--border)">
                 <div style="background:${isCur?'var(--accent)':'var(--border)'};color:${isCur?'#000':'var(--muted)'};border-radius:4px;padding:2px 6px;font-weight:600;font-family:var(--mono)">${h}h</div></td>`
            : `<td style="border-bottom:1px solid var(--border)"></td>`;
        }).join('')}
      </tr>`;
    }
  }

  html += '</tbody></table></div>';
  gantt.innerHTML = html;
}

function toggleTeamMember(safeId) {
  const rows  = document.querySelectorAll(`.team-detail-${safeId}`);
  const arrow = document.getElementById('team-arrow-' + safeId);
  const open  = rows.length && rows[0].style.display === 'none';
  rows.forEach(r => r.style.display = open ? '' : 'none');
  arrow.style.transform = open ? 'rotate(90deg)' : '';
}

// ── Tidslinje (Gantt) ──────────────────────────────────────────
let planningData      = null;
let teamPlanningData  = null;
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
  const from    = document.getElementById('gantt-from').value;
  const to      = document.getElementById('gantt-to').value;
  const project = document.getElementById('gantt-project').value;
  if (!from || !to) return;
  // Uppdatera vecko-knapp med faktisk vecka för vald period
  const [wFrom] = isoWeek(new Date(from));
  const [wTo]   = isoWeek(new Date(to));
  const wkBtn = document.getElementById('gantt-week-btn');
  if (wkBtn) wkBtn.textContent = wFrom === wTo ? 'V' + wFrom : 'V' + wFrom + '–' + wTo;
  updateWkHint('gantt-from'); updateWkHint('gantt-to');
  const r = await fetch(`/api/gantt?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&project=${project}`);
  ganttData = (await r.json()).filter(g => isProgVisible('gantt', g.process_name));
  ganttExpandedRows.clear();
  ganttOffsetX = 0;
  drawGantt();
  refreshProjectDropdown('gantt-project', from, to);
  updateProjectSummary('gantt-proj-summary', project, from, to);
  if (document.getElementById('geo-section')?.style.display !== 'none') loadGeoLocations();
  loadTimeReport(from, to);
}

async function loadTimeReport(from, to) {
  const sec = document.getElementById('time-report-section');
  const tbl = document.getElementById('time-report-table');
  const r   = await fetch(`/api/time-report?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
  const d   = await r.json();
  if (!d.projects || !d.projects.length) { sec.style.display = 'none'; return; }
  sec.style.display = '';

  const days = d.days;
  const DAY_W = 64;
  const LABEL_W_TR = 200;

  // Formatera dag-rubrik: "mån 5/5"
  const dayNames = ['sön','mån','tis','ons','tor','fre','lör'];
  function fmtDay(iso) {
    const dt = new Date(iso + 'T12:00:00');
    return `${dayNames[dt.getDay()]} ${dt.getDate()}/${dt.getMonth()+1}`;
  }

  // Avrunda uppåt till närmaste halvtimme
  function roundUp(sec) {
    if (sec === 0) return 0;
    return Math.ceil(sec / 1800) * 0.5;
  }

  let html = `<div style="overflow-x:auto"><table style="border-collapse:collapse;font-size:12px;font-family:var(--mono);min-width:${LABEL_W_TR + days.length * DAY_W}px">`;

  // Rubrikrad
  html += `<tr style="color:var(--muted)">`;
  html += `<th style="width:${LABEL_W_TR}px;min-width:${LABEL_W_TR}px;text-align:left;padding:6px 10px;border-bottom:1px solid var(--border)">Projekt</th>`;
  for (const day of days) {
    const dt = new Date(day + 'T12:00:00');
    const isWeekend = dt.getDay() === 0 || dt.getDay() === 6;
    html += `<th style="width:${DAY_W}px;text-align:center;padding:6px 4px;border-bottom:1px solid var(--border);${isWeekend ? 'opacity:.4' : ''}">${fmtDay(day)}</th>`;
  }
  html += `</tr>`;

  // En rad per projekt
  for (const proj of d.projects) {
    const totalSec = Object.values(proj.days).reduce((a,b) => a+b, 0);
    const dimRow   = totalSec < 1800;
    html += `<tr style="${dimRow ? 'opacity:.35' : ''}">`;
    const label = proj.name ? `${proj.project} – ${proj.name}` : proj.project;
    html += `<td style="padding:6px 10px;border-bottom:1px solid var(--border);color:var(--accent);font-weight:600" title="${proj.name || ''}">${label}</td>`;
    for (const day of days) {
      const sec = proj.days[day] || 0;
      const h   = roundUp(sec);
      const dt  = new Date(day + 'T12:00:00');
      const isWeekend = dt.getDay() === 0 || dt.getDay() === 6;
      html += `<td style="text-align:center;padding:6px 4px;border-bottom:1px solid var(--border);${isWeekend ? 'opacity:.4' : ''}">`;
      if (h > 0) html += `<span style="color:var(--text)">${h.toFixed(1)}h</span>`;
      html += `</td>`;
    }
    html += `</tr>`;
  }

  html += `</table></div>`;
  tbl.innerHTML = html;
}


function _svgEsc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function drawGantt() {
  if (!ganttData) return;
  const hSvg = document.getElementById('gantt-header');
  const svg  = document.getElementById('gantt-svg');
  const wrap = document.getElementById('gantt-wrap');
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
  const axisH  = showDayLabels ? HEADER_H + 18 : HEADER_H;
  const totalW = Math.max(wrapW, LABEL_W + totalSec * ganttScale + 40);
  const bodyH  = rows.reduce((s,r) => s + (r.type==='header'?22 : r.type==='gap'?SECTION_GAP : ROW_H), 0) + 20;

  const cs = getComputedStyle(document.documentElement);
  const C = {
    bg:      cs.getPropertyValue('--bg').trim(),
    surface: cs.getPropertyValue('--surface').trim(),
    border:  cs.getPropertyValue('--border').trim(),
    accent:  cs.getPropertyValue('--accent').trim(),
    muted:   cs.getPropertyValue('--muted').trim(),
    text:    cs.getPropertyValue('--text').trim(),
    accent2: cs.getPropertyValue('--accent2').trim(),
    font:    cs.getPropertyValue('--font').trim() || 'Plus Jakarta Sans, sans-serif',
  };

  const tickIntervals = [60,300,600,1800,3600,7200,14400,21600,43200,86400];
  const tickSec = tickIntervals.find(t => t * ganttScale >= 60) || 86400;
  const nowSec  = (new Date() - from) / 1000;
  const panX    = LABEL_W + ganttOffsetX;

  // ── Header SVG ────────────────────────────────────────────────
  hSvg.setAttribute('width', totalW);
  hSvg.setAttribute('height', axisH);
  hSvg.style.width  = totalW + 'px';
  hSvg.style.height = axisH + 'px';

  let hPan = '';
  for (let s = 0; s <= totalSec + tickSec; s += tickSec) {
    const x = s * ganttScale;
    hPan += `<line x1="${x}" y1="0" x2="${x}" y2="${axisH}" stroke="${C.muted}44" stroke-width="1"/>`;
    const lbl = new Date(from.getTime() + s*1000).toTimeString().slice(0,5);
    hPan += `<text x="${x}" y="${HEADER_H-6}" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="10" fill="${C.muted}">${lbl}</text>`;
  }
  if (showDayLabels) {
    const sd = new Date(from); sd.setHours(0,0,0,0);
    for (let d = new Date(sd); d <= to; d.setDate(d.getDate()+1)) {
      const s = (d - from) / 1000;
      hPan += `<line x1="${s*ganttScale}" y1="0" x2="${s*ganttScale}" y2="${axisH}" stroke="${C.muted}88" stroke-width="1.5"/>`;
      const mx = (s + 43200) * ganttScale;
      hPan += `<text x="${mx}" y="${HEADER_H+13}" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="10" font-weight="bold" fill="${C.accent}">${DAYS_SV[d.getDay()]} ${d.getDate()}/${d.getMonth()+1}</text>`;
    }
  }
  const nowH = (nowSec > 0 && nowSec < totalSec)
    ? `<line x1="${panX + nowSec*ganttScale}" y1="0" x2="${panX + nowSec*ganttScale}" y2="${axisH}" stroke="${C.accent2}" stroke-width="1.5" stroke-dasharray="4,3"/>` : '';

  hSvg.innerHTML = `
    <rect x="0" y="0" width="${totalW}" height="${axisH}" fill="${C.border}"/>
    <rect x="0" y="0" width="${LABEL_W}" height="${axisH}" fill="${C.surface}"/>
    <defs><clipPath id="gh-clip"><rect x="${LABEL_W}" y="0" width="${totalW}" height="${axisH}"/></clipPath></defs>
    <g clip-path="url(#gh-clip)"><g id="gantt-header-pan" transform="translate(${panX},0)">${hPan}</g></g>
    ${nowH}`;

  // ── Body SVG ──────────────────────────────────────────────────
  svg.setAttribute('width', totalW);
  svg.setAttribute('height', bodyH);
  svg.style.width  = totalW + 'px';
  svg.style.height = bodyH + 'px';

  let rowBg = '', labelHtml = '', gridHtml = '', barsHtml = '';

  labelHtml += `<rect x="0" y="0" width="${LABEL_W}" height="${bodyH}" fill="${C.surface}"/>`;

  for (let s = 0; s <= totalSec + tickSec; s += tickSec)
    gridHtml += `<line x1="${s*ganttScale}" y1="0" x2="${s*ganttScale}" y2="${bodyH}" stroke="${C.muted}22" stroke-width="1"/>`;

  if (showDayLabels) {
    const sd = new Date(from); sd.setHours(0,0,0,0);
    for (let d = new Date(sd); d <= to; d.setDate(d.getDate()+1)) {
      const x = ((d - from)/1000) * ganttScale;
      gridHtml += `<line x1="${x}" y1="0" x2="${x}" y2="${bodyH}" stroke="${C.muted}44" stroke-width="1.5" stroke-dasharray="3,3"/>`;
    }
  }
  if (nowSec > 0 && nowSec < totalSec)
    gridHtml += `<line x1="${nowSec*ganttScale}" y1="0" x2="${nowSec*ganttScale}" y2="${bodyH}" stroke="${C.accent2}" stroke-width="1.5" stroke-dasharray="4,3"/>`;

  let y = 0;
  rows.forEach(row => {
    if (row.type === 'gap') { y += SECTION_GAP; return; }
    if (row.type === 'header') {
      rowBg      += `<rect x="${LABEL_W}" y="${y}" width="${totalW-LABEL_W}" height="20" fill="${C.border}"/>`;
      labelHtml  += `<text x="${LABEL_W+8}" y="${y+14}" font-family="JetBrains Mono,monospace" font-size="9" fill="${C.muted}">${_svgEsc(row.label)}</text>`;
      y += 22; return;
    }

    const isProc   = row.type === 'proc';
    const isActive = row.mode === 'active';
    const periods  = row.data.periods;
    const barColor = isActive ? (isProc ? C.accent : C.accent+'99') : (isProc ? C.muted+'aa' : C.muted+'55');

    rowBg     += `<rect x="0" y="${y}" width="${totalW}" height="${ROW_H}" fill="rgba(128,128,128,0.04)"/>`;
    rowBg     += `<line x1="0" y1="${y}" x2="${totalW}" y2="${y}" stroke="${C.border}" stroke-width="1"/>`;

    let displayLabel;
    if (row.type === 'title') {
      const raw = row.data.window_title || '';
      const cutAt = raw.search(/ [-–|] [A-Z]/);
      const clean = cutAt > 0 ? raw.slice(0,cutAt) : raw;
      displayLabel = '  ' + (clean.length > 24 ? clean.slice(0,23)+'…' : clean);
    } else {
      const lbl = row.data.process_name;
      displayLabel = lbl.length > 26 ? lbl.slice(0,25)+'…' : lbl;
    }
    const fillColor = isActive ? C.text : C.muted;
    const fontSize  = isProc ? 13 : 11;
    labelHtml += `<text x="8" y="${y+ROW_H/2+4}" font-family="${_svgEsc(C.font)},sans-serif" font-size="${fontSize}" fill="${fillColor}">${_svgEsc(displayLabel)}</text>`;

    if (isProc && row.data.titles && row.data.titles.length > 0) {
      const arrow = ganttExpandedRows.has(row.data.process_name) ? '▼' : '▶';
      labelHtml += `<text x="${LABEL_W-6}" y="${y+ROW_H/2+4}" text-anchor="end" font-size="10" fill="${C.muted}">${arrow}</text>`;
    }

    periods.forEach(p => {
      const ps = (new Date(p.started_at) - from) / 1000;
      const pe = (new Date(p.ended_at)   - from) / 1000;
      const bx = ps * ganttScale;
      const bw = Math.max(2, (pe - ps) * ganttScale);
      const bh = isProc ? 14 : 10;
      const by = y + (ROW_H - bh) / 2;
      barsHtml += `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="3" fill="${barColor}"/>`;
    });

    y += ROW_H;
  });

  svg.innerHTML = `
    <defs><clipPath id="gantt-clip"><rect x="${LABEL_W}" y="0" width="${totalW}" height="${bodyH}"/></clipPath></defs>
    <rect x="0" y="0" width="${totalW}" height="${bodyH}" fill="${C.bg}"/>
    ${rowBg}
    <g clip-path="url(#gantt-clip)">
      <g id="gantt-pan" transform="translate(${panX},0)">${gridHtml}${barsHtml}</g>
    </g>
    ${labelHtml}`;

  svg._rows = rows;
  svg._rowY = (() => { let yy=0,ys=[]; rows.forEach(r=>{ys.push(yy);yy+=r.type==='header'?22:r.type==='gap'?SECTION_GAP:ROW_H;}); return ys; })();
  svg._from = from;
  svg._totalSec = totalSec;
}

function updateGanttPan() {
  const panX = LABEL_W + ganttOffsetX;
  document.getElementById('gantt-header-pan')?.setAttribute('transform', `translate(${panX},0)`);
  document.getElementById('gantt-pan')?.setAttribute('transform', `translate(${panX},0)`);
}

// Gantt SVG event handlers
document.addEventListener('DOMContentLoaded', () => {
  const svg  = document.getElementById('gantt-svg');
  const hSvg = document.getElementById('gantt-header');
  const tip  = document.getElementById('gantt-tip');

  // ── Tooltip vid hovring ──────────────────────────────────────
  svg.addEventListener('mousemove', e => {
    if (ganttDragging || !svg._rows) { tip.style.display='none'; return; }
    const rect = svg.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const from = new Date(document.getElementById('gantt-from').value);

    let found = null;
    svg._rows.forEach((row, i) => {
      if (row.type === 'header' || row.type === 'gap') return;
      const ry = svg._rowY[i];
      if (my < ry || my >= ry + ROW_H) return;

      if (mx <= LABEL_W) {
        const d = row.data;
        if (row.type === 'proc') {
          const parts = [d.process_name];
          if (d.active_sec) parts.push(fmtDur(d.active_sec) + ' aktiv');
          if (d.total_sec)  parts.push(fmtDur(d.total_sec)  + ' totalt');
          found = parts.join(' · ');
        } else {
          const path = truncatePath(d.url || d.exe_path || '');
          found = d.window_title + (path ? '\n' + path : '');
        }
      } else {
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
      tip.innerText = found;
      const tipW = tip.offsetWidth || 300;
      const overflowsRight = (e.clientX + 14 + tipW) > window.innerWidth;
      tip.style.left = overflowsRight ? (e.clientX - tipW - 8) + 'px' : (e.clientX + 14) + 'px';
      tip.style.top  = (e.clientY + 14) + 'px';
    } else {
      tip.style.display = 'none';
    }
  });

  svg.addEventListener('mouseleave', () => { tip.style.display = 'none'; });

  svg.addEventListener('click', e => {
    if (!svg._rows) return;
    const rect = svg.getBoundingClientRect();
    const my = e.clientY - rect.top;
    const mx = e.clientX - rect.left;
    if (mx > LABEL_W) return;
    svg._rows.forEach((row, i) => {
      const ry = svg._rowY[i];
      if (row.type === 'proc' && my >= ry && my < ry + ROW_H) {
        const pn = row.data.process_name;
        if (ganttExpandedRows.has(pn)) ganttExpandedRows.delete(pn);
        else ganttExpandedRows.add(pn);
        drawGantt();
      }
    });
  });

  // Klick på dagrubrik → zooma till den dagen
  hSvg.style.cursor = 'default';
  hSvg.addEventListener('click', e => {
    const fromEl = document.getElementById('gantt-from');
    const toEl   = document.getElementById('gantt-to');
    const from   = new Date(fromEl.value);
    const to     = new Date(toEl.value);
    if ((to - from) <= 3600 * 25 * 1000) return;
    const rect = hSvg.getBoundingClientRect();
    const mx   = e.clientX - rect.left;
    if (mx <= LABEL_W) return;
    const clickedSec  = (mx - LABEL_W - ganttOffsetX) / ganttScale;
    const clickedDate = new Date(from.getTime() + clickedSec * 1000);
    clickedDate.setHours(0, 0, 0, 0);
    const y = clickedDate.getFullYear();
    const m = String(clickedDate.getMonth() + 1).padStart(2, '0');
    const d = String(clickedDate.getDate()).padStart(2, '0');
    const dayStr = `${y}-${m}-${d}`;
    fromEl.value = dayStr + 'T00:00';
    toEl.value   = dayStr + 'T23:59';
    savePref('gantt-from', fromEl.value);
    savePref('gantt-to',   toEl.value);
    ganttOffsetX = 0;
    loadGantt();
  });

  hSvg.addEventListener('mousemove', e => {
    const from = new Date(document.getElementById('gantt-from').value);
    const to   = new Date(document.getElementById('gantt-to').value);
    const rect = hSvg.getBoundingClientRect();
    const mx   = e.clientX - rect.left;
    hSvg.style.cursor = ((to - from) > 3600 * 25 * 1000 && mx > LABEL_W) ? 'pointer' : 'default';
  });

  // Drag för panorering
  svg.addEventListener('mousedown', e => {
    if (e.clientX - svg.getBoundingClientRect().left <= LABEL_W) return;
    ganttDragging = true;
    ganttDragStartX = e.clientX;
    ganttDragStartOffset = ganttOffsetX;
    svg.style.cursor = 'grabbing';
  });
  window.addEventListener('mousemove', e => {
    if (!ganttDragging) return;
    ganttOffsetX = ganttDragStartOffset + (e.clientX - ganttDragStartX);
    updateGanttPan();
  });
  window.addEventListener('mouseup', () => {
    ganttDragging = false;
    const s = document.getElementById('gantt-svg');
    if (s) s.style.cursor = 'grab';
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
  checkAiSource();
}

async function checkAiSource() {
  const banner  = document.getElementById('ai-no-source');
  const s       = JSON.parse(localStorage.getItem('at-ai-settings') || '{}');
  const provider = s.provider || 'ollama';
  // Moln-provider med API-nyckel → alltid OK
  if ((provider === 'openai' || provider === 'anthropic') && s.api_key) {
    banner.style.display = 'none'; return;
  }
  // Ollama (eller moln utan nyckel) → kolla om Ollama svarar
  const diag = await fetch('/api/diagnostics').then(r => r.json()).catch(() => null);
  const ollamaOk = diag && diag.ollama_running;
  banner.style.display = ollamaOk ? 'none' : '';
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
  const modelSel = document.getElementById('ai-model');
  const keyInput = document.getElementById('ai-api-key');
  if (p === 'ollama') {
    badge.className = 'ai-provider-badge local'; badge.textContent = '🔒 Lokalt';
    keyWrap.style.display = 'none';
    refreshBtn.style.display = '';
    refreshOllamaModels();
  } else if (p === 'openai') {
    badge.className = 'ai-provider-badge cloud'; badge.textContent = '☁ Moln';
    keyWrap.style.display = 'flex';
    refreshBtn.style.display = 'none';
    keyInput.placeholder = 'sk-...';
    modelSel.innerHTML = `
      <option value="gpt-4o-mini">gpt-4o-mini (snabb/billig)</option>
      <option value="gpt-4o">gpt-4o (bäst)</option>
      <option value="gpt-4.1-mini">gpt-4.1-mini</option>
      <option value="gpt-4.1">gpt-4.1</option>`;
  } else {
    badge.className = 'ai-provider-badge cloud'; badge.textContent = '☁ Moln';
    keyWrap.style.display = 'flex';
    refreshBtn.style.display = 'none';
    keyInput.placeholder = 'sk-ant-...';
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
    unique_apps  = db.execute(f"SELECT COUNT(DISTINCT p.process_name) FROM periods p WHERE {df}", params).fetchone()[0]
    total_per    = db.execute(f"SELECT COUNT(*) FROM periods p WHERE {df}", params).fetchone()[0]

    # Unik tid vid datorn: slå ihop överlappande perioder och summera
    all_periods = db.execute(
        f"SELECT started_at, ended_at FROM periods p WHERE {df} ORDER BY started_at", params
    ).fetchall()
    total_unique = 0
    cur_start = cur_end = None
    for row in all_periods:
        s = datetime.fromisoformat(row["started_at"])
        e = datetime.fromisoformat(row["ended_at"])
        if cur_start is None:
            cur_start, cur_end = s, e
        elif s <= cur_end:
            cur_end = max(cur_end, e)
        else:
            total_unique += int((cur_end - cur_start).total_seconds())
            cur_start, cur_end = s, e
    if cur_start is not None:
        total_unique += int((cur_end - cur_start).total_seconds())

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
        "total_active_sec":  total_active,
        "total_unique_sec":  total_unique,
        "unique_apps":      unique_apps,
        "total_periods":    total_per,
        "top_apps":         [dict(r) for r in top_apps],
        "hourly":           [dict(r) for r in hourly],
    })


@app.route("/api/browser-history")
def api_browser_history():
    from_str = request.args.get("from", "")
    to_str   = request.args.get("to", "")
    try:
        start = datetime.fromisoformat(from_str) if from_str else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end   = datetime.fromisoformat(to_str)   if to_str   else datetime.now()
        # Om bara datum angetts (ingen tid) sätt end till slutet av dagen
        if to_str and len(to_str) <= 10:
            end = end.replace(hour=23, minute=59, second=59)
    except ValueError:
        return jsonify({"error": "Ogiltigt datumformat"}), 400
    try:
        if _tracker is None:
            return jsonify({"error": "tracker ej tillgänglig"}), 500
        urls = _tracker.get_browser_urls(start, end)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"urls": urls})


@app.route("/api/periods")
def api_periods():
    from_date   = request.args.get("from","")
    to_date     = request.args.get("to","")
    search      = request.args.get("search","")
    active      = request.args.get("active","")
    project_num = request.args.get("project","")
    sort_col    = request.args.get("sort","started_at")
    sort_dir    = request.args.get("dir","desc")
    page        = max(1, int(request.args.get("page",1)))
    limit       = int(request.args.get("limit",50))
    offset      = (page-1)*limit

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
    rows_all  = db.execute(
        f"SELECT p.process_name, p.window_title, p.url, p.exe_path, p.started_at, p.ended_at, p.duration_sec, p.is_active FROM periods p WHERE {where} ORDER BY {sort_col} {sort_dir}",
        p
    ).fetchall()
    db.close()

    registry, kws = _get_registry_and_kws()

    # Hämta webbläsarhistorik en gång om projektfilter är aktivt
    # (URL:er lagras ej i periods-tabellen för browsers)
    browser_history = []  # lista av (visited_at: datetime, url: str)
    if project_num and _tracker is not None:
        try:
            from_dt = datetime.fromisoformat(from_date) if from_date else datetime(2000, 1, 1)
            to_dt   = datetime.fromisoformat(to_date)   if to_date   else datetime.now()
            if to_date and len(to_date) <= 10:
                to_dt = to_dt.replace(hour=23, minute=59, second=59)
            for b in _tracker.get_browser_urls(from_dt, to_dt):
                browser_history.append((datetime.fromisoformat(b["visited_at"]), b["url"]))
        except Exception:
            pass

    result   = []
    for r in rows_all:
        row = dict(r)
        matched = None
        for t in [row.get("window_title"), row.get("url"), row.get("exe_path")]:
            matched = _match_project(t, kws)
            if matched:
                break
        # Om ingen match och det är en webbläsare – sök i historiken för perioden
        if not matched and row.get("process_name", "").lower() in BROWSER_PROCS and browser_history:
            p_start = datetime.fromisoformat(row["started_at"])
            p_end   = datetime.fromisoformat(row["ended_at"])
            for visited_at, url in browser_history:
                if p_start <= visited_at <= p_end:
                    m = _match_project(url, kws)
                    if m:
                        matched = m
                        break
        row["project_num"]  = matched
        row["project_name"] = registry.get(matched, "") if matched else ""
        if project_num and matched != project_num:
            continue
        result.append(row)

    total = len(result)
    paged = result[offset:offset+limit]
    return jsonify({"total": total, "rows": paged})


@app.route("/api/app_titles")
def api_app_titles():
    proc        = request.args.get("proc","")
    from_date   = request.args.get("from","")
    to_date     = request.args.get("to","")
    active      = request.args.get("active","")
    project_num = request.args.get("project","")
    df, params  = date_filter(from_date, to_date)
    clauses = [df, "p.process_name = ?"]
    p = list(params) + [proc]
    if active in ("0","1"):
        clauses.append("p.is_active=?"); p.append(int(active))
    where = " AND ".join(clauses)
    db = get_db()
    rows = db.execute(
        f"SELECT p.window_title, MAX(p.url) as url, MAX(p.exe_path) as exe_path, SUM(p.duration_sec) as total_sec, SUM(CASE WHEN p.is_active=1 THEN p.duration_sec ELSE 0 END) as active_sec, COUNT(*) as cnt FROM periods p WHERE {where} AND p.window_title IS NOT NULL AND p.window_title != '' GROUP BY p.window_title ORDER BY total_sec DESC LIMIT 50",
        p
    ).fetchall()
    db.close()

    registry, kws = _get_registry_and_kws()
    result = []
    for r in rows:
        row     = dict(r)
        matched = _match_row_project(row, kws)
        row["project_num"]  = matched
        row["project_name"] = registry.get(matched, "") if matched else ""
        if project_num and matched != project_num:
            continue
        result.append(row)
    return jsonify(result)


@app.route("/api/apps")
def api_apps():
    from_date = request.args.get("from","")
    to_date   = request.args.get("to","")
    active    = request.args.get("active","")
    project   = request.args.get("project","").strip()
    df, params = date_filter(from_date, to_date)
    clauses=[df]; p=list(params)
    if active in ("0","1"):
        clauses.append("p.is_active=?"); p.append(int(active))
    where=" AND ".join(clauses)
    db=get_db()
    if project:
        rows = db.execute(
            f"SELECT p.process_name, p.window_title, p.url, p.exe_path, p.duration_sec, p.ended_at FROM periods p WHERE {where}",
            p
        ).fetchall()
        db.close()
        rows = [dict(r) for r in rows]
        _, keywords = _get_registry_and_kws()
        rows = [r for r in rows if _match_row_project(r, keywords) == project]
        groups = defaultdict(lambda: {"total_sec": 0, "period_count": 0, "last_seen": ""})
        for r in rows:
            pn = r["process_name"]
            groups[pn]["total_sec"] += r["duration_sec"]
            groups[pn]["period_count"] += 1
            if r["ended_at"] > groups[pn]["last_seen"]:
                groups[pn]["last_seen"] = r["ended_at"]
        result = [{"process_name": pn, **v} for pn, v in groups.items()]
        result.sort(key=lambda x: x["total_sec"], reverse=True)
        return jsonify(result)
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

    project_filter = request.args.get("project", "").strip()

    db = get_db()
    # Hämta alla perioder inom intervallet
    rows = db.execute(
        "SELECT process_name, window_title, url, exe_path, started_at, ended_at, duration_sec, is_active "
        "FROM periods WHERE started_at >= ? AND started_at < date(?, '+1 day') ORDER BY started_at",
        (from_str, to_str)
    ).fetchall()
    db.close()

    # Konvertera till dict-lista (behövs för _match_row_project som använder .get())
    rows = [dict(r) for r in rows]

    # Projektfiltrering
    if project_filter:
        _, keywords = _get_registry_and_kws()
        rows = [r for r in rows if _match_row_project(r, keywords) == project_filter]

    # Gruppera per process_name
    procs = defaultdict(lambda: {"periods":[], "titles": defaultdict(lambda: {"periods":[],"is_active":0}), "has_active":0, "active_sec":0})

    for r in rows:
        pn = r["process_name"]
        period = {"started_at": r["started_at"], "ended_at": r["ended_at"], "duration_sec": r["duration_sec"]}
        procs[pn]["periods"].append(period)
        if r["is_active"]:
            procs[pn]["has_active"] = 1
            procs[pn]["active_sec"] += r["duration_sec"]
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
            "active_sec":   data["active_sec"],
            "total_sec":    sum(p["duration_sec"] for p in data["periods"]),
        })
    return jsonify(result)


def _merge_intervals(ivs):
    """Slår ihop överlappande intervall. ivs = lista av (start, end) i sekunder."""
    if not ivs:
        return []
    ivs = sorted(ivs)
    merged = [list(ivs[0])]
    for s, e in ivs[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def _subtract_intervals(ivs, subtract):
    """Klipper bort 'subtract'-intervall från 'ivs'."""
    result = []
    for iv_s, iv_e in ivs:
        rem = [(iv_s, iv_e)]
        for sub_s, sub_e in subtract:
            new_rem = []
            for r_s, r_e in rem:
                if sub_e <= r_s or sub_s >= r_e:
                    new_rem.append((r_s, r_e))
                else:
                    if r_s < sub_s:
                        new_rem.append((r_s, sub_s))
                    if sub_e < r_e:
                        new_rem.append((sub_e, r_e))
            rem = new_rem
        result.extend(rem)
    return result


def _sum_intervals(ivs):
    return sum(e - s for s, e in ivs)


@app.route("/api/time-report")
def api_time_report():
    PTV = 0.25  # Passivtidvikt – bakgrundstid räknas till 25%

    from_str = request.args.get("from", "")
    to_str   = request.args.get("to", "")
    if not from_str or not to_str:
        return jsonify([])

    try:
        d0 = date.fromisoformat(from_str[:10])
        d1 = date.fromisoformat(to_str[:10])
    except ValueError:
        return jsonify([])

    days = []
    cur = d0
    while cur <= d1:
        days.append(cur.isoformat())
        cur += timedelta(days=1)

    db = get_db()
    all_rows = db.execute(
        "SELECT process_name, window_title, url, exe_path, started_at, ended_at, is_active "
        "FROM periods WHERE started_at >= ? AND started_at < date(?, '+1 day') AND ended_at IS NOT NULL",
        (from_str, to_str)
    ).fetchall()
    db.close()

    all_rows = [dict(r) for r in all_rows]
    registry, keywords = _get_registry_and_kws()

    def to_ts(s):
        return datetime.fromisoformat(s).timestamp()

    # Bygg dag -> projekt -> {fg, bg} intervalllistor + dag -> alla intervall (för span)
    day_proj = defaultdict(lambda: defaultdict(lambda: {"fg": [], "bg": []}))
    day_all  = defaultdict(list)

    for r in all_rows:
        day   = r["started_at"][:10]
        ts_s  = to_ts(r["started_at"])
        ts_e  = to_ts(r["ended_at"])
        if ts_e <= ts_s:
            continue
        # Klipp perioder som sträcker sig över midnatt till dagsgränsen
        midnight = to_ts(day + "T23:59:59") + 1
        ts_e = min(ts_e, midnight)

        day_all[day].append((ts_s, ts_e))

        proj = _match_row_project(r, keywords)
        if not proj:
            continue
        key = "fg" if r["is_active"] else "bg"
        day_proj[day][proj][key].append((ts_s, ts_e))

    all_projects = {proj for dp in day_proj.values() for proj in dp}
    result = []
    for proj in sorted(all_projects):
        day_totals = {}
        for day in days:
            pd = day_proj.get(day, {}).get(proj)
            if not pd:
                day_totals[day] = 0
                continue

            fg_merged = _merge_intervals(pd["fg"])
            bg_only   = _subtract_intervals(_merge_intervals(pd["bg"]), fg_merged)
            weighted  = _sum_intervals(fg_merged) + _sum_intervals(bg_only) * PTV

            # Dag-tak = union av alla perioder den dagen (exkl. pauser/sleep)
            day_span = _sum_intervals(_merge_intervals(day_all.get(day, [])))
            day_totals[day] = int(min(weighted, day_span))

        result.append({
            "project": proj,
            "name":    registry.get(proj, ""),
            "days":    day_totals,
        })
    return jsonify({"days": days, "projects": result})


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


def extract_projects(db, since_days=7):
    """Identifierar projektnummer ur sökvägar och fönsterrubriker."""
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
            for m in _PS_CODE_RE.findall(text):
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

    # Platser (senaste 14 dagarna)
    try:
        loc_rows = db.execute("""
            SELECT date(logged_at) as day, logged_at, address
            FROM locations
            WHERE date(logged_at) >= ?
            ORDER BY logged_at
        """, (two_weeks_ago,)).fetchall()

        if loc_rows:
            locs_by_day = defaultdict(list)
            for r in loc_rows:
                if r["address"]:
                    locs_by_day[r["day"]].append(
                        (r["logged_at"][11:16], r["address"])  # HH:MM + adress
                    )

            lines.append("PLATSER (ur platsloggning):")
            for day in sorted(locs_by_day.keys(), reverse=True):
                entries = locs_by_day[day]
                # Slå ihop på varandra följande identiska adresser
                merged = [entries[0]]
                for e in entries[1:]:
                    if e[1] != merged[-1][1]:
                        merged.append(e)
                d_obj = datetime.strptime(day, "%Y-%m-%d")
                label = " <- IDAG" if day == today_str else ""
                lines.append(f"  {day} ({DAYS_SV[d_obj.weekday()]}){label}:")
                for time, addr in merged:
                    lines.append(f"    {time}  {addr}")
            lines.append("")
    except Exception:
        pass  # locations-tabellen kanske inte finns ännu

    # Resursplanering (planerade aktiviteter denna och förra veckan)
    try:
        cfg = load_config()
        if cfg.get("planning_enabled") and _planner:
            cache_path = PLAN_CACHE_PATH
            if cache_path.exists():
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
                plan_rows = cache.get("rows", [])
                iso = today.isocalendar()
                cur_week = f"V{str(iso[0] % 100).zfill(2)}{str(iso[1]).zfill(2)}"
                # Filtrera på innevarande vecka
                relevant = [r for r in plan_rows if r.get("week") == cur_week]
                if relevant:
                    lines.append("RESURSPLANERING (innevarande vecka):")
                    for r in relevant:
                        lines.append(f"  {r['week']}  {r['project']}  {r['activity']}  {r['hours']}h")
                    lines.append("")
    except Exception:
        pass

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


def stream_openai(messages, model, api_key, context):
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}] + messages
    payload = json.dumps({
        "model": model,
        "messages": full_messages,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
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
                        text = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
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
        yield f"\n\n⚠️ OpenAI-fel: {msg}"
    except urllib.error.URLError as e:
        yield f"\n\n⚠️ Nätverksfel: {e.reason}"


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
        elif provider == "openai":
            gen = stream_openai(messages, model, api_key, context)
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


_registry_cache: dict = {"registry": None, "kws": None, "mtime": None}


def _get_registry_and_kws() -> tuple:
    """Returnerar (registry, keywords). Läser filen bara om den ändrats sedan senast."""
    try:
        mtime = PLAN_CACHE_PATH.stat().st_mtime
    except FileNotFoundError:
        return {}, {}
    c = _registry_cache
    if c["mtime"] == mtime and c["registry"] is not None:
        return c["registry"], c["kws"]
    registry = _build_project_registry()
    kws      = _project_keywords(registry)
    c["registry"], c["kws"], c["mtime"] = registry, kws, mtime
    return registry, kws


def _build_project_registry() -> dict:
    try:
        cache = json.loads(PLAN_CACHE_PATH.read_text(encoding="utf-8"))
        if "full_registry" in cache:
            return cache["full_registry"]
        registry = {}
        for row in cache.get("rows", []):
            m = _PS_CODE_RE.match(row["project"])
            if m:
                num  = m.group()
                registry[num] = row["project"][len(num):].strip(" -–")
        return registry
    except Exception:
        return {}


def _project_keywords(registry: dict) -> dict:
    result = {}
    for num, name in registry.items():
        words = [w.lower() for w in re.split(r'[\s,&/:;\-]+', name) if len(w) > 3]
        words.sort(key=len, reverse=True)
        result[num] = words[:5]
    return result


def _match_project(text: str, keywords: dict) -> str | None:
    """Direktmatchning på P/S+5 siffror, annars nyckelordsmatchning (minst 2 av N)."""
    if not text:
        return None
    m = _PS_CODE_RE.search(text)
    if m:
        return m.group()
    text_lower = text.lower()
    for num, kws in keywords.items():
        if not kws:
            continue
        if sum(1 for kw in kws if kw in text_lower) >= min(len(kws), 2):
            return num
    return None


def _match_row_project(row, kws: dict) -> str | None:
    """Matchar en databasrad mot projektnummer via window_title, url och exe_path."""
    return (_match_project(row.get("window_title"), kws) or
            _match_project(row.get("url"), kws) or
            _match_project(row.get("exe_path"), kws))


@app.route("/api/project-registry")
def api_project_registry():
    registry, _ = _get_registry_and_kws()
    return jsonify({"ok": True, "projects": [
        {"number": num, "name": name} for num, name in sorted(registry.items())
    ]})


@app.route("/api/project-summary")
def api_project_summary():
    project   = request.args.get("project", "").strip()
    from_date = request.args.get("from", "")
    to_date   = request.args.get("to", "")
    if not project or not from_date or not to_date:
        return jsonify({"ok": False}), 400

    registry, kws = _get_registry_and_kws()

    db   = get_db()
    rows = db.execute(
        "SELECT window_title, process_name, url, exe_path, duration_sec "
        "FROM periods WHERE started_at >= ? AND started_at < date(?, '+1 day') AND is_active = 1",
        (from_date, to_date)
    ).fetchall()
    db.close()

    totals = {}
    for r in rows:
        matched = (_match_project(r["window_title"], kws) or
                   _match_project(r["url"], kws) or
                   _match_project(r["exe_path"], kws))
        if matched != project:
            continue
        title = r["window_title"] or r["process_name"] or "—"
        totals[title] = totals.get(title, 0) + r["duration_sec"]

    sorted_titles = sorted(totals.items(), key=lambda x: -x[1])
    total_sec = sum(v for _, v in sorted_titles)

    return jsonify({
        "ok":           True,
        "project_num":  project,
        "project_name": registry.get(project, ""),
        "total_sec":    total_sec,
        "top_titles":   [{"title": t, "sec": s} for t, s in sorted_titles[:6]],
    })


@app.route("/api/active-projects")
def api_active_projects():
    """Returnerar de projekt som faktiskt hittats i aktivitetsdatan för vald period."""
    from_date = request.args.get("from", "")
    to_date   = request.args.get("to", "")

    registry, kws = _get_registry_and_kws()

    if not from_date or not to_date:
        # Inget datumintervall – returnera alla kända projekt
        return jsonify({"ok": True, "projects": [
            {"number": k, "name": v} for k, v in sorted(registry.items())
        ]})

    db   = get_db()
    rows = db.execute(
        "SELECT window_title, url, exe_path FROM periods "
        "WHERE started_at >= ? AND started_at < date(?, '+1 day')",
        (from_date, to_date)
    ).fetchall()
    db.close()

    found = {}
    for r in rows:
        for text in [r["window_title"] or "", r["url"] or "", r["exe_path"] or ""]:
            if not text:
                continue
            # Direkt mönstersökning (P/S + 5 siffror)
            for m in _PS_CODE_RE.finditer(text):
                code = m.group()
                if code not in found:
                    found[code] = registry.get(code, "")
            # Nyckelordsmatchning mot planerade projekt
            matched = _match_project(text, kws)
            if matched and matched not in found:
                found[matched] = registry.get(matched, "")

    projects = [{"number": k, "name": v} for k, v in sorted(found.items())]
    return jsonify({"ok": True, "projects": projects})


@app.route("/api/geo-config", methods=["GET", "POST"])
def api_geo_config():
    cfg = load_config()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cfg["geo_enabled"]  = data.get("enabled", False)
        cfg["geo_interval"] = int(data.get("interval", 5))
        save_config(cfg)
        # Starta/stoppa geotrackern direkt
        if _geotracker:
            try:
                if cfg["geo_enabled"]:
                    _geotracker.start(cfg["geo_interval"])
                else:
                    _geotracker.stop()
            except Exception as e:
                return jsonify({"ok": True, "warning": str(e)})
        return jsonify({"ok": True})
    return jsonify({
        "enabled":  cfg.get("geo_enabled", False),
        "interval": cfg.get("geo_interval", 5),
    })


@app.route("/api/screenshot-config", methods=["GET", "POST"])
def api_screenshot_config():
    cfg = load_config()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cfg["screenshot_rename_enabled"] = data.get("enabled", True)
        save_config(cfg)
        if _screenshot_watcher:
            try:
                if cfg["screenshot_rename_enabled"]:
                    _screenshot_watcher.start()
                else:
                    _screenshot_watcher.stop()
            except Exception as e:
                return jsonify({"ok": True, "warning": str(e)})
        return jsonify({"ok": True})
    return jsonify({"enabled": cfg.get("screenshot_rename_enabled", True)})


_PLAN_FILE_SKIP_DIRS = {"äldre versioner", "utvecklingsfiler", "arkiv", "backup"}
_PLAN_FILE_NAMES = {
    "goteborg":  "Oaks Resursplanering.xlsm",
    "stockholm": "Oaks Resursplanering_Stockholm.xlsm",
}
_PLAN_CACHE_TTL = 60  # sekunder
_plan_file_cache: dict = {}  # {office: (path_or_none, timestamp)}


def _find_planning_file(office: str = "goteborg") -> str | None:
    """Söker efter planeringsfil i OneDrive-synkad mapp. Cachar resultatet 60s."""
    cached = _plan_file_cache.get(office)
    if cached and (time.time() - cached[1]) < _PLAN_CACHE_TTL:
        return cached[0]

    filename = _PLAN_FILE_NAMES.get(office, "Oaks Resursplanering.xlsm")
    result = None
    for candidate in Path.home().rglob(filename):
        parts = {p.lower() for p in candidate.parts}
        if parts & _PLAN_FILE_SKIP_DIRS:
            continue
        try:
            if candidate.stat().st_size == 0:  # OneDrive "Endast online"-platshållare
                continue
        except OSError:
            continue
        result = str(candidate)
        break

    _plan_file_cache[office] = (result, time.time())
    return result


@app.route("/api/office-config", methods=["GET", "POST"])
def api_office_config():
    cfg = load_config()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cfg["office"] = data.get("office", "goteborg")
        save_config(cfg)
    office = cfg.get("office", "goteborg")
    suggested = _find_planning_file(office)
    return jsonify({"office": office, "suggested_path": suggested})


@app.route("/api/geo-locations")
def api_geo_locations():
    from_date = request.args.get("from", "")
    to_date   = request.args.get("to", "")
    db = get_db()
    try:
        if from_date and to_date:
            rows = db.execute(
                "SELECT logged_at, latitude, longitude, accuracy_m, address "
                "FROM locations WHERE logged_at >= ? AND logged_at < date(?, '+1 day') "
                "ORDER BY logged_at",
                (from_date, to_date)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT logged_at, latitude, longitude, accuracy_m, address "
                "FROM locations ORDER BY logged_at DESC LIMIT 100"
            ).fetchall()
    except Exception:
        rows = []
    db.close()
    return jsonify({"ok": True, "locations": [dict(r) for r in rows]})


@app.route("/api/planning-config", methods=["GET", "POST"])
def api_planning_config():
    cfg = load_config()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cfg["planning_enabled"]  = data.get("enabled", False)
        cfg["planning_file"]     = data.get("file", "")
        cfg["planning_resource"] = data.get("resource", "")
        save_config(cfg)
        return jsonify({"ok": True})
    return jsonify({
        "enabled":  cfg.get("planning_enabled", False),
        "file":     cfg.get("planning_file", ""),
        "resource": cfg.get("planning_resource", ""),
    })


@app.route("/api/planning")
def api_planning():
    cfg = load_config()
    if not cfg.get("planning_enabled"):
        return jsonify({"ok": False, "error": "Resursplanering inte aktiverad"}), 403

    file_path = cfg.get("planning_file", "")
    resource  = cfg.get("planning_resource", "")
    if not file_path or not resource:
        return jsonify({"ok": False, "error": "Sökväg och namn måste konfigureras"}), 400

    from_str = request.args.get("from", "")
    to_str   = request.args.get("to", "")
    try:
        from_date = datetime.fromisoformat(from_str) if from_str else datetime.now() - timedelta(weeks=2)
        to_date   = datetime.fromisoformat(to_str)   if to_str   else datetime.now() + timedelta(weeks=4)
        if to_str and len(to_str) <= 10:
            to_date = to_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        return jsonify({"ok": False, "error": "Ogiltigt datumformat"}), 400

    try:
        if _planner is None:
            raise ImportError("planner ej tillgänglig")
        rows         = _planner.read_planning(file_path, resource, from_date, to_date)
        full_registry = _planner.read_all_projects(file_path)
        # Spara till cache
        PLAN_CACHE_PATH.write_text(json.dumps({
            "rows":          rows,
            "full_registry": full_registry,
            "cached_at":     datetime.now().isoformat(),
            "from":          from_date.isoformat(),
            "to":            to_date.isoformat(),
        }, ensure_ascii=False), encoding="utf-8")
        return jsonify({"ok": True, "rows": rows, "from_cache": False, "cached_at": None})
    except Exception as e:
        # Försök med cache om Excel inte är tillgänglig
        try:
            cache = json.loads(PLAN_CACHE_PATH.read_text(encoding="utf-8"))
            return jsonify({"ok": True, "rows": cache["rows"], "from_cache": True, "cached_at": cache["cached_at"]})
        except Exception:
            return jsonify({"ok": False, "error": str(e)}), 500


TEAM_PLAN_CACHE_PATH = Path.home() / "activity_tracker" / "team_planning_cache.json"

@app.route("/api/team-planning")
def api_team_planning():
    cfg = load_config()
    if not cfg.get("planning_enabled"):
        return jsonify({"ok": False, "error": "Resursplanering inte aktiverad"}), 403

    file_path = cfg.get("planning_file", "")
    resource  = cfg.get("planning_resource", "")
    if not file_path or not resource:
        return jsonify({"ok": False, "error": "Sökväg och namn måste konfigureras"}), 400

    from_str = request.args.get("from", "")
    to_str   = request.args.get("to", "")
    try:
        from_date = datetime.fromisoformat(from_str) if from_str else datetime.now() - timedelta(weeks=2)
        to_date   = datetime.fromisoformat(to_str)   if to_str   else datetime.now() + timedelta(weeks=4)
        if to_str and len(to_str) <= 10:
            to_date = to_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        return jsonify({"ok": False, "error": "Ogiltigt datumformat"}), 400

    try:
        if _planner is None:
            raise ImportError("planner ej tillgänglig")
        data = _planner.read_team_planning(file_path, resource, from_date, to_date)
        TEAM_PLAN_CACHE_PATH.write_text(json.dumps({
            **data, "cached_at": datetime.now().isoformat()
        }, ensure_ascii=False), encoding="utf-8")
        return jsonify({"ok": True, **data, "from_cache": False, "cached_at": None})
    except Exception as e:
        try:
            cache = json.loads(TEAM_PLAN_CACHE_PATH.read_text(encoding="utf-8"))
            return jsonify({"ok": True, "group": cache.get("group",""), "rows": cache.get("rows",[]),
                            "from_cache": True, "cached_at": cache.get("cached_at")})
        except Exception:
            return jsonify({"ok": False, "error": str(e)}), 500


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
    # Starta geotracker om den var aktiverad
    if _geotracker:
        cfg = load_config()
        if cfg.get("geo_enabled"):
            _geotracker.start(cfg.get("geo_interval", 5))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
