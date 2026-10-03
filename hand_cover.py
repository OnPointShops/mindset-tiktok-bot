"""
Cover im "Slogan auf der Hand"-Stil: Schwarz-Weiß-Foto einer offenen Handfläche, der Slogan
des Videos steht wie mit Edding auf die Haut geschrieben.

Ablauf (alles kostenlos, keine Kreditkarte):
  1. Hand-Foto von Pixabay (gleicher Key wie die Hintergrundvideos), auf 1080x1920 gecroppt
  2. Gemini-Vision (gleicher Gratis-Key wie die Skripte) sagt, WO die Handfläche liegt und wie
     sie gedreht ist -> Schrift sitzt auf der Handfläche statt irgendwo im Bild
     (ohne Gemini-Key/bei Fehler: sinnvolle Standardposition)
  3. Slogan in Marker-Handschrift (assets/fonts/PermanentMarker-Regular.ttf), leicht schief
     pro Zeile, der Handwölbung folgend, per Multiply-Blend -> Tinte liegt IN der Haut
  4. S/W-Grading + Vignette + Korn wie der Rest des Kanals

Jeder Fehler wirft eine Exception -> cover.make_cover() fällt dann auf das prozedurale Cover zurück.
"""
import base64
import io
import json
import logging
import os
import random
import re
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import backgrounds
import config

logger = logging.getLogger("hand_cover")

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "PermanentMarker-Regular.ttf"
MAC_MARKER_FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Marker Felt.ttc",
    "/System/Library/Fonts/MarkerFelt.ttc",
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
]
HAND_QUERIES = ["open hand palm", "hand palm stop", "palm of hand", "raised hand palm", "hand fingers spread"]
INK = (22, 20, 18)
DEFAULT_PALM = {"cx": 0.50, "cy": 0.60, "w": 0.56, "angle": -12.0}


def _marker_font(size: int):
    for f in [str(FONT_PATH), *MAC_MARKER_FALLBACKS]:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    import cover
    return cover.find_font(size)  # Notfall: Impact/Arial -> sieht nicht handgeschrieben aus, aber läuft


# ── 1. Foto ──────────────────────────────────────────────────────────────────────────────

def _fetch_candidates(n: int = 5) -> list[str]:
    """Lädt bis zu n verschiedene Hand-Fotos (Hochformat bevorzugt, Graustufen bevorzugt)."""
    key = backgrounds.PIXABAY_API_KEY
    if not key:
        raise RuntimeError("PIXABAY_API_KEY fehlt (Hand-Foto-Quelle)")
    paths: list[str] = []
    queries = HAND_QUERIES[:]
    random.shuffle(queries)
    for q in queries:
        for colors in ("grayscale", None):
            params = {"key": key, "q": q, "per_page": 30, "image_type": "photo",
                      "orientation": "vertical", "safesearch": "true", "order": "popular"}
            if colors:
                params["colors"] = colors
            try:
                r = requests.get("https://pixabay.com/api/", params=params, timeout=20)
                r.raise_for_status()
                hits = r.json().get("hits", [])
            except Exception as e:  # noqa: BLE001
                logger.warning("Pixabay-Suche '%s' fehlgeschlagen: %s", q, e)
                continue
            random.shuffle(hits)
            for hit in hits:
                if hit.get("imageHeight", 0) < 1200:
                    continue
                url = hit.get("largeImageURL") or hit.get("webformatURL")
                pth = str(config.VIDEO_DIR / f"_hand_{len(paths)}.jpg")
                try:
                    Path(pth).write_bytes(requests.get(url, timeout=60).content)
                    paths.append(pth)
                except Exception:  # noqa: BLE001
                    continue
                if len(paths) >= n:
                    return paths
    if not paths:
        raise RuntimeError("Kein Hand-Foto gefunden")
    return paths


def _crop_to_canvas(img: Image.Image) -> Image.Image:
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    img = img.convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


# ── 2. Handfläche finden ─────────────────────────────────────────────────────────────────

