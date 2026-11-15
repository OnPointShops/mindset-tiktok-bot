"""
Obsidian-Brücke: Das Gedächtnis als Vault — lesbar, verlinkt, beschreibbar.

Zwei Richtungen:

  Gedächtnis → Vault   (nach jedem Autopilot-Lauf)
      00 Dashboard.md       Ampel, offene Fragen, laufende Vorhaben, Top-Ideen
      01 Inbox.md           DEIN Eingang (siehe unten)
      Ideen/*.md            eine Notiz je Idee, mit Frontmatter (Dataview-tauglich)
      Fragen/*.md           eine Notiz je offener Frage an dich
      Entscheidungen.md · Erkenntnisse.md · Fehler.md · Kennzahlen.md
      Briefings/JJJJ-MM-TT.md   der Tagesbericht des Autopiloten

  Vault → Gedächtnis   (vor jedem Autopilot-Lauf)
      Fragen beantworten:  in der Frage-Notiz unter "## Deine Antwort" schreiben
                           (oder im Frontmatter `antwort:` ausfüllen)
      Ideen steuern:       im Frontmatter `status:` ändern
                           (neu | geprueft | laeuft | erledigt | verworfen)
      Inbox:               Zeilen in 01 Inbox.md, z.B.
                             - idee: Freebie-PDF aus eigenen Daten | 3h | 400€
                             - erkenntnis: Hooks mit Zahl schlagen Fragen-Hooks
                             - entscheidung: Account C -> abschalten | weil 1.100 Views in 6 Wochen
                           Verarbeitete Zeilen wandern nach "## Verarbeitet".

Was du unter "<!-- deine notizen -->" in eine Ideen- oder Frage-Notiz schreibst,
wird nie überschrieben.

Setup: in .env  OBSIDIAN_VAULT=/Pfad/zu/deinem/Vault   (leer = aus)
Nutzung:
    python3 obsidian_sync.py            # einlesen + schreiben
    python3 obsidian_sync.py --status   # nur zeigen, was konfiguriert ist
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import brain
import config

log = logging.getLogger("obsidian")

STATE_FILE = brain.BRAIN_DIR / "obsidian_state.json"
MARKER = "<!-- deine notizen -->"
STATUS_ERLAUBT = {"neu", "geprueft", "laeuft", "erledigt", "verworfen"}
ANTWORT_PLATZHALTER = "_(hier antworten — ja/nein reicht)_"


# ── Grundlagen ─────────────────────────────────────────────────────────────────
def ordner() -> Path | None:
    """Zielordner im Vault, oder None wenn die Brücke aus ist."""
    if not config.OBSIDIAN_VAULT:
        return None
    vault = Path(config.OBSIDIAN_VAULT).expanduser()
    if not vault.is_dir():
        raise RuntimeError(f"OBSIDIAN_VAULT existiert nicht: {vault}")
    ziel = vault / config.OBSIDIAN_ORDNER
    for sub in ("", "Ideen", "Fragen", "Briefings"):
        (ziel / sub).mkdir(parents=True, exist_ok=True)
    return ziel


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"ideen": {}, "fragen": {}}


def _save_state(s: dict):
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def _dateiname(text: str, max_len: int = 70) -> str:
    """Obsidian- und iCloud-sicherer Dateiname (keine [] # ^ | / \\ : etc.)."""
    t = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", text)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return (t[:max_len].rstrip() or "ohne Titel")


def _schreib(pfad: Path, inhalt: str) -> bool:
    """Schreibt nur bei Änderung — sonst triggert jeder Lauf unnötig iCloud/Obsidian-Sync."""
    if pfad.exists() and pfad.read_text(encoding="utf-8") == inhalt:
        return False
    pfad.write_text(inhalt, encoding="utf-8")
    return True


def _frontmatter(daten: dict) -> str:
    zeilen = ["---"]
    for k, v in daten.items():
        if isinstance(v, list):
            zeilen.append(f"{k}: [{', '.join(json.dumps(x, ensure_ascii=False) for x in v)}]")
        elif isinstance(v, (int, float)):
            zeilen.append(f"{k}: {v}")
        else:
            zeilen.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    zeilen.append("---")
    return "\n".join(zeilen)


def _lies(pfad: Path) -> tuple[dict, str]:
    """Flaches YAML-Frontmatter + Body. Bewusst ohne PyYAML — wir schreiben es ja selbst."""
    text = pfad.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for zeile in m.group(1).splitlines():
        if ":" not in zeile:
            continue
        k, v = zeile.split(":", 1)
        v = v.strip()
        if v.startswith('"'):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = v.strip('"')
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]
        fm[k.strip()] = v
    return fm, m.group(2)


