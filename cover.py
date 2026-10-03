"""Erzeugt ein Titelbild (1080x1920 PNG) zum Thema: Hintergrund + Hook-Text. Kein Key nötig."""
import logging
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import backgrounds
import config

logger = logging.getLogger("cover")
# Impact zuerst: kräftige, kondensierte Groteskschrift -> Street-Art-Zitat-Poster-Look
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Impact.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def find_font(size: int):
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size=size)


def make_cover(script: dict, out_path: str) -> str:
    bg = backgrounds._procedural(4.0, script.get("topic", "x") + script.get("hook", ""))
    frame = bg.get_frame(3.0)
    if backgrounds.VISUAL_STYLE == "street_bw":
        frame = backgrounds._bw_grade_frame(frame)
    img = Image.fromarray(frame).convert("RGB")
    d = ImageDraw.Draw(img)
    font = find_font(110)
    hook_color = (255, 255, 255) if backgrounds.VISUAL_STYLE == "street_bw" else (255, 235, 90)
    lines = textwrap.wrap(script.get("hook", "").upper(), width=14)
    line_h = 135
    y = (config.VIDEO_HEIGHT - line_h * len(lines)) // 2 - 80
    for ln in lines:
        w = d.textlength(ln, font=font)
        x = (config.VIDEO_WIDTH - w) / 2
        d.text((x, y), ln, font=font, fill=hook_color, stroke_width=9, stroke_fill=(0, 0, 0))
        y += line_h
    tag = find_font(48)
    t = script.get("topic", "").upper()
    d.text(((config.VIDEO_WIDTH - d.textlength(t, font=tag)) / 2, y + 60), t, font=tag,
           fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    img.save(out_path)
    logger.info("Titelbild: %s", out_path)
    return out_path
