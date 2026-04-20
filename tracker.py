"""
Activity Tracker – Periodbaserad bakgrundstjänst
"""

import sqlite3
import time
import ctypes
import ctypes.wintypes
import os
import json
import shutil
import logging
import tempfile
import threading
import psutil
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ── Konfiguration ──────────────────────────────────────────────
POLL_INTERVAL  = 5      # sekunder mellan varje kontroll
MIN_PERIOD_SEC = 60     # perioder kortare än detta sparas inte
DB_PATH   = Path.home() / "activity_tracker" / "activity.db"
LOG_PATH  = Path.home() / "activity_tracker" / "tracker.log"
LIVE_PATH = Path.home() / "activity_tracker" / "live.json"
# ───────────────────────────────────────────────────────────────

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

user32   = ctypes.windll.user32
psapi    = ctypes.windll.psapi
kernel32 = ctypes.windll.kernel32

BROWSER_PROCS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"}
DOC_EXTS = {'.docx','.doc','.xlsx','.xls','.pptx','.ppt','.pdf','.txt','.csv','.odt','.ods','.odp',
            '.vsdx','.vsd','.vsdm','.dwg','.dxf','.mpp','.mpt'}

# Executor för timeout-skyddade anrop
_executor = ThreadPoolExecutor(max_workers=2)

# Stop-event som tray_app kan sätta för att avbryta loop:en vid hängning
_stop_event = threading.Event()


def stop():
    """Signalerar till run()-loopen att avsluta (används av watchdogen)."""
    _stop_event.set()


# ── Windows-API helpers ────────────────────────────────────────

def _is_screensaver_running() -> bool:
    """Returnerar True om skärmsläckaren (eller låsskärmen) är aktiv."""
    running = ctypes.wintypes.BOOL(False)
    user32.SystemParametersInfoW(0x0072, 0, ctypes.byref(running), 0)
    return bool(running.value)


def _exe_for_pid(pid):
    handle = kernel32.OpenProcess(0x0410, False, pid)
    buf = ctypes.create_unicode_buffer(1024)
    if handle:
        psapi.GetModuleFileNameExW(handle, None, buf, 1024)
        kernel32.CloseHandle(handle)
    return buf.value


def _get_active_window_inner():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None, None, None
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value.strip()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    exe = _exe_for_pid(pid.value)
    proc = os.path.basename(exe) if exe else "unknown"
    return proc, title, exe, pid.value


def get_active_window():
    """Hämtar aktivt fönster med 3 sekunders timeout."""
    try:
        future = _executor.submit(_get_active_window_inner)
        return future.result(timeout=3)
    except Exception:
        return None, None, None, None


def _enum_windows_inner():
    """Körs i separat tråd med timeout för att skydda mot hängande API-anrop."""
    results = {}

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = _exe_for_pid(pid.value)
        proc = os.path.basename(exe) if exe else "unknown"
        if proc not in results:
            results[proc] = (proc, title, exe)
        return True

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(CB(cb), 0)
    return set(results.keys()), results


def get_all_visible_windows():
    """Hämtar alla synliga fönster med 5 sekunders timeout."""
    holder = [None]

    def _run():
        try:
            holder[0] = _enum_windows_inner()
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5)
    if holder[0] is not None:
        return holder[0]
    return set(), {}


# ── Dokumentsökväg via psutil (med timeout) ───────────────────

def _get_doc_path(pid, title):
    """Körs i separat tråd med timeout för att undvika hängning."""
    try:
        proc = psutil.Process(pid)
        try:
            files = proc.open_files()
        except Exception:
            return None

        candidates = []
        for f in files:
            try:
                ext = os.path.splitext(f.path)[1].lower()
                if ext not in DOC_EXTS:
                    continue
                p = f.path.lower()
                # Skippa cache- och tempfiler
                if any(s in p for s in ['officfilecache', 'appdata\\local\\temp',
                                         'inetcache', 'appdata\\roaming',
                                         'appdata\\locallow']):
                    continue
                candidates.append(f.path)
            except Exception:
                continue

        if not candidates:
            return None

        # Matcha mot fönsterrubriken
        title_lower = title.lower()
        for path in candidates:
            fname = os.path.splitext(os.path.basename(path))[0].lower()
            if fname and fname in title_lower:
                return path

        return candidates[0]
    except Exception:
        return None


