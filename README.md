# Activity Tracker

Loggar vilka program och fönster du har öppna medan datorn är aktiv.
Sparar data i en lokal SQLite-databas och erbjuder ett webb-gränssnitt för analys.

---

## Filer

```
activity_tracker/
├── tracker.py    – Bakgrundstjänst (loggar aktiva fönster)
├── web_app.py    – Flask webb-gränssnitt
├── tray_app.py   – System tray-app (samordnar allt)
├── setup.py      – Installationsscript
└── README.md     – Den här filen
```

Data sparas i: `C:\Users\<ditt namn>\activity_tracker\`
- `activity.db`  – SQLite-databas med alla händelser
- `tracker.log`  – Loggfil

---

## Installation

### Krav
- Python 3.9 eller senare  
  Ladda ner: https://www.python.org/downloads/

### Steg 1 – Kör installationsscriptet
```
python setup.py
```
Scriptet installerar beroenden (`flask`, `pystray`, `pillow`) och lägger till autostart i Windows.

### Steg 2 – Starta
Antingen via `start.bat` i app-mappen, eller via genvägen på skrivbordet.

En liten ikon visas i aktivitetsfältet (nere till höger).

---

## Användning

### Dashboard
Dubbelklicka på tray-ikonen (eller högerklicka → *Öppna dashboard*).

Webbläsaren öppnar: **http://localhost:5757**

### Flikar
| Flik | Innehåll |
|---|---|
| **Dashboard** | KPI-kort, topp-program, aktivitet per timme |
| **Logg** | Alla händelser, sökbart och sorterbart |
| **Program** | Sammanfattning per applikation med uppskattad tid |
| **Sessioner** | Datorns aktiva perioder |

### Exportera
Under **Logg** → knappen **↓ CSV** exporterar filtrerade rader till en CSV-fil.

---

## Inställningar

Öppna `tracker.py` och justera:

```python
POLL_INTERVAL = 5   # sekunder mellan varje loggning (default: 5)
```

---

## Autostart

Installationsscriptet lägger automatiskt till en `.bat`-fil i:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```
Det innebär att trackern startar automatiskt varje gång du loggar in i Windows.

### Ta bort autostart
Öppna Run-dialogen (Win+R), skriv `shell:startup` och ta bort `ActivityTracker.bat`.

---

## Felsökning

**Trackern loggar ingenting?**  
Kontrollera `tracker.log` för eventuella fel.

**Dashboard svarar inte?**  
Se till att `tray_app.py` körs. Starta om med `start.bat`.

**Port 5757 används av annat program?**  
Ändra `WEB_PORT = 5757` i `tray_app.py` och `web_app.py`.
