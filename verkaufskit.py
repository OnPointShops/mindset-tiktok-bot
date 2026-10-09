"""
Verkaufs-Kit: erzeugt für EINEN konkreten Betrieb vier fertige Beispiel-Beiträge
plus ein einseitiges Angebot — zum Mitnehmen ins Gespräch.

Warum dieses Werkzeug zuerst: Im Gedächtnis hat "Zwei lokale Betriebe als
Done-for-you-Kunden gewinnen" die höchste Bewertung (200) — 6 Stunden Aufwand,
1.200 EUR im Monat. Es ist der einzige Umsatzweg, der vor Monat 5 Geld bringt.
Und der Unterschied zwischen "ich könnte für Sie Content machen" und "hier sind
vier Beiträge, die ich für Ihren Betrieb schon gemacht habe" ist der ganze Auftrag.

    python3 verkaufskit.py "Malerbetrieb Schmitz" maler
    python3 verkaufskit.py "Physio am Dom" physio --ort Trier

Ausgabe in  verkauf/<betrieb>/ :
    slide_01..04.png     vier fertige Beiträge (zeigbar auf dem Handy)
    ANGEBOT.md           eine Seite zum Ausdrucken
    GESPRAECH.md         Einstieg, Einwände, Preis
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import brain
import carousel
import config

log = logging.getLogger("verkaufskit")

AUSGABE = config.BASE_DIR / "verkauf"

# Branchen, die in Trier erreichbar sind und erfahrungsgemäß wenig Social Media machen.
# Die Schmerzpunkte sind das Verkaufsargument — nicht die Technik.
BRANCHEN = {
    "handwerk":  {"name": "Handwerksbetrieb", "schmerz": "Fachkräftemangel und Kundenakquise",
                  "themen": ["Nachwuchs gewinnen", "Vorher-Nachher einer Baustelle",
                             "Warum Pfusch am Ende teurer ist", "Was ein Angebot wirklich enthält"]},
    "maler":     {"name": "Malerbetrieb", "schmerz": "Auftragslücken im Winter",
                  "themen": ["Wann streichen sich wirklich lohnt", "Schimmel: was hilft, was nicht",
                             "Farbe nach Himmelsrichtung wählen", "Vorher-Nachher Treppenhaus"]},
    "physio":    {"name": "Physiotherapie", "schmerz": "volle Termine, aber keine Selbstzahler",
                  "themen": ["Rückenschmerz: die eine Übung", "Wann zum Arzt, wann zur Physio",
                             "Warum Schonen das Problem verlängert", "Haltung am Schreibtisch"]},
    "fitness":   {"name": "Fitnessstudio", "schmerz": "Mitglieder kommen im Februar nicht mehr",
                  "themen": ["Warum die meisten im Februar aufhören", "Drei Übungen für den Anfang",
                             "Krafttraining ab 40", "Wie lange bis man etwas sieht"]},
    "gastro":    {"name": "Restaurant", "schmerz": "leere Tische unter der Woche",
                  "themen": ["Was heute frisch reinkam", "Der Mensch hinter dem Herd",
                             "Warum regional teurer ist", "Mittagstisch für Handwerker"]},
    "auto":      {"name": "Autohaus / Werkstatt", "schmerz": "Preisvergleich mit Ketten",
                  "themen": ["Was die Inspektion wirklich prüft", "Wann Reparatur sich nicht mehr lohnt",
                             "Winterreifen: der echte Unterschied", "Freie Werkstatt und Garantie"]},
    "immobilien": {"name": "Immobilienbüro", "schmerz": "zu wenige Objekte im Zulauf",
                   "themen": ["Was dein Haus wirklich wert ist", "Die drei teuersten Verkaufsfehler",
                              "Makler oder privat verkaufen", "Was Käufer zuerst anschauen"]},
}

PROMPT = """Du schreibst vier Instagram-Beiträge als ARBEITSPROBE für einen konkreten Betrieb.

Betrieb: {betrieb}
Branche: {branche}
Ort: {ort}
Typischer Schmerzpunkt der Branche: {schmerz}

Themenvorschläge (du darfst abweichen, wenn etwas Besseres passt):
{themen}

REGELN:
- Schreib für die KUNDEN des Betriebs, nicht für den Betrieb selbst.
- Nützlich zuerst, Werbung höchstens am Rand. Ein Beitrag, der nur "wir sind toll"
  sagt, überzeugt niemanden — weder den Kunden noch den Betriebsinhaber im Gespräch.
