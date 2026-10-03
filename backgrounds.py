"""
Hintergründe für die Videos. Reihenfolge bei BG_PROVIDER=auto:
  1. Pexels   (nur wenn PEXELS_API_KEY gesetzt — Vergabe neuer Keys ist aktuell ausgesetzt)
  2. Pixabay  (nur wenn PIXABAY_API_KEY gesetzt, kostenlos: https://pixabay.com/api/docs/)
  3. Prozedural: animierter Cinematic-Hintergrund (Farbverlauf + schwebende Lichtpunkte),
     braucht KEINEN Key, keinen Download, funktioniert immer.
"""
import hashlib
import logging
import os
import random
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from moviepy import VideoClip, VideoFileClip, concatenate_videoclips

import config

logger = logging.getLogger("backgrounds")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
BG_PROVIDER = os.getenv("BG_PROVIDER", "auto")  # auto | procedural | pexels | pixabay

# (oben, unten, Lichtfarbe) – dunkel & edel, damit weiße/gelbe Schrift immer lesbar bleibt
PALETTES = [
    ((8, 14, 32), (18, 70, 96), (120, 220, 255)),    # Nachtblau -> Petrol
    ((14, 8, 10), (92, 18, 30), (255, 120, 110)),    # Schwarz -> Weinrot
    ((10, 10, 14), (60, 52, 22), (255, 210, 120)),   # Anthrazit -> Gold
    ((6, 16, 18), (14, 74, 62), (120, 255, 200)),    # Tiefgrün
    ((14, 8, 28), (66, 32, 104), (200, 150, 255)),   # Violett
]


