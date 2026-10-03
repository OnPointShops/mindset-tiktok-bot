"""
Baut aus (Skript + Voiceover) ein fertiges 9:16 TikTok-Video:

1. Passendes Stock-Hintergrundvideo von Pexels laden (thematisch zum Skript-Topic)
2. Auf 1080x1920 zuschneiden/skalieren, auf Voiceover-Länge loopen/trimmen
3. Voiceover als Audiospur drauflegen
4. Whisper transkribiert das Voiceover -> Wort-Timings für Auto-Captions
5. Captions als animierte Text-Overlays einbrennen (TikTok-Stil: große, zentrierte
   Wortgruppen, die synchron zum Sprechen erscheinen)
6. Hook-Text prominent in den ersten 1.5s als Text-Overlay (Pattern-Interrupt)
"""
import random
import logging
import requests
from pathlib import Path

from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips,
)
from faster_whisper import WhisperModel

import config
import backgrounds
import cover

logger = logging.getLogger("video_builder")

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        # "base" reicht für kurze, klar gesprochene 15-25s Voiceovers völlig aus
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper-Modell (base, CPU/int8) geladen.")
    return _whisper_model


def fetch_stock_clip(query: str, out_path: str, min_duration=20) -> str:
    """Lädt ein passendes vertikales Stock-Video von Pexels."""
    if not config.PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY fehlt in .env")

    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": config.PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 15, "size": "medium"},
        timeout=20,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    # Nach Dauer filtern (lang genug, nicht ewig -> schnellerer Download)
    candidates = [v for v in videos if v["duration"] >= min_duration]
    if not candidates:
        candidates = videos
    if not candidates:
        raise RuntimeError(f"Kein Pexels-Clip gefunden für Query: {query}")

    chosen = random.choice(candidates[:10])
    # Beste verfügbare vertikale HD-Datei wählen
    files = sorted(
        [f for f in chosen["video_files"] if f["width"] <= 1080],
        key=lambda f: f["width"], reverse=True,
    )
    video_url = files[0]["link"] if files else chosen["video_files"][0]["link"]

    video_data = requests.get(video_url, timeout=60).content
    Path(out_path).write_bytes(video_data)
    logger.info("Stock-Clip geladen: %s (%s)", query, out_path)
    return out_path


def transcribe_with_timings(audio_path: str) -> list[dict]:
    """Gibt Wort-Level-Timings zurück: [{"word": ..., "start": ..., "end": ...}, ...]"""
    model = _get_whisper()
    segments, _ = model.transcribe(audio_path, word_timestamps=True, language="de")
    words = []
    for seg in segments:
        for w in seg.words:
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words


def get_word_timings(audio_path: str, text: str, duration: float) -> list[dict]:
    """1) Timings von edge-tts  2) Whisper  3) Schätzung nach Wortlänge. Captions fallen nie aus."""
    import json
    j = Path(audio_path + ".words.json")
    if j.exists():
        try:
            w = json.loads(j.read_text(encoding="utf-8"))
            if w:
                return w
        except Exception:  # noqa: BLE001
            pass
    try:
        w = transcribe_with_timings(audio_path)
        if w:
            return w
    except Exception as e:  # noqa: BLE001
        logger.warning("Whisper nicht verfügbar (%s) -> geschätzte Timings", e)
    words = text.split()
    if not words:
        return []
    total = sum(len(x) + 2 for x in words)
    t, out, span = 0.15, [], max(duration - 0.4, 1.0)
    for x in words:
        d = span * (len(x) + 2) / total
        out.append({"word": x, "start": t, "end": t + d})
        t += d
    return out


# Kurze deutsche Stoppwörter -> werden nie als Emphase-Wort gewählt, auch wenn sie
# zufällig das längste Wort in der Gruppe wären (praktisch selten, aber zur Sicherheit).
_STOPWORDS = {"der", "die", "das", "und", "oder", "aber", "ist", "sind", "war", "waren",
              "ein", "eine", "einen", "einem", "nicht", "du", "ich", "er", "sie", "es",
              "dein", "deine", "mein", "meine", "für", "mit", "von", "auf", "zu", "im",
              "in", "an", "am", "wie", "was", "wenn", "dann", "nur", "noch", "schon"}

# Blutrot/Amber-Akzent fürs Schlüsselwort je Caption-Gruppe: ein einzelner Farbfleck auf
# sonst reinem Schwarz-Weiß (street_bw) bzw. Weiß (cinematic) -> klassischer "Sin City"-
# Effekt, zieht den Blick genau auf das Wort, das den Gedanken trägt.
ACCENT_COLOR = (214, 40, 40, 255)