- Konkret statt allgemein: eine Zahl, eine Situation, ein Handgriff.
- Siezen. Regionaler, bodenständiger Ton. Keine Werbesprache, keine Ausrufezeichen-Ketten.
- Jeder Beitrag: EIN Gedanke. Erste Zeile muss zum Weiterlesen zwingen.
- Keine erfundenen Fakten über diesen Betrieb (keine Preise, keine Jahreszahlen,
  keine Mitarbeiterzahlen) — du kennst ihn nicht.

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "beitraege": [
   {{"hook": "max 9 Wörter, erste Zeile des Beitrags",
     "body": "3-5 kurze Sätze, jeder ein eigener Gedanke",
     "cta": "eine Zeile, die zu Kommentar oder Anruf führt",
     "caption": "1-2 Sätze Bildunterschrift + eine Frage an die Leser",
     "hashtags": ["5 Hashtags, regional gemischt"]}}
 ]
}}"""


def _fallback(branche: dict, betrieb: str) -> list[dict]:
    """Wenn keine KI erreichbar ist: brauchbare Beiträge aus den Themen bauen.
    Lieber eine schlichte Arbeitsprobe als gar keine im Gespräch."""
    return [{
        "hook": thema,
        "body": (f"Die meisten erfahren das erst, wenn es zu spät ist. "
                 f"Dabei entscheidet sich hier, ob es teuer wird oder nicht. "
                 f"Wer früh fragt, zahlt am Ende weniger."),
        "cta": "Schreiben Sie uns, wenn Sie das für Ihren Fall wissen wollen.",
        "caption": f"{thema} — kurz erklärt. Was ist Ihre Erfahrung damit?",
        "hashtags": [branche["name"].split()[0].lower(), "trier", "handwerk", "regional", "tipps"],
    } for thema in branche["themen"][:4]]


def _erzeuge(betrieb: str, branche: dict, ort: str) -> list[dict]:
    try:
        import content_generator
        text = content_generator.generate_llm(
            "Du antwortest ausschliesslich mit validem JSON.",
            PROMPT.format(betrieb=betrieb, branche=branche["name"], ort=ort,
                          schmerz=branche["schmerz"],
                          themen="\n".join(f"- {t}" for t in branche["themen"])),
            max_tokens=2000)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            beitraege = json.loads(m.group(0)).get("beitraege", [])
            if beitraege:
                return beitraege[:4]
    except Exception as e:  # noqa: BLE001
        log.warning("KI nicht erreichbar (%s) — nutze Vorlagen", e)
    return _fallback(branche, betrieb)


ANGEBOT = """# Social Media für {betrieb}

**Zwanzig Beiträge im Monat. Sie müssen nichts dafür tun.**

---

## Was Sie bekommen

- **20 fertige Beiträge pro Monat** — Texte, Bilder, Veröffentlichung
- Auf Instagram und Facebook, auf Wunsch zusätzlich TikTok
- Themen aus Ihrem Fach, für Ihre Kunden geschrieben
- Veröffentlicht zu den Zeiten, zu denen Ihre Kunden online sind
- Einmal im Monat ein kurzer Bericht: was gelesen wurde, was nicht

## Was Sie dafür tun müssen

Nichts. Wenn Sie wollen, schauen Sie vorher drüber — müssen Sie aber nicht.
Ein Telefonat alle vier Wochen reicht, oft nicht mal das.

## Was es kostet

**{preis} € im Monat. Monatlich kündbar. Keine Einrichtungsgebühr, keine Laufzeit.**

Zum Vergleich: Eine Agentur nimmt für denselben Umfang zwischen 1.200 und 2.500 €
und verlangt zwölf Monate Bindung.

## Warum es bei mir günstiger geht

Ich habe die Produktion automatisiert. Die Technik, die hinter Ihren Beiträgen
steht, läuft ohnehin — für Sie fällt zusätzlich fast nur noch das an, was wirklich
Kopfarbeit ist: die Themen und der Ton. Diesen Vorteil gebe ich weiter, solange
ich die ersten Kunden aufbaue.

## Die Arbeitsprobe

Die vier Beiträge, die dabeiliegen, sind für **{betrieb}** gemacht — nicht aus
einer Mappe. Wenn sie Ihnen nichts sagen, lassen Sie es. Dann haben Sie nichts
verloren außer zehn Minuten.

---

**{absender}**
{kontakt}
"""

GESPRAECH = """# Gesprächsleitfaden — {betrieb}

Nicht auswendig lernen. Nur die Struktur im Kopf behalten.

## Einstieg (am Telefon oder an der Tür)

> „Ich baue automatisierte Social-Media-Inhalte für Betriebe hier aus der Region.
> Zwanzig Beiträge im Monat, Sie müssen nichts tun und nichts freigeben, außer
> Sie wollen. {preis} im Monat, monatlich kündbar. Ich zeig Ihnen vier Beispiele,
> die ich für Ihren Betrieb gemacht habe — wenn's Ihnen nichts bringt, lassen Sie's."

Dann: **Handy raus, vier Beiträge zeigen, Mund halten.** Die Arbeitsprobe
verkauft, nicht die Erklärung. Wer in diesem Moment weiterredet, redet den
Auftrag kaputt.

## Die vier Einwände, die kommen

**„Das macht meine Nichte / mein Azubi schon."**
> „Gut. Wie viele Beiträge waren es letzten Monat?"
Meist kommt eine Zahl unter fünf. Dann: „Zwanzig sind was anderes als fünf.
Nicht besser gemacht — nur regelmäßig. Regelmäßigkeit ist der ganze Trick."

