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

Regeln für jedes Skript:
- HOOK: max 8 Wörter, in den ersten 1.5 Sekunden muss der Zuschauer hängen bleiben. \
Nutze Muster wie direkte Ansprache, ein überraschendes Statement, oder eine unbequeme Wahrheit. \
Niemals "Hey Leute" oder ähnliche Floskeln.
- BODY: 3-5 kurze Sätze, sprechbar in 12-20 Sekunden, jeder Satz ist ein eigenständiger \
Gedanke (wichtig fürs Auto-Caption-Timing). Direkte, klare Sprache, keine Füllwörter.
- CTA: eine Zeile, die zu Kommentar/Share/Follow anregt, ohne verzweifelt zu wirken.
- CAPTION: die Video-Beschreibung für TikTok (1-2 Sätze + relevante Frage an die Community)
- HASHTAGS: 5-6 Hashtags, Mix aus breit (#mindset #motivation) und spezifisch zum Thema

Gib AUSSCHLIESSLICH valides JSON zurück, keine Markdown-Codeblöcke, kein Fließtext davor/danach:
{
  "topic": "kurzes Thema-Label",
  "hook": "...",
  "body": "...",
  "cta": "...",
  "caption": "...",
  "hashtags": ["...", "..."],
  "format": "das verwendete Format-Label",
  "visual_query": "3-5 ENGLISCHE Suchwörter fürs Hintergrund-Stockvideo: GRAFISCHE, kontraststarke Motive, die auch in Schwarz-Weiß stark wirken (Silhouette, raue Textur, Grossstadt-Beton, Bewegung). Beispiele: 'man walking away silhouette alone', 'boxer wrapping hands gym', 'urban concrete wall texture gritty', 'lone figure city street night', 'storm ocean waves dramatic silhouette'. KEINE abstrakten Begriffe, immer ein konkretes Motiv mit roher, kämpferischer Stimmung.",
  "full_voiceover_text": "HOOK. BODY. CTA — als ein zusammenhängender, natürlich \
sprechbarer Text ohne Labels."
}
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

    for attempt in range(4):
        model = _gemini_pick_model()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen_cfg}
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=body, timeout=60)
        if r.status_code == 200:
            return _parts_text(r.json())
        if r.status_code in (429, 503) and attempt < 2:  # kurze Ueberlastung -> warten, neu
            import time
            wait = 4 * (attempt + 1)
            logger.warning("Gemini ausgelastet (HTTP %s) -> warte %ds und versuche erneut", r.status_code, wait)
            time.sleep(wait)
            continue
        if r.status_code == 404 and attempt < 2:
            logger.warning("Gemini-Modell '%s' nicht verfügbar -> suche aktuelles", model)
            _gemini_model_cache = _discover_model()
            continue
        if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in gen_cfg:
            gen_cfg.pop("thinkingConfig")  # Modell erlaubt kein Abschalten -> ohne neu
            continue
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:250]}")


def _gen_claude(system: str, user: str, max_tokens: int = 700) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt in .env")
    resp = Anthropic(api_key=config.ANTHROPIC_API_KEY).messages.create(
        model="claude-sonnet-4-5", max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}])
    return resp.content[0].text


def generate_llm(system: str, user: str, max_tokens: int = 700) -> str:
    """Einheitlicher Text-Aufruf mit Fallback-Kette je nach AI_BACKEND."""
    order = {"gemini": ["gemini", "claude"], "claude": ["claude", "gemini"]}.get(AI_BACKEND, [])
    last = None
    for b in order:
        try:
            if b == "gemini" and GEMINI_API_KEY:
                return _gen_gemini(system, user, max_tokens)
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


def generate_script(theme_hint: str | None = None) -> dict:
    """Erzeugt ein einzelnes Skript. theme_hint optional, sonst wählt Claude aus Trends."""
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

Erstelle EIN neues Skript nach den Systemregeln. Sei konkret, keine generischen Plattitüden."""

    if AI_BACKEND == "offline":
        used = {h.get("topic") for h in history}
        return _offline_script(fmt, used)

    try:
        raw = generate_llm(SYSTEM_PROMPT, user_prompt, max_tokens=700)
        script = _extract_json(raw)
    except Exception as e:  # noqa: BLE001  (kein Key / Dienst weg -> Offline-Vorrat)
        logger.warning("KI nicht verfügbar (%s) -> Offline-Vorrat", e)
        used = {h.get("topic") for h in history}
        return _offline_script(fmt, used)
    script["generated_at"] = datetime.now().isoformat()
    script.setdefault("format", fmt)
    return script


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
