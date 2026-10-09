"""
Der Autopilot. Läuft mehrmals täglich auf dem MacBook und macht einen
kompletten Durchgang: prüfen → heilen → messen → posten → entdecken → planen → melden.

SICHERHEITSGRENZE — bewusst und nicht verhandelbar:
Der Autopilot ändert NIEMALS selbst seinen eigenen Programmcode. Er darf
reparieren (Paket nachinstallieren, Platte aufräumen, Lauf wiederholen),
messen, recherchieren und VORSCHLAGEN. Code-Änderungen landen als Vorschlag
im Gedächtnis und werden in einer Sitzung mit Claude umgesetzt.

Der Grund ist nicht Vorsicht um ihrer selbst willen: Ein System, das sich
nachts unbeaufsichtigt umschreibt, ist irgendwann kaputt, und niemand weiß
wann oder warum. Ein System, das Vorschläge sammelt, wird jede Woche besser
und bleibt dabei jederzeit erklärbar.

Aufruf:
    python3 autopilot.py              # kompletter Durchgang
    python3 autopilot.py --kurz       # nur prüfen, heilen, posten (zwischendurch)
    python3 autopilot.py --bericht    # nur den aktuellen Stand zeigen
"""
from __future__ import annotations

import json
import logging
import signal
import subprocess
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import brain
import config

LOG_DIR = config.LOGS_DIR
BRIEF_DIR = config.BASE_DIR / "briefing"
BRIEF_DIR.mkdir(exist_ok=True)
STATE_FILE = brain.BRAIN_DIR / "autopilot_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / f"{datetime.now():%Y-%m-%d}.log"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("autopilot")


# Harte Obergrenze pro Lauf. Ohne die kann ein haengender Download oder eine
# langsame Installation den Lauf blockieren — und weil launchd alle paar Stunden
# erneut startet, stapeln sich die Laeufe, bis der Mac kriecht. Lieber ein
# abgebrochener Lauf mit Meldung als zehn Zombie-Prozesse.
ZEITGRENZE_VOLL = 25 * 60
ZEITGRENZE_KURZ = 8 * 60


class Zeitueberschreitung(RuntimeError):
    pass


def _wecker(sekunden: int):
    """Setzt einen Wecker, der den Lauf abbricht. Ohne SIGALRM wirkungslos."""
    def ausgeloest(signum, frame):  # noqa: ARG001
        dauer = f"{sekunden // 60} Minuten" if sekunden >= 60 else f"{sekunden} Sekunden"
        raise Zeitueberschreitung(f"Lauf nach {dauer} abgebrochen")
    try:
        signal.signal(signal.SIGALRM, ausgeloest)
        signal.alarm(sekunden)
    except (AttributeError, ValueError):
        pass          # Windows oder Nicht-Hauptthread: dann eben ohne Wecker


def _wecker_aus():
    try:
        signal.alarm(0)
    except (AttributeError, ValueError):
        pass


def _state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(s: dict):
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def _einmal_taeglich(schluessel: str) -> bool:
    """True, wenn diese Aufgabe heute noch nicht lief (teure Dinge nur 1x/Tag)."""
    s = _state()
    heute = datetime.now().date().isoformat()
    if s.get(schluessel) == heute:
        return False
    s[schluessel] = heute
    _save_state(s)
    return True


def notify(titel: str, text: str):
    """macOS-Mitteilung. Auf anderen Systemen still."""
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{text}" with title "{titel}"'],
                       timeout=10, capture_output=True)
    except Exception:  # noqa: BLE001
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  1. PRÜFEN
# ══════════════════════════════════════════════════════════════════════════════
def _einzeilig(text: str, max_len: int = 110) -> str:
    """Fehlermeldungen enthalten oft ganze Setup-Anleitungen mit Zeilenumbruechen.
    Im Bericht braucht es davon genau eine lesbare Zeile."""
    kurz = " ".join(str(text).split())
    return kurz[:max_len] + ("…" if len(kurz) > max_len else "")


def pruefen() -> tuple[bool, list[str]]:
    probleme = []
    try:
        import selftest
        ok, health = selftest.run_selftest()
        for c in health.get("checks", []):
            if not c["ok"]:
                brain.log_error(c["name"], c.get("detail", ""))
                if c.get("critical"):
                    probleme.append(f"{c['name']}: {_einzeilig(c.get('detail', ''))}")
        return ok, probleme
    except Exception as e:  # noqa: BLE001
        brain.log_error("selftest", f"{e}\n{traceback.format_exc(limit=1)}")
        return False, [f"Selbsttest abgestürzt: {e}"]


