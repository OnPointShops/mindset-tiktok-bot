# Faceless-Content-Automation (Mindset / KI / Nebenverdienst)

Vollautomatische Pipeline für ein **Account-Portfolio**:
Trend-Research → Skript (KI) → Voiceover → Video **oder** Karussell →
Upload auf **TikTok / Instagram / YouTube Shorts** → stündlicher Cron.

Darüber liegt ein **Autopilot**, der fünfmal täglich prüft, Fehler selbst
repariert, Zahlen misst, online nach neuen Möglichkeiten forscht und den
nächsten Schritt plant — mit einem **Gedächtnis**, das lokal bleibt.

**→ Fang hier an: [START_HIER.md](START_HIER.md)** (eine Seite, ohne Fachbegriffe)
Geschäftsplan und Zahlen: [STRATEGIE_10K.md](STRATEGIE_10K.md)
Startliste der Handgriffe: [TODO_KAI.md](TODO_KAI.md)

Gebaut und in dieser Sandbox getestet: Config, Content-Generator, TTS (live
generiert, Audio-Datei existiert), Video-Rendering-Pipeline (live gerendert,
1080x1920/h264/aac verifiziert), Upload-Modul (Library importiert sauber).
Whisper-Auto-Captions liefen bei Entwicklung nur mit Mock-Daten, weil diese
Sandbox keinen HuggingFace-Zugriff hat (Modell-Download blockiert) — auf
deinem eigenen Server läuft das ohne Änderung.

---

## Was DU noch liefern musst (kein Weg daran vorbei)

| # | Was | Warum ich das nicht für dich tun kann |
|---|-----|----------------------------------------|
| 1 | **Anthropic API Key** (`ANTHROPIC_API_KEY`) | Braucht deine eigene Abrechnung — console.anthropic.com/settings/keys |
| 2 | **Pexels API Key** (`PEXELS_API_KEY`) | Kostenlos, sofort — pexels.com/api |
| 3 | **Ein Server/VPS mit GUI-fähigem Chromium** | Der allererste TikTok-Login (Schritt unten) MUSS mit sichtbarem Browser passieren — TikTok verlangt hier bewusst einen Menschen, das lässt sich nicht umgehen. Diese Cloud-Sandbox hier hat keinen Display-Server, ist also nicht der Ort für den Erst-Login. |
| 4 | **TikTok-Account-Login** (einmalig, manuell, im Browser) | Ich brauche NIE dein Passwort — s.u. |

**Was ich bewusst NICHT von dir will: dein TikTok-Passwort.** Der Login läuft
komplett in deinem eigenen Browser, ich sehe ihn nie. Danach übernehmen
Cookies die Authentifizierung.

---

## Setup (einmalig)

```bash
# 1. Auf deinem Server/PC (mit Display, für Schritt 4 nötig):
git clone <dieses-repo> && cd mindset-tiktok-bot
pip install -r requirements.txt --break-system-packages
phantomwright_driver install chromium
sudo apt install espeak-ng ffmpeg      # falls nicht vorhanden

# 2. Kokoro-Modelldateien laden (einmalig, ~340MB):
mkdir -p assets
curl -L -o assets/kokoro-v1.0.onnx \
  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
curl -L -o assets/voices-v1.0.bin \
  "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

# 3. .env anlegen
cp .env.example .env
# -> ANTHROPIC_API_KEY und PEXELS_API_KEY eintragen

# 4. Einmaliger manueller TikTok-Login:
python3 -c "from tiktokautouploader import upload_tiktok; upload_tiktok(
    video='irgendein_test.mp4', description='test',
    accountname='DEIN_ACCOUNT_NAME', headless=False)"
# -> Browser öffnet sich, dort bei TikTok einloggen. Fertig.
# Danach liegt TK_cookies_DEIN_ACCOUNT_NAME.json im Ordner -> nach cookies/ verschieben.

# 5. Ersten Trend-Refresh + Testlauf:
python3 trend_research.py
python3 scheduler.py
```

## Automatischer Betrieb (danach läuft's ohne dich)

