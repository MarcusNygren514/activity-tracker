"""
Activity Tracker – OTA-uppdaterare
Kollar ny version direkt mot GitHub Releases API en gång per dag.
Installerar ALDRIG utan att användaren godkänner via tray-menyn.
"""

import os
import re
import json
import time
import shutil
import logging
import tempfile
import threading
import subprocess
import urllib.request
from pathlib import Path

log = logging.getLogger("updater")

# ── Konfiguration ─────────────────────────────────────────────────
GITHUB_REPO     = "MarcusNygren514/activity-tracker"
CURRENT_VERSION = ""
CHECK_INTERVAL  = 86400    # sekunder (1 dygn)

_GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_tray_icon    = None
_app_dir      = Path(__file__).parent
_skipped_file = _app_dir / "skipped_versions.json"

# ── Väntande uppdatering ──────────────────────────────────────────
_pending      = None        # {"version": "v1.1", "url": "...", "notes": "..."}
_pending_lock = threading.Lock()
_installing   = False

# ── Callbacks (sätts från tray_app) ──────────────────────────────
on_update_available = None
on_update_cleared   = None


def configure(current_version: str, tray_icon=None, app_dir: Path | None = None):
    global CURRENT_VERSION, _tray_icon, _app_dir, _skipped_file
    CURRENT_VERSION = current_version
    _tray_icon      = tray_icon
    if app_dir:
        _app_dir      = app_dir
        _skipped_file = app_dir / "skipped_versions.json"


def _notify(title: str, msg: str):
    if _tray_icon:
        try:
            _tray_icon.notify(msg, title)
        except Exception:
            pass


def _version_tuple(v: str):
    return tuple(int(x) for x in re.findall(r'\d+', v)) or (0,)


def _load_skipped() -> set:
    try:
        return set(json.loads(_skipped_file.read_text()))
    except Exception:
        return set()


def _save_skipped(versions: set):
    try:
        _skipped_file.write_text(json.dumps(sorted(versions)))
    except Exception as e:
        log.warning(f"Kunde inte spara hoppade versioner: {e}")


def get_pending() -> dict | None:
    with _pending_lock:
        return _pending


def skip_pending():
    global _pending
    with _pending_lock:
        if _pending:
            skipped = _load_skipped()
            skipped.add(_pending["version"])
            _save_skipped(skipped)
            log.info(f"Version {_pending['version']} markerad som hoppad")
            _pending = None
    if on_update_cleared:
        try:
            on_update_cleared()
        except Exception:
            pass


def install_pending():
    global _installing
    with _pending_lock:
        if _installing:
            return
        info = _pending
        if not info:
            return
        _installing = True
    t = threading.Thread(target=_download_and_install,
                         args=(info["url"], info["version"]),
                         daemon=True, name="OTA-install")
    t.start()


def check_and_update(force: bool = False):
    """
    Kollar om ny version finns via GitHub Releases API.
    Sätter _pending och anropar on_update_available – installerar INTE automatiskt.
    """
    global _pending

    try:
        req = urllib.request.Request(
            _GITHUB_API,
            headers={
                "User-Agent":  "ActivityTracker",
                "Accept":      "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        log.warning(f"Kunde inte kontrollera version: {e}")
        return

    latest = data.get("tag_name", "")
    notes  = data.get("body", "")
    asset  = next(
        (a for a in data.get("assets", []) if a["name"].endswith(".exe")),
        None,
    )
    dl_url = asset["browser_download_url"] if asset else None
    size_b = asset["size"] if asset else 0

    if not latest or not dl_url:
        log.warning("GitHub-svaret saknar version eller nedladdningslänk")
        return

    try:
        if not force and _version_tuple(latest) <= _version_tuple(CURRENT_VERSION):
            log.info(f"Ingen uppdatering: {CURRENT_VERSION} är senaste")
            return
    except Exception:
        pass

    if not force and latest in _load_skipped():
        log.info(f"Version {latest} är hoppad av användaren")
        return

    log.info(f"Ny version hittad: {latest} (nuvarande: {CURRENT_VERSION})")

    size_mb = f"{size_b / 1_048_576:.1f} MB" if size_b else ""

    with _pending_lock:
        _pending = {"version": latest, "url": dl_url, "notes": notes, "size_mb": size_mb}

    _notify(
        "Uppdatering tillgänglig",
        f"Activity Tracker {latest} finns.\n"
        f"Öppna tray-menyn för att installera eller hoppa över.",
    )

    if on_update_available:
        try:
            on_update_available()
        except Exception as e:
            log.warning(f"on_update_available-callback misslyckades: {e}")


def _download_and_install(url: str, version: str):
    global _pending, _installing
    tmp_dir = None
    try:
        tmp_dir  = Path(tempfile.mkdtemp())
        exe_path = tmp_dir / f"ActivityTracker_{version}_setup.exe"

        log.info(f"Laddar ned: {url} → {exe_path}")
        _notify("Laddar ned uppdatering…", f"Activity Tracker {version} laddas ned.")

        req = urllib.request.Request(url, headers={"User-Agent": "ActivityTracker"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            exe_path.write_bytes(resp.read())

        log.info("Nedladdning klar – startar installer")
        _notify("Installerar…", f"Activity Tracker {version} installeras. Appen startar om.")

        subprocess.Popen(
            [str(exe_path), "/VERYSILENT", "/SUPPRESSMSGBOXES",
             "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS",
             "/LOG=" + str(tmp_dir / "install.log")],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        with _pending_lock:
            _pending = None

        time.sleep(3)
        os._exit(0)

    except Exception as e:
        log.error(f"Uppdatering misslyckades: {e}")
        _notify("Uppdatering misslyckades", str(e))
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        _installing = False


def start_background_checker():
    """Startar en bakgrundstråd som kollar en gång per dag."""
    def _loop():
        time.sleep(30)
        while True:
            check_and_update()
            time.sleep(CHECK_INTERVAL)

    t = threading.Thread(target=_loop, daemon=True, name="OTA-checker")
    t.start()
    log.info("OTA-checker startad (GitHub API direkt)")
