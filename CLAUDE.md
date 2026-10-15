# Activity Tracker – Claude-kontextfil

## Vad är det här?
Lokal Windows-app (Python/Flask) som spårar aktiva fönster och program. Körs som system tray-app, visar ett webbgränssnitt på localhost:5757. Distribueras som .exe via Inno Setup + GitHub Releases. Backend på Railway.

## Starta
- Tray-appen: `python tray_app.py` (eller kör `start.bat`)
- Dev-läge parallellt med installerat bygge: `python tray_app.py --dev` → localhost:5758, eget lås `tray.dev.lock`
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
- Watchdog i tray_app kontrollerar `live.json`-ålder (timeout: 90s). Vid hängning startas en **ny process** (`--wait-lock`) och den gamla avslutas med `os._exit(0)` – efter viloläge kan processen hamna i ett läge där inga nya trådar kommer igång. Rör inte tray-ikonen före `os._exit` – en hängd tray-tråd blockerar då för evigt (2026-10-14).
- Watchdogen startar också om webb-servertråden om den dör

**Webbläsarhistorik:**
- Kopierar History-filen till temp för att undvika DB-låsning
- Chrome/Edge: mikrosekunder sedan 1601-01-01 (Chrome-epok)
- Firefox: mikrosekunder sedan Unix-epoken, `moz_historyvisits`-tabell
- Alla profiler skannas

**Projektidentifiering:** regex `\b(?:SI|SP|[IPS])\d{5}\b` — Göteborg (P/S + 5 siffror) och Stockholm (I/SI/SP + 5 siffror), ordgräns på båda sidor

**OTA:**
- Backend serverar `/version` → hämtar från GitHub Releases API
- Backend serverar `/download/<tag>` → proxy till GitHub asset (kräver token)
- Klient lägger uppdatering i "pending", installerar aldrig utan användarens godkännande
- Inno Setup-flaggor: `/VERYSILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS`

**Databas-migrering:** inline med `PRAGMA user_version` i `tracker.py::init_db()`

**Instansskydd:** `msvcrt.locking` på `~/activity_tracker/tray.lock` (dev: `tray.dev.lock`)  
Vid upptaget lås (`_hantera_upptaget_las`): listar andra instanser via PowerShell `Get-CimInstance` (python/pythonw med `tray_app.py`, eller `ActivityTracker.exe`; `--dev` som eget argument skiljer lägena åt). Frisk instans (live.json < 90 s) eller nystartad (< 3 min) → avsluta. Hängd → `taskkill` och ta över låset. Aldrig mer manuell inblandning. **Använd inte `wmic`** – finns inte i nyare Windows 11 (det fick appen att krascha tyst vid start).

**Loggning:** i praktiken till `~/activity_tracker/tracker.log` (tracker.py konfigurerar loggningen först). Oväntade fel i tray_app loggas via `sys.excepthook` – pythonw/exe har ingen konsol.

## Backend-miljövariabler (Railway)
`GMAIL_USER`, `GMAIL_APP_PASSWORD`, `ADMIN_EMAIL`, `GITHUB_TOKEN`, `GITHUB_REPO`, `DB_PATH`

## Aktuell version
`v0.33b` (släppt 2026-07-19). Se `CHANGELOG.md` för fullständig historik.

## Autostart
Appen registreras för autostart via Windows-registret:
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `ActivityTracker`

Värdet pekar normalt på källkoden:
`"C:\Python312\pythonw.exe" "C:\dev\verktyg\activity_tracker\tray_app.py"`

Inno Setup-installern skriver sin egen post (pekar på installerad `.exe`) men den skrivs över manuellt till källkods-sökvägen så att senaste källkod alltid används vid start.

## Bygga installer
PyInstaller → `.exe`, sedan Inno Setup för installationsprogram. Releaser görs via GitHub Releases – backend servar nedladdningar.
`release.ps1` kräver en post `## vX (ej släppt)` i CHANGELOG som matchar `VERSION` i `web_app.py`.
`release.ps1` ska vara sparad som UTF-8 **med BOM** och läsa filer med `-Encoding UTF8` – annars förstör Windows PowerShell 5.1 å/ä/ö i CHANGELOG, MANUAL och CLAUDE.md (hände tidigare, lagat 2026-10-15).
