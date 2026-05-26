# Ändringslogg – Activity Tracker

## v0.19b (2026-05-26)
- Buggfix: markeringen för aktuell vecka i planeringsdelen uppdateras nu korrekt vid varje besök i Tidslinje-fliken (tidigare frös den om appen lämnades öppen över ett veckoskifte)
- Buggfix: positioner som kräver >200 km/h sedan föregående logg kastas bort (skydd mot helt orimliga WiFi-felläsningar)

## v0.18b (2026-05-07)
- Buggfix: tidslinje-zoom klickade en dag fel pga UTC-konvertering (lokal tidszon används nu)
- Program-vyn filtrerar nu programlistan på valt projekt (tidigare visades alla program oavsett projekt)
- Feedback skickas nu direkt via backend (Gmail) utan att öppna mailappen – fallback till mailto om backend ej nås
- Självläkande start: stale lock-fil rensas automatiskt vid uppstart om ingen annan instans faktiskt körs; start.bat försöker upp till 3 gånger om appen inte svarar
- Maj-Britt: stöd för OpenAI/ChatGPT som AI-källa (gpt-4o, gpt-4o-mini m.fl.)
- Maj-Britt: visar tydlig guide om ingen AI-källa är konfigurerad (Ollama ej installerat och ingen API-nyckel)
- Tidsredovisningsförslag under tidslinjen: intervallbaserad beräkning med PTV (Passivtidvikt 25%), upprundat uppåt till närmaste halvtimme, projektnamn från planeringsfilen; kollapsbar sektion
- Förbättrad projektmatchning: bakgrundsfönster identifieras nu via öppna filsökvägar (psutil) för bättre projekttillhörighet
- Buggfix: S-projekt (S12345) identifierades inte i Maj-Britts kontext
- Buggfix: pilknappar i Dashboard och Perioder stegar nu korrekt – en dag om en dag är vald, en vecka om en vecka är vald
- Hjälptexter för alla flikar genomgångna och uppdaterade

## v0.17b (2026-04-23)
- Program-vyn: aktiv/bakgrund-filter uppdaterar listan direkt utan att klicka Uppdatera
- Tidslinje: klick på en dag i tidsaxeln zoomar till just den dagen (vid flerdagarsvy)
- Planering: rubriken visar nu "Planering Grupp [namn]"
- Planering: timmar > 40 per person och vecka markeras i rött

## v0.16b (2026-04-20)
- Datumavgränsare per dag i Besökta platser-sektionen
- Webbläsaren minns vilken flik som var öppen vid omladdning
- Webbläsarens valda datum, filter och sökfält sparas och återställs per vy
- Platser med GPS-felmarginal > 300m filtreras bort i Besökta platser (±50km visas inte längre)
- Firefox-historik stöds nu (moz_historyvisits, alla profiler)
- Tid räknas inte längre när skärmsläckaren eller låsskärmen är aktiv
- Resursplanering ersatt av gruppvy: planeringen visas nu för hela teamet (GRUPP-kolumnen)
- Inloggad användare ingår i gruppsummeringen
- Varje gruppmedlem har en summerad rubrikrad som kan expanderas för detaljvy
- Resursplanering laddas inte om automatiskt vid varje tabbyte

## v0.15b (2026-04-15)
- Valfri platsloggning (geotracking) via Windows Location API
- Adresser hämtas via Nominatim/OpenStreetMap – inget skickas till externa tjänster
- Loggar bara vid förflyttning > 150m – sparar resurser och batteri
- Konfigurerbart loggningsintervall (1 / 5 / 15 / 30 min)
- På/av-toggle i Inställningar med tydlig integritetsinformation
- Besökta platser-sektion i Tidslinje-fliken (kollapsbar) med tid, adress och noggrannhet
- Resursplanering i Tidslinje gjord kollapsbar
- Maj-Britt får tillgång till platsdata och resursplanering i sina svar
- Uppdatera-knappen placerad direkt efter datumfälten i Dashboard och Program
- Buggfix: Uppdatera-knappen låg fel i Program-fliken
- Buggfix: Projektsammanfattningskortet i Program-fliken hamnade inuti filter-raden och visades för litet
- Buggfix: Tooltippar hade hårdkodad mörk bakgrund som inte fungerade i ljustemat
- Ljustemat omgjort med Oaks-palett: varm cream-bakgrund, mörkgrön text och guld-accent
- Automatisk layout-validering via pre-commit hook (check_layout.py)
- Buggfix: Tid räknades på program även när skärmsläckaren eller låsskärmen var aktiv
- Webbläsaren minns vilken flik som var öppen vid omladdning
- run_version.bat: versionsväxlare för att köra äldre versioner (t.ex. för att matcha betatestare)

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