**Empfohlen: Cron**, stündlich. Der Scheduler prüft selbst, welcher Account
gerade einen fälligen Posting-Zeitpunkt hat (definiert in `content/accounts.json`),
und holt verpasste Slots später am Tag nach:
```bash
crontab -e
5 * * * * cd /pfad/zum/projekt && /usr/bin/python3 scheduler.py >> logs/cron.log 2>&1
0 6 * * * cd /pfad/zum/projekt && /usr/bin/python3 daily_run.py >> logs/cron.log 2>&1
0 5 * * 1 cd /pfad/zum/projekt && /usr/bin/python3 trend_research.py >> logs/cron.log 2>&1
```

Status jederzeit prüfen:
```bash
python3 accounts.py     # welcher Account postet wann, welche Plattformen sind verbunden
```

**Alternative, falls kein Cron verfügbar:** `python3 main.py` als Dauerprozess
(via `systemd`, `pm2`, oder `nohup ... &`).

---

## Das Team — wer hier arbeitet

Jedes Skript geht durch eine kleine Redaktion, bevor es gerendert wird.
Übersicht und Arbeitsprotokoll: `python3 team.py`

| Mitarbeiter | Aufgabe | Wann |
|---|---|---|
| Autor | schreibt das Skript | wenn der Vorrat knapp wird |
| **Lektor** | benotet 1–10 (Hook, Sog, Konkretheit, Loop), schreibt unter Note 7 neu | vor jedem Rendern |
| **Compliance-Prüfer** | sperrt Heil- und Einkommensversprechen, setzt die Werbekennzeichnung | vor jedem Rendern |
| **Analyst** | vergleicht echte Abrufe nach Format, Länge und Lektor-Note | täglich |
| Späher · Stratege · Planer | neue Umsatzwege · Content-Strategie · nächster Schritt | täglich |

Fett = neu. Drei Dinge, die du wissen solltest:

- **Fällt ein Prüfer aus, wird trotzdem gepostet.** Kein Netz oder leeres
  Kontingent hält den Betrieb nicht an. Ausnahme: Ein Wortfilter sperrt
  eindeutige Heil- und Geldversprechen auch ohne KI.
- **Der Compliance-Prüfer ersetzt keinen Anwalt.** Er fängt die Fälle ab, bei
  denen ein vorsichtiger Redakteur "so nicht" sagen würde. Bei Affiliate-Links
  und bezahlten Kooperationen bleibt die Kennzeichnung deine Verantwortung.
- **Ob der Lektor etwas bringt, misst der Analyst selbst.** Er vergleicht die
  Abrufe überarbeiteter Skripte mit den Original-Fassungen — ab 12 gemessenen
  Beiträgen. Wenn der Lektor nichts bringt, steht das im Gedächtnis.

Kosten: zwei zusätzliche KI-Aufrufe pro Skript, mit Gemini im kostenlosen
Kontingent. Abschalten: `TEAM_AKTIV=0` in `.env`.

Bewusst **kein** Agenten-Framework (CrewAI, LangGraph, Agent SDKs): Deren
Nutzen sind Rollen und Ablaufsteuerung. Die Ablaufsteuerung hat dieses Projekt
schon; die Rollen sind je ein Prompt. Begründung im Kopf von `team.py`.

---

## Der Hauptagent und die Fachagenten

Über der Redaktion steht ein Hauptagent, der Aufträge verteilt und das Personal führt.

| Fachagent | Zuständig für |
|---|---|
| `recht` | rechtliche Vorprüfung: Verträge, Impressum, Werberecht, Behördenpost |
| `steuern` | steuerliche Vorprüfung: Umsatz-, Einkommen-, Gewerbesteuer, Fristen |
| `buchhaltung` | Belege, Rechnungen, Monatsabschluss, Liquiditätsvorschau |
| `marketing` | Kundengewinnung, Kampagnen, Texte |
| `grafik` | Logos, Social-Media-Grafik, Druckvorlagen |
| `automaten` | Standorte, Kalkulation, Sortiment, Genehmigungen |
| `assistenz` | E-Mails, Termine, Fristen, Behördengänge |
| `controller` | rechnet, was sich lohnt — auch bei den Agenten selbst |

**Im Chat:** Claude liest in jeder neuen Sitzung in diesem Repo `CLAUDE.md` und die
Agenten in `.claude/agents/`, verteilt deine Aufträge und stellt bei Bedarf neue
Agenten ein. Du musst nichts aufrufen.

