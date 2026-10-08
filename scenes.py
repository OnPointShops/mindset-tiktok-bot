"""
KI-Szenen: statt irgendwelcher Stock-Clips erzeugt der Bot zu JEDEM Textabschnitt eine passende,
filmische Szene (gleicher Protagonist, gleicher Look) und fährt mit der Kamera darüber (ffmpeg).

Ablauf: LLM plant 4-7 Einstellungen passend zum Sprechtext -> Bildgenerator (kostenlos, ohne Key:
Pollinations/Flux) -> ffmpeg_bg animiert Kamerafahrten + Film-Grading.
Jeder Fehler wirft eine Exception -> backgrounds.get_background() fällt auf Stock-Footage zurück.

.env:
  AI_SCENES=1              # 0 = aus (nur Stock-Footage)
  SCENE_LOOK=cinema        # cinema | streetart
  POLLINATIONS_TOKEN=      # optional, kostenlos auf auth.pollinations.ai (schneller, ohne Wasserzeichen)
"""
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

import config

logger = logging.getLogger("scenes")

SCENE_LOOK = os.getenv("SCENE_LOOK", "cinema")
POLLINATIONS_TOKEN = os.getenv("POLLINATIONS_TOKEN", "")

LOOKS = {
    "cinema": ("cinematic film still, 35mm anamorphic lens, dramatic chiaroscuro lighting, shallow depth of field, "
               "fine film grain, moody teal and orange color grade, photorealistic, emotional, vertical 9:16 "
               "composition, no text, no watermark, no logo"),
    "streetart": ("large street art mural on a gritty concrete wall, spray paint and stencil style like Banksy, "
                  "high contrast black white and red, dripping paint, urban night, vertical 9:16 composition, "
                  "no text, no watermark, no logo"),
}
MOVES = ["push", "pan_r", "pull", "pan_l", "push", "pan_r", "pull"]

PLAN_SYSTEM = """Du bist Kameramann und Regisseur für kurze, emotionale Mindset-Videos (TikTok, 9:16).
Aufgabe: Plane aus dem Sprechtext eine Folge von EXAKT {n} Einstellungen. Einstellung i gehört zum i-ten Abschnitt
des Textes (Text in {n} gleich lange Teile gedacht), zeigt GENAU das, worum es dort geht, und treibt eine kleine
Geschichte voran (Anfang -> Tiefpunkt -> Wendung -> Entschlossenheit).
Regeln:
- Ein durchgehender Protagonist: beschreibe ihn EINMAL im Feld "character" (Alter, Haar, Kleidung, 12-20 Wörter,
  englisch), er kommt in den meisten Einstellungen vor. Menschen und Gesichter mit klarem GEFÜHL, keine Tiere.
- Jede Einstellung "shot": englisch, 18-35 Wörter, konkret und bildhaft (Ort, Licht, Körperhaltung, Gesichtsausdruck,
  Kameraeinstellung wie close-up / medium shot / wide shot). Abwechslung in Nähe und Ort. Keine Schrift im Bild.
- Keine Gewalt, kein Blut, keine Waffen, keine bekannten realen Personen oder Figuren, keine Marken.
Antworte NUR mit JSON: {{"character": "...", "shots": ["...", ...]}}"""


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def plan_scenes(script: dict, n: int) -> list[str]:
    """LLM -> n fertige Bild-Prompts (Protagonist + Einstellung + Look)."""
    import content_generator
    text = script.get("full_voiceover_text") or " ".join(
        script.get(k, "") for k in ("hook", "body", "cta"))
    out = content_generator.generate_llm(
        PLAN_SYSTEM.format(n=n), f"Thema: {script.get('topic', '')}\n\nSprechtext:\n{text}", max_tokens=1400)
    data = _extract_json(out)
    shots = [str(s).strip() for s in data.get("shots", []) if str(s).strip()]
    if len(shots) < 2:
        raise RuntimeError("Szenenplan zu kurz")
    while len(shots) < n:
        shots.append(shots[-1])
    shots = shots[:n]
    char = str(data.get("character", "")).strip()
    look = LOOKS.get(SCENE_LOOK, LOOKS["cinema"])
    return [f"{s}. Protagonist: {char}. {look}"[:900] for s in shots]


_last_request = [0.0]


def _generate_image(prompt: str, out_path: str, seed: int) -> str:
    """Pollinations (Flux). Anonym: ca. 1 Bild / 15 s -> Abstand halten, bei Fehlern erneut versuchen."""
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
    params = {"width": 720, "height": 1280, "model": "flux", "seed": seed, "nologo": "true", "enhance": "false"}
    headers = {}
    if POLLINATIONS_TOKEN:
        params["token"] = POLLINATIONS_TOKEN
        headers["Authorization"] = f"Bearer {POLLINATIONS_TOKEN}"
    gap = 4 if POLLINATIONS_TOKEN else 16
    last = ""
    for attempt in range(4):
        wait = gap - (time.time() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.time()
        try:
            r = requests.get(url, params=params, headers=headers, timeout=150)
        except requests.RequestException as e:
            last = str(e)
            continue
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image") and len(r.content) > 20000:
            Path(out_path).write_bytes(r.content)
            return out_path
        last = f"HTTP {r.status_code} {ctype} {len(r.content)}B"
        params["seed"] = seed + attempt + 1  # anderer Seed hilft bei hängenden Anfragen
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Bildgenerator: {last}")


def build_parts(script: dict, duration: float) -> list[dict]:
    """Gibt ffmpeg-Teile [{path, dur, image, move}] zurück (oder wirft eine Exception)."""
    n = max(4, min(7, round(duration / 4.5)))
    prompts = plan_scenes(script, n)
    seed0 = abs(hash(script.get("topic", "") + script.get("hook", ""))) % 100000
    paths = []
    for i, p in enumerate(prompts):
        out = str(config.VIDEO_DIR / f"_scene_{i}.jpg")
        try:
            paths.append(_generate_image(p, out, seed0 + i))
            logger.info("Szene %d/%d erzeugt", i + 1, n)
        except Exception as e:  # noqa: BLE001
            logger.warning("Szene %d/%d fehlgeschlagen: %s", i + 1, n, e)
            paths.append(None)
    ok = [p for p in paths if p]
    if len(ok) < 2:
        raise RuntimeError("zu wenige Szenen erzeugt")
    paths = [p or ok[min(i, len(ok) - 1)] for i, p in enumerate(paths)]
    each = duration / n
    return [{"path": p, "dur": each, "image": True, "move": MOVES[i % len(MOVES)]} for i, p in enumerate(paths)]
