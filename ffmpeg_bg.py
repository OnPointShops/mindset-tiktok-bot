"""
Hintergrund-Rendering komplett in ffmpeg (nativ, C-Geschwindigkeit) statt Frame für Frame in Python.

Warum: moviepy rechnet jedes 1080x1920-Frame in Python/numpy (Zoom, S/W-Grading, Vignette, Korn,
mehrere Composite-Ebenen) - das dauerte pro Videosekunde viele Sekunden. Hier läuft alles in EINEM
ffmpeg-Aufruf: Clips -> Cover-Crop -> Zoom -> aneinanderhängen -> S/W + Kontrast -> Vignette -> Korn.
Danach legt moviepy nur noch die Captions über die fertige Datei (billig).

Jeder Fehler wirft eine Exception -> backgrounds.get_background() fällt auf den alten Pfad zurück.
"""
import logging
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

import config

logger = logging.getLogger("ffmpeg_bg")
W, H, FPS = config.VIDEO_WIDTH, config.VIDEO_HEIGHT, 30


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # kommt mit moviepy -> immer vorhanden
    return imageio_ffmpeg.get_ffmpeg_exe()


def _overlay_png(path: Path, style: str = "street_bw") -> str:
    """Schwarze Vignette + Verlauf unten (Untertitel) / oben (Hook) als RGBA-PNG - gleiche Werte wie
    der frühere Python-Overlay-Pfad."""
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = np.clip((((xs / W - 0.5) * 1.5) ** 2 + ((ys / H - 0.5) * 1.3) ** 2) * 0.8, 0, 0.72)
    bottom = np.clip((ys / H - 0.5) / 0.5, 0, 1) ** 1.5 * 0.55
    top = np.clip((0.28 - ys / H) / 0.28, 0, 1) * 0.35
    alpha = np.clip(vig + bottom + top, 0, 0.82)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")
    if style == "street_modern":
        img = _street_marks(img)
    img.save(path)
    return str(path)


def _street_marks(img):
    """Moderner Street-Art-Look: rote Spruehfarbe (Spritzer + Drips), Klebeband-Ecke, Stencil-Pfeil/Kreuz-Marken.
    Zufaellig pro Video, bleibt aber in Raendern (Untertitel/Gesichter in der Mitte bleiben frei)."""
    import random
    from PIL import ImageDraw, ImageFilter
    rnd = random.Random()
    RED = (222, 30, 36)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # Spruehnebel-Spritzer in einer Ecke oben (hinter Hook-Text, aber nicht im Gesichtsbereich)
    cx = rnd.choice([int(W * 0.12), int(W * 0.88)])
    cy = rnd.randint(int(H * 0.05), int(H * 0.12))
    for _ in range(260):
        r = rnd.gauss(0, 120)
        a = rnd.uniform(0, 6.283)
        x, y = cx + r * np.cos(a), cy + r * np.sin(a) * 0.8
        s = max(1.5, rnd.expovariate(1 / 7))
        d.ellipse([x - s, y - s, x + s, y + s], fill=RED + (rnd.randint(110, 235),))
    soft = layer.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(soft, layer)
    d = ImageDraw.Draw(layer)
    # Farbkern + Drips
    d.ellipse([cx - 70, cy - 55, cx + 70, cy + 55], fill=RED + (225,))
    for k in range(rnd.randint(3, 5)):
        x = cx + rnd.randint(-60, 60)
        ln = rnd.randint(120, 380)
        wd = rnd.randint(5, 10)
        d.rounded_rectangle([x - wd, cy, x + wd, cy + ln], radius=wd, fill=RED + (225,))
        d.ellipse([x - wd - 3, cy + ln - wd, x + wd + 3, cy + ln + wd * 1.4], fill=RED + (225,))
    # Klebeband-Streifen unten links/rechts
    tape = Image.new("RGBA", (360, 70), (235, 228, 205, 215)).rotate(rnd.choice([-32, 30]), expand=True)
    tx = rnd.choice([-60, W - 300])
    layer.alpha_composite(tape, (tx, int(H * 0.93)))
    # Stencil-Kreuzmarken (Registrierkreuze) an den Raendern
    for (x, y) in ((70, 70), (W - 70, H - 70)):
        d.line([x - 26, y, x + 26, y], fill=(255, 255, 255, 200), width=4)
        d.line([x, y - 26, x, y + 26], fill=(255, 255, 255, 200), width=4)
    # Schmale rote Balkenmarke vertikal am Rand (wie Poster-Streifen)
    bx = rnd.choice([34, W - 52])
    d.rectangle([bx, int(H * 0.30), bx + 18, int(H * 0.52)], fill=RED + (235,))
    return Image.alpha_composite(img, layer)


