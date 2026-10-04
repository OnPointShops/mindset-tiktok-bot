"""
Generiert Mindset/Motivation-Skripte per Claude API.
Nutzt den aktuellen Trend-Kontext (aus trend_research.py) damit die Hooks
nicht generisch, sondern an dem orientiert sind, was gerade zieht.
"""
import os
import json
import re
import random
import logging
import requests
from datetime import datetime
from anthropic import Anthropic

import config

logger = logging.getLogger("content_generator")

SYSTEM_PROMPT = """Du bist ein Ghostwriter für virale Mindset/Motivation-TikTok-Kanäle im \
deutschsprachigen Raum (Zielgruppe: 18-35, Ehrgeiz/Selbstoptimierung/Stoizismus-affin).

VIRALITÄTS-REGELN 2026 (datenbasiert, nicht verhandelbar):
- Algorithmus belohnt vor allem COMPLETION RATE (>=70% des Videos geschaut) und SHARES, \
NICHT Likes. Jeder Satz muss die Neugier auf den nächsten Satz offen halten - keine Lücke, \
in der jemand wegswipen würde.
- Die ersten 3 Sekunden entscheiden alles. Hook-Typen, die nachweislich performen: \
Contrarian-Take (Gegenteil der üblichen Meinung), Outcome-Promise (Ergebnis vorwegnehmen), \
Curiosity-Gap (bewusste Lücke, die erst später geschlossen wird). KEIN "Hey Leute", \
keine Begrüßungsfloskel.
- Roher, authentischer Ton schlägt nachweislich glatte Hochglanz-Sprache (Studien zeigen \
~30% höheres Engagement bei "raw" wirkendem Content). Lieber ein Satz, der wie eine echte \
Erkenntnis klingt, als ein polierter Werbespruch.
- Trending Sounds sind KEIN Viralitäts-Hebel mehr (unter 2% der viralen Clips nutzen sie) - \
nicht danach optimieren, die Stimme/Message trägt das Video.
- CTA soll einen "Tag jemanden, der das lesen muss"- oder Wiedererkennungs-Moment triggern \
(Share-Trigger), nicht nur plump nach Likes fragen.
- Der letzte Satz darf inhaltlich/emotional lose zum Hook zurückführen (Loop-Potenzial = \
Algorithmus-Bonus, da das Video beim Re-Watch weiterläuft statt neu zu starten).

KLISCHEE-VERBOT (diese/ähnliche Sätze sind verbrannt, NIE verwenden):
- "Der Unterschied zwischen Siegern und Verlierern ist..."
- "Niemand wird dich retten" / "Niemand kommt und rettet dich"
- "Du bist stärker als du denkst" / "Glaub an dich"
- "Erfolg ist eine Reise, keine Reise... äh Ziel" (und jede Variante davon)
- "Jeden Tag ein bisschen besser" / "1% besser jeden Tag" (ausgelutscht)
- irgendein Satz, der genauso gut unter JEDEM beliebigen Mindset-Video stehen könnte \
(der Test: wenn der Satz nicht erkennbar zu DIESEM Thema gehört, ist er zu generisch -> umschreiben)

TIEFE statt Plattitüde:
- Jeder Gedanke braucht ein KONKRETES Bild, eine Zahl, eine Situation oder einen Moment \
(keine abstrakten Behauptungen ohne Beleg). Schlecht: "Disziplin schlägt Motivation." \
Gut: "Motivation hält bis zum ersten Regentag. Disziplin steht trotzdem um 5 Uhr auf."
- Zeig eine Perspektive, die NICHT die naheliegendste ist (Contrarian-Take) oder eine, \
die im ersten Moment unangenehm/unbequem ist, bevor sie Sinn ergibt.
- Variiere Satzrhythmus bewusst: kurz-kurz-lang oder lang-kurz-kurz, nie drei gleich lange \
Sätze hintereinander (klingt sonst wie eine Liste, nicht wie eine Erkenntnis).

ARBEITSWEISE (nicht im Output zeigen, nur befolgen): Entwirf den Hook innerlich in 2 \
Varianten (einen Contrarian-Take, einen Curiosity-Gap), vergleiche beide gegen die \
Viralitäts-Regeln oben und das Klischee-Verbot, und gib NUR die stärkere Variante aus.

Regeln für jedes Skript:
- HOOK: max 8 Wörter, in den ersten 1.5 Sekunden muss der Zuschauer hängen bleiben. \
Nutze Muster wie direkte Ansprache, ein überraschendes Statement, oder eine unbequeme Wahrheit. \
Niemals "Hey Leute" oder ähnliche Floskeln.
- BODY: 4-6 kurze Sätze, sprechbar in 16-26 Sekunden, jeder Satz ist ein eigenständiger \
Gedanke (wichtig fürs Auto-Caption-Timing UND für die Bild-Wechsel, die am Satzende \
geschnitten werden). Direkte, klare Sprache, keine Füllwörter, mindestens EIN konkretes \
Bild/eine Szene (siehe TIEFE oben).
- CTA: eine Zeile, die zu Kommentar/Share/Follow anregt, ohne verzweifelt zu wirken.
- CAPTION: die Video-Beschreibung für TikTok (1-2 Sätze + relevante Frage an die Community)
- HASHTAGS: 5-6 Hashtags, Mix aus breit (#mindset #motivation) und spezifisch zum Thema

Beispiel für den geforderten Ton (Thema/Wortlaut NICHT kopieren, nur Stil/Tiefe als Maßstab):
Hook: "Die meisten geben genau einen Tag vor dem Durchbruch auf."
Body: "Du kennst nicht die Zahl der Versuche vor einem Erfolg. Du siehst nur den einen, \
der geklappt hat. Der Typ, der dich belächelt hat, hat beim fünften Rückschlag aufgehört. \
Du bist beim siebten noch da. Das ist der ganze Unterschied."

Gib AUSSCHLIESSLICH valides JSON zurück, keine Markdown-Codeblöcke, kein Fließtext davor/danach:
{
  "topic": "kurzes Thema-Label",
  "hook": "...",
  "body": "...",
  "cta": "...",
  "caption": "...",
  "hashtags": ["...", "..."],
  "format": "das verwendete Format-Label",
  "cover_slogan": "3-8 Wörter, wie von Hand auf eine Handfläche geschrieben: die Kernbotschaft als roher, zitierfähiger Slogan (darf zweiteilig sein, z.B. 'Sie sagen: Steh auf. Dann sehen sie dich fallen.'). Nicht identisch mit dem Hook, aber gleiche Aussage; keine Hashtags, keine Emojis.",
  "visual_queries": [
    "3-5 ENGLISCHE Suchwörter fürs Hintergrund-Stockvideo passend zum HOOK/Einstieg",
    "3-5 ENGLISCHE Suchwörter passend zur MITTE des BODY (der Kern-Gedanke)",
    "3-5 ENGLISCHE Suchwörter passend zum CTA/Ende (Auflösung, Aufstehen, Entschlossenheit)"
  ],
  "full_voiceover_text": "HOOK. BODY. CTA — als ein zusammenhängender, natürlich \
sprechbarer Text ohne Labels."
}

Für visual_queries IMMER: GRAFISCHE, kontraststarke Motive von MENSCHEN IN DER BEWEGUNG DES \
KAMPFS/AUFSTEHENS, die auch in Schwarz-Weiß stark wirken. Beispiele: 'man getting up after \
falling struggle', 'exhausted athlete standing up determination', 'person climbing out of pit \
effort', 'boxer rising after knockdown', 'man walking through smoke fire silhouette', 'runner \
collapsing pushing through pain', 'hands gripping ledge climbing up'. Die drei Queries sollen \
sich klar unterscheiden (nicht dreimal dasselbe Motiv) und zusammen einen kleinen Bogen \
erzählen: Fall/Kampf -> Anstrengung -> Aufstehen/Entschlossenheit. IMMER ein Mensch in echter \
körperlicher Anstrengung, NIE nur Landschaft oder Abstraktes. EMOTION ZUERST: Bevorzuge GESICHTER und Nahaufnahmen mit klarem Gefühl (tears crying face closeup, 
man face fear closeup, woman smiling relieved, people laughing joy, lonely man thinking window, exhausted 
face determination). Jede Query soll ein anderes GEFÜHL zeigen, passend zum Satz: Angst, Schmerz, Einsamkeit, 
Trotz, Erleichterung, Freude. KEINE TIERE in den Queries (kein dog, wolf, 
bird, horse, lion ...), außer das Thema verlangt ausdrücklich ein Tier. Immer 'man', 'woman' oder 'people' 
in die Query schreiben; Menschen in Straßen-/Urban-Szenen (Beton, Graffiti-Wände, Nacht, Stadt) sind ideal.
"""