def _locate_palm(img: Image.Image):
    """Gemini-Vision: Handflächen-Mittelpunkt, nutzbare Breite, Schreibwinkel.
    Gibt dict zurück, None wenn keine Handfläche sichtbar, DEFAULT_PALM wenn kein Key/Fehler."""
    import content_generator as cg
    if not cg.GEMINI_API_KEY:
        logger.info("Kein GEMINI_API_KEY -> Standard-Position für den Slogan")
        return dict(DEFAULT_PALM)
    small = img.copy()
    small.thumbnail((640, 640))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    prompt = (
        "Look at this photo. Is the PALM (inner side, the flat skin area) of a human hand clearly "
        "visible and facing the camera? If yes, tell me where a handwritten marker slogan would "
        "fit on that palm. Reply ONLY with JSON: "
        '{"found": true/false, "cx": 0-1 palm-center x as fraction of image width, '
        '"cy": 0-1 palm-center y as fraction of image height, '
        '"w": 0-1 width of the writable flat palm area as fraction of image width, '
        '"angle": rotation of the text baseline in degrees along the palm orientation '
        "(0 = horizontal, negative = rising to the right, positive = falling to the right, "
        "range -45..45)}"
    )
    body = {"contents": [{"role": "user", "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg",
                                 "data": base64.b64encode(buf.getvalue()).decode()}}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300,
                                 "responseMimeType": "application/json",
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cg._gemini_pick_model()}:generateContent"
    try:
        r = requests.post(url, params={"key": cg.GEMINI_API_KEY}, json=body, timeout=60)
        if r.status_code == 400 and "thinking" in r.text.lower():
            body["generationConfig"].pop("thinkingConfig")
            r = requests.post(url, params={"key": cg.GEMINI_API_KEY}, json=body, timeout=60)
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"].get("parts", [])
        data = json.loads(re.search(r"\{.*\}", "".join(p.get("text", "") for p in parts), re.S).group(0))
    except Exception as e:  # noqa: BLE001
        logger.warning("Handflächen-Erkennung fehlgeschlagen (%s) -> Standard-Position", e)
        return dict(DEFAULT_PALM)
    if not data.get("found"):
        return None
    try:
        return {"cx": min(max(float(data["cx"]), 0.2), 0.8),
                "cy": min(max(float(data["cy"]), 0.25), 0.8),
                "w": min(max(float(data["w"]), 0.30), 0.75),
                "angle": min(max(float(data.get("angle", -12)), -45), 45)}
    except (KeyError, TypeError, ValueError):
        return dict(DEFAULT_PALM)


# ── 3. Handschrift aufs Foto ─────────────────────────────────────────────────────────────

def _wrap_fit(text: str, area_w: int, area_h: int):
    """Größte Schriftgröße, bei der der umbrochene Slogan in die Handfläche passt."""
    probe = ImageDraw.Draw(Image.new("L", (10, 10)))
    words = text.upper().split()
    for size in range(170, 40, -6):
        font = _marker_font(size)
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if probe.textlength(trial, font=font) <= area_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= 6 and len(lines) * size * 1.0 <= area_h and \
                max(probe.textlength(ln, font=font) for ln in lines) <= area_w * 1.02:
            return font, size, lines
    font = _marker_font(44)
    return font, 44, [text.upper()]