def _group_words_for_captions(words: list[dict], group_size=3) -> list[dict]:
    """Fasst Wörter zu kurzen, TikTok-typischen Caption-Häppchen zusammen (2-4 Wörter) und
    markiert pro Gruppe das stärkste Wort (längstes Nicht-Stoppwort) für die Akzentfarbe."""
    groups = []
    for i in range(0, len(words), group_size):
        chunk = words[i:i + group_size]
        if not chunk:
            continue
        texts = [w["word"].upper() for w in chunk]
        candidates = [j for j, w in enumerate(chunk) if w["word"].lower() not in _STOPWORDS]
        pool = candidates or list(range(len(chunk)))
        emphasis_idx = max(pool, key=lambda j: len(chunk[j]["word"]))
        groups.append({
            "words": texts,
            "emphasis_idx": emphasis_idx,
            "start": chunk[0]["start"],
            "end": chunk[-1]["end"],
        })
    return groups


def _pop_in(clip, base_x: int, base_y: int, pop_dur=0.12):
    """Kurzer Scale-Pop beim Erscheinen (1.18 -> 1.0) statt starrem Einblenden -> Captions
    wirken geschnitten/energiegeladen statt wie Untertitel aus einem Textfeld. Position wird
    pro Frame so verschoben, dass die Mitte des Texts während des Pops fix bleibt."""
    start_scale, dur = 1.18, max(pop_dur, 0.02)
    w0, h0 = clip.w, clip.h

    def factor(t):
        return 1.0 if t >= dur else start_scale + (1.0 - start_scale) * (t / dur)

    def pos(t):
        f = factor(t)
        return (base_x - (w0 * f - w0) / 2, base_y - (h0 * f - h0) / 2)

    return clip.resized(factor).with_position(pos)


def _text_clip(text_or_words, font_size: int, fill, y_frac: float, start: float, dur: float,
               max_w_frac: float = 0.88, stroke: int = 8, emphasis_idx: int | None = None,
               pop: bool = False):
    """Text mit dicker Umrandung per Pillow (kein moviepy-TextClip: schneidet Umlaute/Unterlängen ab).
    text_or_words: entweder ein String (alter Pfad, z.B. Hook) oder eine Liste von Wörtern
    (Caption-Gruppe) — dann wird emphasis_idx in ACCENT_COLOR statt `fill` gezeichnet."""
    from PIL import Image, ImageDraw
    import numpy as np
    from moviepy import ImageClip
    font = cover.find_font(font_size)
    max_w = int(config.VIDEO_WIDTH * max_w_frac)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    words = text_or_words if isinstance(text_or_words, list) else text_or_words.split()
    # Zeilenumbruch, aber Wort-Index je Zeile merken (für die Akzentfarbe nach dem Umbruch).
    lines, cur_words, cur = [], [], ""
    for idx, word in enumerate(words):
        trial = (cur + " " + word).strip()
        if probe.textlength(trial, font=font) <= max_w - 2 * stroke or not cur:
            cur = trial
            cur_words.append(idx)
        else:
            lines.append(cur_words)
            cur, cur_words = word, [idx]
    if cur_words:
        lines.append(cur_words)

    line_h = int(font_size * 1.25)
    h = line_h * len(lines) + 2 * stroke + 10
    img = Image.new("RGBA", (config.VIDEO_WIDTH, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, idxs in enumerate(lines):
        ln = " ".join(words[j] for j in idxs)
        x = (config.VIDEO_WIDTH - d.textlength(ln, font=font)) / 2
        if emphasis_idx is None or emphasis_idx not in idxs:
            d.text((x, stroke + i * line_h), ln, font=font, fill=fill,
                   stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        else:
            # Wortweise zeichnen, damit genau EIN Wort die Akzentfarbe bekommt.
            cx = x
            for j in idxs:
                w_txt = words[j]
                col = ACCENT_COLOR if j == emphasis_idx else fill
                d.text((cx, stroke + i * line_h), w_txt, font=font, fill=col,
                       stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                cx += d.textlength(w_txt + " ", font=font)

    base_y = int(config.VIDEO_HEIGHT * y_frac)
    dur = max(dur, 0.2)
    arr = np.array(img)
    if not pop:
        return [ImageClip(arr).with_start(start).with_duration(dur).with_position((0, base_y))]
    # Pop nur in den ersten 0.12s (skalierter Clip), Rest statisch. Ein resized(f(t)) über die
    # ganze Lebenszeit würde jeden Frame durch PIL schicken, auch wenn der Faktor längst 1.0 ist
    # -> war einer der Hauptgründe für minutenlange Renderzeiten.
    pop_dur = min(0.12, dur)
    parts = [_pop_in(ImageClip(arr).with_start(start).with_duration(pop_dur), base_x=0, base_y=base_y)]
    if dur - pop_dur > 0.01:
        parts.append(ImageClip(arr).with_start(start + pop_dur).with_duration(dur - pop_dur)
                     .with_position((0, base_y)))
    return parts


def _mix_music(voice_path: str, script: dict) -> str:
    """Mischt ein emotionales Musikbett unter die Stimme (Ducking). Bei Fehler: Stimme pur."""
    import shutil
    import subprocess
    try:
        import music
        duration = AudioFileClip(voice_path).duration
        track = music.get_music_track(duration, script.get("topic", "") + script.get("hook", ""))
        if not track or not shutil.which("ffmpeg"):
            return voice_path
        gain = music.MUSIC_GAIN_DB

        # Schritt 1: Musik auf EXAKTE, ENDLICHE Stimmlänge bringen (eigener, einfacher Schritt).
        # Der alte Code hat das inline im selben Filtergraph mit aloop(size=2e9) gemacht - das
        # kann ffmpeg eine "unendliche" Laufzeit für den Musikstream vorspiegeln und in
        # Kombination mit sidechaincompress zu Aussetzern/Stille in der zweiten Hälfte führen.
        # Jetzt: Musik VORHER auf feste Länge loopen+zuschneiden -> beide Inputs sind endlich
        # und exakt gleich lang, bevor sidechaincompress überhaupt ins Spiel kommt.
        fitted = voice_path.replace(".wav", "_musicfit.wav")
        r0 = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", track,
             "-t", f"{duration:.3f}", "-ar", "24000", "-ac", "1", fitted],
            capture_output=True, timeout=60,
        )
        if r0.returncode != 0 or not Path(fitted).exists():
            logger.warning("Musik-Vorbereitung fehlgeschlagen, Stimme pur: %s",
                           r0.stderr.decode(errors="replace")[:200])
            return voice_path

        out = voice_path.replace(".wav", "_mixed.wav")
        fc = (f"[1:a]volume={gain}dB[m];"
              f"[m][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[mc];"
              f"[0:a][mc]amix=inputs=2:duration=first:dropout_transition=0,"
              f"dynaudnorm=f=200[a]")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice_path, "-i", fitted,
                            "-filter_complex", fc, "-map", "[a]", "-t", f"{duration:.3f}",
                            "-ar", "24000", out],
                           capture_output=True, timeout=120)
        Path(fitted).unlink(missing_ok=True)
        if r.returncode != 0 or not Path(out).exists():
            logger.warning("Musik-Mix fehlgeschlagen, Stimme pur: %s", r.stderr.decode(errors="replace")[:200])
            return voice_path
        words_src = Path(voice_path + ".words.json")
        if words_src.exists():
            import shutil
            shutil.copyfile(words_src, out + ".words.json")  # Timings dem neuen Pfad mitgeben
        logger.info("Musik untergemischt (%s dB)", gain)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("Musik-Mix übersprungen (%s)", e)
        return voice_path


