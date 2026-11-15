"""
Das Team. Fest angestellte KI-Mitarbeiter mit je EINER klaren Aufgabe.

Bisher schrieb eine einzige KI das Skript, und was sie schrieb, ging ungeprüft
raus. Jetzt arbeitet eine kleine Redaktion nach dem Vier-Augen-Prinzip:

  Autor        schreibt das Skript                  (content_generator.py, gab es schon)
  Lektor       prüft und verbessert es              (NEU — vor jedem Rendern)
  Compliance   sperrt, was rechtlich Ärger macht    (NEU — vor jedem Rendern)
  Analyst      sucht in den Zahlen nach Mustern     (NEU — einmal täglich)
  Späher       sucht neue Umsatzwege                (ideas_scout.py, gab es schon)
  Stratege     hält die Content-Strategie aktuell   (improver.py, gab es schon)
  Planer       nennt den einen nächsten Schritt     (autopilot.py, gab es schon)

Warum KEIN Agenten-Framework (CrewAI, LangGraph, Agent SDKs)?
Die bringen zwei Dinge mit: Rollen und Ablaufsteuerung. Rollen sind ein Prompt
und ein Ausgabeformat — das steht unten in 40 Zeilen. Die Ablaufsteuerung hat
dieses Projekt schon (Scheduler, Autopilot, Gedächtnis). Ein Framework würde
hunderte Megabyte Abhängigkeiten auf das MacBook bringen und die kostenlose
KI-Kette (Gemini -> Groq -> Claude) durch eine eigene ersetzen. Übernommen sind
deshalb die MUSTER, nicht die Pakete:
  - Rollen mit engem Auftrag statt einer Alles-KI        (CrewAI)
  - Prüfer-Verbesserer-Schleife vor der Veröffentlichung  (Evaluator-Optimizer)
  - feste Reihenfolge im Code statt freier Agenten-Chats  (Workflow statt Autonomie)
  - gemeinsames Gedächtnis, in dem jeder Lauf nachlesbar ist

Zwei Regeln, die für jeden Mitarbeiter gelten:
1. Fällt ein Mitarbeiter aus (kein Netz, Kontingent leer), wird trotzdem
   gepostet. Ein Prüfer, der den Betrieb lahmlegt, ist schlimmer als keiner.
   Einzige Ausnahme: Compliance sperrt bei harten Treffern auch ohne KI.
2. Kein Mitarbeiter ändert Programmcode. Sie ändern Skripte und schreiben ins
   Gedächtnis — dieselbe Grenze wie beim Autopiloten.

Aufruf:
    python3 team.py            # wer arbeitet hier, und was haben sie zuletzt getan
    python3 team.py --probe    # ein Skript aus dem Vorrat einmal durch die Redaktion
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass

import brain
import config
import content_generator

log = logging.getLogger("team")

AKTIV = os.getenv("TEAM_AKTIV", "1") != "0"
# Unter dieser Note (1-10) übernimmt die Redaktion die Fassung des Lektors.
MIN_NOTE = int(os.getenv("TEAM_MIN_NOTE", "7"))
# Ab so vielen gemessenen Beiträgen zieht der Analyst Schlüsse. Darunter ist
# jedes "Muster" Zufall, und Zufall als Erkenntnis zu speichern macht das System dümmer.
MIN_DATENPUNKTE = int(os.getenv("TEAM_MIN_DATENPUNKTE", "12"))


@dataclass(frozen=True)
class Mitarbeiter:
    id: str
    name: str
    aufgabe: str          # ein Satz, für die Übersicht
    wann: str
    modul: str
    auftrag: str = ""     # System-Prompt; leer bei Mitarbeitern aus anderen Modulen


LEKTOR = Mitarbeiter(
    id="lektor", name="Lektor", modul="team.py",
    aufgabe="Prüft jedes Skript gegen die Viralitäts-Regeln und schreibt schwache Stellen neu.",
    wann="vor jedem Rendern",
    auftrag="""Du bist Lektor einer deutschsprachigen Kurzvideo-Redaktion. Du schreibst nicht \
selbst — du bekommst das Skript eines Autors und entscheidest, ob es so rausgeht.

Du bist streng. Eine 7 heißt: geht raus. Eine 9 ist selten. Benote, was dasteht, nicht was \
gemeint war. Prüfe genau diese fünf Punkte:

