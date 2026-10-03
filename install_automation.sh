#!/bin/bash
# Richtet den täglichen Autopilot per launchd ein (Mac). Einmal ausführen.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
# ~/Downloads ist für Hintergrundjobs gesperrt (macOS-Datenschutz) -> nach ~ verschieben
if [[ "$DIR" == *"/Downloads/"* ]]; then
  echo "Verschiebe Projekt nach ~/mindset-tiktok-bot (Downloads ist für Autostart gesperrt)..."
  mv "$DIR" "$HOME/mindset-tiktok-bot"
  exec bash "$HOME/mindset-tiktok-bot/install_automation.sh"
fi
PY="$(which python3)"
HOUR="${1:-18}"; MIN="${2:-0}"
PLIST="$HOME/Library/LaunchAgents/de.jk24.mindsetbot.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>de.jk24.mindsetbot</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$DIR/daily_run.py</string></array>
<key>WorkingDirectory</key><string>$DIR</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin</string></dict>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
<key>StandardOutPath</key><string>$DIR/logs/launchd.log</string>
<key>StandardErrorPath</key><string>$DIR/logs/launchd.err</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✓ Autopilot aktiv: täglich $HOUR:$(printf %02d $MIN) (verpasste Läufe holt der Mac nach dem Aufwachen nach)."
echo "  Projekt liegt jetzt in: $DIR"
echo "  Tipp: Mac soll um diese Zeit an sein -> Systemeinstellungen > Batterie/Energie: Ruhezustand bei Netzteil verhindern."