def build_video(script: dict, audio_path: str, output_path: str) -> str:
    """Kompletter Build: Stock-Footage + Voiceover + Hook-Overlay + Auto-Captions."""
    audio_path = _mix_music(audio_path, script)  # emotionale Musik leise drunter
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # 1. Hintergrund (Stock oder prozedural, siehe backgrounds.py)
    bg = backgrounds.get_background(script, duration).with_audio(audio)

    # 2. Auto-Captions via Whisper-Timings
    words = get_word_timings(audio_path, script.get("full_voiceover_text", ""), duration)
    caption_groups = _group_words_for_captions(words, group_size=3)

    # Street-Art-Poster-Stil: Hook & Captions beide weiß (wie die Beton-Wand-Zitate),
    # kein Gelb-Akzent -> passt zur entsättigten Schwarz-Weiß-Grading der Hintergründe.
    hook_fill = (255, 255, 255, 255) if backgrounds.VISUAL_STYLE == "street_bw" else (255, 235, 90, 255)

    caption_clips = [
        part for g in caption_groups
        for part in _text_clip(g["words"], 84, (255, 255, 255, 255), 0.66, g["start"],
                               max(g["end"] - g["start"], 0.3), emphasis_idx=g["emphasis_idx"], pop=True)
    ]

    # 3. Hook-Overlay für die ersten 1.8s (Pattern-Interrupt oben im Bild)
    hook_clips = _text_clip(script.get("hook", "").upper(), 96, hook_fill, 0.16,
                            0, min(1.8, duration), max_w_frac=0.9, stroke=9, pop=True)

    final = CompositeVideoClip([bg, *hook_clips, *caption_clips], size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
    final.write_videofile(
        output_path, fps=config.VIDEO_FPS, codec="libx264", audio_codec="aac",
        threads=4, preset="veryfast", logger="bar",
    )

    # Aufräumen
    for f in config.VIDEO_DIR.glob("_bg_*.mp4"):
        f.unlink(missing_ok=True)
    audio.close()
    bg.close()
    final.close()

    logger.info("Video fertiggestellt: %s", output_path)
    return output_path


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    # Testlauf mit dem vorhandenen test_de.wav + einem Dummy-Skript
    test_script = {
        "topic": "self discipline",
        "hook": "Motivation ist eine Lüge.",
    }
    build_video(test_script, str(config.AUDIO_DIR / "test_de.wav"), str(config.VIDEO_DIR / "test_output.mp4"))
