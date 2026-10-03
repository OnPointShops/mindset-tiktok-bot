#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# JK24 Mindset-TikTok-Bot — KOMPLETT-KOSTENLOS SETUP
# Getestet auf: Ubuntu 22.04 / 24.04 (Oracle Cloud Always Free, Hetzner, etc.)
#
# Kosten nach diesem Setup:
#   Server:       0€  (Oracle Cloud Always Free — dauerhaft, kein Ablaufdatum)
#   TTS:          0€  (Piper + Thorsten-Voice, lokal)
#   Stock-Videos: 0€  (Pexels API, kostenlos)
#   TikTok-Upload:0€  (Browser-Automation)
#   Skript-Gen:  ~1€/Monat (Claude API, ca. 30 Skripte/Monat bei 1 Post/Tag)
#
# Einzige Kosten: Anthropic API ~1-2€/Monat für die Texte
# ══════════════════════════════════════════════════════════════════════════════

set -e  # Abbruch bei Fehler

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     JK24 TikTok-Bot — Kostenlos-Setup startet       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. System-Pakete ──────────────────────────────────────────────────────────
echo "[1/7] System-Pakete installieren..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    ffmpeg \
    espeak-ng \
    wget curl \
    git

echo "      ✓ System-Pakete fertig"

# ── 2. Python-Abhängigkeiten ──────────────────────────────────────────────────
echo "[2/7] Python-Pakete installieren (dauert 2-3 Minuten)..."

# setuptools-Kompatibilität zuerst (verhindert tiktokautouploader-Fehler)
pip install "setuptools==68.2.2" --break-system-packages -q

pip install -r requirements.txt --break-system-packages -q

# Piper TTS separat (natives Deutsch)
pip install piper-tts --break-system-packages -q

echo "      ✓ Python-Pakete fertig"

# ── 3. Phantomwright Browser für TikTok-Upload ───────────────────────────────
echo "[3/7] Browser für TikTok-Upload einrichten..."
phantomwright_driver install chromium 2>/dev/null || echo "      (Phantomwright bereits installiert)"
echo "      ✓ Browser fertig"

# ── 4. Piper Thorsten-Voice Stimmmodell laden ─────────────────────────────────
echo "[4/7] Deutsche Stimme herunterladen (Thorsten-Voice, ~65MB)..."
mkdir -p assets/piper

MODEL_FILE="assets/piper/de_DE-thorsten-high.onnx"
CONFIG_FILE="assets/piper/de_DE-thorsten-high.onnx.json"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high"

if [ ! -f "$MODEL_FILE" ]; then
    wget -q --show-progress \
        "$BASE_URL/de_DE-thorsten-high.onnx" \
        -O "$MODEL_FILE"
    echo "      ✓ Stimmmodell geladen"
else
    echo "      ✓ Stimmmodell bereits vorhanden"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    wget -q \
        "$BASE_URL/de_DE-thorsten-high.onnx.json" \
        -O "$CONFIG_FILE"
    echo "      ✓ Stimm-Konfiguration geladen"
else
    echo "      ✓ Stimm-Konfiguration bereits vorhanden"
fi

# ── 5. Ordnerstruktur anlegen ─────────────────────────────────────────────────
echo "[5/7] Ordner anlegen..."
mkdir -p audio videos content cookies logs
echo "      ✓ Ordner bereit"

# ── 6. .env Datei einrichten ──────────────────────────────────────────────────
echo "[6/7] Konfiguration einrichten..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  WICHTIG: Trage jetzt deine API-Keys in .env ein!  │"
    echo "  │                                                     │"
    echo "  │  1. ANTHROPIC_API_KEY  (console.anthropic.com)     │"
    echo "  │  2. PEXELS_API_KEY     (pexels.com/api)            │"
    echo "  │  3. TIKTOK_ACCOUNT_NAME (dein TikTok-Username)     │"
    echo "  │                                                     │"
    echo "  │  Befehl zum Bearbeiten:  nano .env                 │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
else
    echo "      ✓ .env bereits vorhanden"
fi

# ── 7. Quick-Test der Stimme ──────────────────────────────────────────────────
echo "[7/7] Stimm-Test läuft..."
echo "Erfolg. Die Stimme klingt jetzt wie ein echter Deutscher." | \
    piper \
    --model assets/piper/de_DE-thorsten-high.onnx \
    --config assets/piper/de_DE-thorsten-high.onnx.json \
    --output_file audio/stimme_test.wav 2>/dev/null \
    && echo "      ✓ Stimm-Test gespeichert: audio/stimme_test.wav" \
    || echo "      ⚠ Stimm-Test fehlgeschlagen — prüfe ob Modell-Download fertig"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                  Setup fertig! ✓                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Nächste Schritte:"
echo ""
echo "  1. API-Keys eintragen:     nano .env"
echo "  2. TikTok einmalig einloggen:"
echo "     python3 -c \"from tiktokautouploader import upload_tiktok; \\"
echo "       upload_tiktok(video='audio/stimme_test.wav', description='test', \\"
echo "       accountname='\$(grep TIKTOK_ACCOUNT_NAME .env | cut -d= -f2)', \\"
echo "       headless=False)\""
echo "     (Browser öffnet sich — dort einloggen)"
echo ""
echo "  3. Erst-Test komplett:     python3 scheduler.py"
echo ""
echo "  4. Automatik einschalten:"
echo "     crontab -e"
echo "     # Zeile einfügen (täglich 18:30 Uhr):"
echo "     30 18 * * * cd $(pwd) && python3 scheduler.py >> logs/cron.log 2>&1"
echo "     # Zeile einfügen (montags Trend-Update):"
echo "     0 6 * * 1 cd $(pwd) && python3 trend_research.py >> logs/cron.log 2>&1"
echo ""
echo "  Danach läuft alles automatisch. Fertig."
echo ""
