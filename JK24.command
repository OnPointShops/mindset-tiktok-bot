#!/bin/bash
# Doppelklick-Datei: zeigt den Stand und lässt dich offene Fragen beantworten.
cd "$(dirname "$0")"
clear
python3 - <<'PYEOF'
import sys
sys.path.insert(0, ".")
import brain
from pathlib import Path

s = brain.status()
brief = Path("briefing/latest.md")

print("\n" + "═" * 64)
print("  JK24 AUTOPILOT")
print("═" * 64 + "\n")

if brief.exists():
    print(brief.read_text(encoding="utf-8"))
else:
    print("Noch kein Lauf passiert. Starte einen mit:  python3 autopilot.py\n")

print("─" * 64)
print(f"  Ideen: {s['ideen_neu']} neu, {s['ideen_laufend']} laufend, {s['ideen_erledigt']} erledigt")
print(f"  Erkenntnisse: {s['erkenntnisse']}   Entscheidungen: {s['entscheidungen']}")
print(f"  Offene Fehler: {s['fehler_offen']}   Offene Fragen: {s['fragen_offen']}")
print("─" * 64 + "\n")

fragen = brain.offene_fragen()
if fragen:
    print("OFFENE FRAGEN — antworte direkt hier (Enter = überspringen):\n")
    for q in fragen[:5]:
        print(f"  {q['frage']}")
        if q["kontext"]:
            print(f"    ({q['kontext']})")
        try:
            a = input("  Deine Antwort: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if a:
            brain.antworte(q["id"], a)
            brain.decide(q["frage"], a, von="kai")
            print("  ✓ gespeichert\n")
        else:
            print()
    brain.export_markdown()

print("\nWas noch geht:")
print("  python3 autopilot.py          jetzt sofort einen vollen Lauf starten")
print("  open brain/GEDAECHTNIS.md     alle Ideen und Erkenntnisse lesen")
print()
PYEOF
echo
read -n 1 -s -r -p "Taste drücken zum Schließen..."
