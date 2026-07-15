# Ã„ndringslogg â€” Activity Tracker

## v0.25b (2026-07-15)
- Buggfix: OTA-uppdateringar kunde installera filerna korrekt men ändå inte starta om appen automatiskt (upptäckt vid v0.24b-utrullningen) – appen avslutade sig själv innan Inno Setups installer hann registrera processen hos Windows RestartManager, så /RESTARTAPPLICATIONS fick inget att starta om. Appen startar nu om sig själv explicit efter att installern bekräftat är klar, oberoende av Inno Setups timing.

## v0.24b (2026-07-15)
- Buggfix: spårningen kunde helt sluta logga aktivitet efter en lång vilolägesperiod och läkte då inte av sig själv, trots den inbyggda watchdogen – en delad trådpool för fönster- och dokumentsökningar kunde låsa sig permanent (t.ex. om ett anrop mot ett processhandtag hängde sig efter uppvakning), och watchdogens omstart ärvde av misstag samma trasiga pool. Poolen återskapas nu varje gång trackern startar om.

## v0.23b (2026-06-08)
- Tray-ikonen visar nu aktuell version i tooltip och i högerklicksmenyn
- Buggfix: tracker-kraschar loggas nu korrekt till tray.log (skrevs tidigare till stdout som förkastas i produktion)
- Buggfix: race condition i start_tracker() – en threading.Lock förhindrar nu att två tracker-trådar startas parallellt
- Buggfix: OTA-notiser vid nedladdning och fel fungerar nu korrekt (tray-ikonen kopplades aldrig in i updater)
- Buggfix: dubbelklick på “Installera uppdatering” kan inte längre starta två installerare parallellt
- Buggfix: tempmapp med nedladdad installer städas nu bort om nedladdningen misslyckas
- Buggfix: SQLite-connection i webbläsarhistorik (Chrome/Edge och Firefox) stängs nu korrekt även vid exceptions

## v0.22b (2026-06-05)
- Buggfix: appen startar nu korrekt efter OTA-installation – stale lock-fil hanteras även när appen kör som ActivityTracker.exe (tidigare kontrollerades bara pythonw.exe)

## v0.21b (2026-06-05)
- Tidslinje: Gantt-diagrammet ritas nu i SVG istället för Canvas – skarp rendering i alla upplösningar och skalningsnivåer
- Tidslinje: panorering via drag uppdaterar nu bara SVG-transformationen (ingen omritning) – märkbart smidigare
- Dashboard: timdiagrammet skalas nu korrekt för skärmar med hög upplösning (DPR-fix)

## v0.20b (2026-05-29)
- Maj-Britt tillfÃ¤lligt dold ur menyn (koden finns kvar, Ã¥teraktiveras nÃ¤r AI-motor Ã¤r beslutad)
- InstÃ¤llningar: kontorsval (GÃ¶teborg/Stockholm) â€“ sparas och anvÃ¤nds fÃ¶r projektigenkÃ¤nning i kommande versioner
- InstÃ¤llningar: sÃ¶kvÃ¤g till Resursplanering.xlsm detekteras automatiskt via OneDrive-synk (fungerar fÃ¶r alla kontor, hoppar Ã¶ver arkiv- och utvecklingsmappar)
- ProjektigenkÃ¤nning utÃ¶kad med Stockholmsformat: I, SI och SP fÃ¶ljt av 5 siffror (tidigare bara P och S)

## v0.19b (2026-05-26)
- Buggfix: markeringen fÃ¶r aktuell vecka i planeringsdelen uppdateras nu korrekt vid varje besÃ¶k i Tidslinje-fliken (tidigare frÃ¶s den om appen lÃ¤mnades Ã¶ppen Ã¶ver ett veckoskifte)
- Buggfix: positioner som krÃ¤ver >200 km/h sedan fÃ¶regÃ¥ende logg kastas bort (skydd mot helt orimliga WiFi-fellÃ¤sningar)
- InstÃ¤llningar: automatisk namngivning av skÃ¤rmdumpar kan nu slÃ¥s av/pÃ¥ (tidigare alltid aktiv)

## v0.18b (2026-05-07)
- Buggfix: tidslinje-zoom klickade en dag fel pga UTC-konvertering (lokal tidszon anvÃ¤nds nu)
- Program-vyn filtrerar nu programlistan pÃ¥ valt projekt (tidigare visades alla program oavsett projekt)
- Feedback skickas nu direkt via backend (Gmail) utan att Ã¶ppna mailappen â€“ fallback till mailto om backend ej nÃ¥s
- SjÃ¤lvlÃ¤kande start: stale lock-fil rensas automatiskt vid uppstart om ingen annan instans faktiskt kÃ¶rs; start.bat fÃ¶rsÃ¶ker upp till 3 gÃ¥nger om appen inte svarar
- Maj-Britt: stÃ¶d fÃ¶r OpenAI/ChatGPT som AI-kÃ¤lla (gpt-4o, gpt-4o-mini m.fl.)
- Maj-Britt: visar tydlig guide om ingen AI-kÃ¤lla Ã¤r konfigurerad (Ollama ej installerat och ingen API-nyckel)
- TidsredovisningsfÃ¶rslag under tidslinjen: intervallbaserad berÃ¤kning med PTV (Passivtidvikt 25%), upprundat uppÃ¥t till nÃ¤rmaste halvtimme, projektnamn frÃ¥n planeringsfilen; kollapsbar sektion
- FÃ¶rbÃ¤ttrad projektmatchning: bakgrundsfÃ¶nster identifieras nu via Ã¶ppna filsÃ¶kvÃ¤gar (psutil) fÃ¶r bÃ¤ttre projekttillhÃ¶righet
- Buggfix: S-projekt (S12345) identifierades inte i Maj-Britts kontext
- Buggfix: pilknappar i Dashboard och Perioder stegar nu korrekt â€“ en dag om en dag Ã¤r vald, en vecka om en vecka Ã¤r vald
- HjÃ¤lptexter fÃ¶r alla flikar genomgÃ¥ngna och uppdaterade