# ══════════════════════════════════════════════════════════════════════════════
#  2. HEILEN — nur bekannte, sichere Reparaturen
# ══════════════════════════════════════════════════════════════════════════════
def _fix_paket_fehlt(fehler: dict) -> str | None:
    """'No module named X' -> Paket nachinstallieren."""
    import re
    m = re.search(r"No module named '([\w\-\.]+)'", fehler["meldung"])
    if not m:
        return None
    paket = m.group(1).split(".")[0]
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "--break-system-packages", paket],
                       capture_output=True, text=True, timeout=300)
    return f"pip install {paket}" if r.returncode == 0 else None


def _fix_platte_voll(fehler: dict) -> str | None:
    """'No space left' -> alte Videos und öffentliche Dateien wegräumen."""
    if "No space left" not in fehler["meldung"] and "Errno 28" not in fehler["meldung"]:
        return None
    geloescht = 0
    grenze = datetime.now() - timedelta(days=7)
    for ordner in (config.VIDEO_DIR, config.AUDIO_DIR, config.BASE_DIR / "public"):
        if not ordner.exists():
            continue
        for f in ordner.rglob("*"):
            if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < grenze:
                f.unlink(missing_ok=True)
                geloescht += 1
    return f"{geloescht} alte Dateien gelöscht" if geloescht else None


def _fix_browser_fehlt(fehler: dict) -> str | None:
    if "playwright" not in fehler["meldung"].lower() and \
       "executable doesn't exist" not in fehler["meldung"].lower():
        return None
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       capture_output=True, text=True, timeout=600)
    return "Chromium nachinstalliert" if r.returncode == 0 else None


def _braucht_kai(fehler: dict) -> str | None:
    """Fehler, die ein Mensch lösen muss — als Frage ins Gedächtnis statt endlos retry."""
    meldung = fehler["meldung"].lower()
    faelle = {
        "oauth": "Instagram-Token abgelaufen — im Graph API Explorer neu erzeugen (5 Min).",
        "access token": "Zugangstoken abgelaufen — bitte erneuern.",
        "cookie": "TikTok-Login abgelaufen — einmal `python3 uploader.py --login` ausführen.",
        "login": "TikTok-Login abgelaufen — einmal `python3 uploader.py --login` ausführen.",
        "quota": "API-Kontingent erschöpft — morgen wieder, oder Limit erhöhen.",
        "api key": "Ein API-Schlüssel fehlt oder ist ungültig — .env prüfen.",
    }
    for muster, text in faelle.items():
        if muster in meldung:
            brain.frage_kai(text, f"Fehler in {fehler['komponente']}, {fehler['anzahl']}x aufgetreten.",
                            dringlichkeit=3 if fehler["anzahl"] > 2 else 2)
            with brain._db() as con:
                con.execute("UPDATE errors SET status='braucht_kai' WHERE fingerprint=?",
                            (fehler["fingerprint"],))
            return "an Kai weitergegeben"
    return None


REPARATUREN = [_braucht_kai, _fix_paket_fehlt, _fix_platte_voll, _fix_browser_fehlt]


def heilen(max_reparaturen: int = 3) -> list[str]:
    """
    Versucht jede bekannte Reparatur auf jeden offenen Fehler. Nie Code-Änderungen.

    Höchstens drei echte Reparaturen pro Lauf: Wenn zehn Pakete fehlen, ist etwas
    Grundsätzliches kaputt, und zehn Installationen hintereinander lösen das nicht,
    sie verbrauchen nur das Zeitbudget. Der nächste Lauf macht weiter.
    """
    erledigt = []
    for fehler in brain.offene_fehler():
        if len([e for e in erledigt if "an Kai" not in e]) >= max_reparaturen:
            log.info("Reparatur-Grenze erreicht — Rest beim nächsten Lauf")
            break
        for reparatur in REPARATUREN:
            try:
                ergebnis = reparatur(fehler)
            except Exception as e:  # noqa: BLE001
                log.warning("Reparatur %s fehlgeschlagen: %s", reparatur.__name__, e)
                continue
            if ergebnis:
                if ergebnis != "an Kai weitergegeben":
                    brain.fehler_behoben(fehler["fingerprint"], ergebnis)
                erledigt.append(f"{fehler['komponente']}: {ergebnis}")
                brain.event("heilung", f"{fehler['komponente']} -> {ergebnis}")
                break
    return erledigt


