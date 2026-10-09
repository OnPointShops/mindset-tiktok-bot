#!/bin/bash
# Richtet den Autopiloten auf dem MacBook ein. Einmal ausführen, danach läuft alles.
#
#   Voller Lauf   07:00 und 20:00  (prüfen, heilen, posten, messen, forschen, planen)
#   Kurzer Lauf   11:00, 14:00, 17:00  (prüfen, heilen, posten)
#
# Verpasste Läufe holt macOS nach, sobald der Mac wieder wach ist.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# ~/Downloads ist für Hintergrundjobs gesperrt (macOS-Datenschutz)
if [[ "$DIR" == *"/Downloads/"* ]]; then
  echo "Verschiebe Projekt nach ~/jk24-autopilot (Downloads ist für Autostart gesperrt)..."
  mv "$DIR" "$HOME/jk24-autopilot"
  exec bash "$HOME/jk24-autopilot/install_autopilot_mac.sh"
fi

PY="$(which python3)"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs" "$DIR/brain"

schreibe_plist () {
  local LABEL="$1" ARGS="$2" ZEITEN="$3"
  local PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$DIR/autopilot.py</string>$ARGS
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartCalendarInterval</key><array>$ZEITEN</array>
  <key>StandardOutPath</key><string>$DIR/logs/autopilot.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/autopilot.err</string>
</dict></plist>
PL
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "  ✓ $LABEL"
}

echo "Fülle das Gedächtnis..."
"$PY" "$DIR/brain_seed.py" || echo "  (übersprungen)"

echo "Richte Autopilot ein..."
schreibe_plist "de.jk24.autopilot.voll" "" \
  "<dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
   <dict><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>"

schreibe_plist "de.jk24.autopilot.kurz" "<string>--kurz</string>" \
  "<dict><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
   <dict><key>Hour</key><integer>14</integer><key>Minute</key><integer>0</integer></dict>
   <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>"

cat <<EOF

✓ Fertig. Der Autopilot läuft jetzt 5x am Tag.

   07:00  voll    prüfen · heilen · posten · messen · forschen · planen
   11:00  kurz    prüfen · heilen · posten
   14:00  kurz
   17:00  kurz
   20:00  voll

Projekt liegt in: $DIR

Jederzeit nachschauen — Doppelklick auf:  JK24.command
Oder im Terminal:  python3 autopilot.py --bericht

WICHTIG: Systemeinstellungen → Batterie → "Ruhezustand bei Netzteil verhindern"
einschalten, sonst verschläft der Mac die Läufe (holt sie aber beim Aufwachen nach).
EOF