## v0.17b (2026-04-23)
- Program-vyn: aktiv/bakgrund-filter uppdaterar listan direkt utan att klicka Uppdatera
- Tidslinje: klick pÃ¥ en dag i tidsaxeln zoomar till just den dagen (vid flerdagarsvy)
- Planering: rubriken visar nu "Planering Grupp [namn]"
- Planering: timmar > 40 per person och vecka markeras i rÃ¶tt

## v0.16b (2026-04-20)
- DatumavgrÃ¤nsare per dag i BesÃ¶kta platser-sektionen
- WebblÃ¤saren minns vilken flik som var Ã¶ppen vid omladdning
- WebblÃ¤sarens valda datum, filter och sÃ¶kfÃ¤lt sparas och Ã¥terstÃ¤lls per vy
- Platser med GPS-felmarginal > 300m filtreras bort i BesÃ¶kta platser (Â±50km visas inte lÃ¤ngre)
- Firefox-historik stÃ¶ds nu (moz_historyvisits, alla profiler)
- Tid rÃ¤knas inte lÃ¤ngre nÃ¤r skÃ¤rmslÃ¤ckaren eller lÃ¥sskÃ¤rmen Ã¤r aktiv
- Resursplanering ersatt av gruppvy: planeringen visas nu fÃ¶r hela teamet (GRUPP-kolumnen)
- Inloggad anvÃ¤ndare ingÃ¥r i gruppsummeringen
- Varje gruppmedlem har en summerad rubrikrad som kan expanderas fÃ¶r detaljvy
- Resursplanering laddas inte om automatiskt vid varje tabbyte

## v0.15b (2026-04-15)
- Valfri platsloggning (geotracking) via Windows Location API
- Adresser hÃ¤mtas via Nominatim/OpenStreetMap â€“ inget skickas till externa tjÃ¤nster
- Loggar bara vid fÃ¶rflyttning > 150m â€“ sparar resurser och batteri
- Konfigurerbart loggningsintervall (1 / 5 / 15 / 30 min)
- PÃ¥/av-toggle i InstÃ¤llningar med tydlig integritetsinformation
- BesÃ¶kta platser-sektion i Tidslinje-fliken (kollapsbar) med tid, adress och noggrannhet
- Resursplanering i Tidslinje gjord kollapsbar
- Maj-Britt fÃ¥r tillgÃ¥ng till platsdata och resursplanering i sina svar
- Uppdatera-knappen placerad direkt efter datumfÃ¤lten i Dashboard och Program
- Buggfix: Uppdatera-knappen lÃ¥g fel i Program-fliken
- Buggfix: Projektsammanfattningskortet i Program-fliken hamnade inuti filter-raden och visades fÃ¶r litet
- Buggfix: Tooltippar hade hÃ¥rdkodad mÃ¶rk bakgrund som inte fungerade i ljustemat
- Ljustemat omgjort med Oaks-palett: varm cream-bakgrund, mÃ¶rkgrÃ¶n text och guld-accent
- Automatisk layout-validering via pre-commit hook (check_layout.py)
- Buggfix: Tid rÃ¤knades pÃ¥ program Ã¤ven nÃ¤r skÃ¤rmslÃ¤ckaren eller lÃ¥sskÃ¤rmen var aktiv
- WebblÃ¤saren minns vilken flik som var Ã¶ppen vid omladdning
- run_version.bat: versionsvÃ¤xlare fÃ¶r att kÃ¶ra Ã¤ldre versioner (t.ex. fÃ¶r att matcha betatestare)