def get_document_path(pid, title):
    """Hämtar dokumentsökväg med 2 sekunders timeout."""
    try:
        future = _executor.submit(_get_doc_path, pid, title)
        return future.result(timeout=2)
    except Exception:
        return None


# ── Webbläsarhistorik ─────────────────────────────────────────

# Chrome/Edge sparar tid som mikrosekunder sedan 1601-01-01
_CHROME_EPOCH_DELTA = 11644473600  # sekunder mellan 1601-01-01 och 1970-01-01

def _browser_history_paths() -> dict:
    """Returnerar alla tillgängliga History-filer för Chrome och Edge (alla profiler)."""
    paths = {}
    for browser, base in [
        ("chrome", Path.home() / "AppData/Local/Google/Chrome/User Data"),
        ("edge",   Path.home() / "AppData/Local/Microsoft/Edge/User Data"),
    ]:
        if not base.exists():
            continue
        for profile_dir in base.iterdir():
            if not profile_dir.is_dir():
                continue
            h = profile_dir / "History"
            if h.exists():
                key = f"{browser}_{profile_dir.name}"
                paths[key] = h
    return paths


def _firefox_history_paths() -> dict:
    """Returnerar alla tillgängliga places.sqlite-filer för Firefox (alla profiler)."""
    paths = {}
    base = Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles"
    if not base.exists():
        return paths
    for profile_dir in base.iterdir():
        if not profile_dir.is_dir():
            continue
        h = profile_dir / "places.sqlite"
        if h.exists():
            paths[f"firefox_{profile_dir.name}"] = h
    return paths


def _chrome_ts_to_datetime(chrome_ts: int) -> datetime:
    """Konverterar Chrome-tidsstämpel (µs sedan 1601) till datetime (UTC)."""
    epoch_sec = chrome_ts / 1_000_000 - _CHROME_EPOCH_DELTA
    return datetime.fromtimestamp(epoch_sec)


def get_browser_urls(start: datetime, end: datetime) -> list[dict]:
    """
    Läser Chrome/Edge/Firefox-historik och returnerar URL:er besökta inom [start, end].
    Kopierar DB-filen till temp för att undvika låsningsproblem.
    Returnerar lista med {url, title, visited_at, browser}.
    """
    results = []

    # ── Chrome / Edge ──────────────────────────────────────────
    start_chrome = int((start.timestamp() + _CHROME_EPOCH_DELTA) * 1_000_000)
    end_chrome   = int((end.timestamp()   + _CHROME_EPOCH_DELTA) * 1_000_000)

    for browser, path in _browser_history_paths().items():
        if not path.exists():
            continue
        tmp = None
        try:
            tmp = Path(tempfile.mktemp(suffix=".db"))
            shutil.copy2(path, tmp)
            conn = sqlite3.connect(str(tmp))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT url, title, last_visit_time
                FROM urls
                WHERE last_visit_time BETWEEN ? AND ?
                ORDER BY last_visit_time
            """, (start_chrome, end_chrome)).fetchall()
            conn.close()
            for row in rows:
                url = row["url"]
                if url.startswith(("chrome://", "chrome-extension://", "edge://", "data:", "about:")):
                    continue
                results.append({
                    "url":        url,
                    "title":      row["title"] or "",
                    "visited_at": _chrome_ts_to_datetime(row["last_visit_time"]).isoformat(),
                    "browser":    browser,
                })
        except Exception as e:
            logging.warning(f"Kunde inte läsa {browser}-historik: {e}")
        finally:
            if tmp and tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    # ── Firefox ────────────────────────────────────────────────
    # Firefox sparar tid som mikrosekunder sedan Unix-epoken (1970)
    start_ff = int(start.timestamp() * 1_000_000)
    end_ff   = int(end.timestamp()   * 1_000_000)

    for browser, path in _firefox_history_paths().items():
        if not path.exists():
            continue
        tmp = None
        try:
            tmp = Path(tempfile.mktemp(suffix=".db"))
            shutil.copy2(path, tmp)
            conn = sqlite3.connect(str(tmp))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT p.url, p.title, v.visit_date
                FROM moz_historyvisits v
                JOIN moz_places p ON p.id = v.place_id
                WHERE v.visit_date BETWEEN ? AND ?
                ORDER BY v.visit_date
            """, (start_ff, end_ff)).fetchall()
            conn.close()
            for row in rows:
                url = row["url"]
                if url.startswith(("about:", "moz-extension://", "data:")):
                    continue
                results.append({
                    "url":        url,
                    "title":      row["title"] or "",
                    "visited_at": datetime.fromtimestamp(row["visit_date"] / 1_000_000).isoformat(),
                    "browser":    browser,
                })
        except Exception as e:
            logging.warning(f"Kunde inte läsa {browser}-historik: {e}")
        finally:
            if tmp and tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    # Deduplicera på URL – behåll senaste besök
    seen = {}
    for r in results:
        seen[r["url"]] = r
    return list(seen.values())