# ── KI-Backend-Router ───────────────────────────────────────────────────────────
# "gemini"  → KOSTENLOS, KEINE Kreditkarte (Key: https://aistudio.google.com/apikey) [DEFAULT]
# "claude"  → Anthropic API (Cent-Beträge, Guthaben nötig)
# "offline" → kein Key, zieht aus content/script_bank.json (immer gratis, keine Recherche)
AI_BACKEND = os.getenv("AI_BACKEND", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
SCRIPT_BANK = config.CONTENT_DIR / "script_bank.json"

_gemini_model_cache = None


def _newest_flash(names):
    import re as _re
    def ver(n):
        m = _re.search(r"gemini-(\d+)\.?(\d*)-flash", n)
        return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
    flash = [n for n in names if "flash" in n and "thinking" not in n
             and "lite" not in n and "exp" not in n and "preview" not in n]
    return max(flash, key=ver) if flash else (names[0] if names else GEMINI_MODEL)


def _discover_model() -> str:
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         params={"key": GEMINI_API_KEY}, timeout=20)
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        return _newest_flash(names)
    except Exception:  # noqa: BLE001
        return GEMINI_MODEL


_avail_cache = None


def _gemini_available_models() -> list:
    """Echte, fuer DIESEN Key verfuegbare Flash-Modelle (neueste zuerst) - keine fest verdrahteten Namen mehr."""
    global _avail_cache
    if _avail_cache is not None:
        return _avail_cache
    import re as _re
    out = []
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         params={"key": GEMINI_API_KEY, "pageSize": 200}, timeout=20)
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]

        def ver(n):
            m = _re.search(r"gemini-(\d+)\.?(\d*)", n)
            return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
        flash = [n for n in names if "flash" in n and "thinking" not in n and "exp" not in n
                 and "image" not in n and "tts" not in n and "live" not in n and "audio" not in n]
        out = sorted(flash, key=lambda n: (ver(n), "lite" not in n), reverse=True)[:5]
    except Exception:  # noqa: BLE001
        pass
    _avail_cache = out
    logger.info("Gemini-Modelle fuer diesen Key: %s", ", ".join(out) or "(keine gefunden)")
    return out


