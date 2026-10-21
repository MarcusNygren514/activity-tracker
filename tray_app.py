"""
Activity Tracker – System Tray App
Hanterar bakgrundstjänsten och webb-gränssnittet via ikon i aktivitetsfältet.
Kräver: pip install pystray pillow
"""

import sys
import threading
import webbrowser
import subprocess
import os
import time
import logging
import traceback
import json
import re
import urllib.request
from pathlib import Path

# Importera moduler – fungerar både direkt och paketerat med PyInstaller
if getattr(sys, 'frozen', False):
    # Körs som PyInstaller-exe – modulerna är inbyggda
    _app_dir = Path(sys.executable).parent
else:
    _app_dir = Path(__file__).parent
sys.path.insert(0, str(_app_dir))
if "--doc-helper" in sys.argv:
    # Exe-läge: samma exe startas som hjälpprocess för psutil.open_files() (se doc_helper.py).
    # Avgrena före övriga importer så att hjälpprocessen inte laddar Flask m.m.
    import doc_helper
    doc_helper.serve_from_env()
    sys.exit(0)
import updater
import tracker
import web_app
import screenshot_watcher

# Logga till fil – fångar kraschar som pythonw.exe annars sväljer
_LOG_FILE = Path.home() / "activity_tracker" / "tray.log"
_LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
logging.getLogger("PIL").setLevel(logging.WARNING)


def _logga_okant_fel(typ, varde, tb):
    """pythonw/exe har ingen konsol – utan detta dör processen helt tyst vid ett oväntat fel."""
    logging.critical("Oväntat fel:\n" + "".join(traceback.format_exception(typ, varde, tb)))


sys.excepthook = _logga_okant_fel

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
except ImportError:
    print("Installerar beroenden...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pystray", "pillow", "flask"])
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw

_DEV_MODE = "--dev" in sys.argv
# Schemalagd aktivitet (ActivityTracker-vakt) startar med --scheduled var 15:e min och
# vid upplåsning. Har användaren valt "Avsluta" ska den inte starta appen igen –
# markeringen tas bort vid nästa vanliga start (autostart vid inloggning eller manuellt).
_SCHEDULED_ARG = "--scheduled"
_QUIT_MARKER = Path.home() / "activity_tracker" / ("user_quit.dev" if _DEV_MODE else "user_quit")
WEB_PORT = 5758 if _DEV_MODE else 5757

# ── Global state ──────────────────────────────────────────────
tracker_thread = None
web_thread = None
tracker_running = False
_tracker_lock = threading.Lock()
_tray = None


def make_icon(active=True):
    """Klocka med visare i Oaks-färger."""
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    bg     = (64, 78, 79)   if active else (44, 53, 53)
    yellow = (255, 204, 0)  if active else (140, 112, 0)
    d.ellipse([2, 2, 61, 61], fill=bg)
    d.ellipse([12, 12, 51, 51], outline=yellow, width=3)
    d.line([32, 32, 22, 20], fill=yellow, width=3)
    d.line([32, 32, 32, 16], fill=yellow, width=3)
    d.ellipse([28, 28, 35, 35], fill=yellow)
    return img


def start_ollama():
    """Startar Ollama i bakgrunden utan synligt fönster, om det inte redan körs."""
    try:
        req = urllib.request.Request("http://localhost:11434")
        urllib.request.urlopen(req, timeout=2)
        logging.info("Ollama körs redan")
        return
    except Exception:
        pass
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logging.info("Ollama startad i bakgrunden")
    except FileNotFoundError:
        logging.warning("ollama.exe hittades inte – Maj-Britt kräver manuell start")


def start_tracker():
    global tracker_thread, tracker_running
    with _tracker_lock:
        if tracker_running:
            return
        tracker_running = True

    def run():
        global tracker_running
        try:
            tracker.run()
        except Exception:
            logging.exception("Tracker kraschade")
        finally:
            tracker_running = False

    tracker_thread = threading.Thread(target=run, daemon=True)
    tracker_thread.start()
    print("[Tray] Tracker startad")