def render_background(parts, duration, out_path, bw=True, style="street_bw"):
    """Erst mit Zoom; scheitert die lokale ffmpeg-Version daran, nochmal ohne Zoom (statisch, aber schnell)."""
    try:
        return _render(parts, duration, out_path, bw, style, zoom=True)
    except RuntimeError as e:
        logger.warning("ffmpeg mit Zoom fehlgeschlagen (%s) -> Versuch ohne Zoom", str(e)[:300])
        return _render(parts, duration, out_path, bw, style, zoom=False)


def _render(parts: list[dict], duration: float, out_path: str, bw: bool = True,
            style: str = "street_bw", zoom: bool = True) -> str:
    """parts: [{"path": str, "dur": float, "image": bool}, ...] in Reihenfolge; Summe(dur) ~ duration.
    Schreibt ein stummes 1080x1920/30fps-H.264-Video exakt `duration` Sekunden lang nach out_path."""
    if not parts:
        raise RuntimeError("Keine Hintergrund-Quellen")
    overlay = _overlay_png(Path(out_path).with_suffix(".overlay.png"), style)

    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error"]
    for p in parts:
        if p.get("image"):
            cmd += ["-loop", "1", "-t", f"{p['dur']:.3f}", "-i", p["path"]]
        else:
            cmd += ["-stream_loop", "-1", "-t", f"{p['dur']:.3f}", "-i", p["path"]]
    cmd += ["-loop", "1", "-i", overlay]
    ov_idx = len(parts)

    chains = []
    for i, p in enumerate(parts):
        z = (0.06 if p.get("image") else 0.09) if zoom else 0.0
        d = max(p["dur"], 0.5)
        # 1) mittig auf 9:16 zuschneiden, 2) EIN Skalierschritt mit Zoom (eval=frame), 3) auf 1080x1920 croppen
        chains.append(
            f"[{i}:v]crop='min(iw\\,ih*{W}/{H})':'min(ih\\,iw*{H}/{W})',setsar=1,fps={FPS},"
            f"scale=w='2*trunc({W}*(1+{z}*t/{d:.3f})/2)':h='2*trunc({H}*(1+{z}*t/{d:.3f})/2)':eval=frame:flags=bilinear,"
            f"crop={W}:{H},setpts=PTS-STARTPTS[v{i}]")
    concat_in = "".join(f"[v{i}]" for i in range(len(parts)))
    chains.append(f"{concat_in}concat=n={len(parts)}:v=1:a=0[cat]")

    look = "[cat]"
    if bw:
        # gleiche Kurve wie früher: entsättigen, Kontrast 1.38 um Mittelgrau, Schwarz/Weiß nie ganz clippen
        if style == "street_modern":
            # harte S-Kurve (Stencil/Poster-Look): tiefes Schwarz, helles Weiss, wenig Mitteltoene
            chains.append("[cat]hue=s=0,eq=contrast=1.55:brightness=-0.03,"
                          "curves=all='0/0 0.22/0.07 0.5/0.5 0.78/0.94 1/1',"
                          "lutyuv=y='clip(val\\,8\\,247)',format=yuv420p[bw]")
        else:
            chains.append("[cat]hue=s=0,eq=contrast=1.38,lutyuv=y='clip(val\\,6\\,249)',format=yuv420p[bw]")
        look = "[bw]"
    else:
        chains.append("[cat]format=yuv420p[col]")
        look = "[col]"
    # yuva420p-Overlay ist ~4x billiger als rgba (gemessen); Filmkorn entfällt im nativen Pfad
    # (noise-Filter kostete ~120% Mehrzeit, H.264 verschluckt feines Korn ohnehin).
    chains.append(f"[{ov_idx}:v]format=yuva420p[ov]")
    chains.append(f"{look}[ov]overlay=0:0:shortest=1:format=yuv420,"
                  f"tpad=stop_mode=clone:stop_duration=3,format=yuv420p[out]")

    cmd += ["-filter_complex", ";".join(chains), "-map", "[out]", "-t", f"{duration:.3f}",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
            "-pix_fmt", "yuv420p", "-an", out_path]
    r = subprocess.run(cmd, capture_output=True, timeout=900)
    Path(overlay).unlink(missing_ok=True)
    if r.returncode != 0 or not Path(out_path).exists():
        raise RuntimeError("ffmpeg-Hintergrund fehlgeschlagen: " + r.stderr.decode(errors="replace")[:500])
    return out_path