def _gemini_pick_model() -> str:
    """Nimmt das in .env gesetzte Modell. Leer -> neuestes flash automatisch."""
    global _gemini_model_cache
    if _gemini_model_cache:
        return _gemini_model_cache
    _gemini_model_cache = GEMINI_MODEL or _discover_model()
    return _gemini_model_cache


def _gen_gemini(system: str, user: str, max_tokens: int = 700) -> str:
    global _gemini_model_cache
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY fehlt in .env")
    gen_cfg = {"temperature": 1.0, "maxOutputTokens": max(max_tokens, 2048),
               "thinkingConfig": {"thinkingBudget": 0}}  # Denkmodus aus -> volle Tokens fuer JSON

    def _parts_text(data):
        parts = data["candidates"][0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    import time
    primary = _gemini_pick_model()
    # Bei Ueberlastung (503/429) durch Modelle rotieren statt nur zu warten
    chain = [primary] + [m for m in _gemini_available_models() if m != primary]
    last_err = ""
    for attempt in range(8):
        model = chain[attempt % len(chain)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen_cfg}
        try:
            r = requests.post(url, params={"key": GEMINI_API_KEY}, json=body, timeout=60)
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(3)
            continue
        if r.status_code == 200:
            try:
                txt = _parts_text(r.json())
            except (KeyError, IndexError):
                txt = ""
            if txt.strip():
                return txt
            last_err = "leere Antwort"
            continue
        last_err = f"HTTP {r.status_code}: {r.text[:150]}"
        if r.status_code in (429, 500, 502, 503, 504):
            wait = min(3 * (attempt + 1), 15)
            logger.warning("Gemini %s ausgelastet (HTTP %s) -> naechstes Modell in %ds", model, r.status_code, wait)
            time.sleep(wait)
            continue
        if r.status_code == 404:
            logger.warning("Gemini-Modell '%s' nicht verfuegbar -> naechstes", model)
            continue
        if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in gen_cfg:
            gen_cfg.pop("thinkingConfig")
            continue
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:250]}")
    raise RuntimeError(f"Gemini nach 8 Versuchen nicht erreichbar ({last_err})")


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _gen_groq(system: str, user: str, max_tokens: int = 700) -> str:
    """Groq (KOSTENLOS, keine Kreditkarte, sehr schnell): Llama 3.3 70B als Reserve, wenn Gemini ausgelastet ist."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY fehlt in .env")
    import time
    last = ""
    for attempt in range(3):
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                          json={"model": GROQ_MODEL, "temperature": 0.9, "max_tokens": max(max_tokens, 2048),
                                "response_format": {"type": "json_object"},
                                "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]}, timeout=90)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        last = f"HTTP {r.status_code}: {r.text[:200]}"
        if r.status_code in (429, 500, 502, 503):
            time.sleep(5 * (attempt + 1))
            continue
        break
    raise RuntimeError(f"Groq {last}")


def _gen_claude(system: str, user: str, max_tokens: int = 700) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt in .env")
    resp = Anthropic(api_key=config.ANTHROPIC_API_KEY).messages.create(
        model="claude-sonnet-4-5", max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return resp.content[0].text


def generate_llm(system: str, user: str, max_tokens: int = 700) -> str:
    """Einheitlicher Text-Aufruf mit Fallback-Kette je nach AI_BACKEND."""
    order = {"gemini": ["gemini", "groq", "claude"], "claude": ["claude", "gemini", "groq"],
             "groq": ["groq", "gemini", "claude"]}.get(AI_BACKEND, [])
    last = None
    for b in order:
        try:
            if b == "gemini" and GEMINI_API_KEY:
                return _gen_gemini(system, user, max_tokens)
            if b == "groq" and GROQ_API_KEY:
                return _gen_groq(system, user, max_tokens)
            if b == "claude" and config.ANTHROPIC_API_KEY:
                return _gen_claude(system, user, max_tokens)
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning("KI-Backend %s fehlgeschlagen: %s", b, e)
    raise RuntimeError(f"Kein KI-Backend verfügbar (AI_BACKEND={AI_BACKEND}). Letzter Fehler: {last}")


def _offline_script(fmt: str, used_topics: set) -> dict:
    """Zieht ein unbenutztes Skript aus dem Offline-Vorrat (kein Key nötig)."""
    if not SCRIPT_BANK.exists():
        raise RuntimeError("Offline-Vorrat fehlt: content/script_bank.json")
    bank = json.loads(SCRIPT_BANK.read_text(encoding="utf-8"))
    pool = [s for s in bank if s.get("topic") not in used_topics]
    if not pool:
        pool = bank  # alle durch -> von vorn (nach genug Zeit ok)
    pref = [s for s in pool if s.get("format") == fmt]
    choice = dict(random.choice(pref or pool))
    choice["generated_at"] = datetime.now().isoformat()
    choice["source"] = "offline"
    return choice



def _client():
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt in .env — siehe .env.example")
    return Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _load_trends():
    if config.TRENDS_FILE.exists():
        return json.loads(config.TRENDS_FILE.read_text(encoding="utf-8"))
    return {"themes": [], "hook_styles": [], "updated": None}


def _extract_json(text: str) -> dict:
    """Robust gegen Markdown-Fences und Vor-/Nachtext: greift das groesste {...}-Objekt."""
    text = text.strip()
    text = re.sub(r"```(json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Kein JSON in der KI-Antwort gefunden")


def _load_strategy() -> dict:
    f = config.CONTENT_DIR / "strategy.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _history() -> list[dict]:
    if config.QUEUE_FILE.exists():
        return json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
    return []


def _pick_format(strategy: dict, history: list[dict]) -> str:
    """Wählt das Format, das am längsten nicht benutzt wurde (Vielseitigkeit)."""
    formats = strategy.get("formats") or [
        "Harte Wahrheit", "Mini-Story", "3 Regeln", "Mythos entlarven",
        "Stoiker-Zitat + Auslegung", "Früher-Ich vs. Jetzt-Ich", "Frage an den Zuschauer"]
    last_used = {f: -1 for f in formats}
    for i, h in enumerate(history):
        if h.get("format") in last_used:
            last_used[h["format"]] = i
    return min(formats, key=lambda f: last_used[f])


def _normalize_visual_queries(script: dict) -> dict:
    """Stellt sicher, dass visual_queries (Liste von 3) existiert — auch für alte
    Skripte aus dem Offline-Vorrat oder Cache, die noch das alte Einzelfeld
    visual_query haben."""
    vq = script.get("visual_queries")
    if isinstance(vq, list) and len(vq) >= 1:
        vq = [str(q) for q in vq if q][:8]
        while len(vq) < 3:
            vq.append(vq[-1])
        script["visual_queries"] = vq
        return script
    single = script.get("visual_query") or "person struggle rising determination"
    script["visual_queries"] = [single, single, single]
    return script


LONG_FORM_RULES = """
LANGFORM-MODUS (überschreibt die Längenvorgaben oben):
- BODY: 10-14 Sätze, sprechbar in 40-60 Sekunden. Baue einen echten Spannungsbogen:
  1) Unbequeme Ausgangslage/Schmerz  2) Eskalation: was es wirklich kostet  3) Wendepunkt/
  Erkenntnis (der Contrarian-Kern)  4) Konsequenz: was die wenigen anders machen  5) Auflösung.
