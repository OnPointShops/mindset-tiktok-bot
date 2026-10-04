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


def _overlay_png(path: Path) -> str:
    """Schwarze Vignette + Verlauf unten (Untertitel) / oben (Hook) als RGBA-PNG - gleiche Werte wie
    der frühere Python-Overlay-Pfad."""
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    vig = np.clip((((xs / W - 0.5) * 1.5) ** 2 + ((ys / H - 0.5) * 1.3) ** 2) * 0.8, 0, 0.72)
    bottom = np.clip((ys / H - 0.5) / 0.5, 0, 1) ** 1.5 * 0.55
    top = np.clip((0.28 - ys / H) / 0.28, 0, 1) * 0.35
    alpha = np.clip(vig + bottom + top, 0, 0.82)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(path)
    return str(path)


def render_background(parts: list[dict], duration: float, out_path: str, bw: bool = True) -> str:
    """parts: [{"path": str, "dur": float, "image": bool}, ...] in Reihenfolge; Summe(dur) ~ duration.
    Schreibt ein stummes 1080x1920/30fps-H.264-Video exakt `duration` Sekunden lang nach out_path."""
    if not parts:
        raise RuntimeError("Keine Hintergrund-Quellen")
    overlay = _overlay_png(Path(out_path).with_suffix(".overlay.png"))

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
        z = 0.06 if p.get("image") else 0.09
        d = max(p["dur"], 0.5)
        # 1) mittig auf 9:16 zuschneiden, 2) EIN Skalierschritt mit Zoom (eval=frame), 3) auf 1080x1920 croppen
        chains.append(
            f"[{i}:v]crop='min(iw\\,ih*{W}/{H})':'min(ih\\,iw*{H}/{W})',setsar=1,fps={FPS},"
            f"scale=w='{W}*(1+{z}*t/{d:.3f})':h='{H}*(1+{z}*t/{d:.3f})':eval=frame:flags=bilinear,"
            f"crop={W}:{H},setpts=PTS-STARTPTS[v{i}]")
    concat_in = "".join(f"[v{i}]" for i in range(len(parts)))
    chains.append(f"{concat_in}concat=n={len(parts)}:v=1:a=0[cat]")

    look = "[cat]"
    if bw:
        # gleiche Kurve wie früher: entsättigen, Kontrast 1.38 um Mittelgrau, Schwarz/Weiß nie ganz clippen
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
        raise RuntimeError("ffmpeg-Hintergrund fehlgeschlagen: " + r.stderr.decode(errors="replace")[-400:])
    return out_path