# ── Databas ────────────────────────────────────────────────────

SCHEMA_VERSION = 1

# Migreringar i ordning – varje post är (version, sql)
# Lägg till nya migreringar i slutet, höj SCHEMA_VERSION
_MIGRATIONS = [
    (1, """
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS periods (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL,
            process_name TEXT NOT NULL,
            window_title TEXT,
            exe_path     TEXT,
            url          TEXT,
            started_at   TEXT NOT NULL,
            ended_at     TEXT NOT NULL,
            duration_sec INTEGER NOT NULL,
            is_active    INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
        CREATE INDEX IF NOT EXISTS idx_periods_proc  ON periods(process_name);
        CREATE INDEX IF NOT EXISTS idx_periods_start ON periods(started_at);
    """),
]


def init_db(conn):
    cur_version = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in _MIGRATIONS:
        if cur_version < version:
            logging.info(f"Kör DB-migrering till version {version}")
            conn.executescript(sql)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.commit()
    logging.info(f"DB schema version: {SCHEMA_VERSION}")


def start_session(conn):
    cur = conn.execute(
        "INSERT INTO sessions (started_at) VALUES (?)",
        (datetime.now().isoformat(),)
    )
    conn.commit()
    return cur.lastrowid


def end_session(conn, session_id):
    conn.execute(
        "UPDATE sessions SET ended_at = ? WHERE id = ?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()


def flush_period(conn, session_id, proc, title, exe, url, started_at, ended_at, is_active):
    duration = int((ended_at - started_at).total_seconds())
    if duration < MIN_PERIOD_SEC:
        return
    conn.execute(
        "INSERT INTO periods (session_id, process_name, window_title, exe_path, url, started_at, ended_at, duration_sec, is_active) VALUES (?,?,?,?,?,?,?,?,?)",
        (session_id, proc, title, exe, url,
         started_at.isoformat(), ended_at.isoformat(), duration, int(is_active))
    )
    conn.commit()


def write_live(open_since, open_title, open_url, active_proc):
    now = datetime.now()
    entries = []
    for proc, started in open_since.items():
        entries.append({
            "process_name": proc,
            "window_title": open_title.get(proc, ""),
            "url":          open_url.get(proc),
            "started_at":   started.isoformat(),
            "duration_sec": int((now - started).total_seconds()),
            "is_active":    int(proc == active_proc),
        })
    entries.sort(key=lambda x: x["duration_sec"], reverse=True)
    try:
        LIVE_PATH.write_text(json.dumps({"updated_at": now.isoformat(), "entries": entries}), encoding="utf-8")
    except Exception:
        pass


# ── Huvud-loop ─────────────────────────────────────────────────

def run():
    _stop_event.clear()
    logging.info("Tracker starting...")
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    init_db(conn)
    session_id = start_session(conn)

    open_since  = {}
    open_title  = {}
    open_exe    = {}
    open_url    = {}
    active_proc = None
    last_tick   = datetime.now()
    screen_was_inactive = False

    try:
        while True:
            now = datetime.now()

            # Detektera viloläge: om mer än 60s gått sedan förra ticken
            # stäng alla öppna perioder och börja om med ny session
            elapsed = (now - last_tick).total_seconds()
            if elapsed > 60:
                logging.info(f"Wake from sleep detected ({int(elapsed)}s gap) – flushing periods.")
                for proc in list(open_since.keys()):
                    flush_period(conn, session_id, proc,
                                 open_title[proc], open_exe[proc], open_url[proc],
                                 open_since[proc], last_tick, is_active=(proc == active_proc))
                open_since.clear(); open_title.clear(); open_exe.clear(); open_url.clear()
                end_session(conn, session_id)
                session_id = start_session(conn)
                screen_was_inactive = False
            last_tick = now

            # Detektera skärmsläckare / låsskärm
            screen_inactive = _is_screensaver_running()
            if screen_inactive and not screen_was_inactive:
                logging.info("Screensaver/lock detected – flushing periods.")
                for proc in list(open_since.keys()):
                    flush_period(conn, session_id, proc,
                                 open_title[proc], open_exe[proc], open_url[proc],
                                 open_since[proc], now, is_active=(proc == active_proc))
                open_since.clear(); open_title.clear(); open_exe.clear(); open_url.clear()
                end_session(conn, session_id)
                session_id = start_session(conn)
            if not screen_inactive and screen_was_inactive:
                logging.info("Screensaver/lock ended – resuming tracking.")
            screen_was_inactive = screen_inactive

            # Hoppa över resten av loopen medan skärmen är inaktiv
            if screen_inactive:
                if _stop_event.wait(POLL_INTERVAL):
                    break
                continue

            try:
                active_name, active_title, active_exe, active_pid = get_active_window()
            except Exception:
                active_name = active_title = active_exe = active_pid = None

            try:
                visible_procs, visible_info = get_all_visible_windows()
            except Exception:
                visible_procs, visible_info = set(), {}

            # Hämta dokumentsökväg för aktivt icke-webbläsar-program
            active_url = None
            if active_pid and active_name and active_name.lower() not in BROWSER_PROCS:
                active_url = get_document_path(active_pid, active_title or "")

            # Bygg samlad bild
            current = {}
            for proc in visible_procs:
                info = visible_info[proc]
                current[proc] = (info[1], info[2], None)
            if active_name:
                current[active_name] = (active_title, active_exe, active_url)

            # Hantera öppna program
            for proc, (title, exe, url) in current.items():
                if proc not in open_since:
                    open_since[proc] = now
                    open_title[proc] = title
                    open_exe[proc]   = exe
                    open_url[proc]   = url
                elif title != open_title[proc]:
                    flush_period(conn, session_id, proc,
                                 open_title[proc], open_exe[proc], open_url[proc],
                                 open_since[proc], now, is_active=(proc == active_proc))
                    open_since[proc] = now
                    open_title[proc] = title
                    open_exe[proc]   = exe
                    open_url[proc]   = url
                else:
                    if url:
                        open_url[proc] = url

            # Stäng perioder för försvunna program
            for proc in list(set(open_since.keys()) - set(current.keys())):
                flush_period(conn, session_id, proc,
                             open_title[proc], open_exe[proc], open_url[proc],
                             open_since[proc], now, is_active=(proc == active_proc))
                del open_since[proc]
                del open_title[proc]
                del open_exe[proc]
                del open_url[proc]

            active_proc = active_name
            write_live(open_since, open_title, open_url, active_proc)
            if _stop_event.wait(POLL_INTERVAL):
                break  # watchdog begärde stopp

    except KeyboardInterrupt:
        pass
    finally:
        now = datetime.now()
        for proc in list(open_since.keys()):
            flush_period(conn, session_id, proc,
                         open_title[proc], open_exe[proc], open_url[proc],
                         open_since[proc], now, is_active=(proc == active_proc))
        end_session(conn, session_id)
        conn.close()
        try: LIVE_PATH.unlink(missing_ok=True)
        except Exception: pass
        logging.info("Tracker stopped.")


if __name__ == "__main__":
    run()
