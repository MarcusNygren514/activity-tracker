# Ändringslogg – Activity Tracker

## v0.14b (ej släppt)
- Valfri platsloggning (geotracking) via Windows Location API
- Adresser hämtas via Nominatim/OpenStreetMap – inget skickas till externa tjänster
- Loggar bara vid förflyttning > 150m – sparar resurser och batteri
- Konfigurerbart loggningsintervall (1 / 5 / 15 / 30 min)
- På/av-toggle i Inställningar med tydlig integritetsinformation
- Resor-sektion i Tidslinje-fliken (kollapsbar) med tid, adress och noggrannhet
- Resursplanering i Tidslinje gjord kollapsbar
- Maj-Britt får tillgång till platsdata och resursplanering i sina svar
- Uppdatera-knappen placerad direkt efter datumfälten i Dashboard och Program
- Buggfix: Uppdatera-knappen låg fel i Program-fliken

## v0.13b (2026-04-12)
- Resursplanering: ny Gantt-vy i Tidslinje-fliken
- Inställningssida tillagd (resursplanering opt-in)
- Veckoformat visas som "V 15" istället för "V2615"
- Totalrad med summerade timmar per vecka i planeringen
- Innevarande vecka markerad med accentfärg och ◀
- Övriga veckor tonade för bättre kontrast
- Tidsstämpel för senaste laddning av aktiviteter (datum + tid utan sekunder)
- Beskrivningstext tillagd på inställningssidan för resursplanering
- Resursplanering laddas automatiskt när Tidslinje-fliken öppnas
- Planeringscache sparas lokalt – fungerar även utan nätverksåtkomst
- Tidsstämpeln visar om data är färsk eller hämtad från cache
- Klickbara URL:er från webbläsarhistorik (Chrome/Edge) i Perioder-fliken
- Klickbara URL:er även i Program-fliken (Titlar-vyn)
- Stöd för alla Chrome/Edge-profiler (ej bara Default)
- Projektfilter i Perioder-, Program- och Tidslinje-flikarna
- Projektnummer (P12345) identifieras automatiskt i fönsterrubriker, URL:er och sökvägar
- Nyckelordsmatchning mot projektnamn för aktiviteter utan synligt projektnummer
- Tooltip på projektobjekt i dropdown-listan visar fullständigt projektnamn
- Projektdropdown visar endast projekt som identifierats i vald tidsperiod
- Hela resursdokumentet (alla resurser) skannas för projektnummer vid inläsning
- Projekt utan namn (ej i resursdokumentet) visas ändå om de hittas i aktivitetsdatan
- S-projekt (S12345) stöds nu parallellt med P-projekt
- Visio (.vsdx/.vsd), AutoCAD (.dwg/.dxf) och MS Project (.mpp) läggs nu till som dokumenttyper
- Tooltip på tider i Program-fliken visar förgrunds- respektive bakgrundstid
- Tooltip hamnar till vänster om markören om den annars skulle hamna utanför skärmen
- Tidslinje-hover visar nu både aktiv tid och total tid
- Processnamn i Tidslinje använder samma typsnitt som övriga flikar
- "Total öppen tid" på Dashboard ersatt med "Tid vid datorn" (unik tid utan dubbelräkning)
- "Uppdatera"-knappen i Tidslinje flyttad till direkt efter datumfälten
- Projektsammanfattningskort visas i Perioder-, Program- och Tidslinje-flikarna (förgrundstid + toppfönster)
- Planerad tid visas i sammanfattningskortet när exakt en hel vecka är vald i Tidslinje
- Planeringsvyn döljer aktiviteter som inte tillhör valt projekt; totalraden uppdateras accordingly
- Buggfix: datumfilter i projektsammanfattning och aktiva projekt returnerade för få resultat
- Buggfix: projektfiltrering i Tidslinje kraschade vid sökning i sqlite3.Row-objekt

## v0.12b (2026-04-10)
- OTA: användaren kan nu välja att installera eller hoppa över en uppdatering via tray-menyn
- Hoppade versioner sparas i skipped_versions.json
- Gmail-adress borttagen från källkoden (hämtas nu via /api/config)
- .gitignore skapad – skyddar databaser, loggar och .env
- Inno Setup: ber användaren stänga appen manuellt istället för tvångsstängning
- Inno Setup: städar bort gamla startfiler (bat/exe) vid installation

## v0.11b (2026-04-10)
- Registrering: timeout ökad från 45s till 90s
- Backend väcks i bakgrunden vid appstart (minskar väntetid vid registrering)
- Statustext uppdaterad till "kan ta upp till 60s första gången"

## v0.1b (2026-04-09)
- Första betaversionen
- Aktivitetstracker med SQLite-databas
- Webb-gränssnitt på localhost:5757
- System tray-ikon med notis vid start
- Registreringsmodal med koppling till Render-backend
- Feedback via mailto (öppnar användarens e-postklient)
- OTA-infrastruktur via GitHub Releases och Render-backend
- Sleep/wake-detektion med watchdog och heartbeat
- Enkelt instans-skydd via låsfil
- Ollama startas i bakgrunden utan synligt fönster
- Oaks-typsnitt (Plus Jakarta Sans) i alla teman
- Hjälppopupar för alla navigeringsposter
- Inno Setup-installationsprogram
- Autostart via Windows-registret (HKCU)
- Databasmigreringar med PRAGMA user_version