- Halte die Spannung über die GANZE Länge: alle 2-3 Sätze ein neues Bild, eine neue Wendung
  oder ein Mini-Cliffhanger ("Aber das ist nicht das Schlimmste."). Keine Wiederholungen,
  kein Auffüllen - jede Zeile muss etwas Neues liefern.
- visual_queries: exakt 6 Einträge, die den Bogen Fall -> Kampf -> Tiefpunkt -> Aufstehen ->
  Weitergehen -> Entschlossenheit in sich klar unterscheidenden Motiven erzählen.
"""


def generate_script(theme_hint: str | None = None, length: str = "normal") -> dict:
    """Erzeugt ein einzelnes Skript. theme_hint optional, sonst wählt Claude aus Trends.
    length="long" -> 40-60s Langform mit Spannungsbogen und 6 Bildsegmenten."""
    trends = _load_trends()
    trend_context = ""
    if trends.get("themes"):
        trend_context = (
            "Aktuell gut performende Themen/Hook-Stile in dieser Nische:\n- "
            + "\n- ".join(trends["themes"][:8])
        )

    strategy = _load_strategy()
    history = _history()
    fmt = _pick_format(strategy, history)
    recent = [h.get("topic", "") for h in history[-25:]]
    strategy_ctx = ""
    if strategy.get("lessons"):
        strategy_ctx += "Erkenntnisse aus der täglichen Analyse:\n- " + "\n- ".join(strategy["lessons"][:8]) + "\n"
    if strategy.get("hook_patterns"):
        strategy_ctx += "Aktuell starke Hook-Muster:\n- " + "\n- ".join(strategy["hook_patterns"][:6]) + "\n"
    strategy_ctx += f"Nutze für dieses Skript das Format: {fmt}\n"
    if recent:
        strategy_ctx += "Diese Themen kamen zuletzt schon, wiederhole sie NICHT: " + "; ".join(recent) + "\n"

    user_prompt = f"""{trend_context}
{strategy_ctx}

