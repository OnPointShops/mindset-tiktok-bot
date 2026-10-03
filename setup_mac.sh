#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# JK24 Mindset-TikTok-Bot — MAC SETUP (macOS 12+)
# ══════════════════════════════════════════════════════════════════════════════

set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     JK24 TikTok-Bot — Mac Setup startet             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Homebrew prüfen ────────────────────────────────────────────────────────
echo "[1/7] Homebrew prüfen..."
if ! command -v brew &>/dev/null; then
    echo "      Homebrew fehlt — wird installiert (dauert ~2 Min)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon: brew in PATH aufnehmen
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
fi
echo "      ✓ Homebrew bereit"

# ── 2. System-Pakete via Homebrew ─────────────────────────────────────────────
echo "[2/7] ffmpeg + espeak-ng installieren..."
HOMEBREW_NO_AUTO_UPDATE=1 brew install -y ffmpeg espeak-ng 2>/dev/null || \
HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade ffmpeg espeak-ng 2>/dev/null || true
echo "      ✓ ffmpeg + espeak-ng fertig"

# ── 3. Python-Pakete ──────────────────────────────────────────────────────────
echo "[3/7] Python-Pakete installieren (2-3 Min)..."
pip3 install "setuptools==68.2.2" -q
pip3 install -r requirements.txt -q
pip3 install piper-tts -q
bash install_tiktok_uploader.sh
echo "      ✓ Python-Pakete fertig"

# ── 4. Browser für TikTok-Upload ─────────────────────────────────────────────
echo "[4/7] Browser für TikTok-Upload..."
phantomwright_driver install chromium 2>/dev/null || echo "      (bereits installiert)"
echo "      ✓ Browser fertig"

# ── 5. Piper Thorsten-Voice (~65MB) ──────────────────────────────────────────
echo "[5/7] Deutsche Stimme laden (Thorsten-Voice)..."
mkdir -p assets/piper

BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high"

[ ! -f "assets/piper/de_DE-thorsten-high.onnx" ] && \
    curl -L --progress-bar "$BASE/de_DE-thorsten-high.onnx" \
         -o "assets/piper/de_DE-thorsten-high.onnx"

[ ! -f "assets/piper/de_DE-thorsten-high.onnx.json" ] && \
    curl -sL "$BASE/de_DE-thorsten-high.onnx.json" \
         -o "assets/piper/de_DE-thorsten-high.onnx.json"

echo "      ✓ Stimme fertig"

# ── 6. Ordner + .env ─────────────────────────────────────────────────────────
echo "[6/7] Ordner und Konfiguration..."
mkdir -p audio videos content cookies logs

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  ┌──────────────────────────────────────────────────────┐"
    echo "  │  JETZT: Trage deine API-Keys in .env ein            │"
    echo "  │                                                      │"
    echo "  │  Befehl:  open -e .env   (öffnet in TextEdit)       │"
    echo "  │                                                      │"
    echo "  │  1. ANTHROPIC_API_KEY  → console.anthropic.com      │"
    echo "  │  2. PEXELS_API_KEY     → pexels.com/api             │"
    echo "  │  3. TIKTOK_ACCOUNT_NAME → dein TikTok-Username      │"
    echo "  └──────────────────────────────────────────────────────┘"
    echo ""
else
    echo "      ✓ .env bereits vorhanden"
fi

# ── 7. Stimm-Test ─────────────────────────────────────────────────────────────
echo "[7/7] Stimm-Test..."
echo "Setup erfolgreich. Die Stimme klingt jetzt wie ein echter Deutscher." | \
    piper \
    --model assets/piper/de_DE-thorsten-high.onnx \
    --config assets/piper/de_DE-thorsten-high.onnx.json \
    --output_file audio/stimme_test.wav 2>/dev/null \
    && afplay audio/stimme_test.wav \
    && echo "      ✓ Stimme läuft — du hast sie gerade gehört" \
    || echo "      ⚠ Stimm-Test fehlgeschlagen — manuell prüfen"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║              Setup fertig! ✓                        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Nächste Schritte:"
echo ""
echo "  1. Keys eintragen:    open -e .env"
echo ""
echo "  2. TikTok einloggen (EINMALIG, öffnet Browser):"
echo "     python3 uploader.py --login"
echo ""
echo "  3. Erster Test-Post:"
echo "     python3 scheduler.py"
echo ""
echo "  4. Automatik (Mac-Cron, täglich 18:30 Uhr):"
echo "     crontab -e"
echo "     Zeile einfügen:"
echo "     30 18 * * * cd $(pwd) && python3 scheduler.py >> logs/cron.log 2>&1"
echo ""
echo "  WICHTIG: Damit der Bot täglich postet, muss der Mac wach bleiben."
echo "  Systemeinstellungen → Energie sparen → 'Ruhezustand verhindern' ✓"
echo ""
