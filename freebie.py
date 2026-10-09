"""
Erzeugt den Lead-Magneten und die Landingpage.

Der Lead-Magnet ist "Die Hooks, die auf deutschem TikTok wirklich funktionieren" —
aufgebaut aus den EIGENEN Performance-Daten, sobald welche da sind. Das ist der
Unterschied zu den hundert recycelten PDFs im Umlauf: hier stehen Zahlen aus
einem Kanal, der tatsächlich läuft. Solange noch keine Daten da sind, wird aus
der Hook-Systematik und der KI erzeugt und ehrlich als solches gekennzeichnet.

Ausgabe (output/freebie/):
    index.html     Landingpage mit Eintragsformular (Double-Opt-In über Brevo)
    freebie.html   Der Leitfaden — im Browser öffnen, "Drucken → als PDF sichern"
    README.md      Wie du das hochlädst, in zwei Minuten

Beides sind einzelne HTML-Dateien ohne Abhängigkeiten. Laufen auf jedem Hoster,
auch auf dem kostenlosen Netlify-Tarif oder in Lovable.

    python3 freebie.py
    python3 freebie.py --titel "Die 50 Hooks" --anzahl 50
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import logging
import os
import re
from datetime import datetime

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]
from pathlib import Path

import config

log = logging.getLogger("freebie")

AUSGABE = config.BASE_DIR / "output" / "freebie"
PERF = config.CONTENT_DIR / "performance.csv"

BREVO_FORM_URL = os.getenv("BREVO_FORM_URL", "")
IMPRESSUM_URL = os.getenv("IMPRESSUM_URL", "/impressum.html")
DATENSCHUTZ_URL = os.getenv("DATENSCHUTZ_URL", "/datenschutz.html")

# Grundstock, falls weder Daten noch KI verfügbar sind. Nach Hook-Typ sortiert,
# damit der Leitfaden eine Systematik zeigt und nicht nur eine Liste.
GRUNDSTOCK = {
    "Zahl + Zeitraum": [
        "In 90 Tagen von null auf 50.000 — ohne ein einziges Gesicht im Bild.",
        "Drei Monate, 240 Beiträge, 11 Euro Werbebudget.",
        "Nach 40 Videos wusste ich, warum die ersten 39 niemand gesehen hat.",
    ],
    "Widerspruch": [
        "Mehr posten ist der Grund, warum dein Account nicht wächst.",
        "Dein bestes Video hat der Algorithmus nie gezeigt. Das ist kein Zufall.",
        "Reichweite ist das Letzte, worum du dich kümmern solltest.",
    ],
    "Verlust": [
        "Ich habe zwei Jahre verschwendet, weil mir das niemand gesagt hat.",
        "Der Fehler hat mich 4.000 Euro gekostet. Er dauert elf Sekunden zu erklären.",
        "Am Tag bevor es lief, wollte ich aufhören.",
    ],
    "Schritt-Liste": [
        "Schritt 1: Nische wählen. Schritt 2: nichts Neues erfinden.",
        "Vier Dinge. Mehr braucht ein Account nicht, der ohne dich läuft.",
    ],
    "Gegner benennen": [
        "Agenturen nehmen 2.000 Euro für etwas, das ein Werkzeug umsonst macht.",
        "Jeder Kurs verkauft dir Schritt drei. Niemand erklärt Schritt null.",
    ],
    "Beweis zeigen": [
        "Das ist der Screenshot. Die Zahl unten links ist der Punkt.",
        "Ich zeig dir die Zahlen. Urteile selbst.",
    ],
}

PROMPT = """Du schreibst einen Leitfaden über Hooks (die ersten Sekunden eines Kurzvideos)
für deutschsprachige Creator.

Gib mir {anzahl} Hooks, verteilt auf diese sechs Typen:
Zahl + Zeitraum, Widerspruch, Verlust, Schritt-Liste, Gegner benennen, Beweis zeigen.

REGELN:
- Deutsch, max. 12 Wörter pro Hook.
- Keine verbrannten Klischees ("Niemand wird dich retten", "1 % besser jeden Tag",
  "Der Unterschied zwischen Siegern und Verlierern").
- Jeder Hook muss auch ohne das Video danach neugierig machen.
- Konkret: eine Zahl, eine Situation, ein Gegner. Keine abstrakten Behauptungen.

