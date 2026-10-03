# Mindset-TikTok-Automation

Vollautomatische Pipeline: Trend-Research → Skript (Claude) → Voiceover (Kokoro TTS)
→ Video (Stock-Footage + Auto-Captions) → Upload (TikTok) → täglich per Cron.

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

**Empfohlen: Cron** (robuster als Dauerprozess, übersteht Server-Neustarts):
```bash
crontab -e
# Einmal täglich posten (Uhrzeit an POST_TIME in .env anpassen):
30 18 * * * cd /pfad/zum/projekt && /usr/bin/python3 scheduler.py >> logs/cron.log 2>&1
# Wöchentlich Trends aktualisieren:
0 6 * * 1 cd /pfad/zum/projekt && /usr/bin/python3 trend_research.py >> logs/cron.log 2>&1
```

**Alternative, falls kein Cron verfügbar:** `python3 main.py` als Dauerprozess
(via `systemd`, `pm2`, oder `nohup ... &`).

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

## Monetarisierung — realistischer Zeitrahmen

TikTok Creator Rewards Program (Deutschland eligible): 10.000 Follower +
100.000 Views/30 Tage, Videos >60s, ~0,40-1,00€/1000 Views. Bei konstantem
Posten realistisch 6-18 Monate bis dahin. Schneller nutzbar: TikTok Shop /
Affiliate-Links (ab 1.000 Follower) oder LIVE-Gifts (ab ~1.000 Follower,
kein Posting-Zwang). "Nebenbei Geld verdienen ohne eigenen Aufwand" ist als
System-Ziel jetzt gebaut — als Zeitplan bleibt Geduld der Preis.

---

## Dateiübersicht

```
config.py             Zentrale Konfiguration (.env-basiert)
content_generator.py  Claude generiert Hook/Body/CTA/Hashtags
tts_engine.py         Kokoro (lokal) oder Fish Audio (cloud) TTS
video_builder.py      Pexels-Footage + Voiceover + Whisper-Auto-Captions
uploader.py           tiktokautouploader-Wrapper
trend_research.py     Wöchentlicher Themen-Refresh
scheduler.py          Ein kompletter Tages-Zyklus (Cron-Ziel)
main.py               Dauerprozess-Fallback ohne Cron
```
