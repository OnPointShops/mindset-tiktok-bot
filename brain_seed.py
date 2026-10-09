"""
Füllt das Gedächtnis mit allem, was wir bisher gemeinsam erarbeitet haben.

Einmal ausführen (macht der Installer automatisch). Mehrfaches Ausführen
schadet nicht — alles wird nach Titel abgeglichen, nichts doppelt angelegt.
"""
import logging

import brain

log = logging.getLogger("brain_seed")

ERKENNTNISSE = [
    ("Plattform-Ausschüttungen tragen kein Zieleinkommen: TikTok zahlt in DE 0,60-0,90 EUR "
     "pro 1.000 qualifizierte Views, Instagram zahlt pro View gar nichts.", "Recherche 10/2026"),
    ("Reichweite ist Traffic, nicht Umsatz. Jedes Video ohne Weg zu einem Angebot ist Hobby.",
     "Strategie"),
    ("Die E-Mail-Liste ist das einzige Asset, das uns gehört. Accounts können gesperrt werden.",
     "Lehre aus The Jeffrey und OnPoint"),
    ("Kais echter Engpass ist Zeit (10-12 h/Woche), nie Technik. Jede Idee konkurriert um "
     "dieselben Stunden.", "Grundannahme"),
    ("Markendeals sind bei faceless Accounts 30-50 % schlechter bezahlt als bei Gesichts-Creators "
     "und sind transaktional, nicht wiederkehrend.", "Recherche 10/2026"),
    ("Die ersten 3 Sekunden entscheiden über 90 % der Reichweite. Completion-Rate und Shares "
     "schlagen Likes.", "Algorithmus-Evidenz"),
    ("Karussell-Posts (Text auf Schwarz) kosten praktisch nichts in der Produktion und haben in "
     "der Business-Nische die höchste Speicherrate.", "Format-Analyse"),
    ("Kein einzelner Account ist planbar erfolgreich. Ein Portfolio aus mehreren ist es "
     "statistisch.", "Portfolio-Prinzip"),
]

ENTSCHEIDUNGEN = [
    ("Monetarisierung", "Fünf Umsatzströme statt nur Markendeals",
     "Produkt, Dienstleistung, Affiliate, Markendeals, Creator Rewards — kein Bein trägt über 40 %."),
    ("Reihenfolge", "Dienstleistung vor Produkt",
     "Der Done-for-you-Retainer bringt ab Monat 2 Geld und validiert die Zahlungsbereitschaft, "
     "bevor 40 Stunden in ein Produkt fließen."),
    ("Account-Struktur", "Drei Accounts parallel, Abschaltkriterien nach Woche 6/10/16",
     "Portfolio statt Einzelwette, aber mit harter Frist gegen das Festhalten an Verlierern."),
    ("Upload-Weg", "Instagram und YouTube über die offiziellen APIs, nicht per Browser-Automation",
     "Eine Sperre wäre bei laufendem Umsatz ein Geschäftsausfall, kein Ärgernis."),
    ("Rechtsform", "Getrennt von JK24 führen",
     "Lehre aus OnPoint: keine gemeinsame Kasse ohne wasserdichten Vertrag."),
    ("Steuern", "Von Anfang an Regelbesteuerung statt Kleinunternehmerregelung",
     "Die 25.000-EUR-Grenze fällt planmäßig in Monat 8; der Wechsel mitten im Jahr ist lästiger "
     "als der Mehraufwand von Beginn an."),
    ("Autonomie des Autopiloten", "Der Autopilot ändert niemals selbst seinen Programmcode",
     "Ein System, das sich unbeaufsichtigt umschreibt, ist irgendwann kaputt und niemand weiß warum. "
     "Vorschläge sammeln und gemeinsam umsetzen ist langsamer, aber bleibt erklärbar."),
]

IDEEN = [
    ("Zwei lokale Betriebe als Done-for-you-Kunden gewinnen",
     "20 Beiträge/Monat für 600 EUR, monatlich kündbar. Zielgruppe: Handwerk, Physio, Fitness, "
     "Gastro in Trier. Zugang über Heers & Peters und die JK24-Standortgespräche.",
     "Strategie Phase 1", 6, 1200, 1),
    ("Freebie-PDF aus eigenen Performance-Daten",
     "'Die 50 Hooks, die 2026 auf deutschem TikTok funktionieren' — erzeugt aus den echten Zahlen "
     "in performance.csv. Echte Daten sind der unfaire Vorteil gegenüber recyceltem Kursmaterial.",
     "Strategie Phase 2", 3, 400, 1),
    ("Landingpage mit Double-Opt-In und Impressum",
     "Brevo (EU-Server, bis 300 Mails/Tag kostenlos). Ohne Double-Opt-In ist die Liste rechtlich "
     "wertlos, ohne Impressum ist der Account abmahnfähig.",
     "Strategie Phase 2", 4, 0, 1),
    ("Affiliate-Programme für KI-Tools mit wiederkehrender Provision",
     "20-30 % recurring statt Einmalprovision. Nur Tools empfehlen, die im eigenen System "
     "tatsächlich laufen.",
     "Strategie Phase 2", 3, 300, 1),
    ("Hauptprodukt 149 EUR aufnehmen",
     "Jeder Arbeitsschritt am eigenen System wird beim Machen zum Kursmodul — nicht hinterher "
     "nachgestellt.",
     "Strategie Phase 3", 40, 5200, 2),
    ("Umstellung auf die offizielle TikTok Content Posting API",
     "Audit dauert 2-4 Wochen, deshalb früh beantragen. Beseitigt das größte Einzelrisiko "
     "des gesamten Systems.",
     "Strategie Phase 4", 8, 0, 1),
    ("Setup-Angebot 2.500 EUR für Unternehmen",
     "Einmalige Einrichtung des Systems beim Kunden statt monatlicher Betreuung. Höherer Preis, "
     "kein Dauer-Aufwand.",
     "Strategie Phase 4", 10, 1250, 2),
]

FRAGEN = [
    ("Wann wird deine Restschuldbefreiung erteilt?",
     "Blockiert Gewerbeanmeldung, erste Rechnung und Zahlungsanbieter. Accounts und Content "
     "können sofort starten. Ein Anruf beim Insolvenzverwalter klärt es.", 3),
]


def run():
    for text, beleg in ERKENNTNISSE:
        brain.learn(text, beleg)
    for thema, entscheidung, begruendung in ENTSCHEIDUNGEN:
        # Nur anlegen, wenn dieses Thema noch nicht entschieden wurde
        if not any(d["thema"] == thema for d in brain.entscheidungen(100)):
            brain.decide(thema, entscheidung, begruendung, von="kai+claude")
    for titel, beschreibung, quelle, aufwand, umsatz, risiko in IDEEN:
        brain.idea(titel, beschreibung, quelle, aufwand, umsatz, risiko)
    for frage, kontext, dringlichkeit in FRAGEN:
        brain.frage_kai(frage, kontext, dringlichkeit)

    brain.event("seed", "Gedächtnis mit der gemeinsamen Strategie gefüllt")
    pfad = brain.export_markdown()
    s = brain.status()
    print(f"✓ Gedächtnis gefüllt: {s['ideen_neu']} Ideen, {s['erkenntnisse']} Erkenntnisse, "
          f"{s['entscheidungen']} Entscheidungen, {s['fragen_offen']} offene Frage(n)")
    print(f"  Nachlesen: {pfad}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