def start_web():
    global web_thread

    def run():
        try:
            web_app.run(port=WEB_PORT)
        except Exception:
            logging.exception("Webb-servern kraschade")

    web_thread = threading.Thread(target=run, daemon=True)
    web_thread.start()
    print(f"[Tray] Webb-server startad på port {WEB_PORT}")


def open_browser(icon=None, item=None):
    webbrowser.open(f"http://localhost:{WEB_PORT}")


def quit_app(icon, item):
    print("[Tray] Avslutar...")
    try:
        _QUIT_MARKER.touch()
    except OSError:
        pass
    icon.stop()
    os._exit(0)


def _build_menu(tray):
    """Bygger tray-menyn. Lägger till uppdateringsval om ny version väntar."""
    pending = updater.get_pending()
    items = [
        item("📊 Öppna dashboard", open_browser, default=True),
        pystray.Menu.SEPARATOR,
        item(f"Version {web_app.VERSION}", lambda *a: None, enabled=False),
        item("Tracker: aktiv ✓", lambda *a: None, enabled=False),
        item(f"Webb: localhost:{WEB_PORT}", lambda *a: None, enabled=False),
    ]
    if pending:
        items += [
            pystray.Menu.SEPARATOR,
            item(f"⬆ Installera {pending['version']}", lambda *a: updater.install_pending()),
            item("Hoppa över denna version", lambda *a: updater.skip_pending()),
        ]
    items += [
        pystray.Menu.SEPARATOR,
        item("Avsluta", quit_app),
    ]
    tray.menu = pystray.Menu(*items)


def create_tray():
    icon_img = make_icon(active=True)

    tray = pystray.Icon(
        "ActivityTracker",
        icon_img,
        f"Activity Tracker {web_app.VERSION}",
    )

    # Koppla OTA-callbacks innan vi bygger menyn
    updater.on_update_available = lambda: _build_menu(tray)
    updater.on_update_cleared   = lambda: _build_menu(tray)
    updater._tray_icon = tray

    _build_menu(tray)
    return tray


LIVE_PATH = Path.home() / "activity_tracker" / "live.json"
HEARTBEAT_TIMEOUT = 90  # sekunder utan tick → hängd
_WAIT_LOCK_ARG = "--wait-lock"


