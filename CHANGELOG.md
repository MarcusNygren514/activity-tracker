# Ändringslogg — Activity Tracker

## v0.34b (ej släppt)
- Buggfix: trackern kunde sluta logga helt efter viloläge utan att watchdogen fick igång den igen – processen fastnade i ett läge där inga nya trådar startade, och watchdogens omstart hängde av samma skäl. Watchdogen startar nu en helt ny process och avslutar den gamla.
- Buggfix: vid den omstarten kunde den gamla processen fastna på att dölja tray-ikonen (en hängd tray-tråd blockerade för evigt). Den höll då kvar låsfilen och port 5757, så appen gick inte att starta igen – varken via watchdogen, autostart eller launchern. Den gamla processen avslutas nu direkt.
- Buggfix: appen kraschade helt tyst vid start om en annan instans höll låset, eftersom kontrollen använde `wmic` som inte längre finns i Windows 11. Kontrollen görs nu med PowerShell, och en hängd instans (som inte loggat på länge) avslutas automatiskt så att den nya kan ta över.
- Oväntade fel loggas nu till loggfilen i stället för att processen dör tyst.
- Buggfix: grundorsaken till hängningarna och en krasch efter viloläge. Sökningen efter vilka dokument som är öppna (psutil) frös hela appen medan den pågick – även watchdogen – och kunde vid fastnade filhandtag lämna Windows interna lås trasiga, så att nya trådar aldrig startade eller appen kraschade (`ntdll.dll`). Sökningen körs nu i en egen liten hjälpprocess: fastnar eller kraschar den startas bara den om, och resten av appen påverkas inte.
- Buggfix: watchdogen startade om appen i onödan direkt efter viloläge, innan spårningen hunnit komma igång igen. Den räknar nu från uppvaknandet. Under skärmsläckare skickar spårningen också livstecken, så att den inte tas för hängd.
- Nytt: en schemalagd aktivitet (**ActivityTracker-vakt**) startar appen igen inom 15 minuter, eller när datorn låses upp, om den inte körs – t.ex. om den stängts av en avbruten avstängning. Appen skapar aktiviteten själv vid start (som användaren, utan admin), och avinstallationen tar bort den. Väljer man **Avsluta** i menyn förblir appen avstängd till nästa inloggning eller tills man startar den själv, och vakten startar den aldrig mitt i en uppdatering.
- Release-skriptet förstörde å/ä/ö i CHANGELOG, manualen och CLAUDE.md (Windows PowerShell läste filerna som ANSI). Skriptet läser nu UTF-8, och de trasiga tecknen är lagade.

## v0.33b (2026-07-19)
- Buggfix: webb-servern kunde krascha helt tyst (t.ex. vid nätverksfel kring sömn/uppvakning) utan att någon startade om den – watchdogen övervakade bara spårningstråden, aldrig webb-servertråden, och kraschen loggades via `print()` som är osynligt i den fönsterlösa .exe:n. Watchdogen startar nu om webb-servern om tråden dör, och krascher loggas korrekt till tray.log.

## v0.32b (2026-07-17)
- Testrelease: slutgiltig, ren verifiering av det fullständiga OTA-flödet end-to-end från v0.31b utan något manuellt ingrepp i själva installationskedjan.

## v0.31b (2026-07-17)
- Buggfix: vakt-processen kunde krascha helt tyst direkt vid start (varken install.log eller egen watcher.log skrevs) på grund av `DETACHED_PROCESS`-flaggan i kombination med `CREATE_NO_WINDOW` när PowerShell-processen skapades. Bekräftat genom fristående reproduktion av exakt samma anrop. Barnprocesser dödas inte automatiskt på Windows när föräldern avslutas, så flaggan behövdes aldrig – borttagen, kvar är bara `CREATE_NO_WINDOW`.

## v0.30b (2026-07-17)
- Testrelease: slutgiltig verifiering av det fullständiga OTA-flödet (vakt-process med -Verb RunAs och egen loggning) end-to-end, från v0.29b utan manuellt ingrepp.

## v0.29b (2026-07-17)
- Buggfix: vakt-processens installer-anrop saknade `-Verb RunAs`, vilket krävs för att Windows ska höja installern till admin (PrivilegesRequired=admin) – utan det misslyckades starten direkt (ERROR_ELEVATION_REQUIRED) och vakt-processen, som saknade felhantering, avslutades helt tyst utan installation eller omstart. Fixat, plus en egen loggfil för vakt-processen så framtida fel går att felsöka.

## v0.28b (2026-07-17)
- Testrelease: verifierar att OTA-omstartsflödet från v0.27b (fristående vakt-process, installer startas efter att appen redan avslutat sig) faktiskt fungerar fullt ut i praktiken, inklusive automatisk omstart utan manuellt ingrepp.

## v0.27b (2026-07-17)
- Buggfix: OTA-uppdateringar avbröts och rullades tyst tillbaka helt (utan felmeddelande, trots att nedladdnings-/installationsnotiserna såg normala ut) eftersom installern startades medan appen fortfarande kördes – Windows RestartManager hittade appen men kunde inte stänga den snyggt (pystray/Flask hanterar inte avstängningssignalen), och Inno Setup gav då upp installationen. Installern startas nu av en fristående vakt-process EFTER att appen redan avslutat sig själv, så det aldrig finns något körande att stänga.

## v0.26b (2026-07-17)
- Buggfix: v0.25b:s omstartsfix kunde få appen att tvångsdödas av installern själv (via /CLOSEAPPLICATIONS + RestartManager) medan den väntade in installationen, eftersom den då fortfarande höll sina egna filer låsta – uppdateringen kunde då avslutas helt tyst utan att appen startade om. Väntan och omstart sköts nu av en fristående vakt-process istället, så appen själv avslutar direkt och släpper sina fillås utan att blockera.

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
- Maj-Britt tillfälligt dold ur menyn (koden finns kvar, återaktiveras när AI-motor är beslutad)
- Inställningar: kontorsval (Göteborg/Stockholm) – sparas och används för projektigenkänning i kommande versioner
- Inställningar: sökväg till Resursplanering.xlsm detekteras automatiskt via OneDrive-synk (fungerar för alla kontor, hoppar över arkiv- och utvecklingsmappar)
- Projektigenkänning utökad med Stockholmsformat: I, SI och SP följt av 5 siffror (tidigare bara P och S)

## v0.19b (2026-05-26)
- Buggfix: markeringen för aktuell vecka i planeringsdelen uppdateras nu korrekt vid varje besök i Tidslinje-fliken (tidigare frös den om appen lämnades öppen över ett veckoskifte)
- Buggfix: positioner som kräver >200 km/h sedan föregående logg kastas bort (skydd mot helt orimliga WiFi-felläsningar)
- Inställningar: automatisk namngivning av skärmdumpar kan nu slås av/på (tidigare alltid aktiv)

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














