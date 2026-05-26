"""
Activity Tracker – Geotracking
Loggar position (adress + koordinater) med konfigurerbart intervall.
Loggar bara när positionen förändrats mer än MIN_DISTANCE_M meter.
Skriver ALDRIG position utan att användaren aktiverat funktionen.
"""

import asyncio
import json
import logging
import math
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger("geotracker")

DB_PATH = Path.home() / "activity_tracker" / "activity.db"

# Minsta förflyttning (meter) för att en ny position skall loggas
MIN_DISTANCE_M = 150

# Max rimlig hastighet (km/h) – positioner som kräver högre hastighet
# sedan förra loggen betraktas som felaktiga GPS-avläsningar och kastas bort
MAX_SPEED_KMH = 200

_stop_event   = threading.Event()
_thread       = None
_enabled      = False
_interval_min = 5   # minuter


# ── Haversine-avstånd ──────────────────────────────────────────

def _distance_m(lat1, lon1, lat2, lon2) -> float:
    """Avstånd i meter mellan två koordinater (Haversine)."""
    R = 6_371_000
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


# ── Windows Location API ───────────────────────────────────────

async def _get_position() -> tuple[float, float, float] | None:
    """Returnerar (lat, lon, accuracy_m) eller None vid fel."""
    try:
        from winsdk.windows.devices.geolocation import Geolocator, PositionAccuracy
        loc = Geolocator()
        loc.desired_accuracy = PositionAccuracy.HIGH
        pos = await loc.get_geoposition_async()
        c = pos.coordinate
        return c.latitude, c.longitude, c.accuracy
    except Exception as e:
        log.warning(f"Kunde inte hämta position: {e}")
        return None


# ── Nominatim reverse geocoding ────────────────────────────────

def _reverse_geocode(lat: float, lon: float) -> str:
    """Returnerar läsbar adress för koordinaterna, eller tom sträng."""
    try:
        url = (f"https://nominatim.openstreetmap.org/reverse"
               f"?lat={lat}&lon={lon}&format=json&addressdetails=1")
        req = urllib.request.Request(
            url, headers={"User-Agent": "ActivityTracker/0.13b"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        addr = data.get("address", {})
        road = addr.get("road", "")
        city = (addr.get("city") or addr.get("town")
                or addr.get("village") or addr.get("municipality", ""))
        postcode = addr.get("postcode", "")
        return ", ".join(filter(None, [road, city, postcode]))
    except Exception as e:
        log.warning(f"Reverse geocoding misslyckades: {e}")
        return ""


# ── Databas ────────────────────────────────────────────────────

def _ensure_table():
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS locations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_at    TEXT NOT NULL,
            latitude     REAL NOT NULL,
            longitude    REAL NOT NULL,
            accuracy_m   REAL,
            address      TEXT,
            is_suspicious INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_locations_time ON locations(logged_at);
    """)
    # Migrera befintlig tabell om kolumnen saknas
    cols = [r[1] for r in conn.execute("PRAGMA table_info(locations)").fetchall()]
    if "is_suspicious" not in cols:
        conn.execute("ALTER TABLE locations ADD COLUMN is_suspicious INTEGER DEFAULT 0")
    conn.commit()
    conn.close()


def _save(lat, lon, accuracy, address):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO locations (logged_at, latitude, longitude, accuracy_m, address) "
        "VALUES (?,?,?,?,?)",
        (datetime.now().isoformat(), lat, lon, accuracy, address)
    )
    conn.commit()
    conn.close()




def _last_position() -> tuple[float, float, str] | None:
    """Returnerar (lat, lon, logged_at) för senast loggade position, eller None."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT latitude, longitude, logged_at FROM locations ORDER BY logged_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return (row[0], row[1], row[2]) if row else None
    except Exception:
        return None


# ── Huvudloop ──────────────────────────────────────────────────

def _run_loop(interval_min: int):
    _ensure_table()
    log.info(f"Geotracker startad (intervall: {interval_min} min)")

    while not _stop_event.is_set():
        try:
            result = asyncio.run(_get_position())
            if result:
                lat, lon, acc = result
                last = _last_position()
                if last is not None:
                    dist_m = _distance_m(last[0], last[1], lat, lon)
                    if dist_m < MIN_DISTANCE_M:
                        log.debug("Position oförändrad – inget loggas")
                        _stop_event.wait(interval_min * 60)
                        continue
                    # Hastighetskontroll: kasta bort orimliga GPS-hopp
                    try:
                        elapsed_h = (datetime.now() - datetime.fromisoformat(last[2])).total_seconds() / 3600
                        if elapsed_h > 0:
                            speed_kmh = (dist_m / 1000) / elapsed_h
                            if speed_kmh > MAX_SPEED_KMH:
                                log.warning(
                                    f"GPS-hopp ignorerat: {dist_m/1000:.1f} km på {elapsed_h*60:.0f} min "
                                    f"({speed_kmh:.0f} km/h) – sannolikt felaktig avläsning"
                                )
                                _stop_event.wait(interval_min * 60)
                                continue
                    except Exception:
                        pass
                address = _reverse_geocode(lat, lon)
                _save(lat, lon, acc, address)
                log.info(f"Position loggad: {address} ({lat:.5f}, {lon:.5f}, ±{acc:.0f}m)")
        except Exception as e:
            log.warning(f"Geotracker-fel: {e}")

        _stop_event.wait(interval_min * 60)

    log.info("Geotracker stoppad.")


# ── Publik API ─────────────────────────────────────────────────

def start(interval_min: int = 5):
    """Startar geotracking i bakgrundstråd."""
    global _thread, _enabled, _interval_min
    if _thread and _thread.is_alive():
        return
    _interval_min = interval_min
    _enabled = True
    _stop_event.clear()
    _thread = threading.Thread(
        target=_run_loop, args=(interval_min,), daemon=True, name="geotracker")
    _thread.start()


def stop():
    """Stoppar geotracking."""
    global _enabled
    _enabled = False
    _stop_event.set()


def is_running() -> bool:
    return bool(_thread and _thread.is_alive() and not _stop_event.is_set())