{"Fokussiere dich auf dieses Thema: " + theme_hint if theme_hint else "Wähle ein Thema, das aktuell in der Mindset/Motivation-Nische zieht."}

Erstelle EIN neues Skript nach den Systemregeln. Sei konkret, keine generischen Plattitüden.
{LONG_FORM_RULES if length == "long" else ""}"""

    if AI_BACKEND == "offline":
        used = {h.get("topic") for h in history}
        return _normalize_visual_queries(_offline_script(fmt, used))

    try:
        raw = generate_llm(SYSTEM_PROMPT, user_prompt, max_tokens=2200 if length == "long" else 900)
        script = _extract_json(raw)
    except Exception as e:  # noqa: BLE001  (kein Key / Dienst weg -> Offline-Vorrat)
        logger.warning("KI nicht verfügbar (%s) -> Offline-Vorrat", e)
        used = {h.get("topic") for h in history}
        return _normalize_visual_queries(_offline_script(fmt, used))
    script["generated_at"] = datetime.now().isoformat()
    script.setdefault("format", fmt)
    return _normalize_visual_queries(script)


def generate_batch(n: int, save=True) -> list[dict]:
    """Generiert n Skripte für die Queue und speichert sie (dedupliziert nach Thema)."""
    scripts = []
    seen_topics = set()
    attempts = 0
    while len(scripts) < n and attempts < n * 3:
        attempts += 1
        try:
            s = generate_script()
        except Exception as e:
            logger.error("Script-Generierung fehlgeschlagen: %s", e)
            continue
        if s.get("topic") in seen_topics:
            continue
        seen_topics.add(s.get("topic"))
        scripts.append(s)
        logger.info("Skript generiert: %s", s.get("topic"))

    if save:
        existing = []
        if config.QUEUE_FILE.exists():
            existing = json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
        existing.extend(scripts)
        config.QUEUE_FILE.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return scripts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_batch(3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
