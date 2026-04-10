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
import urllib.request
from pathlib import Path

# Importera moduler – fungerar både direkt och paketerat med PyInstaller
if getattr(sys, 'frozen', False):
    # Körs som PyInstaller-exe – modulerna är inbyggda
    _app_dir = Path(sys.executable).parent
else:
    _app_dir = Path(__file__).parent
sys.path.insert(0, str(_app_dir))
import updater
import tracker
import web_app

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

WEB_PORT = 5757

# ── Global state ──────────────────────────────────────────────
tracker_thread = None
web_thread = None
tracker_running = False


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
    if tracker_running:
        return

    def run():
        global tracker_running
        tracker_running = True
        try:
            tracker.run()
        except Exception as e:
            print(f"Tracker error: {e}")
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
        except Exception as e:
            print(f"Web error: {e}")

    web_thread = threading.Thread(target=run, daemon=True)
    web_thread.start()
    print(f"[Tray] Webb-server startad på port {WEB_PORT}")


def open_browser(icon=None, item=None):
    webbrowser.open(f"http://localhost:{WEB_PORT}")


def quit_app(icon, item):
    print("[Tray] Avslutar...")
    icon.stop()
    os._exit(0)


def _build_menu(tray):
    """Bygger tray-menyn. Lägger till uppdateringsval om ny version väntar."""
    pending = updater.get_pending()
    items = [
        item("📊 Öppna dashboard", open_browser, default=True),
        pystray.Menu.SEPARATOR,
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
        "Activity Tracker",
    )

    # Koppla OTA-callbacks innan vi bygger menyn
    updater.on_update_available = lambda: _build_menu(tray)
    updater.on_update_cleared   = lambda: _build_menu(tray)

    _build_menu(tray)
    return tray


LIVE_PATH = Path.home() / "activity_tracker" / "live.json"
HEARTBEAT_TIMEOUT = 90  # sekunder utan tick → hängd


def watchdog():
    """Startar om trackern om den kraschar eller hänger (t.ex. efter viloläge)."""
    global tracker_running
    while True:
        time.sleep(30)
        if not tracker_running:
            print("[Watchdog] Tracker är nere – startar om...")
            start_tracker()
        else:
            # Kontrollera att trackern faktiskt tickar (uppdaterar live.json)
            try:
                age = time.time() - LIVE_PATH.stat().st_mtime
                if age > HEARTBEAT_TIMEOUT:
                    print(f"[Watchdog] Tracker hängd ({int(age)}s sedan senaste tick) – tvångsstarta om...")
                    tracker.stop()          # signalera stop-event
                    time.sleep(2)           # ge tråden en chans att avsluta
                    tracker_running = False  # tvinga flaggan om tråden fortfarande hänger
                    start_tracker()
            except FileNotFoundError:
                pass  # live.json finns inte än (precis startat)


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
    time.sleep(1)

    # Watchdog som startar om trackern vid krasch/sleep
    wd = threading.Thread(target=watchdog, daemon=True)
    wd.start()

    # OTA-checker (aktiveras när BACKEND_URL sätts i web_app)
    try:
        updater.configure(
            backend_url=web_app.BACKEND_URL,
            current_version=web_app.VERSION,
        )
        updater.start_background_checker()
    except Exception as e:
        logging.warning(f"OTA-checker kunde inte startas: {e}")

    # Skapa och kör tray-ikonen
    tray = create_tray()
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
    # Förhindra flera instanser med en låsfil
    _LOCK = Path.home() / "activity_tracker" / "tray.lock"
    try:
        _LOCK.parent.mkdir(exist_ok=True)
        _lock_fh = open(_LOCK, "w")
        import msvcrt
        msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
    except (OSError, IOError):
        logging.warning("En instans körs redan – avslutar")
        import sys; sys.exit(0)

    try:
        logging.info("tray_app startar")
        main()
        logging.info("main() returnerade normalt")
    except BaseException:
        logging.critical("Krasch i main:\n" + traceback.format_exc())
        raise
