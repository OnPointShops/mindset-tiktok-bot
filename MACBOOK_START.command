#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
#  JK24 — EINMAL DOPPELKLICKEN. DANN LÄUFT ES.
#
#  Macht alles der Reihe nach: Systemprogramme, Python-Pakete, deutsche Stimme,
#  Schlüssel abfragen, Gedächtnis füllen, Selbsttest, Autopilot einschalten.
#
#  Kann jederzeit abgebrochen und neu gestartet werden — fertige Schritte
#  werden übersprungen. Nichts wird doppelt gemacht.
# ══════════════════════════════════════════════════════════════════════════════
cd "$(dirname "$0")"

G='\033[92m'; Y='\033[93m'; R='\033[91m'; D='\033[90m'; B='\033[1m'; N='\033[0m'
SCHRITT=0
PROBLEME=()

kopf () { clear; echo ""; echo -e "${B}  JK24 AUTOPILOT — EINRICHTUNG${N}"; echo "  ────────────────────────────────────────────────────────"; echo ""; }
schritt () { SCHRITT=$((SCHRITT+1)); echo ""; echo -e "${B}[$SCHRITT/8] $1${N}"; }
ok ()   { echo -e "      ${G}✓${N} $1"; }
warn () { echo -e "      ${Y}!${N} $1"; PROBLEME+=("$1"); }
fehler(){ echo -e "      ${R}✗${N} $1"; PROBLEME+=("$1"); }

kopf

# ── 0. Ort prüfen ─────────────────────────────────────────────────────────────
DIR="$(pwd)"
if [[ "$DIR" == *"/Downloads/"* ]]; then
  echo -e "${Y}Das Projekt liegt im Downloads-Ordner.${N}"
  echo "macOS sperrt dort Hintergrundprogramme. Ich verschiebe es nach ~/jk24-autopilot."
  read -p "Enter = verschieben, Strg+C = abbrechen " _
  mv "$DIR" "$HOME/jk24-autopilot"
  exec bash "$HOME/jk24-autopilot/MACBOOK_START.command"
fi

# ── 1. Python ─────────────────────────────────────────────────────────────────
schritt "Python prüfen"
if ! command -v python3 &>/dev/null; then
  fehler "Python 3 fehlt. Lade es von python.org und starte diese Datei neu."
  read -n 1 -s -r -p "Taste drücken zum Schließen..."; exit 1
fi
PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python $PYV gefunden"

# ── 2. Systemprogramme ────────────────────────────────────────────────────────
schritt "Systemprogramme (ffmpeg, espeak) — beim ersten Mal 2-5 Minuten"
if ! command -v brew &>/dev/null; then
  echo "      Homebrew fehlt, wird installiert. Dein Mac-Passwort kann abgefragt werden."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty || true
  [ -f /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
  [ -f /usr/local/bin/brew ]    && eval "$(/usr/local/bin/brew shellenv)"
fi
if command -v brew &>/dev/null; then
  for p in ffmpeg espeak-ng; do
    if command -v "${p%%-*}" &>/dev/null || brew list "$p" &>/dev/null; then
      ok "$p vorhanden"
    else
      echo "      installiere $p..."
      HOMEBREW_NO_AUTO_UPDATE=1 brew install "$p" >/dev/null 2>&1 && ok "$p installiert" || warn "$p konnte nicht installiert werden"
    fi
  done
else
  warn "Homebrew nicht verfügbar — ffmpeg bitte von ffmpeg.org installieren"
fi

# ── 3. Python-Pakete ──────────────────────────────────────────────────────────
schritt "Python-Pakete — beim ersten Mal 3-5 Minuten"
PIPFLAGS="-q --break-system-packages"
python3 -m pip install $PIPFLAGS --upgrade pip >/dev/null 2>&1 || true
if python3 -m pip install $PIPFLAGS -r requirements.txt 2>/dev/null; then
  ok "Pakete installiert"
else
  # Ältere pip-Versionen kennen --break-system-packages nicht
  python3 -m pip install -q -r requirements.txt && ok "Pakete installiert" || warn "Einige Pakete fehlen — der Selbsttest sagt gleich welche"
fi
python3 -m pip install $PIPFLAGS piper-tts >/dev/null 2>&1 || true
[ -f install_tiktok_uploader.sh ] && bash install_tiktok_uploader.sh >/dev/null 2>&1 && ok "TikTok-Uploader bereit" || warn "TikTok-Uploader nicht installiert"
python3 -m playwright install chromium >/dev/null 2>&1 || true

# ── 4. Deutsche Stimme ────────────────────────────────────────────────────────
schritt "Deutsche Stimme laden (~110 MB, einmalig)"
mkdir -p assets/piper
VOICE="assets/piper/de_DE-thorsten-high.onnx"
BASEURL="https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high"
if [ -f "$VOICE" ] && [ "$(stat -f%z "$VOICE" 2>/dev/null || stat -c%s "$VOICE")" -gt 90000000 ]; then
  ok "Stimme schon da"
else
  curl -L --progress-bar "$BASEURL/de_DE-thorsten-high.onnx" -o "$VOICE" && \
  curl -sL "$BASEURL/de_DE-thorsten-high.onnx.json" -o "$VOICE.json" && \
  ok "Stimme geladen" || warn "Stimme konnte nicht geladen werden (Internet?)"
fi

# ── 5. Schlüssel ──────────────────────────────────────────────────────────────
schritt "Zugangsschlüssel einrichten"
[ ! -f .env ] && cp .env.example .env 2>/dev/null
python3 einrichten.py </dev/tty || warn "Einrichtung unvollständig — später nochmal: python3 einrichten.py"

# ── 6. Gedächtnis ─────────────────────────────────────────────────────────────
schritt "Gedächtnis füllen"
python3 brain_seed.py && ok "Gedächtnis bereit" || warn "Gedächtnis konnte nicht gefüllt werden"

# ── 7. Selbsttest ─────────────────────────────────────────────────────────────
schritt "Selbsttest — prüft, ob wirklich alles läuft"
python3 selftest.py || warn "Selbsttest meldet Probleme (siehe oben)"

# ── 8. Autopilot ──────────────────────────────────────────────────────────────
schritt "Autopilot einschalten (5x täglich)"
bash install_autopilot_mac.sh && ok "Autopilot läuft" || fehler "Autopilot konnte nicht eingerichtet werden"

# ── Abschluss ─────────────────────────────────────────────────────────────────
echo ""
echo "  ════════════════════════════════════════════════════════"
if [ ${#PROBLEME[@]} -eq 0 ]; then
  echo -e "  ${G}${B}FERTIG. Alles läuft.${N}"
else
  echo -e "  ${Y}${B}FERTIG — mit ${#PROBLEME[@]} Hinweis(en):${N}"
  for p in "${PROBLEME[@]}"; do echo "    · $p"; done
fi
echo "  ════════════════════════════════════════════════════════"
cat <<EOF

  Was ab jetzt von allein passiert:
    07:00 · 11:00 · 14:00 · 17:00 · 20:00 — prüfen, posten, verbessern

  Was DU noch machen musst (einmalig, 20 Minuten):
    TikTok-Login. Dafür braucht TikTok bewusst einen Menschen:

        python3 uploader.py --login

    Browser geht auf, du loggst dich ein, fertig.

  Jederzeit nachschauen:  Doppelklick auf  JK24.command

EOF
read -n 1 -s -r -p "  Taste drücken zum Schließen..."