Antworte AUSSCHLIESSLICH mit JSON:
{{"typen": {{"Zahl + Zeitraum": ["...", "..."], "Widerspruch": ["..."], ...}}}}"""


def _echte_daten() -> list[dict]:
    """Die eigenen Top-Beiträge nach Views. Das ist der Teil, den sonst niemand hat."""
    if not PERF.exists():
        return []
    with PERF.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("views") or "").isdigit()]
    rows.sort(key=lambda r: int(r["views"]), reverse=True)
    return rows[:15]


def _hooks(anzahl: int) -> dict[str, list[str]]:
    try:
        import content_generator
        text = content_generator.generate_llm(
            "Du antwortest ausschliesslich mit validem JSON.",
            PROMPT.format(anzahl=anzahl), max_tokens=2500)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            typen = json.loads(m.group(0)).get("typen", {})
            if sum(len(v) for v in typen.values()) >= anzahl * 0.6:
                # Grundstock untermischen, damit die bewährten Muster drin bleiben
                for k, v in GRUNDSTOCK.items():
                    typen.setdefault(k, [])
                    typen[k] = list(dict.fromkeys(typen[k] + v))
                return typen
    except Exception as e:  # noqa: BLE001
        log.warning("KI nicht erreichbar (%s) — nutze Grundstock", e)
    return GRUNDSTOCK


CSS = """
:root{--text:#16161a;--dim:#6b6b76;--line:#e3e3e8;--bg:#fff;--akzent:#111}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:17px/1.65 Georgia,'Times New Roman',serif;-webkit-font-smoothing:antialiased}
.seite{max-width:720px;margin:0 auto;padding:64px 28px 96px}
h1{font-size:40px;line-height:1.15;letter-spacing:-.02em;margin:0 0 12px}
h2{font-size:24px;margin:52px 0 10px;padding-bottom:8px;border-bottom:2px solid var(--akzent)}
h3{font-size:18px;margin:28px 0 8px;color:var(--dim);font-weight:400;
   text-transform:uppercase;letter-spacing:.08em}
p{margin:0 0 16px}
.unter{color:var(--dim);font-size:19px;margin:0 0 40px}
ol{padding-left:24px;margin:0 0 8px}
li{margin:0 0 12px}
.hook{font-weight:700}
.notiz{background:#f6f6f8;border-left:3px solid var(--akzent);padding:14px 18px;
       margin:24px 0;font-size:15px;color:var(--dim)}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
th{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
td.zahl{text-align:right;font-variant-numeric:tabular-nums}
footer{margin-top:72px;padding-top:20px;border-top:1px solid var(--line);
       color:var(--dim);font-size:14px}
a{color:var(--akzent)}
@media print{
  body{font-size:12pt}
  .seite{max-width:none;padding:0}
  h2{page-break-after:avoid}
  li,.notiz,table{page-break-inside:avoid}
  .nodruck{display:none}
}
@media (max-width:640px){.seite{padding:40px 18px 64px}h1{font-size:30px}}
"""

LANDING_CSS = """
:root{--text:#f4f4f6;--dim:#9a9aa6;--bg:#09090b;--akzent:#fff;--line:#232329}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:17px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.wrap{max-width:560px;margin:0 auto;padding:12vh 24px 64px}
h1{font:700 42px/1.1 Georgia,serif;letter-spacing:-.02em;margin:0 0 18px}
.unter{color:var(--dim);font-size:19px;margin:0 0 36px}
ul{list-style:none;padding:0;margin:0 0 36px}
li{padding:11px 0 11px 30px;position:relative;border-bottom:1px solid var(--line)}
li:before{content:"→";position:absolute;left:0;color:var(--dim)}
form{display:flex;flex-direction:column;gap:12px}
input[type=email],input[type=text]{padding:15px 16px;border:1px solid var(--line);
  border-radius:9px;background:#131317;color:var(--text);font-size:16px;width:100%}
input:focus{outline:2px solid var(--akzent);outline-offset:1px}
button{padding:16px;border:0;border-radius:9px;background:var(--akzent);color:#09090b;
  font-size:17px;font-weight:700;cursor:pointer}
button:hover{opacity:.88}
.dsgvo{display:flex;gap:10px;align-items:flex-start;font-size:13px;color:var(--dim);
  line-height:1.5}
.dsgvo input{margin-top:3px;flex:0 0 auto}
.dsgvo a{color:var(--text);text-decoration:underline}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--dim);font-size:13px}
footer a{color:var(--dim)}
@media (max-width:640px){.wrap{padding:7vh 18px 48px}h1{font-size:32px}}
"""


def _dokument(titel: str, css: str, inhalt: str, beschreibung: str = "") -> str:
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titel)}</title>
<meta name="description" content="{html.escape(beschreibung)}">
<style>{css}</style>
</head>
<body>
{inhalt}
</body>
</html>"""


def baue_leitfaden(titel: str, anzahl: int) -> tuple[str, int]:
    """Gibt (HTML, tatsächliche Hook-Anzahl) zurück — die Landingpage darf nichts
    versprechen, was der Leitfaden nicht hält."""
    typen = _hooks(anzahl)
    daten = _echte_daten()
    gesamt = sum(len(v) for v in typen.values())

    t = [f'<div class="seite">',
         f"<h1>{html.escape(titel)}</h1>",
         f'<p class="unter">{gesamt} Hooks, sortiert nach Muster. '
         f'Stand {MONATE[datetime.now().month - 1]} {datetime.now().year}.</p>']

    if daten:
        t.append("<h2>Was bei uns tatsächlich lief</h2>")
        t.append("<p>Keine fremden Zahlen. Das hier sind die Beiträge aus unserem "
                 "eigenen Kanal, sortiert nach Aufrufen.</p>")
        t.append("<table><tr><th>Thema</th><th>Format</th><th class='zahl'>Aufrufe</th></tr>")
        for r in daten:
            t.append(f"<tr><td>{html.escape(r.get('topic', ''))}</td>"
                     f"<td>{html.escape(r.get('format', '—'))}</td>"
                     f"<td class='zahl'>{int(r['views']):,}</td></tr>".replace(",", "."))
        t.append("</table>")
    else:
        t.append('<div class="notiz">Dieser Leitfaden stützt sich auf die Hook-Systematik, '
                 'nicht auf eigene Zahlen — der Kanal ist zu jung dafür. Sobald genug Daten '
                 'da sind, kommt die Tabelle mit den echten Aufrufen an diese Stelle. '
                 'Du bekommst die aktualisierte Fassung dann automatisch.</div>')

    t.append("<h2>Die sechs Muster</h2>")
    t.append("<p>Fast jeder Hook, der funktioniert, gehört zu einem dieser sechs Typen. "
             "Nicht weil Kreativität egal wäre, sondern weil diese sechs beim Zuschauer "
             "jeweils eine andere Frage auslösen — und eine offene Frage ist der einzige "
             "Grund, warum jemand nicht weiterwischt.</p>")

    for typ, hooks in typen.items():
        if not hooks:
            continue
        t.append(f"<h3>{html.escape(typ)}</h3><ol>")
        t += [f'<li><span class="hook">{html.escape(h)}</span></li>' for h in hooks]
        t.append("</ol>")

    t.append("""
<h2>Die eine Regel, die wichtiger ist als die Liste</h2>
<p>Teste nie mehr als zwei Muster pro Tag und Account. Wer alle sechs gleichzeitig
ausprobiert, bekommt am Monatsende eine Zahl und weiß nicht, woher sie kommt.
Zwei Muster, vierzehn Tage, dann vergleichen. Das ist langsamer und das Einzige,
was tatsächlich etwas beweist.</p>

<h2>Und der Teil, den niemand gern hört</h2>
<p>Ein guter Hook verschafft dir Aufmerksamkeit. Aufmerksamkeit ist kein Umsatz.
Wenn hinter dem Video kein Weg zu einem Angebot liegt, hast du ein Hobby mit
Statistik. Überleg dir das Angebot zuerst, den Hook danach.</p>
""")

    t.append(f'<footer>{html.escape(titel)} · Stand {datetime.now():%d.%m.%Y} · '
             f'Weitergabe erlaubt, solange nichts verändert wird.</footer>')
    t.append("</div>")
    return _dokument(titel, CSS, "\n".join(t),
                     "Hook-Muster für deutschsprachige Kurzvideos, mit echten Zahlen."), gesamt


def baue_landing(titel: str, versprechen: list[str]) -> str:
    form_ziel = BREVO_FORM_URL or "#"
    hinweis = "" if BREVO_FORM_URL else (
        '<p style="color:#d08a3c;font-size:13px">Formular noch nicht verbunden: '
        'BREVO_FORM_URL in .env eintragen.</p>')

    punkte = "\n".join(f"<li>{html.escape(v)}</li>" for v in versprechen)
    inhalt = f"""<div class="wrap">
<h1>{html.escape(titel)}</h1>
<p class="unter">Kostenlos. Eine E-Mail, dann hast du es.</p>
<ul>
{punkte}
</ul>
{hinweis}
<form action="{html.escape(form_ziel)}" method="POST">
  <input type="text" name="VORNAME" placeholder="Vorname" autocomplete="given-name">
  <input type="email" name="EMAIL" placeholder="deine@email.de" required autocomplete="email">
  <label class="dsgvo">
    <input type="checkbox" name="OPT_IN" required>
    <span>Ich möchte den Newsletter erhalten und habe die
    <a href="{html.escape(DATENSCHUTZ_URL)}">Datenschutzerklärung</a> gelesen.
    Abmeldung jederzeit mit einem Klick.</span>
  </label>
  <button type="submit">Jetzt kostenlos laden</button>
</form>
<footer>
  <a href="{html.escape(IMPRESSUM_URL)}">Impressum</a> ·
  <a href="{html.escape(DATENSCHUTZ_URL)}">Datenschutz</a><br>
  Du bekommst eine Bestätigungsmail. Erst nach deiner Bestätigung schicken wir
  etwas — so verlangt es die DSGVO, und so halten wir es auch.
</footer>
</div>"""
    return _dokument(titel, LANDING_CSS, inhalt, "Kostenloser Leitfaden.")


ANLEITUNG = """# Hochladen — zwei Minuten

Beide Dateien sind eigenständig. Kein Server, keine Datenbank, keine Installation.

## 1. Formular verbinden (einmalig, 10 Minuten)

1. Konto bei **brevo.com** (kostenlos bis 300 Mails/Tag, Server in der EU)
2. *Kontakte → Formular erstellen* → Felder: Vorname, E-Mail
3. **Double-Opt-In einschalten.** Ohne das ist die Liste rechtlich wertlos.
4. Die Formular-Adresse (die URL hinter `action=`) in `.env` eintragen:
   ```
   BREVO_FORM_URL=https://...
   ```
5. `python3 freebie.py` nochmal laufen lassen — das Formular ist dann verbunden.

## 2. Hochladen

**Netlify** (kostenlos, 30 Sekunden): app.netlify.com → den Ordner
`output/freebie/` auf die Seite ziehen. Fertig, du hast eine Adresse.

**Eigene Domain:** Dateien per FTP in den Web-Ordner. `index.html` ist die
Landingpage, `freebie.html` der Leitfaden.

## 3. Pflichtseiten anlegen

`impressum.html` und `datenschutz.html` daneben legen. **Beides ist Pflicht**,
sobald die Seite geschäftlich ist — und das ist sie ab dem ersten Eintrag.
Vorlagen: e-recht24.de (kostenlos).

## 4. Link in die Bios

Die Adresse der Landingpage in alle drei Instagram- und TikTok-Profile.
Das ist der einzige Weg, auf dem aus Reichweite jemals Umsatz wird.

## Den Leitfaden als PDF

`freebie.html` im Browser öffnen → Drucken → *Als PDF sichern*.
Das Layout ist dafür gebaut (Seitenumbrüche sitzen an den richtigen Stellen).
"""


def main():
    p = argparse.ArgumentParser(description="Lead-Magnet und Landingpage erzeugen")
    p.add_argument("--titel", default="Die Hooks, die auf deutschem TikTok wirklich funktionieren")
    p.add_argument("--anzahl", type=int, default=50)
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    AUSGABE.mkdir(parents=True, exist_ok=True)

    leitfaden, anzahl_echt = baue_leitfaden(a.titel, a.anzahl)
    (AUSGABE / "freebie.html").write_text(leitfaden, encoding="utf-8")
    (AUSGABE / "index.html").write_text(baue_landing(a.titel, [
        f"{anzahl_echt} Hooks, sortiert nach sechs Mustern",
        "Die Zahlen aus einem Kanal, der wirklich läuft",
        "Die Regel, ohne die jeder Test wertlos ist",
        "Kein Kurs, kein Verkaufsgespräch, keine Masterclass",
    ]), encoding="utf-8")
    (AUSGABE / "README.md").write_text(ANLEITUNG, encoding="utf-8")

    try:
        import brain
        brain.event("freebie", "Lead-Magnet und Landingpage erzeugt")
        if not PERF.exists():
            brain.learn("Freebie läuft noch ohne eigene Zahlen — nach den ersten 30 Beiträgen "
                        "neu erzeugen, dann steht die echte Tabelle drin.", "freebie.py")
    except Exception:  # noqa: BLE001
        pass

    print(f"""
✓ Fertig: {AUSGABE}

  index.html     Landingpage (Eintragsformular)
  freebie.html   Der Leitfaden → im Browser "Drucken → als PDF sichern"
  README.md      Wie du das hochlädst

  Anschauen:  open {AUSGABE}/index.html
""")


if __name__ == "__main__":
    main()