def _procedural(duration: float, seed_text: str) -> VideoClip:
    seed = int(hashlib.md5(seed_text.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    top, bot, glow = (np.array(c, dtype=np.float32) for c in PALETTES[seed % len(PALETTES)])
    W, H = 270, 480  # klein rechnen, hochskalieren -> weicher Look + schnell
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    xs /= W
    ys /= H
    n = 22
    px, py = rng.random(n), rng.random(n)
    rad = rng.uniform(0.03, 0.10, n)
    speed = rng.uniform(0.01, 0.045, n)
    phase = rng.uniform(0, 6.28, n)
    inten = rng.uniform(0.25, 0.75, n)
    vign = 1.0 - 0.55 * (((xs - 0.5) * 1.6) ** 2 + ((ys - 0.5) * 1.1) ** 2)
    vign = np.clip(vign, 0.25, 1.0)[..., None]

    def make_frame(t):
        k = 0.5 + 0.5 * np.sin(t * 0.35)  # Verlauf "atmet" langsam
        grad = top + (bot - top) * (ys[..., None] * (0.75 + 0.5 * k))
        img = grad.copy()
        light = np.zeros((H, W), np.float32)
        for i in range(n):
            cx = (px[i] + 0.04 * np.sin(t * 0.4 + phase[i])) % 1.0
            cy = (py[i] - speed[i] * t) % 1.15 - 0.075  # driftet nach oben
            d2 = (xs - cx) ** 2 + (ys - cy) ** 2
            flick = 0.7 + 0.3 * np.sin(t * 1.3 + phase[i])
            light += inten[i] * flick * np.exp(-d2 / (rad[i] ** 2))
        img += light[..., None] * glow * 0.55
        img *= vign
        frame = np.clip(img, 0, 255).astype(np.uint8)
        big = Image.fromarray(frame).resize((config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.BILINEAR)
        return np.asarray(big)

    return VideoClip(make_frame, duration=duration)


_OVERLAY_CACHE = None


def _cinematic_overlay(clip, duration):
    """Dunkle Vignette + Verlauf unten -> emotionaler Look + Text bleibt lesbar."""
    global _OVERLAY_CACHE
    import numpy as np
    from PIL import Image
    from moviepy import ImageClip
    if _OVERLAY_CACHE is None:
        W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        # Vignette (Raender dunkler)
        vig = (((xs / W - 0.5) * 1.5) ** 2 + ((ys / H - 0.5) * 1.3) ** 2)
        vig = np.clip(vig * 0.8, 0, 0.72)
        # Verlauf unten (wo die Untertitel sitzen) + leicht oben (Hook)
        bottom = np.clip((ys / H - 0.5) / 0.5, 0, 1) ** 1.5 * 0.55
        top = np.clip((0.28 - ys / H) / 0.28, 0, 1) * 0.35
        alpha = np.clip(vig + bottom + top, 0, 0.82)
        rgba = np.zeros((H, W, 4), np.uint8)
        rgba[..., 3] = (alpha * 255).astype(np.uint8)  # schwarz mit variabler Deckkraft
        _OVERLAY_CACHE = rgba
    ov = ImageClip(_OVERLAY_CACHE).with_duration(duration)
    from moviepy import CompositeVideoClip
    return CompositeVideoClip([clip, ov], size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))



def _fit(clip: VideoFileClip, duration: float):
    """Auf 1080x1920 croppen und auf Länge loopen/trimmen."""
    target = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
    if clip.w / clip.h > target:
        clip = clip.resized(height=config.VIDEO_HEIGHT)
        clip = clip.cropped(x_center=clip.w / 2, width=config.VIDEO_WIDTH)
    else:
        clip = clip.resized(width=config.VIDEO_WIDTH)
        clip = clip.cropped(y_center=clip.h / 2, height=config.VIDEO_HEIGHT)
    if clip.duration < duration:
        clip = concatenate_videoclips([clip] * (int(duration // clip.duration) + 1))
    return clip.subclipped(0, duration)


def _download(url: str, name: str) -> str:
    path = str(config.VIDEO_DIR / f"_bg_{name}.mp4")
    Path(path).write_bytes(requests.get(url, timeout=90).content)
    return path


def _pexels(query, duration):
    r = requests.get("https://api.pexels.com/videos/search",
                     headers={"Authorization": config.PEXELS_API_KEY},
                     params={"query": query, "orientation": "portrait", "per_page": 15}, timeout=20)
    r.raise_for_status()
    vids = r.json().get("videos", [])
    if not vids:
        raise RuntimeError("Pexels: nichts gefunden")
    v = random.choice(vids[:10])
    files = sorted([f for f in v["video_files"] if f["width"] <= 1080], key=lambda f: f["width"], reverse=True)
    return _download((files or v["video_files"])[0]["link"], "pexels")


def _pixabay_clips(query, n=3):
    """Lädt bis zu n verschiedene Pixabay-Videos (Liste lokaler Pfade), beste Auflösung zuerst."""
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": PIXABAY_API_KEY, "q": query, "per_page": 30,
                             "safesearch": "true", "order": "popular"}, timeout=20)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        raise RuntimeError("Pixabay: nichts gefunden")
    random.shuffle(hits)
    paths = []
    for i, hit in enumerate(hits):
        if len(paths) >= n:
            break
        v = hit["videos"]
        f = v.get("large") or v.get("medium") or v.get("small")
        if not f:
            continue
        try:
            paths.append(_download(f["url"], f"pixabay_{i}"))
        except Exception:  # noqa: BLE001
            continue
    if not paths:
        raise RuntimeError("Pixabay: kein Clip ladbar")
    return paths


def _pixabay_images(query, n=3):
    """Fallback: Pixabay-Fotos (Liste lokaler Pfade) für Ken-Burns-Hintergrund."""
    r = requests.get("https://pixabay.com/api/",
                     params={"key": PIXABAY_API_KEY, "q": query, "per_page": 30,
                             "image_type": "photo", "orientation": "vertical",
                             "safesearch": "true", "order": "popular"}, timeout=20)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    random.shuffle(hits)
    paths = []
    for i, hit in enumerate(hits[:n]):
        url = hit.get("largeImageURL") or hit.get("webformatURL")
        if not url:
            continue
        pth = str(config.VIDEO_DIR / f"_bgimg_{i}.jpg")
        try:
            Path(pth).write_bytes(requests.get(url, timeout=60).content)
            paths.append(pth)
        except Exception:  # noqa: BLE001
            continue
    if not paths:
        raise RuntimeError("Pixabay: keine Bilder")
    return paths


def _kenburns(image_path, dur):
    """Langsamer Zoom auf ein Standbild (emotionaler als ein Standfoto)."""
    from moviepy import ImageClip
    clip = ImageClip(image_path).with_duration(dur)
    clip = _fit_image(clip)
    return clip.resized(lambda t: 1.0 + 0.06 * t / max(dur, 1)).with_position(("center", "center"))


def _fit_image(clip):
    target = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
    if clip.w / clip.h > target:
        clip = clip.resized(height=config.VIDEO_HEIGHT)
    else:
        clip = clip.resized(width=config.VIDEO_WIDTH)
    return clip


def _sequence(paths, duration):
    """Mehrere Clips nacheinander auf Gesamtlänge, jeder gecroppt auf 1080x1920."""
    from moviepy import VideoFileClip, concatenate_videoclips
    per = max(duration / len(paths), 2.5)
    parts = []
    for pth in paths:
        c = _fit(VideoFileClip(pth).without_audio(), per)
        parts.append(c)
    seq = concatenate_videoclips(parts)
    if seq.duration < duration:
        from moviepy import concatenate_videoclips as cc
        seq = cc([seq] * (int(duration // seq.duration) + 1))
    return seq.subclipped(0, duration)


def get_background(script: dict, duration: float):
    """1080x1920-Hintergrund in Audiolänge, cineastisch abgedunkelt. Reihenfolge: Pixabay-Video ->
    Pixabay-Bild (Ken Burns) -> prozedural. Fällt immer auf etwas zurück."""
    query = script.get("visual_query") or "cinematic motivation"
    if BG_PROVIDER in ("auto", "pixabay") and PIXABAY_API_KEY:
        try:
            clips = _pixabay_clips(query, n=3)
            logger.info("Hintergrund: %d Pixabay-Clips zu '%s'", len(clips), query)
            return _cinematic_overlay(_sequence(clips, duration), duration)
        except Exception as e:  # noqa: BLE001
            logger.warning("Pixabay-Videos fehlgeschlagen (%s) -> versuche Bilder", e)
        try:
            from moviepy import concatenate_videoclips
            imgs = _pixabay_images(query, n=3)
            per = max(duration / len(imgs), 2.5)
            seq = concatenate_videoclips([_kenburns(i, per) for i in imgs])
            if seq.duration < duration:
                seq = concatenate_videoclips([seq] * (int(duration // seq.duration) + 1))
            logger.info("Hintergrund: %d Pixabay-Bilder (Ken Burns)", len(imgs))
            return _cinematic_overlay(seq.subclipped(0, duration), duration)
        except Exception as e:  # noqa: BLE001
            logger.warning("Pixabay-Bilder fehlgeschlagen (%s) -> prozedural", e)
    if BG_PROVIDER in ("auto", "pexels") and config.PEXELS_API_KEY:
        try:
            from moviepy import VideoFileClip
            return _cinematic_overlay(_fit(VideoFileClip(_pexels(query, duration)), duration), duration)
        except Exception as e:  # noqa: BLE001
            logger.warning("Pexels fehlgeschlagen (%s) -> prozedural", e)
    logger.info("Hintergrund: prozedural (kein Stock-Treffer)")
    return _cinematic_overlay(_procedural(duration, script.get("topic", "x") + script.get("hook", "")), duration)