def _notizen(pfad: Path) -> str:
    """Kais eigener Teil unter dem Marker — bleibt bei jedem Export erhalten."""
    if not pfad.exists():
        return ""
    text = pfad.read_text(encoding="utf-8")
    return text.split(MARKER, 1)[1].strip("\n") if MARKER in text else ""


# ══════════════════════════════════════════════════════════════════════════════
#  VAULT → GEDÄCHTNIS
# ══════════════════════════════════════════════════════════════════════════════
def _antwort_aus(fm: dict, body: str) -> str:
    if str(fm.get("antwort", "")).strip():
        return str(fm["antwort"]).strip()
    m = re.search(r"^## Deine Antwort\s*\n(.*?)(?=^## |\Z|" + re.escape(MARKER) + ")",
                  body, re.S | re.M)
    if not m:
        return ""
    t = m.group(1).replace(ANTWORT_PLATZHALTER, "").strip()
    return re.sub(r"<!--.*?-->", "", t, flags=re.S).strip()


def _fragen_einlesen(ziel: Path, st: dict) -> int:
    n = 0
    for pfad in (ziel / "Fragen").glob("*.md"):
        fm, body = _lies(pfad)
        if fm.get("typ") != "frage" or fm.get("status") != "offen":
            continue
        antwort = _antwort_aus(fm, body)
        if not antwort or not str(fm.get("id", "")).isdigit():
            continue
        brain.antworte(int(fm["id"]), antwort)
        brain.decide(f"Frage: {fm.get('frage', '')[:120]}", antwort,
                     "Antwort aus Obsidian", von="kai")
        brain.event("obsidian", f"Frage {fm['id']} beantwortet", {"antwort": antwort[:200]})
        n += 1
    return n


def _ideen_einlesen(ziel: Path, st: dict) -> int:
    """Status-Änderungen übernehmen — aber nur, wenn KAI ihn geändert hat (Diff zum letzten Export)."""
    n = 0
    exportiert = st.get("ideen", {})
    for pfad in (ziel / "Ideen").glob("*.md"):
        fm, _ = _lies(pfad)
        iid = str(fm.get("id", ""))
        if fm.get("typ") != "idee" or iid not in exportiert:
            continue
        neu = str(fm.get("status", "")).strip().lower()
        if neu == exportiert[iid]["status"] or neu not in STATUS_ERLAUBT:
            continue
        with brain._db() as con:
            row = con.execute("SELECT titel FROM ideas WHERE id=?", (int(iid),)).fetchone()
        if not row:
            continue
        grund = str(fm.get("begruendung", "")).strip() or "Status in Obsidian geändert"
        brain.idee_status(row["titel"], neu, grund)
        brain.decide(f"Idee: {row['titel']}", f"Status -> {neu}", grund, von="kai")
        exportiert[iid]["status"] = neu
        n += 1
    return n


INBOX_KOPF = """# 📥 Inbox

Schreib hier rein — der Autopilot holt es beim nächsten Lauf ab.

- `idee: Titel | 3h | 400€ | Beschreibung`  (Stunden, Umsatz/Monat optional)
- `erkenntnis: was du beobachtet hast`
- `entscheidung: Thema -> Entscheidung | weil Begründung`

## Neu

"""


