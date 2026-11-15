"""
Baut die Handy-App "Leitstand" aus der Vorlage und den Agenten-Dateien.

Die App bringt die Aufträge der Fachagenten selbst mit, damit sie am Handy
ohne Repo antworten können. Nach jeder Änderung an .claude/agents/ neu bauen
und in einer Claude-Sitzung veröffentlichen:

    python3 app/build.py        # schreibt app/leitstand.html
"""
import json
import re
from pathlib import Path

HIER = Path(__file__).resolve().parent
AGENTEN = HIER.parent / ".claude" / "agents"


def agenten() -> list[dict]:
    aus = []
    for pfad in sorted(AGENTEN.glob("*.md")):
        kopf, auftrag = re.match(r"^---\n(.*?)\n---\n(.*)$", pfad.read_text(encoding="utf-8"), re.DOTALL).groups()
        k = dict((a.strip(), b.strip()) for a, b in (z.split(":", 1) for z in kopf.splitlines() if ":" in z))
        # Der Abschnitt über Dateien im Repo gilt am Handy nicht.
        auftrag = auftrag.split("## Was für jeden Auftrag gilt")[0].strip()
        aus.append({"id": k["name"], "bereich": k.get("bereich", ""),
                    "kurz": k["description"].split(". Einsetzen")[0].rstrip(".") + ".",
                    "pruefung": k["name"] in ("recht", "steuern"), "auftrag": auftrag})
    return aus


if __name__ == "__main__":
    daten = json.dumps(agenten(), ensure_ascii=False).replace("</", "<\\/")
    seite = (HIER / "leitstand.template.html").read_text(encoding="utf-8").replace("/*AGENTEN*/", daten)
    (HIER / "leitstand.html").write_text(seite, encoding="utf-8")
    print(f"app/leitstand.html geschrieben ({len(seite) // 1024} KB, {len(agenten())} Agenten)")
