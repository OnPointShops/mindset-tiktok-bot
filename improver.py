"""
Tägliche Selbstverbesserung: Claude recherchiert per Web-Suche, was in der
deutschen Mindset/Motivation-Nische auf TikTok aktuell funktioniert, wertet die
eigene Historie aus (Formate, Wiederholungen, Fehler, optional Views aus
content/performance.csv) und schreibt content/strategy.json.
content_generator.py liest diese Datei bei jedem Skript.
Kosten: wenige Cent pro Tag.
"""
import csv
import json
import logging
import re
from collections import Counter
from datetime import datetime

from anthropic import Anthropic

import config
import content_generator

logger = logging.getLogger("improver")
STRATEGY_FILE = config.CONTENT_DIR / "strategy.json"
PERF_FILE = config.CONTENT_DIR / "performance.csv"  # Spalten: topic,format,views,likes,comments,shares


def _history():
    if config.QUEUE_FILE.exists():
        return json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
    return []


def _performance():
    if not PERF_FILE.exists():
        return []
    with PERF_FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _summary():
    h = _history()
    posted = [x for x in h if x.get("status") == "posted"]
    return {
        "gepostet_gesamt": len(posted),
        "fehlgeschlagen": len([x for x in h if x.get("status") in ("error", "failed")]),
        "formate_verteilung": dict(Counter(x.get("format", "?") for x in posted)),
        "letzte_themen": [x.get("topic") for x in h[-20:]],
        "performance_daten": _performance()[-30:],
    }


PROMPT = """Du bist Growth-Stratege für einen automatisierten, deutschsprachigen \
Mindset/Motivation-TikTok-Kanal (Voiceover + Stock-Footage + Untertitel, 1 Video/Tag).

Recherchiere per Web-Suche AKTUELL (Datum: {today}):
1. Welche Hook-Muster, Themen und Formate funktionieren gerade in der DE/EN Mindset-Nische auf TikTok?
2. Aktuelle TikTok-Regeln/Änderungen, die den Kanal betreffen (AI-Content-Kennzeichnung, \
Creator Rewards Program Voraussetzungen, Reichweiten-Faktoren wie Watchtime/Videolänge).
3. Was steigert Vielseitigkeit und Wiedererkennung ohne Wiederholung?

Eigene Kanal-Daten:
{summary}

Wenn performance_daten vorhanden sind: leite daraus konkrete Lehren ab (welches Format/Thema lief besser).
Wenn nicht: sag das offen in "lessons" und stütze dich auf die Recherche.

Antworte AUSSCHLIESSLICH mit JSON:
{{
 "formats": ["7-9 Format-Labels, abwechslungsreich"],
 "hook_patterns": ["5-8 konkrete Hook-Muster mit Beispiel"],
 "lessons": ["5-8 konkrete, umsetzbare Erkenntnisse"],
 "rule_alerts": ["Regeländerungen/Risiken die Kai wissen muss, sonst leer"],
 "best_post_times": ["z.B. 18:30, 12:15"],
 "experiment_of_the_day": "EIN Experiment für morgen (z.B. andere Videolänge, anderer Hook-Typ)",
 "sources": ["URLs"]
}}"""


def _gemini_with_search(prompt: str) -> str:
    """Gemini mit Google-Suche-Grounding (kostenlos, kein Card). Fällt auf Gemini ohne Suche zurück."""
    import requests
    key = content_generator.GEMINI_API_KEY
    model = content_generator._gemini_pick_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    base = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 2500}}
    for body in ({**base, "tools": [{"google_search": {}}]}, base):  # erst mit Suche, dann ohne
        r = requests.post(url, params={"key": key}, json=body, timeout=90)
        if r.status_code == 200:
            cand = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in cand)
        logger.warning("Gemini-Recherche HTTP %s: %s", r.status_code, r.text[:150])
    raise RuntimeError("Gemini-Recherche fehlgeschlagen")


def run_improver():
    prompt = PROMPT.format(today=datetime.now().strftime("%d.%m.%Y"),
                           summary=json.dumps(_summary(), ensure_ascii=False))
    if content_generator.GEMINI_API_KEY:
        text = _gemini_with_search(prompt)
    elif config.ANTHROPIC_API_KEY:
        resp = Anthropic(api_key=config.ANTHROPIC_API_KEY).messages.create(
            model="claude-sonnet-4-5", max_tokens=2500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    else:
        raise RuntimeError("Weder GEMINI_API_KEY noch ANTHROPIC_API_KEY gesetzt")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise RuntimeError("Improver lieferte kein JSON")
    data = json.loads(m.group(0))
    data["updated"] = datetime.now().isoformat()
    STRATEGY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Strategie aktualisiert (%d Lehren, %d Formate)",
                len(data.get("lessons", [])), len(data.get("formats", [])))
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(run_improver(), ensure_ascii=False, indent=2))
