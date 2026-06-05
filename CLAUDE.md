# Activity Tracker â€“ Claude-kontextfil

## Vad Ã¤r det hÃ¤r?
Lokal Windows-app (Python/Flask) som spÃ¥rar aktiva fÃ¶nster och program. KÃ¶rs som system tray-app, visar ett webbgrÃ¤nssnitt pÃ¥ localhost:5757. Distribueras som .exe via Inno Setup + GitHub Releases. Backend pÃ¥ Railway.

## Starta
- Tray-appen: `python tray_app.py` (eller kÃ¶r `start.bat`)
- Bara webb utan tray: `python web_app.py` â†’ localhost:5757
- Bara tracker: `python tracker.py`
- Backend lokalt: `cd backend && python app.py`

## Filstruktur

| Fil | Syfte |
|---|---|
| `tracker.py` | BakgrundstjÃ¤nst â€“ pollar aktiva fÃ¶nster var 5:e sekund, skriver till SQLite |
| `web_app.py` | Flask-app + fullstÃ¤ndig HTML/CSS/JS som enstrengstemplate (~4000 rader) |
| `tray_app.py` | Samordnar tracker + webb, watchdog, OTA, tray-ikon |
| `updater.py` | OTA-uppdaterare â€“ kollar Railway-backend en gÃ¥ng/dygn |
| `geotracker.py` | Valfri GPS-loggning via Windows Location API + Nominatim |
| `planner.py` | LÃ¤ser Oaks Resursplanering.xlsm (openpyxl, read-only kopia) |
| `backend/app.py` | Railway-backend: registrering, feedback, OTA-distribution via GitHub Releases |
| `setup.py` | Installationsscript |
| `check_layout.py` | Pre-commit hook: validerar layout-invarianter |

## Databas och datafiler

Lokal data sparas i `~/activity_tracker/`:
- `activity.db` â€“ SQLite med tabellerna `sessions`, `periods`, `ai_feedback`, `geo_positions`
- `live.json` â€“ realtidsstatus (uppdateras var 5:e sekund av tracker)
- `app_config.json` â€“ anvÃ¤ndarinstÃ¤llningar (sparas via `/api/config`)
- `planning_cache.json` â€“ cache fÃ¶r resursplanering

Backend (Railway): `users.db` med tabellerna `users`, `feedback`

### Schema â€“ periods-tabellen
```
id, session_id, process_name, window_title, exe_path, url,
started_at, ended_at, duration_sec, is_active
```
Perioder kortare Ã¤n 60 sekunder sparas aldrig (`MIN_PERIOD_SEC = 60`).

## Frontend-arkitektur
All HTML/CSS/JS Ã¤r inbÃ¤ddad som en Python-rÃ¥strÃ¤ng `HTML = r"""..."""` i `web_app.py`. Det Ã¤r en SPA-liknande applikation med flikar: Dashboard, Perioder, Program, Tidslinje. JavaScript hanterar state och gÃ¶r fetch-anrop mot Flask-routes.

**Teman:** dark (default), light (Oaks warm â€“ cream/mÃ¶rkgrÃ¶n/guld), oaks (mÃ¶rkgrÃ¶n/gul)  
**Typsnitt:** Plus Jakarta Sans (UI), JetBrains Mono (siffror/kod), Syne (Ã¤ldre)

## Viktiga tekniska detaljer

**Trackerlogik:**
- `POLL_INTERVAL = 5` sekunder
- VilolÃ¤gesdetektering: om >60s gÃ¥tt sedan fÃ¶rra ticken â†’ flush alla perioder + ny session
- SkÃ¤rmslÃ¤ckar/lÃ¥sskÃ¤rm: `SystemParametersInfoW(0x0072)` â†’ stoppa loggning
- Windows API-anrop kÃ¶rs med timeout via `ThreadPoolExecutor` (skyddar mot hÃ¤ngning)
- Watchdog i tray_app kontrollerar `live.json`-Ã¥lder, startar om tracker vid hÃ¤ngning (timeout: 90s)

**WebblÃ¤sarhistorik:**
- Kopierar History-filen till temp fÃ¶r att undvika DB-lÃ¥sning
- Chrome/Edge: mikrosekunder sedan 1601-01-01 (Chrome-epok)
- Firefox: mikrosekunder sedan Unix-epoken, `moz_historyvisits`-tabell
- Alla profiler skannas

**Projektidentifiering:** regex `\b(?:SI|SP|[IPS])\d{5}\b` â€” GÃ¶teborg (P/S + 5 siffror) och Stockholm (I/SI/SP + 5 siffror), ordgrÃ¤ns pÃ¥ bÃ¥da sidor

**OTA:**
- Backend serverar `/version` â†’ hÃ¤mtar frÃ¥n GitHub Releases API
- Backend serverar `/download/<tag>` â†’ proxy till GitHub asset (krÃ¤ver token)
- Klient lÃ¤gger uppdatering i "pending", installerar aldrig utan anvÃ¤ndarens godkÃ¤nnande
- Inno Setup-flaggor: `/VERYSILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS`

**Databas-migrering:** inline med `PRAGMA user_version` i `tracker.py::init_db()`

**Instansskydd:** `msvcrt.locking` pÃ¥ `~/activity_tracker/tray.lock`  
Vid lÃ¥sfel: kontrollerar via WMI om en verklig pythonw-instans kÃ¶r `tray_app.py`. Om inte â†’ raderar stale lock automatiskt och startar om. Aldrig mer manuell inblandning.

## Backend-miljÃ¶variabler (Railway)
`GMAIL_USER`, `GMAIL_APP_PASSWORD`, `ADMIN_EMAIL`, `GITHUB_TOKEN`, `GITHUB_REPO`, `DB_PATH`

## Aktuellt version
`v0.20b` (släppt 2026-05-29). Pågående: `v0.21b` (ej släppt). Se `CHANGELOG.md` för fullständig historik.

## Autostart
Appen registreras fÃ¶r autostart via Windows-registret:
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run` â†’ `ActivityTracker`

VÃ¤rdet pekar normalt pÃ¥ kÃ¤llkoden:
`"C:\Python312\pythonw.exe" "C:\activity_tracker\tray_app.py"`

Inno Setup-installern skriver sin egen post (pekar pÃ¥ installerad `.exe`) men den skrivs Ã¶ver manuellt till kÃ¤llkods-sÃ¶kvÃ¤gen sÃ¥ att senaste kÃ¤llkod alltid anvÃ¤nds vid start.

## Bygga installer
PyInstaller â†’ `.exe`, sedan Inno Setup fÃ¶r installationsprogram. Releaser gÃ¶rs via GitHub Releases â€“ backend servar nedladdningar.