def _inbox_einlesen(ziel: Path) -> int:
    pfad = ziel / "01 Inbox.md"
    if not pfad.exists():
        _schreib(pfad, INBOX_KOPF + "\n## Verarbeitet\n")
        return 0
    text = pfad.read_text(encoding="utf-8")
    kopf, _, rest = text.partition("## Neu")
    neu_teil, _, verarbeitet = rest.partition("## Verarbeitet")

    erledigt, bleibt = [], []
    for zeile in neu_teil.splitlines():
        m = re.match(r"^\s*[-*]\s*(?:\[.\]\s*)?(idee|erkenntnis|entscheidung)\s*:\s*(.+)$", zeile, re.I)
        if not m:
            if zeile.strip():
                bleibt.append(zeile)
            continue
        art, inhalt = m.group(1).lower(), m.group(2).strip()
        try:
            if art == "idee":
                teile = [t.strip() for t in inhalt.split("|")]
                h = next((float(re.sub(r"[^\d.,]", "", t).replace(",", "."))
                          for t in teile[1:] if re.search(r"\d\s*h\b", t)), 0)
                eur = next((float(re.sub(r"[^\d.,]", "", t).replace(".", "").replace(",", "."))
                            for t in teile[1:] if "€" in t or "eur" in t.lower()), 0)
                txt = " ".join(t for t in teile[1:] if not re.search(r"\d\s*h\b|€|eur", t, re.I))
                brain.idea(teile[0], beschreibung=txt, quelle="Kai (Obsidian)",
                           aufwand_h=h, umsatz_monat=eur, risiko=2)
            elif art == "erkenntnis":
                brain.learn(inhalt, "Kai (Obsidian)")
            else:
                haupt, _, grund = inhalt.partition("|")
                thema, _, ent = haupt.partition("->")
                grund = re.sub(r"^\s*weil\s*", "", grund).strip()
                brain.decide(thema.strip(), (ent or thema).strip(), grund, von="kai")
            erledigt.append(f"- ✅ {datetime.now():%d.%m. %H:%M} {art}: {inhalt}")
        except Exception as e:  # eine kaputte Zeile darf den Rest nicht blockieren
            bleibt.append(f"{zeile}  ⚠️ nicht verstanden: {e}")

    if erledigt:
        neu_text = (kopf.rstrip("\n") + "\n\n## Neu\n\n" + "\n".join(bleibt) +
                    ("\n" if bleibt else "") + "\n## Verarbeitet\n\n" +
                    "\n".join(erledigt) + "\n" + verarbeitet.lstrip("\n"))
        _schreib(pfad, neu_text)
        brain.event("obsidian", f"Inbox: {len(erledigt)} Einträge übernommen")
    return len(erledigt)


def einlesen() -> dict:
    """Vault → Gedächtnis. Läuft VOR jedem Autopilot-Lauf."""
    ziel = ordner()
    if not ziel:
        return {}
    st = _state()
    ergebnis = {"fragen": _fragen_einlesen(ziel, st),
                "ideen": _ideen_einlesen(ziel, st),
                "inbox": _inbox_einlesen(ziel)}
    _save_state(st)
    if any(ergebnis.values()):
        log.info("Obsidian eingelesen: %s", ergebnis)
    return ergebnis


# ══════════════════════════════════════════════════════════════════════════════
#  GEDÄCHTNIS → VAULT
# ══════════════════════════════════════════════════════════════════════════════
RISIKO = {1: "niedrig", 2: "mittel", 3: "hoch"}


def _ideen_schreiben(ziel: Path, st: dict) -> dict[int, str]:
    with brain._db() as con:
        alle = [dict(r) for r in con.execute("SELECT * FROM ideas").fetchall()]
    namen, neu_state = {}, {}
    alt = st.get("ideen", {})
    for i in alle:
        sid = str(i["id"])
        name = alt.get(sid, {}).get("datei") or _dateiname(i["titel"])
        pfad = ziel / "Ideen" / f"{name}.md"
        if pfad.exists() and sid not in alt:            # Namenskollision mit fremder Notiz
            name = f"{name} ({sid})"
            pfad = ziel / "Ideen" / f"{name}.md"
        fm = _frontmatter({
            "typ": "idee", "id": i["id"], "status": i["status"], "score": i["score"],
            "aufwand_h": i["aufwand_h"], "umsatz_monat": i["umsatz_monat"],
            "risiko": i["risiko"], "quelle": i["quelle"], "begruendung": i["begruendung"],
            "erstellt": (i["erstellt"] or "")[:10], "aktualisiert": (i["aktualisiert"] or "")[:10],
            "tags": ["jk24/idee", f"status/{i['status']}"],
        })
        body = [
            f"# {i['titel']}", "",
            f"> **Score {i['score']}** · {i['aufwand_h']} h Aufwand · "
            f"{i['umsatz_monat']:.0f} € / Monat · Risiko {RISIKO.get(i['risiko'], i['risiko'])}",
            "", i["beschreibung"] or "_keine Beschreibung_", "",
            "Status ändern: oben im Frontmatter `status:` auf "
            "`neu | geprueft | laeuft | erledigt | verworfen` setzen.", "",
            "Zurück zum [[00 Dashboard]]", "", MARKER, _notizen(pfad),
        ]
        _schreib(pfad, fm + "\n" + "\n".join(body).rstrip() + "\n")
        namen[i["id"]] = name
        neu_state[sid] = {"datei": name, "status": i["status"]}
    st["ideen"] = neu_state
    return namen