1. HOOK: Hält der erste Satz in 1,5 Sekunden fest? Höchstens 8 Wörter, keine Begrüßung, \
kein Satz, den man schon hundertmal gehört hat.
2. SOG: Macht jeder Satz neugierig auf den nächsten? Markiere die Stelle, an der du \
selbst weiterwischen würdest.
3. KONKRET: Gibt es mindestens ein echtes Bild, eine Zahl oder eine Szene? Abstrakte \
Behauptungen ohne Beleg sind ein Mangel.
4. LOOP: Führt der letzte Satz zurück zum Hook, sodass das Video beim Neustart nahtlos \
weiterläuft?
5. EIGENSTÄNDIG: Könnte dieser Text unter jedem beliebigen Video derselben Nische stehen? \
Dann ist er zu generisch.

Wenn die Gesamtnote unter {min_note} liegt, liefere eine überarbeitete Fassung. Behalte Thema, \
Aussage, Tonfall und ungefähre Länge (höchstens 20 % kürzer oder länger). Das Suchwort \
"{keyword}" muss in den ersten zwei Sätzen bleiben. Erfinde keine Fakten, Zahlen oder \
Studien, die nicht im Original stehen. Wenn das Skript gut ist, lass es in Ruhe — \
"ueberarbeitet" ist dann null.

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "note": 7,
 "hook": 7, "sog": 7, "konkret": 7, "loop": 7, "eigenstaendig": 7,
 "maengel": ["konkret, mit der betroffenen Textstelle — leer wenn keine"],
 "ueberarbeitet": null
}}
oder mit Überarbeitung:
 "ueberarbeitet": {{"hook": "...", "body": "...", "cta": "...",
                   "full_voiceover_text": "Hook. Body. CTA — als ein sprechbarer Text"}}""",
)

COMPLIANCE = Mitarbeiter(
    id="compliance", name="Compliance-Prüfer", modul="team.py",
    aufgabe="Sperrt Heil-, Geld- und Erfolgsversprechen und setzt die Werbekennzeichnung.",
    wann="vor jedem Rendern",
    auftrag="""Du prüfst Social-Media-Texte eines deutschen Einzelunternehmers, bevor sie \
automatisch veröffentlicht werden. Niemand liest sie nach dir noch einmal. Der Betreiber \
kann sich keine Abmahnung und keine Kontosperre leisten.

Du bist kein Anwalt und triffst keine Rechtsauskunft. Du erkennst die Fälle, in denen ein \
vorsichtiger Redakteur sagen würde: so nicht. Motivation, harte Worte, zugespitzte Meinungen \
und Übertreibung als Stilmittel sind ausdrücklich erlaubt — sperre nicht aus Vorsicht.

Prüfe auf genau diese Punkte:
1. GESUNDHEIT: Heilversprechen oder der Rat, Therapie, Medikamente oder ärztliche Hilfe \
wegzulassen ("heilt Depression", "du brauchst keinen Therapeuten").
2. GELD: konkrete Einkommens- oder Renditeversprechen ("5.000 EUR im Monat garantiert", \
"ohne Risiko"), Anlageempfehlungen.
3. WERBUNG: Wird ein Produkt, Dienst, Kurs oder Link beworben? Dann ist es Werbung und \
braucht eine Kennzeichnung ("werbung": true). Reine Meinung ohne Produkt ist keine Werbung.
4. PERSONEN: herabsetzende Aussagen über erkennbare echte Personen oder Unternehmen.
5. PLATTFORM: Aufruf zu Selbstverletzung, gefährlichen Mutproben, Hass gegen Gruppen.
6. ERFUNDENE BELEGE: "Studien zeigen", "Forscher haben bewiesen" mit einer Zahl, ohne dass \
eine Quelle genannt wird. Das ist kein Sperrgrund, aber ein Fall für "korrigieren": \
formuliere es als Beobachtung um.

Urteile:
- "ok"          geht so raus
- "korrigieren" geht mit deiner Korrektur raus (liefere NUR die geänderten Felder)
- "sperren"     geht nicht raus (nur bei 1, 2, 4, 5 — und nur, wenn eine Korrektur die \
Aussage zerstören würde)

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "urteil": "ok",
 "werbung": false,
 "gruende": ["konkret, mit Textstelle — leer bei ok"],
 "korrektur": null
}}
"korrektur" enthält bei Bedarf einzelne Felder aus: hook, body, cta, caption, full_voiceover_text.""",
)

ANALYST = Mitarbeiter(
    id="analyst", name="Analyst", modul="team.py",
    aufgabe="Vergleicht die echten Abrufzahlen nach Format, Länge und Lektor-Note.",
    wann="einmal täglich im Autopiloten",
    auftrag="""Du bist Datenanalyst für ein kleines Portfolio automatisierter Kurzvideo-Kanäle. \