## v0.13b (2026-04-12)
- Resursplanering: ny Gantt-vy i Tidslinje-fliken
- InstÃ¤llningssida tillagd (resursplanering opt-in)
- Veckoformat visas som "V 15" istÃ¤llet fÃ¶r "V2615"
- Totalrad med summerade timmar per vecka i planeringen
- Innevarande vecka markerad med accentfÃ¤rg och â—€
- Ã–vriga veckor tonade fÃ¶r bÃ¤ttre kontrast
- TidsstÃ¤mpel fÃ¶r senaste laddning av aktiviteter (datum + tid utan sekunder)
- Beskrivningstext tillagd pÃ¥ instÃ¤llningssidan fÃ¶r resursplanering
- Resursplanering laddas automatiskt nÃ¤r Tidslinje-fliken Ã¶ppnas
- Planeringscache sparas lokalt â€“ fungerar Ã¤ven utan nÃ¤tverksÃ¥tkomst
- TidsstÃ¤mpeln visar om data Ã¤r fÃ¤rsk eller hÃ¤mtad frÃ¥n cache
- Klickbara URL:er frÃ¥n webblÃ¤sarhistorik (Chrome/Edge) i Perioder-fliken
- Klickbara URL:er Ã¤ven i Program-fliken (Titlar-vyn)
- StÃ¶d fÃ¶r alla Chrome/Edge-profiler (ej bara Default)
- Projektfilter i Perioder-, Program- och Tidslinje-flikarna
- Projektnummer (P12345) identifieras automatiskt i fÃ¶nsterrubriker, URL:er och sÃ¶kvÃ¤gar
- Nyckelordsmatchning mot projektnamn fÃ¶r aktiviteter utan synligt projektnummer
- Tooltip pÃ¥ projektobjekt i dropdown-listan visar fullstÃ¤ndigt projektnamn
- Projektdropdown visar endast projekt som identifierats i vald tidsperiod
- Hela resursdokumentet (alla resurser) skannas fÃ¶r projektnummer vid inlÃ¤sning
- Projekt utan namn (ej i resursdokumentet) visas Ã¤ndÃ¥ om de hittas i aktivitetsdatan
- S-projekt (S12345) stÃ¶ds nu parallellt med P-projekt
- Visio (.vsdx/.vsd), AutoCAD (.dwg/.dxf) och MS Project (.mpp) lÃ¤ggs nu till som dokumenttyper
- Tooltip pÃ¥ tider i Program-fliken visar fÃ¶rgrunds- respektive bakgrundstid
- Tooltip hamnar till vÃ¤nster om markÃ¶ren om den annars skulle hamna utanfÃ¶r skÃ¤rmen
- Tidslinje-hover visar nu bÃ¥de aktiv tid och total tid
- Processnamn i Tidslinje anvÃ¤nder samma typsnitt som Ã¶vriga flikar
- "Total Ã¶ppen tid" pÃ¥ Dashboard ersatt med "Tid vid datorn" (unik tid utan dubbelrÃ¤kning)
- "Uppdatera"-knappen i Tidslinje flyttad till direkt efter datumfÃ¤lten
- Projektsammanfattningskort visas i Perioder-, Program- och Tidslinje-flikarna (fÃ¶rgrundstid + toppfÃ¶nster)
- Planerad tid visas i sammanfattningskortet nÃ¤r exakt en hel vecka Ã¤r vald i Tidslinje
- Planeringsvyn dÃ¶ljer aktiviteter som inte tillhÃ¶r valt projekt; totalraden uppdateras accordingly
- Buggfix: datumfilter i projektsammanfattning och aktiva projekt returnerade fÃ¶r fÃ¥ resultat
- Buggfix: projektfiltrering i Tidslinje kraschade vid sÃ¶kning i sqlite3.Row-objekt

## v0.12b (2026-04-10)
- OTA: anvÃ¤ndaren kan nu vÃ¤lja att installera eller hoppa Ã¶ver en uppdatering via tray-menyn
- Hoppade versioner sparas i skipped_versions.json
- Gmail-adress borttagen frÃ¥n kÃ¤llkoden (hÃ¤mtas nu via /api/config)
- .gitignore skapad â€“ skyddar databaser, loggar och .env
- Inno Setup: ber anvÃ¤ndaren stÃ¤nga appen manuellt istÃ¤llet fÃ¶r tvÃ¥ngsstÃ¤ngning
- Inno Setup: stÃ¤dar bort gamla startfiler (bat/exe) vid installation

## v0.11b (2026-04-10)
- Registrering: timeout Ã¶kad frÃ¥n 45s till 90s
- Backend vÃ¤cks i bakgrunden vid appstart (minskar vÃ¤ntetid vid registrering)
- Statustext uppdaterad till "kan ta upp till 60s fÃ¶rsta gÃ¥ngen"

## v0.1b (2026-04-09)
- FÃ¶rsta betaversionen
- Aktivitetstracker med SQLite-databas
- Webb-grÃ¤nssnitt pÃ¥ localhost:5757
- System tray-ikon med notis vid start
- Registreringsmodal med koppling till Render-backend
- Feedback via mailto (Ã¶ppnar anvÃ¤ndarens e-postklient)
- OTA-infrastruktur via GitHub Releases och Render-backend
- Sleep/wake-detektion med watchdog och heartbeat
- Enkelt instans-skydd via lÃ¥sfil
- Ollama startas i bakgrunden utan synligt fÃ¶nster
- Oaks-typsnitt (Plus Jakarta Sans) i alla teman
- HjÃ¤lppopupar fÃ¶r alla navigeringsposter
- Inno Setup-installationsprogram
- Autostart via Windows-registret (HKCU)
- Databasmigreringar med PRAGMA user_version






