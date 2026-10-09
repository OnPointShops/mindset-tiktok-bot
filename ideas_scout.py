"""
Der Ideen-Späher: sucht automatisch nach neuen Wegen, mit dem bestehenden
System Geld zu verdienen — und legt sie bewertet ins Gedächtnis.

Durchsucht per KI-Websuche: GitHub-Projekte, Foren (Reddit, Indie Hackers,
Hacker News), Tool-Neuerscheinungen, Plattform-Regeländerungen.

Harte Regel im Prompt: Eine Idee zählt nur, wenn sie mit DEM BESTEHENDEN
System und unter 10 Stunden Einsatz umsetzbar ist. Alles andere ist für
jemanden mit 50-Stunden-Woche keine Idee, sondern eine Ablenkung.

Läuft einmal täglich aus dem Autopiloten. Kosten: wenige Cent.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

import brain
import content_generator

log = logging.getLogger("ideas_scout")

PROMPT = """Du bist der Research-Partner eines Einzelunternehmers in Deutschland.

SEINE LAGE (unverhandelbar, jede Idee muss dazu passen):
- 50-Stunden-Job als Angestellter. Freie Zeit: 10-12 Stunden pro Woche, abends und am Wochenende.
- Familie mit vier Kindern. Keine Nachtschichten, keine "hustle"-Fantasien.
- Hat bereits ein funktionierendes, automatisiertes Content-System laufen:
  KI schreibt Skripte, erzeugt Videos und Text-Karussells, postet selbst auf
  TikTok, Instagram und YouTube. Mehrere Accounts parallel.
- Kann programmieren lassen (dieser Assistent baut), aber nicht selbst coden.
- Startkapital nahe null. Laufende Kosten müssen unter 50 EUR/Monat bleiben.
- Deutschland: Steuer, DSGVO, Werbekennzeichnung, Impressumspflicht gelten.

WAS ER SCHON ENTSCHIEDEN HAT (nicht neu vorschlagen):
{gedaechtnis}

AUFGABE: Recherchiere online, was es HEUTE ({heute}) Neues gibt, das ihm Umsatz
bringen könnte. Schau konkret nach:
1. GitHub-Projekte, die sein System erweitern könnten (nenne echte Repos mit Namen)
2. Foren/Communities (Reddit r/SideProject, r/Entrepreneur, Indie Hackers, Hacker News):
   Was berichten Leute, das MESSBAR funktioniert — mit Zahlen, nicht mit Versprechen?
3. Neue KI-Tools oder APIs, die etwas billiger/besser machen, das er schon tut
4. Plattform-Änderungen (neue Monetarisierung, neue Formate, neue Regeln in DE/EU)
5. Dienstleistungen, die er mit dem bestehenden System für lokale Unternehmen anbieten kann

FILTER — eine Idee kommt nur in die Liste, wenn ALLES zutrifft:
- in unter 10 Stunden startbar (nicht fertig, aber startbar)
- erster Euro realistisch innerhalb von 60 Tagen
- keine Vorabinvestition über 100 EUR
- legal in Deutschland, ohne Grauzone
- nutzt etwas, das er SCHON HAT (System, Handwerksnetzwerk in Trier, Meisterbrief,
  Erfahrung mit Automaten und Einzelhandel)

SEI SKEPTISCH. Wenn du für eine Behauptung keine Quelle mit echten Zahlen findest,
schreib das in "unsicher" statt es als Fakt zu verkaufen. Lieber zwei belastbare
Ideen als acht schöne.

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "ideen": [
   {{"titel": "kurz und konkret",
     "beschreibung": "2-3 Sätze: was genau, für wen, womit verdient er daran",
     "quelle": "URL oder Repo-Name",
     "aufwand_h": 4,
     "umsatz_monat": 300,
     "risiko": 1,
     "unsicher": "was an dieser Schätzung wacklig ist, ehrlich"}}
 ],
 "regel_warnungen": ["Plattform-/Rechtsänderungen, die ihn betreffen — sonst leer"],
 "werkzeuge": ["neue Tools/Repos, die sein System billiger oder besser machen"],
 "quellen": ["URLs"]
}}"""


def _recherchiere(prompt: str) -> str:
    """Nutzt Gemini mit Google-Suche (kostenlos). Fällt auf das normale KI-Backend zurück."""
    if content_generator.GEMINI_API_KEY:
        try:
            import improver
            return improver._gemini_with_search(prompt)
        except Exception as e:  # noqa: BLE001
            log.warning("Websuche fehlgeschlagen (%s) -> KI ohne Suche", e)
    return content_generator.generate_llm(
        "Du antwortest ausschliesslich mit validem JSON.", prompt, max_tokens=3000)


def run_scout() -> dict:
    """Ein Rechercheslauf. Legt neue Ideen im Gedächtnis ab, gibt die Zusammenfassung zurück."""
    prompt = PROMPT.format(heute=datetime.now().strftime("%d.%m.%Y"),
                           gedaechtnis=brain.kontext_fuer_ki(3000))
    text = _recherchiere(prompt)

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise RuntimeError("Ideen-Späher lieferte kein JSON")
    data = json.loads(m.group(0))

    neu = 0
    for i in data.get("ideen", []):
        titel = (i.get("titel") or "").strip()
        if not titel:
            continue
        beschreibung = (i.get("beschreibung") or "").strip()
        if i.get("unsicher"):
            beschreibung += f"\n\nUnsicher: {i['unsicher']}"
        brain.idea(
            titel=titel,
            beschreibung=beschreibung,
            quelle=i.get("quelle", ""),
            aufwand_h=float(i.get("aufwand_h") or 4),
            umsatz_monat=float(i.get("umsatz_monat") or 0),
            risiko=int(i.get("risiko") or 2),
        )
        neu += 1

    for w in data.get("regel_warnungen", []):
        brain.frage_kai(f"Regeländerung prüfen: {w}", "Vom Ideen-Späher gefunden.", dringlichkeit=3)

    for w in data.get("werkzeuge", []):
        brain.learn(f"Werkzeug-Fund: {w}", "Ideen-Späher")

    brain.event("scout", f"{neu} Ideen geprüft/aktualisiert",
                {"quellen": data.get("quellen", [])[:5]})
    log.info("Ideen-Späher fertig: %d Ideen, %d Warnungen",
             neu, len(data.get("regel_warnungen", [])))
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run_scout(), ensure_ascii=False, indent=2))