**Auf dem Mac:**
```bash
python3 hauptagent.py                         # Personal, Status, Kasse
python3 hauptagent.py "Brauche ich für Affiliate-Links ein Impressum?"
python3 hauptagent.py --umsatz 120 Affiliate  # Einnahme erfassen
python3 hauptagent.py --kosten 15 ElevenLabs  # Ausgabe erfassen
```
Antworten liegen danach in `briefing/auftraege/`.

**Einmal täglich** prüft der Hauptagent im Autopiloten das Personal nach festen,
nachrechenbaren Regeln:

| Wenn … | dann … |
|---|---|
| die Überarbeitungen des Lektors mindestens 30 % weniger Abrufe holen als die Original-Fassungen (je 5+ Beiträge) | wird der Lektor neu besetzt; die neue Fassung muss eine Arbeitsprobe bestehen und wird nur an ihren eigenen Skripten gemessen |
| ein selbst eingestellter Agent 45 Tage keinen Auftrag hatte | wird er gekündigt |
| ein neuer Agent die Probezeit (21 Tage) mit Aufträgen übersteht | wird er übernommen |
| für einen Auftrag kein Agent zuständig ist und das Thema wiederkommen dürfte | wird einer eingestellt |
| Compliance, Autor oder Späher auffallen | bekommst du eine Ja/Nein-Frage |

Was du dazu wissen musst:

- **Ohne erfassten Umsatz kann niemand nach Geld bewertet werden.** Das System
  sieht Abrufe, aber keine Kontobewegungen. Trag Einnahmen mit `--umsatz` ein.
  Bis dahin misst der Hauptagent an Abrufen und Nutzung, nicht an Euro.
- **`recht` und `steuern` sind kein Anwalt und kein Steuerberater.** Sie liefern
  eine Vorprüfung mit Quellen und sagen, wann ein Mensch ran muss. Auf dem Mac
  antwortet das kostenlose KI-Modell; für alles mit Gewicht nimm den Chat.
- **Geschützt sind `recht`, `steuern`, `controller` und Compliance.** Sie werden
  nie automatisch gekündigt. Ein System, das seinen Prüfer entlässt, weil der
  Reichweite kostet, hat das Falsche gelernt.
- **Höchstens zwei Personalwechsel pro Woche**, und keine übernommenen Prompts
  aus dem Netz: Der Hauptagent recherchiert und schreibt jeden Auftrag selbst.
- Selbst eingestellte Agenten liegen in `brain/agenten/` (nur auf dem Mac), alte
  Fassungen in `brain/agenten/archiv/`. Löschst du eine Datei dort, gilt wieder
  der Stand aus dem Repo.

---

## Bewusste Design-Entscheidungen — und ihre Kompromisse

**TTS: Kokoro (lokal, 0€) statt Cloud-TTS.** Kokoro ist ein Englisch-Modell;
Deutsch läuft über espeak-Fallback und hat einen hörbaren Akzent. Getestet,
funktioniert, ist aber nicht "native Qualität". Wenn dir DE-Sprachqualität
wichtiger ist als 0€-Kosten: `.env` → `TTS_BACKEND=fish` + `FISH_API_KEY`
setzen (Fish Audio S2 Pro, ~15€/1M Zeichen, native deutsche Stimmen) — Code
ist bereits vorbereitet, kein weiterer Umbau nötig.

**Upload: Browser-Automation (`tiktokautouploader`) statt offizielle TikTok
API.** Die offizielle Content Posting API schaltet Posts unauditierter
Clients auf privat — Audit dauert 2-4 Wochen. Browser-Automation postet
sofort öffentlich, bewegt sich aber in einer ToS-Grauzone (TikTok verbietet
explizit "automation tools designed to bypass TikTok's systems"). Deshalb:
`stealth=True` ist aktiv, `POSTS_PER_DAY=1` als Standard — bei mehr Volumen
steigt das Ban-Risiko überproportional, nicht linear.

**Trend-Research nutzt Claudes Trainingswissen, nicht Live-Scraping.**
Tagesaktuelle "was ging diese Woche viral"-Daten bräuchten entweder die
TikTok Research API (Non-Profit/Academic-Antrag, 24h-7-Tage-Latenz) oder
einen TikTok-Cookie-Scraper (github.com/Viralway/viralAPI), der alle paar
Wochen manuell erneuert werden muss. Beides ist als Stub in
`trend_research.py` vorbereitet, aber nicht aktiviert — wenn du das willst,
sag Bescheid.