**„Was bringt mir das konkret?"**
> „Ehrlich: Das weiß ich nach vier Wochen, nicht heute. Deshalb monatlich
> kündbar. Wenn nach zwei Monaten nichts passiert, hören wir auf."
Keine Reichweiten versprechen. Niemand kann das, und er merkt es.

**„{preis} ist zu teuer."**
> „Was kostet Sie ein Mitarbeiter, der dafür eine Stunde pro Woche braucht?"
Nicht nachlassen im Preis. Lieber Umfang reduzieren: 10 Beiträge für die Hälfte.
Ein Preis, der nachgibt, war vorher nicht ernst gemeint.

**„Schicken Sie mir mal was per Mail."**
Das heißt fast immer Nein. Stattdessen:
> „Mach ich. Wann passt Ihnen ein kurzer Rückruf — Dienstag oder Donnerstag?"
Ohne Termin ist die Mail erledigt, bevor sie gelesen wird.

## Abschluss

> „Sollen wir's einen Monat probieren? Ich fang nächste Woche an, Sie sehen
> die ersten Beiträge am Freitag."

Kein Vertrag im ersten Gespräch. Eine formlose Auftragsbestätigung per Mail
reicht, bis die erste Rechnung läuft.

## Danach — sofort eintragen

```bash
python3 -c "import brain; brain.event('verkauf', '{betrieb}: <Ergebnis>')"
```

Oder einfach in `JK24.command` bei den offenen Fragen notieren.
"""


def erstelle_kit(betrieb: str, branche_key: str, ort: str = "Trier",
                 preis: int = 600, absender: str = "Kai Schmieder",
                 kontakt: str = "") -> Path:
    branche = BRANCHEN.get(branche_key)
    if not branche:
        raise SystemExit(f"Unbekannte Branche '{branche_key}'. Möglich: {', '.join(BRANCHEN)}")

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", betrieb).strip("_")[:40]
    ordner = AUSGABE / slug
    ordner.mkdir(parents=True, exist_ok=True)

    log.info("Erzeuge Arbeitsprobe für %s (%s)...", betrieb, branche["name"])
    beitraege = _erzeuge(betrieb, branche, ort)

    # Jeder Beitrag wird EIN Bild — im Gespräch blättert man vier Bilder durch,
    # kein Karussell mit zwanzig Slides.
    bilder = []
    for n, b in enumerate(beitraege, 1):
        bloecke = [{"type": "head", "text": b.get("hook", "")},
                   {"type": "space", "factor": 0.7}]
        for satz in re.split(r"(?<=[.!?])\s+", b.get("body", "")):
            if satz.strip():
                bloecke += [{"type": "text", "text": satz.strip()},
                            {"type": "space", "factor": 0.4}]
        pfad = ordner / f"slide_{n:02d}.png"
        carousel.render_slide(bloecke, str(pfad), footer=betrieb, page=f"{n}/{len(beitraege)}")
        bilder.append(str(pfad))

    (ordner / "ANGEBOT.md").write_text(ANGEBOT.format(
        betrieb=betrieb, preis=preis, absender=absender,
        kontakt=kontakt or "Telefon und E-Mail hier eintragen"), encoding="utf-8")

    (ordner / "GESPRAECH.md").write_text(GESPRAECH.format(
        betrieb=betrieb, preis=f"{preis} €"), encoding="utf-8")

    (ordner / "beitraege.json").write_text(
        json.dumps(beitraege, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        brain.idea(f"Verkaufsgespräch: {betrieb}",
                   beschreibung=f"{branche['name']} in {ort}. Arbeitsprobe liegt in {ordner.name}/.",
                   quelle="verkaufskit", aufwand_h=1, umsatz_monat=preis, risiko=1)
        brain.event("verkaufskit", f"Kit erstellt für {betrieb}", {"ordner": str(ordner)})
    except Exception as e:  # noqa: BLE001
        log.warning("Gedächtnis-Eintrag übersprungen: %s", e)

    return ordner


def main():
    p = argparse.ArgumentParser(description="Verkaufs-Kit für einen lokalen Betrieb")
    p.add_argument("betrieb", help='Name des Betriebs, z.B. "Malerbetrieb Schmitz"')
    p.add_argument("branche", choices=sorted(BRANCHEN), help="Branche")
    p.add_argument("--ort", default="Trier")
    p.add_argument("--preis", type=int, default=600)
    p.add_argument("--absender", default="Kai Schmieder")
    p.add_argument("--kontakt", default="")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ordner = erstelle_kit(a.betrieb, a.branche, a.ort, a.preis, a.absender, a.kontakt)

    print(f"""
✓ Fertig: {ordner}

  slide_01..04.png   Zeig die im Gespräch auf dem Handy. Reihenfolge egal.
  ANGEBOT.md         Eine Seite. Ausdrucken und dalassen.
  GESPRAECH.md       Einstieg, die vier Einwände, Abschluss.

  Vorher einmal selbst anschauen:  open {ordner}
""")


if __name__ == "__main__":
    main()