def _ink_layer(text: str, palm: dict, seed: int) -> np.ndarray:
    """Float-Alpha (H,W) in Canvas-Größe: der handgeschriebene Slogan an der Handflächen-Position."""
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    rng = random.Random(seed)
    area_w = int(palm["w"] * W)
    area_h = int(area_w * 1.35)
    font, size, lines = _wrap_fit(text, area_w, area_h)

    pad = int(size * 0.6)
    bw, bh = area_w + 2 * pad, int(len(lines) * size * 1.05) + 2 * pad
    block = Image.new("L", (bw, bh), 0)
    for i, ln in enumerate(lines):
        lw = int(ImageDraw.Draw(block).textlength(ln, font=font)) + 2 * pad
        line_img = Image.new("L", (lw, int(size * 1.7)), 0)
        ImageDraw.Draw(line_img).text((pad, int(size * 0.15)), ln, font=font, fill=255)
        line_img = line_img.rotate(rng.uniform(-3.0, 3.0), resample=Image.BICUBIC, expand=True)
        x = (bw - line_img.width) // 2 + rng.randint(-int(size * 0.18), int(size * 0.18))
        y = pad + int(i * size * 1.05) - int(size * 0.2)
        block.paste(255, (x, y), line_img)  # additiv genug: Linien dürfen sich leicht berühren

    # Handwölbung: Zeilen verlaufen leicht wellig statt kerzengerade
    arr = np.asarray(block, dtype=np.float32) / 255.0
    amp = size * 0.08
    shift = (np.sin(np.linspace(0, np.pi, arr.shape[1])) * amp).astype(int)
    warped = np.zeros_like(arr)
    for x in range(arr.shape[1]):
        warped[:, x] = np.roll(arr[:, x], shift[x])
    block = Image.fromarray((warped * 255).astype(np.uint8))

    block = block.rotate(-palm["angle"], resample=Image.BICUBIC, expand=True)
    block = block.filter(ImageFilter.GaussianBlur(1.3))  # Edding-Ränder laufen leicht in die Haut

    layer = Image.new("L", (W, H), 0)
    px = int(palm["cx"] * W - block.width / 2)
    py = int(palm["cy"] * H - block.height / 2)
    layer.paste(block, (px, py))
    alpha = np.asarray(layer, dtype=np.float32) / 255.0
    # Tinte nicht perfekt deckend: leichte Körnung/Schwankung wie echte Stiftspur auf Haut
    noise = np.random.default_rng(seed).uniform(0.86, 1.0, alpha.shape).astype(np.float32)
    return np.clip(alpha * 1.35 * noise, 0, 1)  # Faktor >1: Ränder bleiben weich, Strichkern wird satt schwarz


def make_hand_cover(script: dict, out_path: str, photo_path: str | None = None,
                    palm: dict | None = None) -> str:
    """Erzeugt das Hand-Cover. photo_path/palm nur für Tests (sonst Pixabay + Gemini)."""
    slogan = (script.get("cover_slogan") or script.get("hook") or script.get("topic") or "").strip()
    if not slogan:
        raise RuntimeError("Kein Slogan für das Cover")
    seed = abs(hash(slogan)) % (2 ** 31)

    base, found = None, None
    if photo_path:
        base, found = _crop_to_canvas(Image.open(photo_path)), palm or dict(DEFAULT_PALM)
    else:
        for pth in _fetch_candidates():
            cand = _crop_to_canvas(Image.open(pth))
            loc = _locate_palm(cand)
            if loc:
                base, found = cand, loc
                break
            logger.info("Foto %s zeigt keine Handfläche -> nächstes", pth)
        if base is None:
            raise RuntimeError("Keins der Hand-Fotos zeigt eine freie Handfläche")

    frame = backgrounds._bw_grade_frame(np.asarray(base)).astype(np.float32)
    alpha = _ink_layer(slogan, found, seed)[..., None]
    ink = np.array(INK, dtype=np.float32) / 255.0
    frame = frame * (1.0 - alpha * (1.0 - ink))  # Multiply: dunkle Tinte, Hautstruktur scheint durch

    # leichte Vignette + Korn wie der Rest des Kanals
    H, W = frame.shape[:2]
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = 1.0 - np.clip((((xs / W - 0.5) * 1.5) ** 2 + ((ys / H - 0.5) * 1.3) ** 2) * 0.55, 0, 0.55)
    frame *= vig[..., None]
    grain = np.random.default_rng(seed + 1).normal(0, 6.0, (H, W, 1)).astype(np.float32)
    frame = np.clip(frame + grain, 0, 255).astype(np.uint8)
    Image.fromarray(frame).save(out_path)

    for f in config.VIDEO_DIR.glob("_hand_*.jpg"):
        f.unlink(missing_ok=True)
    logger.info("Hand-Cover: '%s' -> %s", slogan, out_path)
    return out_path