---

## Monetarisierung

Kurzfassung: **Plattform-Ausschüttungen tragen kein Zieleinkommen.** TikTok zahlt in
Deutschland 0,60–0,90 € pro 1.000 qualifizierte Views (ab 10k Follower + 100k Views/30 Tage,
nur Videos > 60 Sek.), Instagram zahlt pro View gar nichts. Reichweite ist Traffic,
nicht Umsatz — das Geld entsteht erst am Ende des Funnels.

Die vollständige Rechnung, die fünf Umsatzströme und der Monatsplan stehen in
**[STRATEGIE_10K.md](STRATEGIE_10K.md)**.

## Dateiübersicht

```
config.py              Zentrale Konfiguration (.env-basiert)
accounts.py            Account-Portfolio: Nischen, Formate, Posting-Zeiten, Slot-Logik
content_generator.py   KI generiert Hook/Body/CTA/Hashtags
tts_engine.py          Edge / Piper / Kokoro / ElevenLabs / Fish TTS
video_builder.py       Stock-Footage + Voiceover + Auto-Captions
carousel.py            Text-Karussells (schwarz/weiß, Serifenschrift) für Instagram
uploader.py            TikTok (Browser-Automation)
uploader_instagram.py  Instagram Reels + Karussells (offizielle Graph API)
uploader_youtube.py    YouTube Shorts (offizielle Data API v3)
media_host.py          Öffentliche URLs für Instagram (lokal oder S3/R2)
trend_research.py      Wöchentlicher Themen-Refresh
stats_scraper.py       Holt echte View-Zahlen vom Profil
improver.py            Wertet Performance aus, schlägt Experimente vor
scheduler.py           Ein Cron-Lauf: bedient alle fälligen Slots aller Accounts
autopilot.py           Der Hauptlauf: prüfen · heilen · posten · messen · forschen · planen · melden
brain.py               Das Gedächtnis (lokale SQLite, verlässt das Gerät nie)
brain_seed.py          Füllt das Gedächtnis mit der gemeinsamen Strategie
ideas_scout.py         Sucht online nach neuen Verdienstmöglichkeiten, bewertet sie
app/                   Der Leitstand: die Handy-App (Vorlage, Bauskript, fertige Seite)
hauptagent.py          Der Hauptagent: verteilt Aufträge, prüft, kündigt und besetzt Agenten, führt die Kasse
.claude/agents/        Die Fachagenten als Textdateien (Recht, Steuern, Buchhaltung, Marketing, Grafik, …)
CLAUDE.md              Was Claude zu Beginn jeder Sitzung liest: Rolle als Hauptagent, Regeln fürs Team
team.py                Die Redaktion: Lektor, Compliance-Prüfer, Analyst — plus Übersicht aller KI-Mitarbeiter
daily_run.py           Älterer Tageslauf (vom Autopiloten abgelöst, bleibt funktionsfähig)
main.py                Dauerprozess-Fallback ohne Cron
JK24.command           Doppelklick auf dem Mac: Stand ansehen, Fragen beantworten
install_autopilot_mac.sh  Richtet den Autopiloten per launchd ein (5x täglich)
```

### Autopilot

```bash
python3 autopilot.py            # voller Durchgang
python3 autopilot.py --kurz     # nur prüfen, heilen, posten
python3 autopilot.py --bericht  # letzten Stand anzeigen
```

Der Autopilot ändert **niemals selbst seinen Programmcode**. Er repariert
(Paket nachinstallieren, Platte aufräumen, Lauf wiederholen), misst, forscht
und schlägt vor; Code-Änderungen landen als Vorschlag im Gedächtnis. Ein System,
das sich unbeaufsichtigt umschreibt, ist irgendwann kaputt und niemand weiß warum.

### Account-Portfolio

Konfiguriert in `content/accounts.json` (wird beim ersten Lauf angelegt, enthält
**keine Secrets** — die stehen in `.env`). Standard sind drei Accounts mit eigener
Nische, eigenem Format und eigenen Posting-Zeiten. Begründung des Portfolio-Ansatzes
und die Abschalt-Kriterien: STRATEGIE_10K.md, Abschnitt 3.
