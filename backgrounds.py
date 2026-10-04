"""
Hintergründe für die Videos. Reihenfolge bei BG_PROVIDER=auto:
  1. Pexels   (nur wenn PEXELS_API_KEY gesetzt — Vergabe neuer Keys ist aktuell ausgesetzt)
  2. Pixabay  (nur wenn PIXABAY_API_KEY gesetzt, kostenlos: https://pixabay.com/api/docs/)
  3. Prozedural: animierter Cinematic-Hintergrund (Farbverlauf + schwebende Lichtpunkte),
     braucht KEINEN Key, keinen Download, funktioniert immer.
"""
import hashlib
import itertools
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
# "street_bw"  -> raue Schwarz-Weiß-Optik wie Street-Art-Zitat-Poster (Beton, hoher Kontrast, Körnung)
# "cinematic_color" -> der bisherige, farbige, dunkle Cinematic-Look
VISUAL_STYLE = os.getenv("VISUAL_STYLE", "street_modern")

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
_GRAIN_CACHE = None


def _bw_grade_frame(frame):
    """Rohe Schwarz-Weiß-Optik: entsättigt, kontraststark, leicht aufgehellte Schwarzwerte
    (wie ein Beton-Wand-Foto) statt flaches Farbbild."""
    gray = frame.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    gray = (gray - 128.0) * 1.38 + 128.0  # Kontrast rauf
    gray = np.clip(gray, 6, 249)  # nie ganz schwarz/weiß -> wirkt fotografiert, nicht geclippt
    return np.repeat(gray[..., None], 3, axis=2).astype(np.uint8)


def _apply_bw_grade(clip):
    try:
        return clip.image_transform(_bw_grade_frame)
    except AttributeError:
        return clip.fl_image(_bw_grade_frame)  # ältere moviepy-API als Fallback


def _grain_layer(duration):
    """Feines, leicht flackerndes Filmkorn -> roher, fotografierter Street-Art-Look."""
    global _GRAIN_CACHE
    from moviepy import VideoClip
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    small_w, small_h = W // 3, H // 3
    rng = np.random.default_rng(42)
    tiles = rng.integers(90, 170, size=(6, small_h, small_w), dtype=np.uint8)

    def make_frame(t):
        tile = tiles[int(t * 12) % 6]
        big = np.asarray(Image.fromarray(tile).resize((W, H), Image.NEAREST))
        return np.repeat(big[..., None], 3, axis=2)

    return VideoClip(make_frame, duration=duration)


_GRAIN_FRAMES = None


