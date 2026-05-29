"""
Screenshot Watcher – döper om nya skärmdumpar med aktivt fönsters namn.
Pollar Pictures\\Screenshots var 2:e sekund och byter namn på nytillkomna filer.
"""

import os
import re
import threading
import time
import logging
import winreg
from datetime import datetime
from pathlib import Path

import tracker

POLL_INTERVAL = 2   # sekunder

# FOLDERID_Screenshots – fungerar oavsett Windows-språk
_SCREENSHOTS_FOLDER_GUID = "{B7BEDE81-DF94-4682-A7D8-57A52620B86F}"


def _get_screenshots_dir() -> Path:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        val, _ = winreg.QueryValueEx(key, _SCREENSHOTS_FOLDER_GUID)
        winreg.CloseKey(key)
        return Path(os.path.expandvars(val))
    except Exception:
        return Path.home() / "Pictures" / "Screenshots"


SCREENSHOTS_DIR = _get_screenshots_dir()

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n]+')

log = logging.getLogger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _sanitize(name: str, max_len: int = 80) -> str:
    name = _INVALID_CHARS.sub("-", name).strip(" -.")
    return name[:max_len] if name else "Screenshot"


def _new_name(base: str, ts: str, suffix: str) -> str:
    return f"{base} {ts}{suffix}"


def _watch():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    known = {f for f in SCREENSHOTS_DIR.iterdir() if f.is_file()}

    while not _stop_event.is_set():
        _stop_event.wait(POLL_INTERVAL)
        try:
            current = {f for f in SCREENSHOTS_DIR.iterdir() if f.is_file()}
        except Exception as e:
            log.warning(f"[ScreenshotWatcher] Kunde inte läsa mapp: {e}")
            continue

        new_files = current - known
        known      = current

        for path in new_files:
            if re.search(r'\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}', path.stem):
                continue

            base = _sanitize(tracker.get_last_window_title())
            ts   = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            new_path = path.parent / _new_name(base, ts, path.suffix)

            counter = 1
            while new_path.exists() and counter <= 100:
                new_path = path.parent / _new_name(base, ts, f" ({counter}){path.suffix}")
                counter += 1

            try:
                path.rename(new_path)
                log.info(f"[ScreenshotWatcher] {path.name} → {new_path.name}")
            except Exception as e:
                log.warning(f"[ScreenshotWatcher] Kunde inte byta namn på {path.name}: {e}")

            known.discard(path)
            known.add(new_path)


def start():
    """Startar screenshot-watchern i en bakgrundstråd."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_watch, daemon=True, name="ScreenshotWatcher")
    _thread.start()
    log.info("[ScreenshotWatcher] Startad, bevakar: %s", SCREENSHOTS_DIR)


def stop():
    """Stoppar screenshot-watchern."""
    _stop_event.set()
    log.info("[ScreenshotWatcher] Stoppad.")