# ══════════════════════════════════════════════════════════════════════════════
#  3. MESSEN
# ══════════════════════════════════════════════════════════════════════════════
def messen() -> dict:
    zahlen = {}
    try:
        import stats_scraper
        neu = stats_scraper.update_performance()
        zahlen["neue_datenpunkte"] = neu
    except Exception as e:  # noqa: BLE001
        brain.log_error("stats_scraper", str(e))

    try:
        import csv
        perf = config.CONTENT_DIR / "performance.csv"
        if perf.exists():
            with perf.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            gesamt = sum(int(r["views"] or 0) for r in rows)
            brain.metric("views_gesamt", gesamt)
            zahlen["views_gesamt"] = gesamt

            t = brain.trend("views_gesamt", tage=14)
            if t is not None:
                zahlen["trend_14_tage_prozent"] = t
                if t < -20:
                    brain.frage_kai(
                        "Reichweite fällt seit zwei Wochen deutlich. Soll ich die Nische wechseln?",
                        f"Views-Trend: {t} % über 14 Tage.", dringlichkeit=2)
    except Exception as e:  # noqa: BLE001
        brain.log_error("messen", str(e))

    try:
        import accounts as accounts_mod
        for a in accounts_mod.enabled():
            brain.metric("posts_heute", accounts_mod.posted_today(a), account=a.id)
    except Exception as e:  # noqa: BLE001
        brain.log_error("messen_accounts", str(e))

    return zahlen


