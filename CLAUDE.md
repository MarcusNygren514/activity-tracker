# Activity Tracker – Claude-kontextfil

## Vad är det här?
Lokal Windows-app (Python/Flask) som spårar aktiva fönster och program. Körs som system tray-app, visar ett webbgränssnitt på localhost:5757. Distribueras som .exe via Inno Setup + GitHub Releases. Backend på Railway.

## Starta
- Tray-appen: `python tray_app.py` (eller kör `start.bat`)
- Bara webb utan tray: `python web_app.py` → localhost:5757
- Bara tracker: `python tracker.py`
- Backend lokalt: `cd backend && python app.py`

## Filstruktur

| Fil | Syfte |
|---|---|
| `tracker.py` | Bakgrundstjänst – pollar aktiva fönster var 5:e sekund, skriver till SQLite |
| `web_app.py` | Flask-app + fullständig HTML/CSS/JS som enstrengstemplate (~4000 rader) |
| `tray_app.py` | Samordnar tracker + webb, watchdog, OTA, tray-ikon |
| `updater.py` | OTA-uppdaterare – kollar Railway-backend en gång/dygn |
| `geotracker.py` | Valfri GPS-loggning via Windows Location API + Nominatim |
| `planner.py` | Läser Oaks Resursplanering.xlsm (openpyxl, read-only kopia) |
| `backend/app.py` | Railway-backend: registrering, feedback, OTA-distribution via GitHub Releases |
| `setup.py` | Installationsscript |
| `check_layout.py` | Pre-commit hook: validerar layout-invarianter |

## Databas och datafiler

Lokal data sparas i `~/activity_tracker/`:
- `activity.db` – SQLite med tabellerna `sessions`, `periods`, `ai_feedback`, `geo_positions`
- `live.json` – realtidsstatus (uppdateras var 5:e sekund av tracker)
- `app_config.json` – användarinställningar (sparas via `/api/config`)
- `planning_cache.json` – cache för resursplanering

Backend (Railway): `users.db` med tabellerna `users`, `feedback`

### Schema – periods-tabellen
```
id, session_id, process_name, window_title, exe_path, url,
started_at, ended_at, duration_sec, is_active
```
Perioder kortare än 60 sekunder sparas aldrig (`MIN_PERIOD_SEC = 60`).

## Frontend-arkitektur
All HTML/CSS/JS är inbäddad som en Python-råsträng `HTML = r"""..."""` i `web_app.py`. Det är en SPA-liknande applikation med flikar: Dashboard, Perioder, Program, Tidslinje. JavaScript hanterar state och gör fetch-anrop mot Flask-routes.

**Teman:** dark (default), light (Oaks warm – cream/mörkgrön/guld), oaks (mörkgrön/gul)  
**Typsnitt:** Plus Jakarta Sans (UI), JetBrains Mono (siffror/kod), Syne (äldre)

## Viktiga tekniska detaljer

**Trackerlogik:**
- `POLL_INTERVAL = 5` sekunder
- Vilolägesdetektering: om >60s gått sedan förra ticken → flush alla perioder + ny session
- Skärmsläckar/låsskärm: `SystemParametersInfoW(0x0072)` → stoppa loggning
- Windows API-anrop körs med timeout via `ThreadPoolExecutor` (skyddar mot hängning)
- Watchdog i tray_app kontrollerar `live.json`-ålder, startar om tracker vid hängning (timeout: 90s)

**Webbläsarhistorik:**
- Kopierar History-filen till temp för att undvika DB-låsning
- Chrome/Edge: mikrosekunder sedan 1601-01-01 (Chrome-epok)
- Firefox: mikrosekunder sedan Unix-epoken, `moz_historyvisits`-tabell
- Alla profiler skannas

**Projektidentifiering:** regex `[PS]\d{5}` (P eller S + exakt 5 siffror)

**OTA:**
- Backend serverar `/version` → hämtar från GitHub Releases API
- Backend serverar `/download/<tag>` → proxy till GitHub asset (kräver token)
- Klient lägger uppdatering i "pending", installerar aldrig utan användarens godkännande
- Inno Setup-flaggor: `/VERYSILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS`

**Databas-migrering:** inline med `PRAGMA user_version` i `tracker.py::init_db()`

**Instansskydd:** `msvcrt.locking` på `~/activity_tracker/tray.lock`

## Backend-miljövariabler (Railway)
`GMAIL_USER`, `GMAIL_APP_PASSWORD`, `ADMIN_EMAIL`, `GITHUB_TOKEN`, `GITHUB_REPO`, `DB_PATH`

## Aktuellt version
`v0.17b` (släppt 2026-04-23). Se `CHANGELOG.md` för fullständig historik.

## Autostart
Appen registreras för autostart via Windows-registret:
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `ActivityTracker`

Värdet pekar normalt på källkoden:
`"C:\Python312\pythonw.exe" "C:\activity_tracker\tray_app.py"`

Inno Setup-installern skriver sin egen post (pekar på installerad `.exe`) men den skrivs över manuellt till källkods-sökvägen så att senaste källkod alltid används vid start.

## Bygga installer
PyInstaller → `.exe`, sedan Inno Setup för installationsprogram. Releaser görs via GitHub Releases – backend servar nedladdningar.
