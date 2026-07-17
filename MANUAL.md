# Activity Tracker â€“ AnvÃ¤ndarmanual

> Senast uppdaterad: v0.28b (2026-07-17)

---

## 1. Nedladdning

1. GÃ¥ till: https://github.com/MarcusNygren514/activity-tracker/releases/latest
2. Klicka pÃ¥ filen **ActivityTracker_Setup_vX.Yb.exe** under *Assets*.
3. Om webblÃ¤saren varnar ("okÃ¤nd utgivare") â€“ klicka **BehÃ¥ll** eller **KÃ¶r Ã¤ndÃ¥**.  
   *(Installationsfilen Ã¤r inte kodsignerad, men Ã¤r sÃ¤ker.)*

---

## 2. Installation

1. Dubbelklicka pÃ¥ den nedladdade `.exe`-filen.
2. Klicka **NÃ¤sta** och sedan **Installera**.  
   Appen installeras i `C:\Program Files\ActivityTracker\`.
3. LÃ¤mna **"Starta Activity Tracker nu"** ikryssad och klicka **SlutfÃ¶r**.

**Appen startar nu automatiskt** â€“ ett litet ikon visas i systemfÃ¤ltet (nere till hÃ¶ger, vid klockan).

> **Activity Tracker startar automatiskt** vid varje Windows-inloggning â€“ du behÃ¶ver aldrig starta den manuellt. Den kÃ¶rs tyst i bakgrunden och loggar din aktivitet hela arbetsdagen.

---

## 3. FÃ¶rsta start â€“ registrering

Vid allra fÃ¶rsta start visas en **registreringsdialog**.

1. Fyll i ditt **namn** och din **e-postadress**.
2. Klicka **Registrera**.
3. Du fÃ¥r ett bekrÃ¤ftelsemejl â€“ det behÃ¶ver du inte gÃ¶ra nÃ¥got med, det Ã¤r bara en kvittens.

Registreringen anvÃ¤nds fÃ¶r att:
- Ta emot automatiska uppdateringar (OTA)
- Koppla feedback till rÃ¤tt person

> Om dialogen inte dyker upp direkt: hÃ¶gerklicka pÃ¥ tray-ikonen och vÃ¤lj **Ã–ppna** â€“ dialogen visas pÃ¥ startsidan.

---

## 4. GrÃ¤nssnittet

Ã–ppna webbgrÃ¤nssnittet genom att:
- Klicka pÃ¥ **tray-ikonen** (nere till hÃ¶ger), eller
- Ã–ppna en webblÃ¤sare och gÃ¥ till **http://localhost:5757**

GrÃ¤nssnittet har nio flikar:

| Flik | Vad den visar |
|---|---|
| **Dashboard** | Daglig Ã¶versikt â€“ aktiv tid, topp-program, timdiagram |
| **Live** | Vad som Ã¤r Ã¶ppet just nu, uppdateras var 5:e sekund |
| **Perioder** | RÃ¥data â€“ alla loggade aktivitetsperioder |
| **Program** | Tid per program, filtrerat pÃ¥ projekt |
| **Sessioner** | SammanhÃ¤ngande arbetspass |
| **Tidslinje** | Gantt-diagram + tidsredovisningsfÃ¶rslag |
| **Maj-Britt** | AI-assistent â€“ stÃ¤ll frÃ¥gor om din aktivitetsdata |
| **Feedback** | Skicka synpunkter eller felrapporter till utvecklaren |
| **InstÃ¤llningar** | PlatsspÃ¥rning och resursplanering |

Klicka pÃ¥ **?** bredvid en flik fÃ¶r en kort beskrivning av innehÃ¥llet.

---

## 5. Dagligt anvÃ¤ndande

### Projekt
Activity Tracker identifierar automatiskt projekt i fÃ¶nsterrubriker, URL:er och filsÃ¶kvÃ¤gar. Projektnummer pÃ¥ formatet **P12345** eller **S12345** plockas upp utan att du behÃ¶ver gÃ¶ra nÃ¥got.

AnvÃ¤nd **projektfiltret** (dropdown i varje flik) fÃ¶r att se tid kopplad till ett specifikt projekt.

### TidsredovisningsfÃ¶rslag
I **Tidslinje**-fliken finns en sektion *Tidsredovisning* lÃ¤ngst ned (klicka fÃ¶r att expandera).  
Den visar ett fÃ¶rslag pÃ¥ hur mÃ¥nga timmar du bÃ¶r redovisa per projekt och dag, baserat pÃ¥ faktisk aktivitetsdata. Tiden Ã¤r upprundat uppÃ¥t till nÃ¤rmaste halvtimme.

### Maj-Britt (AI-assistenten)
StÃ¤ll frÃ¥gor som:
- *"Vad jobbade jag med igÃ¥r?"*
- *"Hur fÃ¶rdelades min tid pÃ¥ P26028 den hÃ¤r veckan?"*
- *"Vilket program anvÃ¤nde jag mest?"*

VÃ¤lj AI-kÃ¤lla i instÃ¤llningspanelen Ã¶verst:
- **Ollama (lokalt)** â€“ krÃ¤ver att Ollama Ã¤r installerat, all data stannar pÃ¥ din dator
- **OpenAI / ChatGPT** â€“ krÃ¤ver API-nyckel, data skickas till OpenAI
- **Anthropic Claude** â€“ krÃ¤ver API-nyckel, data skickas till Anthropic

### PlatsspÃ¥rning (valfritt)
Aktiveras i **InstÃ¤llningar**-fliken. Loggar din position via Windows Location API och visar besÃ¶kta platser i Tidslinje-fliken. Inga data skickas till externa tjÃ¤nster.

---

## 6. Uppdateringar

Activity Tracker kontrollerar automatiskt om det finns en ny version (en gÃ¥ng per dygn).  
NÃ¤r en uppdatering finns:

1. En notis visas i systemfÃ¤ltet.
2. HÃ¶gerklicka pÃ¥ tray-ikonen â€“ vÃ¤lj **Installera uppdatering**.
3. Installationen sker tyst och appen startar om automatiskt.

Du kan alltid vÃ¤lja **Hoppa Ã¶ver den hÃ¤r versionen** om du inte vill uppdatera just nu.

---

## 7. FelsÃ¶kning

### Appen startar inte
- Kontrollera att ikonen inte redan finns i systemfÃ¤ltet (klicka pÃ¥ pilen `^` bredvid klockan).
- Starta om via: `Start â†’ SÃ¶k â†’ Activity Tracker`.
- Om problemet kvarstÃ¥r: stÃ¤ng eventuellt hÃ¤ngande process via Aktivitetshanteraren (sÃ¶k pÃ¥ `pythonw.exe`), ta bort filen `%USERPROFILE%\activity_tracker\tray.lock` och starta igen.

### WebbgrÃ¤nssnittet Ã¶ppnas inte
- Kontrollera att tray-ikonen visas (appen mÃ¥ste kÃ¶ra).
- GÃ¥ till http://localhost:5757 i webblÃ¤saren.
- VÃ¤nta 10â€“15 sekunder vid fÃ¶rsta start â€“ appen laddar in data.

### Feedback
GÃ¥ till **Feedback**-fliken i grÃ¤nssnittet och beskriv problemet. Diagnostikinformation bifogas automatiskt.

---

## 8. Avinstallation

1. GÃ¥ till **InstÃ¤llningar â†’ Appar** i Windows.
2. SÃ¶k pÃ¥ *Activity Tracker* och vÃ¤lj **Avinstallera**.

> Din data (`%USERPROFILE%\activity_tracker\`) berÃ¶rs inte av avinstallationen.