# ══════════════════════════════════════════════════════════════════════════════
#  4. POSTEN
# ══════════════════════════════════════════════════════════════════════════════
def posten() -> int:
    try:
        import scheduler
        return scheduler.run_cycle()
    except Exception as e:  # noqa: BLE001
        brain.log_error("scheduler", f"{e}\n{traceback.format_exc(limit=1)}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
#  5. ENTDECKEN (1x täglich — kostet Geld und Zeit)
# ══════════════════════════════════════════════════════════════════════════════
def entdecken() -> int:
    if not _einmal_taeglich("scout"):
        return 0
    try:
        import ideas_scout
        data = ideas_scout.run_scout()
        return len(data.get("ideen", []))
    except Exception as e:  # noqa: BLE001
        brain.log_error("ideas_scout", str(e))
        return 0


def strategie_auffrischen():
    if not _einmal_taeglich("improver"):
        return
    try:
        import improver
        d = improver.run_improver()
        for lektion in d.get("lessons", [])[:5]:
            brain.learn(lektion, "improver")
    except Exception as e:  # noqa: BLE001
        brain.log_error("improver", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  5b. WERKZEUGE NUTZEN — Dinge, die der Autopilot selbst anstoßen darf
# ══════════════════════════════════════════════════════════════════════════════
def werkzeuge() -> list[str]:
    """
    Kleine, sichere Automatismen, die sonst liegen bleiben, weil sie niemandem
    auffallen. Keine Code-Änderungen, keine Außenwirkung ohne Kais Zutun.
    """
    getan = []

    # Der Lead-Magnet wird mit echten Zahlen erst gut. Sobald genug Datenpunkte
    # da sind, einmal neu erzeugen — dann steht die echte Tabelle drin.
    try:
        import csv
        perf = config.CONTENT_DIR / "performance.csv"
        if perf.exists():
            with perf.open(encoding="utf-8") as f:
                zeilen = sum(1 for _ in csv.DictReader(f))
            schwelle = _state().get("freebie_bei", 0)
            if zeilen >= 30 and zeilen >= schwelle + 30:
                import freebie
                leitfaden, anzahl = freebie.baue_leitfaden(
                    "Die Hooks, die auf deutschem TikTok wirklich funktionieren", 50)
                freebie.AUSGABE.mkdir(parents=True, exist_ok=True)
                (freebie.AUSGABE / "freebie.html").write_text(leitfaden, encoding="utf-8")
                st = _state(); st["freebie_bei"] = zeilen; _save_state(st)
                getan.append(f"Lead-Magnet mit {zeilen} echten Datenpunkten neu erzeugt")
                brain.learn(f"Lead-Magnet enthält jetzt eigene Zahlen aus {zeilen} Beiträgen — "
                            f"das ist das Verkaufsargument gegenüber recycelten PDFs.", "autopilot")
    except Exception as e:  # noqa: BLE001
        brain.log_error("werkzeuge_freebie", str(e))

    # Montags an den einzigen Umsatzweg erinnern, der vor Monat 5 Geld bringt.
    try:
        if datetime.now().weekday() == 0 and _einmal_taeglich("verkaufserinnerung"):
            offen = [i for i in brain.top_ideen(20, status="neu")
                     if i["titel"].startswith("Verkaufsgespräch:")]
            if offen:
                namen = ", ".join(i["titel"].split(": ", 1)[1] for i in offen[:3])
                brain.frage_kai(f"Diese Verkaufsgespräche stehen noch offen: {namen}. "
                                f"Schon angerufen?",
                                "Arbeitsproben liegen fertig im Ordner verkauf/.", 2)
            else:
                brain.frage_kai("Welchen Betrieb sprichst du diese Woche an?",
                                "Ich erstelle die Arbeitsprobe in 2 Minuten: "
                                "python3 verkaufskit.py \"Name\" branche", 2)
            getan.append("Wochen-Erinnerung Verkauf gesetzt")
    except Exception as e:  # noqa: BLE001
        brain.log_error("werkzeuge_verkauf", str(e))

    return getan


# ══════════════════════════════════════════════════════════════════════════════
#  6. PLANEN — was ist der nächste sinnvolle Schritt?
# ══════════════════════════════════════════════════════════════════════════════
PLAN_PROMPT = """Du bist der operative Kopf eines Ein-Mann-Unternehmens in Deutschland.

Die Lage: 50-Stunden-Job, Familie, 10-12 freie Stunden pro Woche. Ziel sind
10.000 EUR Monatsumsatz in 10 Monaten aus einem automatisierten Content-System.
Der Engpass ist IMMER seine Zeit, nie die Technik.

{gedaechtnis}

Lage heute:
{lage}

AUFGABE: Nenne GENAU EINEN nächsten Schritt für die kommenden sieben Tage.
Nicht drei. Einen. Er muss in unter 3 Stunden machbar sein und dem Umsatz
näher bringen — nicht der Technik.

Wenn etwas nur Kai entscheiden kann, formuliere es als Ja/Nein-Frage.

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "naechster_schritt": "ein Satz, Befehlsform, konkret",
 "warum": "ein Satz",
 "dauer_h": 2,
 "frage_an_kai": "Ja/Nein-Frage oder leer",
 "erkenntnis": "eine Beobachtung aus den Daten, oder leer"
}}"""


def planen(lage: dict) -> dict:
    if not _einmal_taeglich("plan"):
        return {}
    try:
        import content_generator
        import re
        text = content_generator.generate_llm(
            "Du antwortest ausschliesslich mit validem JSON.",
            PLAN_PROMPT.format(gedaechtnis=brain.kontext_fuer_ki(3500),
                               lage=json.dumps(lage, ensure_ascii=False)),
            max_tokens=700)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {}
        plan = json.loads(m.group(0))

        if plan.get("naechster_schritt"):
            brain.idea(plan["naechster_schritt"],
                       beschreibung=plan.get("warum", ""), quelle="Autopilot-Plan",
                       aufwand_h=float(plan.get("dauer_h") or 2),
                       umsatz_monat=0, risiko=1, status="neu")
        if plan.get("frage_an_kai"):
            brain.frage_kai(plan["frage_an_kai"], plan.get("warum", ""))
        if plan.get("erkenntnis"):
            brain.learn(plan["erkenntnis"], "Autopilot-Analyse")
        return plan
    except Exception as e:  # noqa: BLE001
        brain.log_error("planen", str(e))
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  7. MELDEN — kurz. Drei Zeilen und eine Frage.
# ══════════════════════════════════════════════════════════════════════════════
def melden(gepostet: int, geheilt: list[str], zahlen: dict, plan: dict, probleme: list[str]) -> str:
    fragen = brain.offene_fragen()
    fehler = brain.offene_fehler()

    if any(f["status"] == "braucht_kai" for f in fehler) or probleme:
        ampel, wort = "🔴", "braucht dich"
    elif fehler or fragen:
        ampel, wort = "🟡", "läuft, mit Hinweis"
    else:
        ampel, wort = "🟢", "alles läuft"

    z = [f"# {ampel} {wort} — {datetime.now():%d.%m.%Y %H:%M}", ""]
    z.append(f"**Heute gepostet:** {gepostet}  ·  "
             f"**Views gesamt:** {zahlen.get('views_gesamt', '—')}  ·  "
             f"**Trend 14 Tage:** {zahlen.get('trend_14_tage_prozent', '—')} %")
    if geheilt:
        z.append(f"**Selbst repariert:** {'; '.join(_einzeilig(g, 60) for g in geheilt[:3])}")
    z.append("")

    if plan.get("naechster_schritt"):
        z += ["## Dein nächster Schritt", "",
              f"**{plan['naechster_schritt']}**  _(ca. {plan.get('dauer_h', 2)} h)_",
              f"{plan.get('warum', '')}", ""]

    if fragen:
        z += ["## Beantworte das hier (einfach in den Chat schreiben)", ""]
        z += [f"{i}. {q['frage']}" for i, q in enumerate(fragen[:3], 1)]
        z.append("")

    if probleme:
        z += ["## Was klemmt", ""] + [f"- {_einzeilig(p)}" for p in probleme[:3]] + [""]

    z += ["---", "Alle Ideen und Erkenntnisse: `brain/GEDAECHTNIS.md`"]

    text = "\n".join(z)
    (BRIEF_DIR / f"{datetime.now():%Y-%m-%d}.md").write_text(text, encoding="utf-8")
    (BRIEF_DIR / "latest.md").write_text(text, encoding="utf-8")
    brain.export_markdown()

    kurz = plan.get("naechster_schritt", "") or (fragen[0]["frage"] if fragen else "nichts zu tun")
    notify(f"{ampel} JK24-Autopilot", f"{gepostet} gepostet. {kurz[:90]}")
    return text


# ══════════════════════════════════════════════════════════════════════════════
def run(kurz: bool = False) -> str:
    start = datetime.now()
    log.info("═══ Autopilot startet (%s) ═══", "kurz" if kurz else "voll")
    brain.event("start", "Autopilot-Lauf", {"modus": "kurz" if kurz else "voll"})
    _wecker(ZEITGRENZE_KURZ if kurz else ZEITGRENZE_VOLL)

    ok, probleme, geheilt, gepostet = False, [], [], 0
    zahlen, plan = {}, {}

    try:
        ok, probleme = pruefen()
        geheilt = heilen()
        if geheilt:                   # nach einer Reparatur nochmal prüfen
            ok, probleme = pruefen()

        gepostet = posten() if ok else 0
        if not ok:
            probleme.append("Posten übersprungen — Selbsttest hat kritische Fehler gemeldet.")

        if not kurz:
            zahlen = messen()
            strategie_auffrischen()
            entdecken()
            geheilt += werkzeuge()
            plan = planen({"gepostet_heute": gepostet, "probleme": probleme, **zahlen})

    except Zeitueberschreitung as e:
        # Kein Drama: Es wird trotzdem gemeldet, was bis hierhin lief, und der
        # nächste Lauf setzt fort. Nur auffallen muss es.
        log.error("%s", e)
        probleme.append(f"{e} — der nächste Lauf macht weiter.")
        brain.log_error("autopilot", str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("Autopilot-Lauf abgebrochen")
        probleme.append(f"Lauf abgebrochen: {e}")
        brain.log_error("autopilot", f"{e}\n{traceback.format_exc(limit=2)}")
    finally:
        _wecker_aus()

    bericht = melden(gepostet, geheilt, zahlen, plan, probleme)
    dauer = (datetime.now() - start).seconds
    brain.event("ende", f"Lauf fertig in {dauer}s",
                {"gepostet": gepostet, "geheilt": len(geheilt), "probleme": len(probleme)})
    log.info("═══ Autopilot fertig in %ds ═══", dauer)
    return bericht


if __name__ == "__main__":
    if "--bericht" in sys.argv:
        p = BRIEF_DIR / "latest.md"
        print(p.read_text(encoding="utf-8") if p.exists() else "Noch kein Bericht.")
    else:
        print(run(kurz="--kurz" in sys.argv))