def _overlay_tables():
    """Einmalig vorberechnet: Vignette/Verlauf als Multiplikator (H,W,1) + 6 Korn-Frames."""
    global _OVERLAY_CACHE, _GRAIN_FRAMES
    if _OVERLAY_CACHE is None:
        W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        vig = np.clip((((xs / W - 0.5) * 1.5) ** 2 + ((ys / H - 0.5) * 1.3) ** 2) * 0.8, 0, 0.72)
        bottom = np.clip((ys / H - 0.5) / 0.5, 0, 1) ** 1.5 * 0.55   # unten: Untertitel-Zone
        top = np.clip((0.28 - ys / H) / 0.28, 0, 1) * 0.35           # oben: Hook-Zone
        _OVERLAY_CACHE = (1.0 - np.clip(vig + bottom + top, 0, 0.82))[..., None].astype(np.float32)
        rng = np.random.default_rng(42)
        small = rng.integers(90, 170, size=(6, H // 3, W // 3), dtype=np.uint8)
        _GRAIN_FRAMES = [np.asarray(Image.fromarray(t).resize((W, H), Image.NEAREST)) for t in small]
    return _OVERLAY_CACHE, _GRAIN_FRAMES


def _cinematic_overlay(clip, duration):
    """S/W-Grading + Vignette/Verlauf + Filmkorn in EINEM Durchgang pro Frame.
    (Vorher: drei verschachtelte Composite-Clips -> pro Frame mehrere Vollbild-Konvertierungen,
    das war der Hauptgrund für minutenlange Renderzeiten.)"""
    mult, grain = _overlay_tables()
    bw = VISUAL_STYLE in ("street_bw", "street_modern")
    coeff = np.array([0.299, 0.587, 0.114], dtype=np.float32)

    def tf(get_frame, t):
        f = get_frame(t).astype(np.float32)
        if bw:
            g = f @ coeff
            g = np.clip((g - 128.0) * 1.38 + 128.0, 6, 249)[..., None]
            g = g * mult
            g = g * 0.95 + grain[int(t * 12) % 6][..., None].astype(np.float32) * 0.05
            return np.repeat(np.clip(g, 0, 255).astype(np.uint8), 3, axis=2)
        return np.clip(f * mult, 0, 255).astype(np.uint8)

    return clip.transform(tf).with_duration(duration)


def _fit(clip: VideoFileClip, duration: float):
    """Auf 1080x1920 croppen und auf Länge loopen/trimmen."""
    target = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
    if clip.w / clip.h > target:
        if clip.h != config.VIDEO_HEIGHT:  # ffmpeg hat meist schon skaliert -> kein Python-Resize pro Frame
            clip = clip.resized(height=config.VIDEO_HEIGHT)
        clip = clip.cropped(x_center=clip.w / 2, width=config.VIDEO_WIDTH)
    else:
        if clip.w != config.VIDEO_WIDTH:
            clip = clip.resized(width=config.VIDEO_WIDTH)
        clip = clip.cropped(y_center=clip.h / 2, height=config.VIDEO_HEIGHT)
    if clip.duration < duration:
        clip = concatenate_videoclips([clip] * (int(duration // clip.duration) + 1))
    return clip.subclipped(0, duration)


def _slow_zoom(clip, max_zoom=1.09):
    """Leichter Zoom-in übers Segment (wirkt geschnitten statt wie ein Standbild). Schneidet pro
    Frame die Mitte zu und skaliert auf die Originalgröße zurück -> Ausgabegröße bleibt konstant,
    nur ein Resize pro Frame."""
    dur = max(clip.duration, 0.1)

    def tf(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        z = 1.0 + (max_zoom - 1.0) * min(t / dur, 1.0)
        cw, ch = int(w / z), int(h / z)
        x0, y0 = (w - cw) // 2, (h - ch) // 2
        crop = frame[y0:y0 + ch, x0:x0 + cw]
        return np.asarray(Image.fromarray(crop).resize((w, h), Image.BILINEAR))

    return clip.transform(tf)


def _open_clip(path: str):
    """Stock-Video öffnen und von ffmpeg direkt auf Zielhöhe skalieren lassen (schnell, nativ),
    statt jeden 4K-Frame in Python per PIL zu verkleinern."""
    return VideoFileClip(path, target_resolution=(None, config.VIDEO_HEIGHT)).without_audio()  # (Breite, Höhe)


_DL_COUNTER = itertools.count()


def _download(url: str, name: str) -> str:
    path = str(config.VIDEO_DIR / f"_bg_{name}_{next(_DL_COUNTER)}.mp4")
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


_ANIMAL_WORDS = {
    "animal", "animals", "dog", "dogs", "cat", "cats", "bird", "birds", "horse", "horses", "wolf", "wolves",
    "lion", "tiger", "bear", "fish", "insect", "butterfly", "bee", "deer", "fox", "eagle", "owl", "monkey",
    "elephant", "snake", "cow", "pig", "sheep", "duck", "swan", "pet", "pets", "puppy", "kitten", "wildlife",
    "rabbit", "squirrel", "spider", "frog", "dolphin", "whale", "shark", "zoo", "crow", "raven", "pigeon",
}
_PEOPLE_WORDS = {
    "man", "men", "woman", "women", "people", "person", "boy", "girl", "athlete", "runner", "boxer", "silhouette",
    "walking", "running", "hiker", "climber", "fighter", "workout", "fitness", "crowd", "human", "guy", "street",
}


def _tagset(hit):
    return {t.strip().lower() for t in (hit.get("tags") or "").split(",")}


def _prefer_people(hits, query):
    """Tiere raus (ausser die Suche verlangt sie ausdruecklich), Clips mit Menschen nach vorn."""
    q = set(query.lower().split())
    wanted_animals = q & _ANIMAL_WORDS
    kept = [h for h in hits if not ((_tagset(h) & _ANIMAL_WORDS) - wanted_animals)]
    hits = kept or hits
    random.shuffle(hits)
    hits.sort(key=lambda h: 0 if (_tagset(h) & _PEOPLE_WORDS) else 1)
    return hits


def _pixabay_clips(query, n=3):
    """Lädt bis zu n verschiedene Pixabay-Videos (Liste lokaler Pfade), beste Auflösung zuerst."""
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": PIXABAY_API_KEY, "q": query, "per_page": 30,
                             "safesearch": "true", "order": "popular"}, timeout=20)
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        raise RuntimeError("Pixabay: nichts gefunden")
    hits = _prefer_people(hits, query)
    paths = []
    for i, hit in enumerate(hits):
        if len(paths) >= n:
            break
        v = hit["videos"]
        f = v.get("medium") or v.get("large") or v.get("small")
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
    hits = _prefer_people(hits, query)
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
    """Langsamer Zoom auf ein Standbild: Foto einmal auf 1080x1920 croppen, dann Zoom-Transform."""
    from moviepy import ImageClip
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    img = Image.open(image_path).convert("RGB")
    k = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * k) + 1, int(img.height * k) + 1), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    clip = ImageClip(np.asarray(img.crop((x, y, x + W, y + H)))).with_duration(dur)
    return _slow_zoom(clip, max_zoom=1.06)


def _sequence(paths, duration):
    """Mehrere Clips nacheinander auf Gesamtlänge, jeder gecroppt auf 1080x1920 + leichter
    Zoom pro Clip (wirkt geschnitten/dynamisch statt wie ein stehendes Standbild)."""
    from moviepy import VideoFileClip, concatenate_videoclips
    per = max(duration / len(paths), 2.5)
    parts = []
    for pth in paths:
        c = _slow_zoom(_fit(_open_clip(pth), per))
        parts.append(c)
    seq = concatenate_videoclips(parts)
    if seq.duration < duration:
        from moviepy import concatenate_videoclips as cc
        seq = cc([seq] * (int(duration // seq.duration) + 1))
    return seq.subclipped(0, duration)


def _segment_clip(query: str, duration: float, topic_seed: str):
    """Liefert EIN Hintergrund-Segment (ohne Grading/Overlay) der exakten Länge `duration`
    für eine einzelne visual_query. Fallback-Kette pro Segment: Pixabay-Video -> Pixabay-Bild
    (Ken Burns) -> Pexels -> prozedural. Fällt also segment-weise zurück, nie für das ganze
    Video auf einmal, damit ein einzelner schlechter Treffer nicht den ganzen Clip ruiniert."""
    if BG_PROVIDER in ("auto", "pixabay") and PIXABAY_API_KEY:
        try:
            clips = _pixabay_clips(query, n=2)
            return _sequence(clips, duration)
        except Exception as e:  # noqa: BLE001
            logger.warning("Pixabay-Videos für '%s' fehlgeschlagen (%s) -> Bilder", query, e)
        try:
            from moviepy import concatenate_videoclips
            imgs = _pixabay_images(query, n=2)
            per = max(duration / len(imgs), 2.5)
            seq = concatenate_videoclips([_kenburns(i, per) for i in imgs])
            if seq.duration < duration:
                seq = concatenate_videoclips([seq] * (int(duration // seq.duration) + 1))
            return seq.subclipped(0, duration)
        except Exception as e:  # noqa: BLE001
            logger.warning("Pixabay-Bilder für '%s' fehlgeschlagen (%s) -> Pexels", query, e)
    if BG_PROVIDER in ("auto", "pexels") and config.PEXELS_API_KEY:
        try:
            from moviepy import VideoFileClip
            return _slow_zoom(_fit(_open_clip(_pexels(query, duration)), duration))
        except Exception as e:  # noqa: BLE001
            logger.warning("Pexels für '%s' fehlgeschlagen (%s) -> prozedural", query, e)
    return _procedural(duration, topic_seed + query)


def _collect_parts(queries, durations):
    """Lädt je Segment 1-2 Stock-Clips (oder Fotos) und gibt die ffmpeg-Teile zurück:
    [{"path","dur","image"}]. Segmente ohne Treffer leihen sich Material aus anderen Segmenten;
    gar nichts gefunden -> leere Liste (dann greift der alte/prozedurale Pfad)."""
    per_segment = []
    for q, d in zip(queries, durations):
        got = []
        if BG_PROVIDER in ("auto", "pixabay") and PIXABAY_API_KEY:
            try:
                got = [(p, False) for p in _pixabay_clips(q, n=2)]
            except Exception as e:  # noqa: BLE001
                logger.warning("Pixabay-Videos '%s': %s -> Fotos", q, e)
                try:
                    got = [(p, True) for p in _pixabay_images(q, n=2)]
                except Exception as e2:  # noqa: BLE001
                    logger.warning("Pixabay-Fotos '%s': %s", q, e2)
        if not got and BG_PROVIDER in ("auto", "pexels") and config.PEXELS_API_KEY:
            try:
                got = [(_pexels(q, d), False)]
            except Exception as e:  # noqa: BLE001
                logger.warning("Pexels '%s': %s", q, e)
        per_segment.append(got)
    pool = [g for seg in per_segment for g in seg]
    if not pool:
        return []
    parts = []
    for i, (got, d) in enumerate(zip(per_segment, durations)):
        if not got:
            got = [pool[i % len(pool)]]
        each = d / len(got)
        parts += [{"path": p, "dur": each, "image": img} for p, img in got]
    return parts


def _fast_background(queries, durations, duration):
    """Kompletter Hintergrund in einem nativen ffmpeg-Durchgang. Gibt VideoFileClip oder None."""
    import ffmpeg_bg
    parts = _collect_parts(queries, durations)
    if not parts:
        return None
    out = str(config.VIDEO_DIR / "_bg_render.mp4")
    ffmpeg_bg.render_background(parts, duration, out, bw=(VISUAL_STYLE in ("street_bw", "street_modern")), style=VISUAL_STYLE)
    return VideoFileClip(out).without_audio().subclipped(0, duration)


def get_background(script: dict, duration: float):
    """1080x1920-Hintergrund in Audiolänge, cineastisch abgedunkelt. Nutzt 3 verschiedene
    visual_queries (Hook / Body-Mitte / CTA), proportional über die Dauer verteilt, statt
    EINER Query fürs ganze Video -> die Bildsprache entwickelt sich mit dem Text statt
    beliebig irgendein Clip-Wechsel mitten im Satz."""
    queries = script.get("visual_queries") or [script.get("visual_query") or "cinematic motivation"] * 3
    queries = list(queries)[:8]
    while len(queries) < 3:
        queries.append(queries[-1])
    seed = script.get("topic", "x") + script.get("hook", "")

    # Gewichtung: Hook/CTA kurz & knackig, die Mitte teilt sich die meiste Sprechzeit.
    n = len(queries)
    if n == 3:
        weights = [0.22, 0.56, 0.22]
    else:
        edge = 0.12
        weights = [edge] + [(1 - 2 * edge) / (n - 2)] * (n - 2) + [edge]
    min_seg = 2.2
    raw = [max(duration * w, min_seg) for w in weights]
    scale = duration / sum(raw)
    durations = [d * scale for d in raw]

    if os.getenv("BG_RENDER", "ffmpeg") == "ffmpeg":
        try:
            clip = _fast_background(queries, durations, duration)
            if clip is not None:
                logger.info("Hintergrund: %d Segmente nativ via ffmpeg gerendert (%s)",
                            len(queries), " / ".join(queries))
                return clip
            logger.info("Kein Stock-Material gefunden -> prozeduraler Hintergrund")
        except Exception as e:  # noqa: BLE001
            logger.warning("ffmpeg-Hintergrund fehlgeschlagen (%s) -> klassischer Pfad", e)

    segments = []
    for q, d in zip(queries, durations):
        try:
            segments.append(_segment_clip(q, d, seed))
        except Exception as e:  # noqa: BLE001
            logger.warning("Segment '%s' komplett fehlgeschlagen (%s) -> prozedural", q, e)
            segments.append(_procedural(d, seed + q))

    logger.info("Hintergrund: %d Segmente (%s)", len(queries), " / ".join(queries))
    from moviepy import concatenate_videoclips
    full = concatenate_videoclips(segments)
    # Rundungsfehler ausgleichen, exakt auf Audiolänge
    if full.duration < duration:
        full = concatenate_videoclips([full, segments[-1]])
    full = full.subclipped(0, duration)
    return _cinematic_overlay(full, duration)