def restart_process():
    """Startar en ny instans av appen och avslutar den här direkt.

    En hängd tracker kan inte alltid startas om inom processen: efter viloläge
    har processen fastnat i ett läge där inga nya trådar kommer igång, och då
    hänger även watchdogens omstartsförsök. En ny process startar rent.
    Popen skapar inga trådar i den här processen.
    """
    args = [a for a in sys.argv[1:] if a != _WAIT_LOCK_ARG] + [_WAIT_LOCK_ARG]
    if getattr(sys, 'frozen', False):
        cmd = [sys.executable] + args
    else:
        cmd = [sys.executable, str(Path(__file__).resolve())] + args
    logging.warning(f"[Watchdog] Startar om hela processen: {cmd}")
    try:
        subprocess.Popen(
            cmd,
            cwd=str(_app_dir),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except Exception:
        logging.exception("[Watchdog] Kunde inte starta ny process – behåller den gamla")
        return
    # Avsluta direkt – rör inte tray-ikonen. Efter viloläge kan tray-tråden vara hängd,
    # och då blockerade `_tray.visible = False` för evigt: den gamla processen dog aldrig
    # och höll kvar låset, så den nya kunde inte starta (2026-10-14). En kvarglömd ikon
    # försvinner av sig själv när musen förs över den.
    os._exit(0)


def _andra_instanser():
    """Andra körande instanser i samma läge (stabil/dev): [(pid, startad som unix-tid eller None)].
    None om det inte gick att ta reda på. wmic finns inte i nyare Windows 11 – därför PowerShell."""
    ps = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { ($_.Name -match '^pythonw?\\.exe$' -and $_.CommandLine -match 'tray_app\\.py') "
        "-or $_.Name -eq 'ActivityTracker.exe' } | "
        "Select-Object ProcessId, CommandLine, "
        "@{n='Start';e={ if ($_.CreationDate) { [DateTimeOffset]::new($_.CreationDate).ToUnixTimeSeconds() } }} | "
        "ConvertTo-Json -Compress"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        data = json.loads(r.stdout or "[]")
    except Exception:
        logging.exception("Kunde inte lista processer")
        return None
    if isinstance(data, dict):
        data = [data]
    egna = {os.getpid(), os.getppid()}
    instanser = []
    for p in data:
        cl = p.get("CommandLine") or ""
        if p.get("ProcessId") in egna:
            continue
        if "--doc-helper" in cl:
            continue  # trackerns hjälpprocess (ActivityTracker.exe --doc-helper), ingen instans
        # --dev som eget argument – inte som del av en sökväg
        if bool(re.search(r'(^|\s)"?--dev"?(\s|$)', cl)) != _DEV_MODE:
            continue
        instanser.append((p["ProcessId"], p.get("Start")))
    return instanser


def _hantera_upptaget_las(ta_las):
    """Låset hålls av någon annan. Kör en frisk instans → avsluta. Har den inte tickat på
    länge (hängd, t.ex. efter viloläge) → avsluta den och ta över, så att en ny start
    alltid fungerar utan manuell inblandning."""
    instanser = _andra_instanser()
    if instanser:
        try:
            alder = time.time() - LIVE_PATH.stat().st_mtime
        except FileNotFoundError:
            alder = float("inf")
        # En nystartad instans har inte hunnit ticka – rör den inte.
        nystartad = any(start and time.time() - start < 2 * HEARTBEAT_TIMEOUT for _, start in instanser)
        # Direkt efter uppvaknande (vakten körs vid upplåsning) har en frisk instans
        # kanske inte hunnit ticka än – ge den en chans innan den dödas
        for _ in range(20 if alder > HEARTBEAT_TIMEOUT and not nystartad else 0):
            time.sleep(1)
            try:
                alder = time.time() - LIVE_PATH.stat().st_mtime
            except FileNotFoundError:
                pass
            if alder <= HEARTBEAT_TIMEOUT:
                break
        if alder <= HEARTBEAT_TIMEOUT or nystartad:
            logging.warning("En instans körs redan – avslutar")
            sys.exit(0)
        pids = [pid for pid, _ in instanser]
        logging.warning(f"Instans {pids} har inte tickat på {int(alder)}s – avslutar den och tar över")
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    elif instanser is None:
        logging.warning("Kunde inte avgöra om en instans körs – försöker ta låset en stund till")
    for _ in range(15):
        try:
            return ta_las()
        except OSError:
            time.sleep(1)
    logging.error("Kunde inte ta låset – avslutar")
    sys.exit(1)


def watchdog():
    """Startar om trackern och webb-servern om de kraschar eller hänger (t.ex. efter viloläge)."""
    global tracker_running
    last_loop = time.time()
    resumed_at = 0.0
    while True:
        time.sleep(30)
        now = time.time()
        # Har watchdogen själv stått still (datorn har sovit) hinner den annars vakna före
        # trackern och se en gammal live.json – räkna i så fall från uppvaknandet
        if now - last_loop > 60:
            resumed_at = now
        last_loop = now
        if not tracker_running:
            print("[Watchdog] Tracker är nere – startar om...")
            start_tracker()
        else:
            # Kontrollera att trackern faktiskt tickar (uppdaterar live.json)
            try:
                age = now - max(LIVE_PATH.stat().st_mtime, resumed_at)
                if age > HEARTBEAT_TIMEOUT:
                    logging.warning(f"[Watchdog] Tracker hängd ({int(age)}s sedan senaste tick)")
                    restart_process()
            except FileNotFoundError:
                pass  # live.json finns inte än (precis startat)

        # Webb-servern har ingen egen omstartslogik – om tråden kraschar
        # (t.ex. socket-fel kring sömn/uppvakning) lyssnar porten aldrig
        # igen om inte något startar om den.
        if web_thread is None or not web_thread.is_alive():
            logging.warning("[Watchdog] Webb-servern är nere – startar om...")
            start_web()


def on_start(icon):
    """Körs av pystray direkt efter att tray-ikonen startat."""
    def _notify():
        time.sleep(2)
        try:
            icon.notify("Tracker och webb-server körs ✓\nlocalhost:5757", "Activity Tracker")
            time.sleep(5)
            icon.remove_notification()
        except Exception:
            pass
    threading.Thread(target=_notify, daemon=True).start()


def main():
    print("[Activity Tracker] Startar...")
    logging.info("main() startar")

    # Starta bakgrundstjänster
    start_ollama()
    start_tracker()
    time.sleep(1)
    start_web()
    if web_app.load_config().get("screenshot_rename_enabled", True):
        screenshot_watcher.start()
    time.sleep(1)

    # Watchdog som startar om trackern vid krasch/sleep
    wd = threading.Thread(target=watchdog, daemon=True)
    wd.start()

    # OTA-checker – kollar GitHub Releases direkt
    try:
        updater.configure(current_version=web_app.VERSION)
        updater.start_background_checker()
    except Exception as e:
        logging.warning(f"OTA-checker kunde inte startas: {e}")

    # Skapa och kör tray-ikonen
    global _tray
    tray = _tray = create_tray()
    logging.info("Startar tray")
    print("[Activity Tracker] Klar! Ikon i aktivitetsfältet.")
    try:
        tray.run_detached()
        logging.info("tray.run_detached() OK – ikon aktiv")
        on_start(tray)
    except AttributeError:
        logging.info("run_detached saknas, använder run()")
        threading.Thread(target=lambda: tray.run(setup=on_start), daemon=True).start()
    except Exception:
        logging.critical("Tray kraschade:\n" + traceback.format_exc())

    # Håll huvudtråden vid liv – quit_app() anropar os._exit(0)
    logging.info("Huvudloop startar")
    try:
        while True:
            time.sleep(10)
    except BaseException as e:
        logging.critical(f"Huvudloop avbröts: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Förhindra flera instanser med en låsfil (separata lås för stabil/dev)
    _LOCK = Path.home() / "activity_tracker" / ("tray.dev.lock" if _DEV_MODE else "tray.lock")
    import msvcrt, sys

    if _SCHEDULED_ARG in sys.argv:
        if _QUIT_MARKER.exists():
            sys.exit(0)  # användaren har valt Avsluta – starta inte igen
    else:
        _QUIT_MARKER.unlink(missing_ok=True)

    def _acquire_lock():
        _LOCK.parent.mkdir(exist_ok=True)
        fh = open(_LOCK, "w")
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        return fh

    _lock_fh = None
    if _WAIT_LOCK_ARG in sys.argv:
        # Startad av watchdogens restart_process() – vänta tills den gamla
        # processen har avslutats och släppt låset
        for _ in range(30):
            try:
                _lock_fh = _acquire_lock()
                logging.info("Omstartad av watchdog – låset taget")
                break
            except (OSError, IOError):
                time.sleep(1)
    if _lock_fh is None:
        try:
            _lock_fh = _acquire_lock()
        except (OSError, IOError):
            _lock_fh = _hantera_upptaget_las(_acquire_lock)

    try:
        logging.info("tray_app startar")
        main()
        logging.info("main() returnerade normalt")
    except BaseException:
        logging.critical("Krasch i main:\n" + traceback.format_exc())
        raise