def _fragen_schreiben(ziel: Path, st: dict) -> list[tuple[dict, str]]:
    fragen = brain.offene_fragen()
    offen_ids = {q["id"] for q in fragen}
    alt = st.get("fragen", {})
    # beantwortete Fragen: Notiz bleibt als Archiv, Status wird nachgezogen
    for sid, name in list(alt.items()):
        if int(sid) in offen_ids:
            continue
        pfad = ziel / "Fragen" / f"{name}.md"
        if pfad.exists():
            text = pfad.read_text(encoding="utf-8")
            _schreib(pfad, re.sub(r'^status:\s*"?offen"?\s*$', 'status: "beantwortet"',
                                  text, count=1, flags=re.M))
        alt.pop(sid)

    liste = []
    for q in fragen:
        sid = str(q["id"])
        name = alt.get(sid) or f"Frage {q['id']} – {_dateiname(q['frage'], 55)}"
        pfad = ziel / "Fragen" / f"{name}.md"
        fm = _frontmatter({
            "typ": "frage", "id": q["id"], "status": "offen", "frage": q["frage"],
            "dringlichkeit": q["dringlichkeit"], "erstellt": (q["erstellt"] or "")[:10],
            "antwort": "", "tags": ["jk24/frage"],
        })
        if pfad.exists():                 # Kai hat evtl. schon angefangen zu antworten
            alter_fm, alter_body = _lies(pfad)
            antwort = _antwort_aus(alter_fm, alter_body)
        else:
            antwort = ""
        body = [
            f"# {q['frage']}", "",
            f"_{q['kontext']}_" if q["kontext"] else "",
            "", "## Deine Antwort", "", antwort or ANTWORT_PLATZHALTER, "",
            MARKER, _notizen(pfad),
        ]
        _schreib(pfad, fm + "\n" + "\n".join(body).rstrip() + "\n")
        alt[sid] = name
        liste.append((q, name))
    st["fragen"] = alt
    return liste


def _listen_schreiben(ziel: Path):
    z = ["# Erkenntnisse", "", "Sortiert nach Gewicht (wie oft bestätigt).", ""]
    z += [f"- **{x['gewicht']}×** {x['text']}" + (f" — _{x['belege']}_" if x["belege"] else "")
          for x in brain.erkenntnisse(200)] or ["- noch keine"]
    _schreib(ziel / "Erkenntnisse.md", "\n".join(z) + "\n")

    z = ["# Entscheidungen", "", "Was entschieden ist, wird nicht neu aufgerollt.", ""]
    for x in brain.entscheidungen(200):
        z += [f"### {x['erstellt'][:10]} · {x['thema']}", "",
              f"**→ {x['entscheidung']}**  ({x['von']})"]
        if x["begruendung"]:
            z.append(f"_{x['begruendung']}_")
        z.append("")
    _schreib(ziel / "Entscheidungen.md", "\n".join(z) if len(z) > 4 else "# Entscheidungen\n\n- noch keine\n")

    fehler = brain.offene_fehler()
    z = ["# Offene Fehler", ""]
    z += [f"- [ ] `{x['komponente']}` {x['meldung'][:200]} — **{x['anzahl']}×** seit "
          f"{x['zuerst'][:10]}, Status: {x['status']}" for x in fehler] or ["- keine 🎉"]
    _schreib(ziel / "Fehler.md", "\n".join(z) + "\n")

    seit = (datetime.now() - timedelta(days=30)).date().isoformat()
    with brain._db() as con:
        rows = con.execute("SELECT datum, account, kennzahl, wert FROM metrics WHERE datum>=? "
                           "ORDER BY kennzahl, account, datum DESC", (seit,)).fetchall()
    z = ["# Kennzahlen (30 Tage)", ""]
    aktuell = None
    for r in rows:
        k = f"{r['kennzahl']}" + (f" · {r['account']}" if r["account"] else "")
        if k != aktuell:
            aktuell = k
            t = brain.trend(r["kennzahl"], 14, r["account"])
            z += ["", f"## {k}" + (f"  (Trend 14 T: {t:+} %)" if t is not None else ""), "",
                  "| Datum | Wert |", "|---|---:|"]
        z.append(f"| {r['datum']} | {r['wert']:g} |")
    if not rows:
        z.append("- noch keine Zahlen")
    _schreib(ziel / "Kennzahlen.md", "\n".join(z) + "\n")


