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
VISUAL_STYLE = os.getenv("VISUAL_STYLE", "cinema")

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
    bw = VISUAL_STYLE in ("street_bw", "street_modern", "street_art")
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


_LAST_CDN = [0.0]


def _cdn_get(url: str, timeout: int = 90, min_bytes: int = 0) -> bytes:
    """GET mit Drosselung (Pixabay-CDN sperrt bei zu vielen schnellen Abrufen kurz) und
    Pruefung: nur HTTP 200 mit echter Dateigroesse zaehlt. Fehlertexte werden NIE als Datei gespeichert."""
    import time
    err = ""
    for attempt in range(4):
        wait = 0.4 - (time.time() - _LAST_CDN[0])
        if wait > 0:
            time.sleep(wait)
        _LAST_CDN[0] = time.time()
        try:
            r = requests.get(url, timeout=timeout)
        except requests.RequestException as e:
            err = str(e)[:120]
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            err = f"HTTP {r.status_code}"
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        if len(r.content) < min_bytes:
            raise RuntimeError(f"Datei zu klein ({len(r.content)} Bytes)")
        return r.content
    raise RuntimeError(f"Download gescheitert ({err})")


def _video_ok(path: str) -> bool:
    """Prueft mit ffmpeg, ob die Datei wirklich ein abspielbares Video ist."""
    import subprocess
    import ffmpeg_bg
    try:
        r = subprocess.run([ffmpeg_bg.ffmpeg_exe(), "-v", "error", "-t", "0.3", "-i", path,
                            "-f", "null", "-"], capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _download(url: str, name: str) -> str:
    path = str(config.VIDEO_DIR / f"_bg_{name}_{next(_DL_COUNTER)}.mp4")
    Path(path).write_bytes(_cdn_get(url, 180, min_bytes=80_000))
    if not _video_ok(path):
        Path(path).unlink(missing_ok=True)
        raise RuntimeError("Clip defekt/kein Video")
    return path


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


_EMOTION_WORDS = {
    "emotion", "emotional", "emotions", "face", "faces", "portrait", "closeup", "close-up", "crying", "cry", "tears",
    "sad", "sadness", "happy", "smile", "smiling", "laughing", "laugh", "scream", "screaming", "fear", "anger",
    "angry", "shocked", "surprise", "joy", "grief", "lonely", "alone", "depressed", "stress", "stressed", "hope",
    "relief", "expression", "emotions", "thinking", "pain", "determination", "tired", "exhausted",
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
    hits.sort(key=lambda h: 0 if (_tagset(h) & _EMOTION_WORDS and _tagset(h) & _PEOPLE_WORDS | _tagset(h) & {'face', 'portrait', 'crying', 'tears', 'smile'}) else (1 if (_tagset(h) & _PEOPLE_WORDS) else 2))
    return hits


# ── Clip-Auswahl: Gedaechtnis + Stimmungsfilter + KI-Cutter ─────────────────────
import base64
import json as _json
import time as _time

USED_FILE = config.CONTENT_DIR / "used_clips.json"
USED_KEEP = 3000          # so viele zuletzt benutzte Clip-IDs werden nie wieder genommen
VISION_CHECK = os.getenv("VISION_CHECK", "1") != "0"


def _used_load() -> list:
    try:
        return _json.loads(USED_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _used_add(cid: str):
    used = [u for u in _used_load() if u != cid] + [cid]
    try:
        USED_FILE.write_text(_json.dumps(used[-USED_KEEP:]), encoding="utf-8")
    except OSError:
        pass


# Alles mit guter Laune / Werbe-Look / Kitsch fliegt raus — passt nicht zu einem ernsten Kanal.
_BLOCK_MOOD = {
    "happy", "happiness", "smile", "smiling", "smiles", "smiley", "laugh", "laughing", "laughter",
    "joy", "joyful", "fun", "funny", "party", "celebration", "celebrate", "cheerful", "cute",
    "beauty", "model", "models", "fashion", "girl", "girls", "teen", "teenager", "couple",
    "romance", "romantic", "kiss", "wedding", "bride", "dance", "dancing", "christmas",
    "birthday", "kids", "kid", "child", "children", "baby", "selfie", "makeup", "coffee",
    "cafe", "food", "cooking", "playful",
}
# Was ernst, dunkel, filmisch wirkt, wird nach vorne sortiert.
_DARK_MOOD = {
    "dark", "night", "rain", "rainy", "alone", "lonely", "loneliness", "silhouette", "shadow",
    "shadows", "fight", "fighting", "boxer", "boxing", "struggle", "storm", "smoke", "fog", "mist",
    "sad", "sadness", "depressed", "depression", "despair", "crying", "tears", "pain", "tired",
    "exhausted", "determination", "determined", "training", "sweat", "monochrome", "dramatic",
    "cinematic", "serious", "thinking", "city", "street", "urban", "stairs", "running", "gym",
    "fire", "ruins", "black and white", "mountain", "climbing", "warrior", "strength", "power",
}


def _mood_ok(tags: set) -> bool:
    return not (tags & _BLOCK_MOOD)


def _mood_score(tags: set) -> int:
    s = 2 * len(tags & _DARK_MOOD)
    if tags & _PEOPLE_WORDS:
        s += 2
    if (tags & _ANIMAL_WORDS):
        s -= 6
    return s


def _vision_scores(cands: list, query: str):
    """KI-Cutter: Gemini bewertet die Vorschaubilder 0-10 fuer einen ernsten, dunklen,
    filmischen Mindset-Kanal. Rueckgabe [(note, kandidat), ...] oder None (kein Key/Fehler)."""
    key = os.getenv("GEMINI_API_KEY", "")
    pool = [c for c in cands if c.get("thumb")][:8]
    if not (VISION_CHECK and key and len(pool) >= 2):
        return None
    parts = [{"text": (
        "Du bist Cutter fuer einen ERNSTEN, DUNKLEN, CINEASTISCHEN Mindset-Kanal "
        "(Kampf, Niederlage, Einsamkeit, Aufstehen, Entschlossenheit). Gesuchte Szene: "
        f"'{query}'. Bewerte JEDES folgende Bild mit 0-10: Wie gut passt es ernst, dunkel, filmisch "
        "UND zur Szene? 0 Punkte zwingend fuer: lachende/laechelnde Menschen, gute Laune, Party, "
        "huebsche Models/Beauty/Fashion, Paare/Romantik, Kinder, Tiere, Essen/Kaffee, Buero/Werbe-Look, "
        "eingeblendeter Text/Logos. Hohe Noten fuer: Gesichter mit Schmerz/Ernst/Entschlossenheit, "
        "Silhouetten, Nacht, Regen, Gegenlicht, Kampf, Training, einsame Figur. "
        'Antworte NUR mit JSON: {"scores": [Note Bild 1, Note Bild 2, ...]}')}]
    used_pool, fails = [], 0
    for c in pool:
        try:
            data = _cdn_get(c["thumb"], 12, min_bytes=800)
        except Exception:  # noqa: BLE001
            fails += 1
            if fails >= 2:
                break
            continue
        parts.append({"text": f"Bild {len(used_pool) + 1}:"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode()}})
        used_pool.append(c)
    if len(used_pool) < 2:
        return None
    try:
        import content_generator as cg
        models = [cg._gemini_pick_model()] + list(cg._gemini_available_models())[:3]
    except Exception:  # noqa: BLE001
        models = [os.getenv("GEMINI_MODEL", "gemini-2.5-flash")]
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400,
                                 "responseMimeType": "application/json",
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    for attempt, model in enumerate(dict.fromkeys(models)):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": key}, json=body, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504):
                _time.sleep(3 * (attempt + 1))
                continue
            if r.status_code != 200:
                continue
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"].get("parts", []))
            scores = _json.loads(txt[txt.find("{"): txt.rfind("}") + 1]).get("scores", [])
            rated = [(float(s), c) for s, c in zip(scores, used_pool) if isinstance(s, (int, float))]
            rated.sort(key=lambda x: -x[0])
            logger.info("KI-Cutter '%s': Noten %s", query, [int(s) for s, _ in rated])
            return rated
        except Exception as e:  # noqa: BLE001
            logger.warning("KI-Cutter (%s) fehlgeschlagen: %s", model, e)
    return None


def _qbonus(c) -> int:
    q = c.get("q", 1.0)
    return 3 if q >= 0.9 else (1 if q >= 0.66 else (-3 if q < 0.5 else 0))


def _choose(cands: list, query: str, n: int, vision: bool = True) -> list:
    """Benutzte + falsche Stimmung raus, dunkel/ernst/scharf nach vorn, KI-Cutter entscheidet.
    Lehnt die KI alles Gute ab (Note < 3), kommt [] zurueck -> Ersatzsuche statt Notfall-Bild."""
    used = set(_used_load())
    fresh = [c for c in cands if c["id"] not in used and _mood_ok(c["tags"])]
    if not fresh:
        logger.info("Keine neuen, passenden Treffer fuer '%s'", query)
        return []
    random.shuffle(fresh)
    fresh.sort(key=lambda c: -(_mood_score(c["tags"]) + _qbonus(c)))
    top = fresh[:8]
    scored = _vision_scores(top, query) if vision else None
    if scored is None:
        return top[:n]
    picked = [c for s, c in scored if s >= 5] or [c for s, c in scored if s >= 3]
    return picked[:n]


def _pexels_cands(query: str) -> list:
    r = requests.get("https://api.pexels.com/videos/search",
                     headers={"Authorization": config.PEXELS_API_KEY},
                     params={"query": query, "orientation": "portrait", "per_page": 40}, timeout=20)
    r.raise_for_status()
    out = []
    for v in r.json().get("videos", []):
        files = sorted([f for f in v.get("video_files", []) if (f.get("width") or 0) <= 1080],
                       key=lambda f: f.get("width") or 0, reverse=True) or v.get("video_files", [])
        if not files:
            continue
        slug = (v.get("url") or "").rstrip("/").split("/")[-1]  # z.B. "man-walking-in-rain-12345"
        tags = set(slug.replace("-", " ").lower().split())
        f0 = files[0]
        out.append({"id": f"pexels:{v['id']}", "url": f0["link"], "thumb": v.get("image"),
                    "tags": tags, "q": _crop_quality(f0.get("width") or 0, f0.get("height") or 0)})
    return out


def _pexels(query, duration, vision=True):
    picked = _choose(_pexels_cands(query), query, 1, vision)
    if not picked:
        raise RuntimeError("Pexels: nichts Neues/Passendes")
    path = _download(picked[0]["url"], "pexels")
    _used_add(picked[0]["id"])
    return path


def _crop_quality(w: int, h: int) -> float:
    """Wie scharf wird der 9:16-Ausschnitt? 1.0 = volle 1080 Pixel Breite ohne Hochskalieren."""
    if not w or not h:
        return 0.0
    return min(w, h * 9 / 16) / config.VIDEO_WIDTH


def _best_rendition(v: dict):
    """Kleinste Variante, deren 9:16-Ausschnitt scharf genug ist (>= 720 px breit); zu grosse
    Dateien (> 70 MB) werden nur genommen, wenn nichts anderes reicht."""
    opts = [v[k] for k in ("tiny", "small", "medium", "large") if v.get(k) and v[k].get("url")]
    if not opts:
        return None
    sharp = [f for f in opts if _crop_quality(f.get("width") or 0, f.get("height") or 0) >= 0.66]
    ok = [f for f in sharp if (f.get("size") or 0) <= 70_000_000]
    if ok:
        return ok[0]
    if sharp:
        return sharp[0]
    return opts[-1]


def _pixabay_video_cands(query: str) -> list:
    r = requests.get("https://pixabay.com/api/videos/",
                     params={"key": PIXABAY_API_KEY, "q": query, "per_page": 100,
                             "safesearch": "true", "order": "popular"}, timeout=20)
    r.raise_for_status()
    out = []
    for hit in r.json().get("hits", []):
        v = hit.get("videos", {})
        f = _best_rendition(v)
        if not f:
            continue
        thumb = ((v.get("tiny") or {}).get("thumbnail") or (v.get("small") or {}).get("thumbnail")
                 or f.get("thumbnail"))
        if not thumb and hit.get("picture_id"):
            thumb = f"https://i.vimeocdn.com/video/{hit['picture_id']}_640x360.jpg"
        out.append({"id": f"pixabay:{hit['id']}", "url": f["url"], "thumb": thumb, "tags": _tagset(hit),
                    "q": _crop_quality(f.get("width") or 0, f.get("height") or 0)})
    return out


def _pixabay_clips(query, n=3, vision=True):
    """Laedt bis zu n NEUE, stimmungs- und KI-gepruefte Pixabay-Videos (lokale Pfade)."""
    cands = _pixabay_video_cands(query)
    if not cands:
        raise RuntimeError("Pixabay: nichts gefunden")
    paths = []
    for i, c in enumerate(_choose(cands, query, n, vision)):
        try:
            paths.append(_download(c["url"], f"pixabay_{i}"))
            _used_add(c["id"])
        except Exception:  # noqa: BLE001
            continue
    if not paths:
        raise RuntimeError("Pixabay: kein neuer, passender Clip")
    return paths


def _pixabay_images(query, n=3, vision=True):
    """Fallback: Pixabay-Fotos (lokale Pfade) fuer Ken-Burns-Hintergrund, gleiche Filter."""
    r = requests.get("https://pixabay.com/api/",
                     params={"key": PIXABAY_API_KEY, "q": query, "per_page": 100,
                             "image_type": "photo", "orientation": "vertical",
                             "safesearch": "true", "order": "popular"}, timeout=20)
    r.raise_for_status()
    cands = [{"id": f"pixabayimg:{h['id']}", "url": h.get("largeImageURL") or h.get("webformatURL"),
              "thumb": h.get("webformatURL") or h.get("previewURL"), "tags": _tagset(h)}
             for h in r.json().get("hits", []) if h.get("largeImageURL") or h.get("webformatURL")]
    paths = []
    for i, c in enumerate(_choose(cands, query, n, vision)):
        pth = str(config.VIDEO_DIR / f"_bgimg_{i}.jpg")
        try:
            Path(pth).write_bytes(_cdn_get(c["url"], 60, min_bytes=20_000))
            Image.open(pth).verify()
            paths.append(pth)
            _used_add(c["id"])
        except Exception:  # noqa: BLE001
            continue
    if not paths:
        raise RuntimeError("Pixabay: keine neuen, passenden Bilder")
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


_DARK_FALLBACKS = [
    "lonely man silhouette night rain cinematic",
    "boxer training dark gym slow motion",
    "man walking alone city night cinematic",
    "exhausted athlete sweat determination dramatic lighting",
    "man standing storm clouds silhouette",
    "man running stairs night training",
    "man face closeup serious dark",
    "man hood walking fog street",
]


def _fetch_segment(q: str, d: float, vision: bool = True) -> list:
    """Video vor Foto: Pixabay-Videos -> Pexels-Videos -> Pixabay-Fotos. Liste (pfad, ist_bild)."""
    if BG_PROVIDER in ("auto", "pixabay") and PIXABAY_API_KEY:
        try:
            return [(p, False) for p in _pixabay_clips(q, n=2, vision=vision)]
        except Exception as e:  # noqa: BLE001
            logger.warning("Pixabay-Videos '%s': %s", q, e)
    if BG_PROVIDER in ("auto", "pexels") and config.PEXELS_API_KEY:
        try:
            return [(_pexels(q, d, vision), False)]
        except Exception as e:  # noqa: BLE001
            logger.warning("Pexels '%s': %s", q, e)
    if BG_PROVIDER in ("auto", "pixabay") and PIXABAY_API_KEY:
        try:
            return [(p, True) for p in _pixabay_images(q, n=2, vision=vision)]
        except Exception as e:  # noqa: BLE001
            logger.warning("Pixabay-Fotos '%s': %s", q, e)
    return []


def _collect_parts(queries, durations):
    """Lädt je Segment 1-2 Stock-Clips (oder Fotos) und gibt die ffmpeg-Teile zurück:
    [{"path","dur","image"}]. Segmente ohne Treffer leihen sich Material aus anderen Segmenten;
    gar nichts gefunden -> leere Liste (dann greift der alte/prozedurale Pfad)."""
    per_segment = []
    for i, (q, d) in enumerate(zip(queries, durations)):
        got = _fetch_segment(q, d)
        if not got:
            # KI-Cutter/Filter haben alles abgelehnt -> dunkle Ersatzsuche statt Notfall-Hintergrund
            fb = _DARK_FALLBACKS[(i + random.randint(0, 99)) % len(_DARK_FALLBACKS)]
            logger.info("Segment '%s' ohne passenden neuen Clip -> Ersatzsuche '%s'", q, fb)
            got = _fetch_segment(fb, d)
            if not got:
                got = _fetch_segment(fb, d, vision=False)
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
    ffmpeg_bg.render_background(parts, duration, out, bw=(VISUAL_STYLE in ("street_bw", "street_modern", "street_art")), style=VISUAL_STYLE)
    return VideoFileClip(out).without_audio().subclipped(0, duration)


def _sentence_durations(words, duration: float, n: int):
    """Segmentlaengen so, dass jeder Szenenwechsel genau in der Pause NACH einem Satz liegt
    (statt mitten im Satz). None, wenn die Saetze dafuer nicht reichen."""
    if not words or n < 2:
        return None
    ends = []
    for i, w in enumerate(words):
        if str(w.get("word", "")).rstrip().endswith((".", "!", "?", "…", ":")):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else duration
            ends.append((w["end"] + nxt) / 2)
    cuts, last = [], 0.0
    for k in range(1, n):
        target = duration * k / n
        cand = [e for e in ends if e > last + 2.2 and e < duration - 2.2 * (n - k)]
        if not cand:
            return None
        c = min(cand, key=lambda e: abs(e - target))
        cuts.append(c)
        last = c
    b = [0.0] + cuts + [duration]
    return [b[i + 1] - b[i] for i in range(n)]


def get_background(script: dict, duration: float, words=None):
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
    aligned = _sentence_durations(words, duration, n)
    if aligned:
        durations = aligned
        logger.info("Szenenwechsel auf Satzenden: %s", [round(d, 1) for d in durations])

    if os.getenv("BG_RENDER", "ffmpeg") == "ffmpeg" and os.getenv("AI_SCENES", "0") == "1":
        try:
            import scenes
            import ffmpeg_bg
            parts = scenes.build_parts(script, duration)
            out = str(config.VIDEO_DIR / "_bg_render.mp4")
            look = "cinema" if scenes.SCENE_LOOK != "streetart" else "street_art"
            ffmpeg_bg.render_background(parts, duration, out, bw=False, style=look)
            logger.info("Hintergrund: %d KI-Szenen (%s-Look) gerendert", len(parts), scenes.SCENE_LOOK)
            return VideoFileClip(out).without_audio().subclipped(0, duration)
        except Exception as e:  # noqa: BLE001
            logger.warning("KI-Szenen nicht moeglich (%s) -> Stock-Footage", e)

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