Du bekommst fertig gerechnete Zahlen. Rechne nicht neu, deute sie.

Sei geizig mit Schlüssen. Ein Unterschied zählt nur, wenn beide Gruppen mindestens 5 Beiträge \
haben und der Abstand mindestens 30 % beträgt. Alles darunter ist Rauschen — dann schreib \
keine Erkenntnis. Null Erkenntnisse sind ein gültiges Ergebnis und besser als eine falsche.

Jede Erkenntnis muss eine Handlungsanweisung für den Autor sein, mit den Zahlen als Beleg.
Schlecht: "Langform läuft gut."
Gut: "Mehr Langform: 44 Sek.-Videos holen im Schnitt 2.100 Abrufe, Kurzform 900 (je 8 Beiträge)."

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "erkenntnisse": [{{"text": "Handlungsanweisung mit Zahlen", "beleg": "welche Gruppen, wie viele Beiträge"}}],
 "frage_an_kai": "Ja/Nein-Frage, nur wenn eine Entscheidung ansteht — sonst leer"
}}""",
)

# Die Kollegen, die es schon gab. Hier nur eingetragen, damit es EINE Übersicht gibt.
BESTAND = [
    Mitarbeiter("autor", "Autor", "Schreibt die Skripte nach Strategie und Trends.",
                "wenn der Vorrat knapp wird", "content_generator.py"),
    Mitarbeiter("spaeher", "Späher", "Sucht online neue Umsatzwege und bewertet sie.",
                "einmal täglich im Autopiloten", "ideas_scout.py"),
    Mitarbeiter("stratege", "Stratege", "Recherchiert, was in der Nische gerade funktioniert.",
                "einmal täglich im Autopiloten", "improver.py"),
    Mitarbeiter("planer", "Planer", "Nennt den einen nächsten Schritt für die Woche.",
                "einmal täglich im Autopiloten", "autopilot.py"),
]
TEAM = [BESTAND[0], LEKTOR, COMPLIANCE, ANALYST, *BESTAND[1:]]


# ══════════════════════════════════════════════════════════════════════════════
#  Gemeinsamer Unterbau: ein Mitarbeiter bekommt eine Aufgabe, liefert JSON,
#  und der Lauf steht danach im Gedächtnis.
# ══════════════════════════════════════════════════════════════════════════════
def _ki_verfuegbar() -> bool:
    return content_generator.AI_BACKEND != "offline" and any(
        (content_generator.GEMINI_API_KEY, content_generator.GROQ_API_KEY, config.ANTHROPIC_API_KEY))


def _frage(m: Mitarbeiter, aufgabe: str, max_tokens: int = 1200, **platzhalter) -> dict | None:
    """Ein Auftrag an einen Mitarbeiter. Gibt None zurück, wenn er ausfällt —
    der Aufrufer entscheidet, was das bedeutet."""
    start = time.monotonic()
    try:
        roh = content_generator.generate_llm(m.auftrag.format(**platzhalter), aufgabe, max_tokens)
        antwort = content_generator._extract_json(roh)
        if not isinstance(antwort, dict):
            raise ValueError("Antwort ist kein JSON-Objekt")
        return antwort
    except Exception as e:  # noqa: BLE001
        log.warning("%s ausgefallen: %s", m.name, e)
        brain.team_log(m.id, "ausfall", str(e)[:200], dauer_s=time.monotonic() - start)
        return None


def _zahl(wert, standard: int = 0) -> int:
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return standard


# ══════════════════════════════════════════════════════════════════════════════
#  Hausregeln — ohne KI, kostenlos, immer. Was sich zählen lässt, zählt der Code.
# ══════════════════════════════════════════════════════════════════════════════
def hausregeln(script: dict) -> list[str]:
    """Bringt das Skript in Form und gibt zurück, was korrigiert wurde."""
    getan = []

    tags = [t if t.startswith("#") else f"#{t}" for t in
            (str(x).strip().replace(" ", "") for x in script.get("hashtags") or []) if t.strip("#")]
    eindeutig = list(dict.fromkeys(t.lower() for t in tags))
    if len(eindeutig) > 3:
        # Das Suchwort muss unter den dreien bleiben — es ist der TikTok-SEO-Anker.
        kw = "#" + str(script.get("keyword") or "").lower().replace(" ", "")
        getan.append(f"Hashtags von {len(eindeutig)} auf 3 gekürzt")
        eindeutig = eindeutig[:2] + [kw] if kw in eindeutig[3:] else eindeutig[:3]
    if eindeutig != script.get("hashtags"):
        script["hashtags"] = eindeutig

    if not (script.get("full_voiceover_text") or "").strip():
        script["full_voiceover_text"] = " ".join(
            (script.get(k) or "").strip() for k in ("hook", "body", "cta")).strip()
        getan.append("Sprechtext aus Hook/Body/CTA zusammengesetzt")

    return getan


# Harte Treffer: Formulierungen, die auch ohne KI-Urteil nicht automatisch rausgehen.
# Bewusst eng gefasst — lieber ein Treffer zu wenig als ein Mindset-Kanal, der
# das Wort "heilen" nicht mehr sagen darf. Die Feinarbeit macht der Compliance-Prüfer.
_HART = [
    (r"\b(heilt|heilen|geheilt)\b.{0,40}\b(depression|krebs|angstst[öo]rung|burnout|adhs|diabetes)",
     "Heilversprechen"),
    (r"\b(depression|krebs|angstst[öo]rung|burnout|adhs|diabetes)\b.{0,40}\b(heilt|heilen|geheilt)\b",
     "Heilversprechen"),
    (r"\b(keine?n?|statt|ohne)\s+(therapie|therapeut\w*|medikament\w*|arzt|antidepressiv\w*)\b.{0,30}"
     r"\b(brauchst|n[öo]tig|setz\w* ab)|\bsetz\w*\s+(deine\s+)?(medikamente|tabletten)\s+ab",
     "Rat gegen medizinische Behandlung"),
    (r"\bgarantiert\w*\b.{0,40}(\d[\d.]*\s*(€|eur|euro)|reich|gewinn|rendite)|"
     r"(\d[\d.]*\s*(€|eur|euro)|rendite|gewinn)\b.{0,40}\bgarantiert", "Garantiertes Einkommen"),
    (r"\b(ohne|kein)\s+(jedes\s+)?risiko\b.{0,40}\b(geld|verdien\w*|invest\w*|rendite)|"
     r"\b(geld|verdien\w*|invest\w*|rendite)\b.{0,40}\b(ohne|kein)\s+(jedes\s+)?risiko\b",
     "Risikofreies Geldversprechen"),
]


def harte_treffer(script: dict) -> list[str]:
    text = " ".join(str(script.get(k) or "") for k in
                    ("hook", "body", "cta", "caption", "full_voiceover_text")).lower()
    return list(dict.fromkeys(name for muster, name in _HART if re.search(muster, text)))


# ══════════════════════════════════════════════════════════════════════════════
#  Lektor
# ══════════════════════════════════════════════════════════════════════════════
def _fassung_brauchbar(alt: dict, neu: dict) -> str | None:
    """Prüft die Fassung des Lektors, bevor sie das Original ersetzt.
    Gibt den Ablehnungsgrund zurück, oder None wenn sie taugt."""
    if not isinstance(neu, dict):
        return "kein Objekt"
    text = (neu.get("full_voiceover_text") or "").strip()
    hook = (neu.get("hook") or "").strip()
    if not text or not hook:
        return "Hook oder Sprechtext fehlt"
    alt_len = len(alt.get("full_voiceover_text") or "") or 1
    if not 0.7 <= len(text) / alt_len <= 1.35:
        # Zu kurz = abgeschnittene Antwort. Zu lang = Videolänge läuft aus dem Ruder
        # (Langform ist auf 35-45 Sek. ausgelegt, das Rendern verlässt sich darauf).
        return f"Länge weicht zu stark ab ({len(text)} statt {alt_len} Zeichen)"
    if hook.lower()[:25] not in text.lower():
        return "Hook steht nicht im Sprechtext"
    kw = (alt.get("keyword") or "").strip().lower()
    if kw and kw in (alt.get("full_voiceover_text") or "").lower() and kw not in text.lower():
        return f"Suchwort '{kw}' ist verloren gegangen"
    return None


def lektorat(script: dict, nische: str = "") -> dict:
    """Benotet das Skript und übernimmt bei schwacher Note die Fassung des Lektors.
    Gibt den Befund zurück; das Skript wird direkt geändert."""
    aufgabe = (f"Nische des Kanals: {nische or 'Mindset / Motivation'}\n"
               f"Länge: {'Langform, 35-45 Sekunden' if script.get('length') == 'long' else 'Kurzform, 16-26 Sekunden'}\n\n"
               "Skript des Autors:\n" + json.dumps(
                   {k: script.get(k, "") for k in
                    ("topic", "hook", "body", "cta", "keyword", "full_voiceover_text")},
                   ensure_ascii=False, indent=1))
    start = time.monotonic()
    antwort = _frage(LEKTOR, aufgabe, max_tokens=2600 if script.get("length") == "long" else 1400,
                     min_note=MIN_NOTE, keyword=script.get("keyword") or "(keins)")
    if antwort is None:
        return {"geprueft": False}

    note = min(max(_zahl(antwort.get("note")), 1), 10)
    befund = {"geprueft": True, "note": note, "ueberarbeitet": False,
              "maengel": [str(m)[:200] for m in (antwort.get("maengel") or [])][:4]}

    neu = antwort.get("ueberarbeitet")
    if note < MIN_NOTE and neu:
        grund = _fassung_brauchbar(script, neu)
        if grund:
            befund["verworfen"] = grund
            log.info("Lektor-Fassung verworfen (%s) — Original bleibt", grund)
        else:
            script["autor_fassung"] = {k: script.get(k, "") for k in
                                       ("hook", "body", "cta", "full_voiceover_text")}
            for k in ("hook", "body", "cta", "full_voiceover_text"):
                if (neu.get(k) or "").strip():
                    script[k] = neu[k].strip()
            befund["ueberarbeitet"] = True

    brain.team_log(LEKTOR.id, "geprueft",
                   f"{script.get('topic', '?')}: Note {note}"
                   + (" → überarbeitet" if befund["ueberarbeitet"] else ""),
                   wert=note, dauer_s=time.monotonic() - start)
    return befund


# ══════════════════════════════════════════════════════════════════════════════
#  Compliance
# ══════════════════════════════════════════════════════════════════════════════
def compliance(script: dict) -> dict:
    """Urteil: ok | korrigieren | sperren. Korrekturen werden direkt eingearbeitet."""
    treffer = harte_treffer(script)
    start = time.monotonic()

    antwort = None
    if _ki_verfuegbar():
        aufgabe = ("Text zur Prüfung:\n" + json.dumps(
            {k: script.get(k, "") for k in ("hook", "body", "cta", "caption", "full_voiceover_text")},
            ensure_ascii=False, indent=1))
        if treffer:
            aufgabe += ("\n\nEin Wortfilter hat vorab angeschlagen: " + ", ".join(treffer)
                        + ". Prüfe diese Stellen besonders — der Filter kennt keinen Zusammenhang "
                          "und kann falsch liegen.")
        antwort = _frage(COMPLIANCE, aufgabe, max_tokens=1600)

    if antwort is None:
        # Ohne Urteil der KI entscheidet der Wortfilter allein: Treffer = gesperrt.
        # Hier ist "im Zweifel nicht posten" richtig — der Vorrat liefert ein anderes Skript.
        urteil = "sperren" if treffer else "ok"
        befund = {"urteil": urteil, "gruende": treffer, "geprueft_von": "wortfilter"}
    else:
        urteil = antwort.get("urteil") if antwort.get("urteil") in ("ok", "korrigieren", "sperren") else "ok"
        befund = {"urteil": urteil, "geprueft_von": "ki",
                  "gruende": [str(g)[:200] for g in (antwort.get("gruende") or [])][:4]}
        if antwort.get("werbung"):
            script["is_ad"] = True          # die Uploader setzen daraufhin die Kennzeichnung
            befund["werbung"] = True
        if urteil == "korrigieren":
            korrektur = antwort.get("korrektur") or {}
            geaendert = [k for k in ("hook", "body", "cta", "caption", "full_voiceover_text")
                         if isinstance(korrektur.get(k), str) and korrektur[k].strip()]
            for k in geaendert:
                script[k] = korrektur[k].strip()
            if not geaendert:
                befund["urteil"] = urteil = "sperren" if treffer else "ok"
            elif harte_treffer(script):
                befund["urteil"] = urteil = "sperren"   # Korrektur hat das Problem nicht beseitigt
                befund["gruende"].append("harter Treffer auch nach Korrektur")

    brain.team_log(COMPLIANCE.id, urteil,
                   f"{script.get('topic', '?')}: {urteil}"
                   + (f" — {'; '.join(befund['gruende'])[:160]}" if befund["gruende"] else ""),
                   dauer_s=time.monotonic() - start)
    return befund


# ══════════════════════════════════════════════════════════════════════════════
#  Redaktion — der Weg eines Skripts vom Autor in die Warteschlange
# ══════════════════════════════════════════════════════════════════════════════
def redaktion(script: dict, acc=None) -> dict | None:
    """Hausregeln → Lektor → Compliance. Gibt das freigegebene Skript zurück,
    oder None, wenn Compliance es sperrt."""
    if not AKTIV:
        return script

    befund: dict = {}
    getan = hausregeln(script)
    if getan:
        befund["hausregeln"] = getan

    if _ki_verfuegbar():
        befund["lektor"] = lektorat(script, nische=getattr(acc, "niche", "") or "")
        if befund["lektor"].get("ueberarbeitet"):
            hausregeln(script)

    befund["compliance"] = compliance(script)
    script["team"] = befund

    if befund["compliance"]["urteil"] == "sperren":
        gruende = "; ".join(befund["compliance"].get("gruende") or ["ohne Angabe"])
        log.warning("Compliance sperrt '%s': %s", script.get("topic"), gruende)
        brain.event("team_sperre", f"{script.get('topic', '?')}: {gruende[:200]}")
        return None
    return script


# ══════════════════════════════════════════════════════════════════════════════
#  Analyst
# ══════════════════════════════════════════════════════════════════════════════
def _gruppen(zeilen: list[dict], schluessel) -> dict:
    """Abrufe je Gruppe: Anzahl, Durchschnitt, Median. Median, weil ein einziger
    viraler Ausreißer den Durchschnitt einer kleinen Gruppe wertlos macht."""
    gruppen = defaultdict(list)
    for z in zeilen:
        g = schluessel(z)
        if g:
            gruppen[g].append(z["views"])
    aus = {}
    for g, werte in gruppen.items():
        werte = sorted(werte)
        aus[g] = {"beitraege": len(werte), "schnitt": round(sum(werte) / len(werte)),
                  "median": werte[len(werte) // 2]}
    return aus


def kennzahlen() -> dict:
    """Verbindet gemessene Abrufe (performance.csv) mit dem, was wir über jedes
    Skript wissen (Warteschlange): Format, Länge, Account, Lektor-Note."""
    perf = config.CONTENT_DIR / "performance.csv"
    if not perf.exists():
        return {"datenpunkte": 0}
    with perf.open(encoding="utf-8") as f:
        gemessen = [r for r in csv.DictReader(f) if str(r.get("views") or "").strip()]

    queue = {}
    if config.QUEUE_FILE.exists():
        for q in json.loads(config.QUEUE_FILE.read_text(encoding="utf-8")):
            queue[q.get("topic")] = q

    zeilen = []
    for r in gemessen:
        q = queue.get(r.get("topic"), {})
        lektor = (q.get("team") or {}).get("lektor") or {}
        zeilen.append({
            "views": _zahl(r.get("views")),
            "format": r.get("format") or q.get("format") or "",
            "laenge": q.get("length") or "",
            "account": q.get("account") or "",
            "art": q.get("format_used") or "",
            "note": lektor.get("note"),
            "ueberarbeitet": lektor.get("ueberarbeitet"),
        })

    def notenband(z):
        if z["note"] is None:
            return ""
        return "Note 8-10" if z["note"] >= 8 else "Note 7" if z["note"] == 7 else "Note 1-6"

    return {
        "datenpunkte": len(zeilen),
        "nach_format": _gruppen(zeilen, lambda z: z["format"]),
        "nach_laenge": _gruppen(zeilen, lambda z: z["laenge"]),
        "nach_account": _gruppen(zeilen, lambda z: z["account"]),
        "nach_art": _gruppen(zeilen, lambda z: z["art"]),
        "nach_lektor_note": _gruppen(zeilen, notenband),
        "nach_ueberarbeitung": _gruppen(
            zeilen, lambda z: "" if z["ueberarbeitet"] is None
            else "vom Lektor überarbeitet" if z["ueberarbeitet"] else "Autor-Fassung"),
    }


def analyse() -> dict:
    """Ein Analyse-Lauf. Schreibt belastbare Muster als Erkenntnisse ins Gedächtnis."""
    zahlen = kennzahlen()
    n = zahlen["datenpunkte"]
    if n < MIN_DATENPUNKTE:
        brain.team_log(ANALYST.id, "wartet", f"{n} von {MIN_DATENPUNKTE} nötigen Datenpunkten")
        return {"erkenntnisse": [], "hinweis": f"zu wenig Daten ({n}/{MIN_DATENPUNKTE})"}
    if not _ki_verfuegbar():
        return {"erkenntnisse": [], "hinweis": "keine KI verfügbar"}

    start = time.monotonic()
    antwort = _frage(ANALYST, "Zahlen (Abrufe je Beitrag, gruppiert):\n"
                     + json.dumps(zahlen, ensure_ascii=False, indent=1), max_tokens=1200)
    if antwort is None:
        return {"erkenntnisse": [], "hinweis": "Analyst ausgefallen"}

    erkenntnisse = []
    for e in (antwort.get("erkenntnisse") or [])[:3]:
        text = (e.get("text") if isinstance(e, dict) else str(e) or "").strip()
        if text:
            brain.learn(text, f"Analyst: {(e.get('beleg') if isinstance(e, dict) else '') or ''}"[:300])
            erkenntnisse.append(text)
    if (antwort.get("frage_an_kai") or "").strip():
        brain.frage_kai(antwort["frage_an_kai"].strip(), "Vom Analysten, aus den Abrufzahlen.")

    brain.team_log(ANALYST.id, "analysiert", f"{n} Datenpunkte, {len(erkenntnisse)} Erkenntnisse",
                   wert=len(erkenntnisse), dauer_s=time.monotonic() - start)
    return {"erkenntnisse": erkenntnisse, "datenpunkte": n}


# ══════════════════════════════════════════════════════════════════════════════
#  Übersicht
# ══════════════════════════════════════════════════════════════════════════════
def kurzbericht(tage: int = 1) -> str:
    """Eine Zeile für den Autopilot-Bericht. Leer, wenn das Team nichts zu tun hatte."""
    b = brain.team_bilanz(tage)
    lek, com = b.get("lektor", {}), b.get("compliance", {})
    teile = []
    if lek.get("geprueft"):
        teile.append(f"Lektor {lek['geprueft']} geprüft (Ø Note {lek.get('schnitt', '—')})")
    if com.get("sperren"):
        teile.append(f"Compliance {com['sperren']} gesperrt")
    if com.get("korrigieren"):
        teile.append(f"{com['korrigieren']} korrigiert")
    ausfaelle = sum(v.get("ausfall", 0) for v in b.values())
    if ausfaelle:
        teile.append(f"{ausfaelle} Ausfälle")
    return " · ".join(teile)


def uebersicht() -> str:
    b = brain.team_bilanz(7)
    z = [f"Team {'aktiv' if AKTIV else 'ABGESCHALTET (TEAM_AKTIV=0)'} · "
         f"KI {'verfügbar' if _ki_verfuegbar() else 'nicht verfügbar — nur Hausregeln und Wortfilter'}", ""]
    for m in TEAM:
        bilanz = ", ".join(f"{'Ø Note' if k == 'schnitt' else k}: {v}" for k, v in b.get(m.id, {}).items())
        z.append(f"{m.name:<18} {m.aufgabe}")
        z.append(f"{'':<18} {m.wann} · {m.modul}" + (f" · letzte 7 Tage: {bilanz}" if bilanz else ""))
    letzte = brain.team_letzte(8)
    if letzte:
        z += ["", "Zuletzt:"] + [f"  {e['zeit'][5:16]}  {e['mitarbeiter']:<11} {e['text']}" for e in letzte]
    return "\n".join(z)


def _probe():
    bank = json.loads(content_generator.SCRIPT_BANK.read_text(encoding="utf-8"))
    script = dict(bank[0])
    print("VORHER:", script["hook"], "|", script["hashtags"])
    ergebnis = redaktion(script)
    if ergebnis is None:
        print("GESPERRT:", script["team"]["compliance"])
    else:
        print("NACHHER:", ergebnis["hook"], "|", ergebnis["hashtags"])
        print(json.dumps(ergebnis["team"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    if "--probe" in sys.argv:
        _probe()
    else:
        print(uebersicht())