def _dashboard_schreiben(ziel: Path, ideen: dict[int, str], fragen: list, briefing: str | None):
    s = brain.status()
    heute = f"{datetime.now():%Y-%m-%d}"
    z = [_frontmatter({"typ": "dashboard", "aktualisiert": datetime.now().isoformat(timespec="minutes"),
                       "tags": ["jk24"]}),
         f"# JK24 Autopilot — {datetime.now():%d.%m.%Y %H:%M}", ""]
    if briefing:
        erste = briefing.strip().splitlines()[0].lstrip("# ").strip()
        z += [f"**{erste}** → [[Briefings/{heute}|Tagesbericht]]", ""]
    z += [f"Ideen neu **{s['ideen_neu']}** · laufend **{s['ideen_laufend']}** · erledigt "
          f"**{s['ideen_erledigt']}** · Fehler offen **{s['fehler_offen']}** · "
          f"Erkenntnisse **{s['erkenntnisse']}**", ""]

    z += ["## ⚠️ Wartet auf dich", ""]
    z += [f"- [[Fragen/{name}|{q['frage']}]]" + (" 🔥" if q["dringlichkeit"] >= 3 else "")
          for q, name in fragen] or ["- nichts — läuft 🎉"]

    for titel, status, n in (("🚀 Läuft", "laeuft", 10), ("💡 Beste Ideen", "neu", 10)):
        liste = brain.top_ideen(n, status=status)
        z += ["", f"## {titel}", ""]
        z += [f"- [[Ideen/{ideen[i['id']]}|{i['titel']}]] — Score {i['score']}"
              for i in liste if i["id"] in ideen] or ["- —"]

    z += ["", "## Alles", "",
          "[[01 Inbox]] · [[Erkenntnisse]] · [[Entscheidungen]] · [[Fehler]] · [[Kennzahlen]]",
          "", "<details><summary>Dataview-Ansicht (wenn Plugin installiert)</summary>", "",
          "```dataview", "TABLE score, status, aufwand_h AS \"h\", umsatz_monat AS \"€/Mon\"",
          f'FROM "{config.OBSIDIAN_ORDNER}/Ideen"', 'WHERE status != "verworfen"',
          "SORT score DESC", "```", "", "</details>"]
    _schreib(ziel / "00 Dashboard.md", "\n".join(z) + "\n")


def schreiben(briefing: str | None = None) -> Path | None:
    """Gedächtnis → Vault. Läuft NACH jedem Autopilot-Lauf."""
    ziel = ordner()
    if not ziel:
        return None
    st = _state()
    ideen = _ideen_schreiben(ziel, st)
    fragen = _fragen_schreiben(ziel, st)
    _listen_schreiben(ziel)
    if briefing:
        _schreib(ziel / "Briefings" / f"{datetime.now():%Y-%m-%d}.md",
                 _frontmatter({"typ": "briefing", "datum": f"{datetime.now():%Y-%m-%d}",
                               "tags": ["jk24/briefing"]}) + "\n" + briefing.rstrip() + "\n")
    _dashboard_schreiben(ziel, ideen, fragen, briefing)
    if not (ziel / "01 Inbox.md").exists():
        _schreib(ziel / "01 Inbox.md", INBOX_KOPF + "\n## Verarbeitet\n")
    _save_state(st)
    return ziel


def sync(briefing: str | None = None) -> dict:
    erg = einlesen()
    ziel = schreiben(briefing)
    return {"eingelesen": erg, "vault": str(ziel) if ziel else None}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not config.OBSIDIAN_VAULT:
        print("Obsidian ist aus. In .env setzen:  OBSIDIAN_VAULT=/Pfad/zum/Vault")
        sys.exit(1)
    if "--status" in sys.argv:
        print(f"Vault:  {config.OBSIDIAN_VAULT}\nOrdner: {config.OBSIDIAN_ORDNER}")
        sys.exit(0)
    latest = config.BASE_DIR / "briefing" / "latest.md"
    print(json.dumps(sync(latest.read_text(encoding="utf-8") if latest.exists() else None),
                     ensure_ascii=False, indent=2))
