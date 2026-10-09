"""
Das Gedächtnis. Nur für uns zwei.

Eine lokale SQLite-Datei (brain/brain.db), die NIE das Gerät verlässt und NIE
ins Git-Repo kommt. Darin steht alles, was wir gemeinsam herausfinden:

  ideas      Ideen, bewertet nach Aufwand/Ertrag/Risiko — mit Status
  decisions  Was entschieden wurde und WARUM (damit nichts zweimal diskutiert wird)
  errors     Jeder Fehler mit Fingerabdruck: wie oft, seit wann, behoben womit
  metrics    Zahlen über die Zeit (Views, Follower, Umsatz)
  learnings  Was funktioniert hat und was nicht
  events     Protokoll jedes Autopilot-Laufs

Warum SQLite und keine Cloud-Lösung: Das Gedächtnis enthält Geschäftszahlen,
Strategien und Zugangs-Metadaten. Je weniger Dienste das sehen, desto besser.
Eine Datei auf deinem MacBook, die du mit Time Machine sicherst, ist genau
die richtige Größe für dieses Problem.

Nutzung von überall im Projekt:
    import brain
    brain.idea("Freebie-PDF aus eigenen Daten", aufwand_h=3, umsatz_monat=400)
    brain.learn("Hook-Typ 'Zahl+Zeit' bringt 2,3x Profilbesuche")
    brain.frage_kai("Soll ich Account C abschalten? Nur 1.100 Views in 6 Wochen.")
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import config

log = logging.getLogger("brain")

BRAIN_DIR = config.BASE_DIR / "brain"
BRAIN_DIR.mkdir(exist_ok=True)
DB_PATH = BRAIN_DIR / "brain.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY,
    titel TEXT NOT NULL UNIQUE,
    beschreibung TEXT DEFAULT '',
    quelle TEXT DEFAULT '',
    aufwand_h REAL DEFAULT 0,
    umsatz_monat REAL DEFAULT 0,
    risiko INTEGER DEFAULT 2,          -- 1 niedrig, 2 mittel, 3 hoch
    score REAL DEFAULT 0,
    status TEXT DEFAULT 'neu',         -- neu | geprueft | laeuft | erledigt | verworfen
    begruendung TEXT DEFAULT '',
    erstellt TEXT, aktualisiert TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    thema TEXT NOT NULL,
    entscheidung TEXT NOT NULL,
    begruendung TEXT DEFAULT '',
    von TEXT DEFAULT 'autopilot',      -- autopilot | kai
    erstellt TEXT
);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    komponente TEXT DEFAULT '',
    meldung TEXT DEFAULT '',
    anzahl INTEGER DEFAULT 1,
    zuerst TEXT, zuletzt TEXT,
    status TEXT DEFAULT 'offen',       -- offen | behoben | braucht_kai | ignoriert
    fix TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY,
    datum TEXT NOT NULL,
    account TEXT DEFAULT '',
    kennzahl TEXT NOT NULL,
    wert REAL NOT NULL,
    UNIQUE(datum, account, kennzahl)
);
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL UNIQUE,
    belege TEXT DEFAULT '',
    gewicht INTEGER DEFAULT 1,         -- wie oft bestätigt
    erstellt TEXT, aktualisiert TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    zeit TEXT, typ TEXT, text TEXT, daten TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS fragen (
    id INTEGER PRIMARY KEY,
    frage TEXT NOT NULL UNIQUE,
    kontext TEXT DEFAULT '',
    dringlichkeit INTEGER DEFAULT 2,   -- 1 kann warten, 2 normal, 3 blockiert alles
    antwort TEXT DEFAULT '',
    status TEXT DEFAULT 'offen',       -- offen | beantwortet
    erstellt TEXT, beantwortet TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrics_datum ON metrics(datum);
CREATE INDEX IF NOT EXISTS idx_events_zeit ON events(zeit);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


# ── Ideen ──────────────────────────────────────────────────────────────────────
def bewerte(aufwand_h: float, umsatz_monat: float, risiko: int) -> float:
    """
    Punktzahl einer Idee: Was bringt sie pro investierter Stunde, abzüglich Risiko?

    Bewusst simpel und nachvollziehbar statt klug: Kai hat 10-12 Stunden pro Woche.
    Jede Idee konkurriert um dieselben Stunden. Eine Idee, die 400 EUR/Monat bringt
    und 3 Stunden kostet, schlägt eine, die 2.000 EUR bringt und 80 Stunden kostet —
    weil die zweite in seinem Leben schlicht nicht stattfindet.
    """
    aufwand_h = max(aufwand_h, 0.5)
    risiko = min(max(risiko, 1), 3)
    return round((umsatz_monat / aufwand_h) / risiko, 2)


def idea(titel: str, beschreibung: str = "", quelle: str = "", aufwand_h: float = 0,
         umsatz_monat: float = 0, risiko: int = 2, status: str = "neu") -> int:
    """Legt eine Idee an oder aktualisiert sie (Titel ist der Schlüssel)."""
    score = bewerte(aufwand_h, umsatz_monat, risiko)
    with _db() as con:
        con.execute("""
            INSERT INTO ideas (titel, beschreibung, quelle, aufwand_h, umsatz_monat,
                               risiko, score, status, erstellt, aktualisiert)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(titel) DO UPDATE SET
                beschreibung=excluded.beschreibung, quelle=excluded.quelle,
                aufwand_h=excluded.aufwand_h, umsatz_monat=excluded.umsatz_monat,
                risiko=excluded.risiko, score=excluded.score, aktualisiert=excluded.aktualisiert
        """, (titel, beschreibung, quelle, aufwand_h, umsatz_monat, risiko, score,
              status, _now(), _now()))
        return con.execute("SELECT id FROM ideas WHERE titel=?", (titel,)).fetchone()["id"]


def idee_status(titel: str, status: str, begruendung: str = ""):
    with _db() as con:
        con.execute("UPDATE ideas SET status=?, begruendung=?, aktualisiert=? WHERE titel=?",
                    (status, begruendung, _now(), titel))


def top_ideen(n: int = 5, status: str = "neu") -> list[dict]:
    with _db() as con:
        rows = con.execute("SELECT * FROM ideas WHERE status=? ORDER BY score DESC LIMIT ?",
                           (status, n)).fetchall()
    return [dict(r) for r in rows]


# ── Entscheidungen ─────────────────────────────────────────────────────────────
def decide(thema: str, entscheidung: str, begruendung: str = "", von: str = "autopilot"):
    """Hält fest, was entschieden wurde — damit es nicht in drei Wochen neu diskutiert wird."""
    with _db() as con:
        con.execute("INSERT INTO decisions (thema, entscheidung, begruendung, von, erstellt) "
                    "VALUES (?,?,?,?,?)", (thema, entscheidung, begruendung, von, _now()))
    log.info("Entscheidung festgehalten: %s -> %s", thema, entscheidung)


def entscheidungen(n: int = 20) -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (n,)).fetchall()]


# ── Fehler ─────────────────────────────────────────────────────────────────────
def log_error(komponente: str, meldung: str) -> dict:
    """
    Merkt sich einen Fehler anhand seines Fingerabdrucks. Derselbe Fehler zum
    fünften Mal ist etwas anderes als ein neuer Fehler — nur so kann der
    Autopilot zwischen 'Ausrutscher' und 'echtes Problem' unterscheiden.
    """
    kern = "".join(c for c in meldung if not c.isdigit())[:400]
    fp = hashlib.sha256(f"{komponente}|{kern}".encode()).hexdigest()[:16]
    with _db() as con:
        con.execute("""
            INSERT INTO errors (fingerprint, komponente, meldung, zuerst, zuletzt)
            VALUES (?,?,?,?,?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                anzahl = errors.anzahl + 1, zuletzt = excluded.zuletzt,
                meldung = excluded.meldung,
                status = CASE WHEN errors.status='behoben' THEN 'offen' ELSE errors.status END
        """, (fp, komponente, meldung[:1000], _now(), _now()))
        return dict(con.execute("SELECT * FROM errors WHERE fingerprint=?", (fp,)).fetchone())


def fehler_behoben(fingerprint: str, fix: str):
    with _db() as con:
        con.execute("UPDATE errors SET status='behoben', fix=? WHERE fingerprint=?",
                    (fix, fingerprint))


def offene_fehler() -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM errors WHERE status IN ('offen','braucht_kai') "
            "ORDER BY anzahl DESC").fetchall()]


# ── Zahlen ─────────────────────────────────────────────────────────────────────
def metric(kennzahl: str, wert: float, account: str = "", datum: str | None = None):
    datum = datum or datetime.now().date().isoformat()
    with _db() as con:
        con.execute("INSERT INTO metrics (datum, account, kennzahl, wert) VALUES (?,?,?,?) "
                    "ON CONFLICT(datum, account, kennzahl) DO UPDATE SET wert=excluded.wert",
                    (datum, account, kennzahl, float(wert)))


def verlauf(kennzahl: str, tage: int = 30, account: str = "") -> list[dict]:
    seit = (datetime.now() - timedelta(days=tage)).date().isoformat()
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT datum, wert FROM metrics WHERE kennzahl=? AND account=? AND datum>=? "
            "ORDER BY datum", (kennzahl, account, seit)).fetchall()]


def trend(kennzahl: str, tage: int = 14, account: str = "") -> float | None:
    """Veränderung in Prozent zwischen erster und zweiter Hälfte des Zeitraums."""
    rows = verlauf(kennzahl, tage, account)
    if len(rows) < 4:
        return None
    mitte = len(rows) // 2
    alt = sum(r["wert"] for r in rows[:mitte]) / mitte
    neu = sum(r["wert"] for r in rows[mitte:]) / (len(rows) - mitte)
    if alt == 0:
        return None
    return round((neu - alt) / alt * 100, 1)


# ── Erkenntnisse ───────────────────────────────────────────────────────────────
def learn(text: str, belege: str = ""):
    """Eine Erkenntnis. Mehrfach bestätigt = höheres Gewicht = wird stärker gewichtet."""
    with _db() as con:
        con.execute("""
            INSERT INTO learnings (text, belege, erstellt, aktualisiert) VALUES (?,?,?,?)
            ON CONFLICT(text) DO UPDATE SET
                gewicht = learnings.gewicht + 1, belege = excluded.belege,
                aktualisiert = excluded.aktualisiert
        """, (text, belege, _now(), _now()))


def erkenntnisse(n: int = 15) -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM learnings ORDER BY gewicht DESC, id DESC LIMIT ?", (n,)).fetchall()]


# ── Fragen an Kai ──────────────────────────────────────────────────────────────
def frage_kai(frage: str, kontext: str = "", dringlichkeit: int = 2):
    """
    Wenn der Autopilot etwas nicht allein entscheiden darf.
    Landet im Briefing als Ja/Nein-Frage — nicht als Aufsatz.
    """
    with _db() as con:
        con.execute("INSERT INTO fragen (frage, kontext, dringlichkeit, erstellt) VALUES (?,?,?,?) "
                    "ON CONFLICT(frage) DO NOTHING", (frage, kontext, dringlichkeit, _now()))


def offene_fragen() -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM fragen WHERE status='offen' ORDER BY dringlichkeit DESC, id").fetchall()]


def antworte(frage_id: int, antwort: str):
    with _db() as con:
        con.execute("UPDATE fragen SET antwort=?, status='beantwortet', beantwortet=? WHERE id=?",
                    (antwort, _now(), frage_id))


# ── Protokoll ──────────────────────────────────────────────────────────────────
def event(typ: str, text: str, daten: dict | None = None):
    with _db() as con:
        con.execute("INSERT INTO events (zeit, typ, text, daten) VALUES (?,?,?,?)",
                    (_now(), typ, text, json.dumps(daten or {}, ensure_ascii=False)))


def letzte_events(n: int = 30) -> list[dict]:
    with _db() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,)).fetchall()]


# ── Für die KI: alles Wichtige in einem Block ──────────────────────────────────
def kontext_fuer_ki(max_zeichen: int = 6000) -> str:
    """
    Das, was die KI bei jedem Lauf über uns wissen muss. Kompakt, weil Kontext
    Geld kostet — und weil zu viel Kontext die Entscheidungen schlechter macht,
    nicht besser.
    """
    teile = ["# Gedächtnis-Auszug"]

    e = erkenntnisse(12)
    if e:
        teile.append("\n## Bestätigte Erkenntnisse (Gewicht = wie oft bestätigt)")
        teile += [f"- [{x['gewicht']}x] {x['text']}" for x in e]

    d = entscheidungen(10)
    if d:
        teile.append("\n## Getroffene Entscheidungen (NICHT neu aufrollen)")
        teile += [f"- {x['thema']}: {x['entscheidung']}" +
                  (f" — weil: {x['begruendung']}" if x["begruendung"] else "") for x in d]

    f = offene_fehler()
    if f:
        teile.append("\n## Offene Fehler")
        teile += [f"- {x['komponente']}: {x['meldung'][:160]} ({x['anzahl']}x seit {x['zuerst'][:10]})"
                  for x in f[:8]]

    laufend = top_ideen(5, status="laeuft")
    if laufend:
        teile.append("\n## Laufende Vorhaben")
        teile += [f"- {x['titel']}" for x in laufend]

    offen = top_ideen(8, status="neu")
    if offen:
        teile.append("\n## Ideen in der Warteschlange (Score = Ertrag je Stunde / Risiko)")
        teile += [f"- [{x['score']}] {x['titel']} ({x['aufwand_h']}h -> {x['umsatz_monat']}EUR/Mon)"
                  for x in offen]

    return "\n".join(teile)[:max_zeichen]


# ── Lesbarer Export (damit Kai reinschauen kann, ohne SQL zu können) ───────────
def export_markdown() -> Path:
    out = BRAIN_DIR / "GEDAECHTNIS.md"
    zeilen = [f"# Unser Gedächtnis — Stand {datetime.now():%d.%m.%Y %H:%M}", ""]

    fragen = offene_fragen()
    if fragen:
        zeilen += ["## ⚠️ Wartet auf deine Antwort", ""]
        zeilen += [f"{i}. **{q['frage']}**" + (f"\n   _{q['kontext']}_" if q["kontext"] else "")
                   for i, q in enumerate(fragen, 1)]
        zeilen.append("")

    zeilen += ["## Ideen (beste zuerst)", "",
               "| Score | Idee | Aufwand | Umsatz/Mon | Status |", "|---:|---|---:|---:|---|"]
    with _db() as con:
        alle = con.execute("SELECT * FROM ideas ORDER BY "
                           "CASE status WHEN 'laeuft' THEN 0 WHEN 'neu' THEN 1 ELSE 2 END, "
                           "score DESC LIMIT 40").fetchall()
    zeilen += [f"| {r['score']} | {r['titel']} | {r['aufwand_h']}h | {r['umsatz_monat']:.0f} € | "
               f"{r['status']} |" for r in alle] or ["| — | noch keine | | | |"]

    zeilen += ["", "## Erkenntnisse", ""]
    zeilen += [f"- **{x['gewicht']}x bestätigt:** {x['text']}" for x in erkenntnisse(25)] or ["- noch keine"]

    zeilen += ["", "## Entscheidungen", ""]
    zeilen += [f"- **{x['thema']}** → {x['entscheidung']}  \n  _{x['begruendung']}_"
               for x in entscheidungen(25)] or ["- noch keine"]

    fehler = offene_fehler()
    zeilen += ["", "## Offene Fehler", ""]
    zeilen += [f"- `{x['komponente']}` {x['meldung'][:140]} — {x['anzahl']}x, Status: {x['status']}"
               for x in fehler] or ["- keine 🎉"]

    out.write_text("\n".join(zeilen), encoding="utf-8")
    return out


def status() -> dict:
    with _db() as con:
        z = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
        return {
            "ideen_neu": z("SELECT COUNT(*) FROM ideas WHERE status='neu'"),
            "ideen_laufend": z("SELECT COUNT(*) FROM ideas WHERE status='laeuft'"),
            "ideen_erledigt": z("SELECT COUNT(*) FROM ideas WHERE status='erledigt'"),
            "fehler_offen": z("SELECT COUNT(*) FROM errors WHERE status IN ('offen','braucht_kai')"),
            "erkenntnisse": z("SELECT COUNT(*) FROM learnings"),
            "entscheidungen": z("SELECT COUNT(*) FROM decisions"),
            "fragen_offen": z("SELECT COUNT(*) FROM fragen WHERE status='offen'"),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    print("\nExport:", export_markdown())
