# Activity Tracker – Användarmanual

> Senast uppdaterad: v0.18b (2026-05-07)

---

## 1. Nedladdning

1. Gå till: https://github.com/MarcusNygren514/activity-tracker/releases/latest
2. Klicka på filen **ActivityTracker_Setup_vX.Yb.exe** under *Assets*.
3. Om webbläsaren varnar ("okänd utgivare") – klicka **Behåll** eller **Kör ändå**.  
   *(Installationsfilen är inte kodsignerad, men är säker.)*

---

## 2. Installation

1. Dubbelklicka på den nedladdade `.exe`-filen.
2. Klicka **Nästa** och sedan **Installera**.  
   Appen installeras i `C:\Program Files\ActivityTracker\`.
3. Lämna **"Starta Activity Tracker nu"** ikryssad och klicka **Slutför**.

**Appen startar nu automatiskt** – ett litet ikon visas i systemfältet (nere till höger, vid klockan).

> Activity Tracker startar automatiskt vid varje Windows-inloggning. Inget behöver göras för att aktivera det.

---

## 3. Första start – registrering

Vid allra första start visas en **registreringsdialog**.

1. Fyll i ditt **namn** och din **e-postadress**.
2. Klicka **Registrera**.
3. Du får ett bekräftelsemejl – det behöver du inte göra något med, det är bara en kvittens.

Registreringen används för att:
- Ta emot automatiska uppdateringar (OTA)
- Koppla feedback till rätt person

> Om dialogen inte dyker upp direkt: högerklicka på tray-ikonen och välj **Öppna** – dialogen visas på startsidan.

---

## 4. Gränssnittet

Öppna webbgränssnittet genom att:
- Klicka på **tray-ikonen** (nere till höger), eller
- Öppna en webbläsare och gå till **http://localhost:5757**

Gränssnittet har sju flikar:

| Flik | Vad den visar |
|---|---|
| **Dashboard** | Daglig översikt – aktiv tid, topp-program, timdiagram |
| **Live** | Vad som är öppet just nu, uppdateras var 5:e sekund |
| **Perioder** | Rådata – alla loggade aktivitetsperioder |
| **Program** | Tid per program, filtrerat på projekt |
| **Sessioner** | Sammanhängande arbetspass |
| **Tidslinje** | Gantt-diagram + tidsredovisningsförslag |
| **Maj-Britt** | AI-assistent – ställ frågor om din aktivitetsdata |

Klicka på **?** bredvid varje flik för en kort beskrivning av innehållet.

---

## 5. Dagligt användande

### Projekt
Activity Tracker identifierar automatiskt projekt i fönsterrubriker, URL:er och filsökvägar. Projektnummer på formatet **P12345** eller **S12345** plockas upp utan att du behöver göra något.

Använd **projektfiltret** (dropdown i varje flik) för att se tid kopplad till ett specifikt projekt.

### Tidsredovisningsförslag
I **Tidslinje**-fliken finns en sektion *Tidsredovisning* längst ned (klicka för att expandera).  
Den visar ett förslag på hur många timmar du bör redovisa per projekt och dag, baserat på faktisk aktivitetsdata. Tiden är upprundat uppåt till närmaste halvtimme.

### Maj-Britt (AI-assistenten)
Ställ frågor som:
- *"Vad jobbade jag med igår?"*
- *"Hur fördelades min tid på P26028 den här veckan?"*
- *"Vilket program använde jag mest?"*

Välj AI-källa i inställningspanelen överst:
- **Ollama (lokalt)** – kräver att Ollama är installerat, all data stannar på din dator
- **OpenAI / ChatGPT** – kräver API-nyckel, data skickas till OpenAI
- **Anthropic Claude** – kräver API-nyckel, data skickas till Anthropic

### Platsspårning (valfritt)
Aktiveras i **Inställningar**-fliken. Loggar din position via Windows Location API och visar besökta platser i Tidslinje-fliken. Inga data skickas till externa tjänster.

---

## 6. Uppdateringar

Activity Tracker kontrollerar automatiskt om det finns en ny version (en gång per dygn).  
När en uppdatering finns:

1. En notis visas i systemfältet.
2. Högerklicka på tray-ikonen – välj **Installera uppdatering**.
3. Installationen sker tyst och appen startar om automatiskt.

Du kan alltid välja **Hoppa över den här versionen** om du inte vill uppdatera just nu.

---

## 7. Felsökning

### Appen startar inte
- Kontrollera att ikonen inte redan finns i systemfältet (klicka på pilen `^` bredvid klockan).
- Starta om via: `Start → Sök → Activity Tracker`.
- Om problemet kvarstår: stäng eventuellt hängande process via Aktivitetshanteraren (sök på `pythonw.exe`), ta bort filen `%USERPROFILE%\activity_tracker\tray.lock` och starta igen.

### Webbgränssnittet öppnas inte
- Kontrollera att tray-ikonen visas (appen måste köra).
- Gå till http://localhost:5757 i webbläsaren.
- Vänta 10–15 sekunder vid första start – appen laddar in data.

### Feedback
Gå till **Feedback**-fliken i gränssnittet och beskriv problemet. Diagnostikinformation bifogas automatiskt.

---

## 8. Avinstallation

1. Gå till **Inställningar → Appar** i Windows.
2. Sök på *Activity Tracker* och välj **Avinstallera**.

> Din data (`%USERPROFILE%\activity_tracker\`) berörs inte av avinstallationen.
