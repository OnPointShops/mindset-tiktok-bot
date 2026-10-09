"""
Karussell-Generator: Text-Posts im Stil der Vorlage (schwarzer Grund, weiße
Serifenschrift, große Typo, viel Luft).

Warum das Format: Produktionskosten praktisch null (keine Stock-Clips, kein TTS,
keine Render-Zeit), und es ist genau das Format, das in der Nische
"Business/KI/Selbstständigkeit" auf Instagram die höchste Speicher- und
Teilen-Rate hat. Speichern ist dort das stärkste Reichweiten-Signal.

Ausgabe: 1080x1350 PNG pro Slide (Instagram-Feed-Maximum im Hochformat).
"""
from __future__ import annotations

import logging
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

log = logging.getLogger("carousel")

WIDTH, HEIGHT = 1080, 1350
MARGIN_X = 90
MARGIN_TOP = 110
MARGIN_BOTTOM = 120
BG = (0, 0, 0)
FG = (255, 255, 255)
DIM = (150, 150, 150)
MAX_FONT = 104   # Obergrenze, sonst wirken 3-Wort-Slides wie ein Schreifehler

# Serifenschrift, fett — in dieser Reihenfolge gesucht.
# Playfair/Georgia treffen die Vorlage am genauesten; DejaVu/Liberation sind der
# Fallback, der auf jedem Linux-Server ohne Zusatzinstallation vorhanden ist.
FONT_CANDIDATES = [
    str(config.ASSETS_DIR / "fonts" / "PlayfairDisplay-Bold.ttf"),
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
]

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        for path in FONT_CANDIDATES:
            if Path(path).exists():
                _font_cache[size] = ImageFont.truetype(path, size)
                break
        else:
            log.warning("Keine Serifenschrift gefunden — Default-Font (sieht schlechter aus).")
            _font_cache[size] = ImageFont.load_default(size=size)
    return _font_cache[size]


# ── Textumbruch nach Pixelbreite (nicht nach Zeichenzahl) ──────────────────────
def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        probe = f"{cur} {w}".strip()
        if draw.textlength(probe, font=font) <= max_width or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _measure(draw, blocks: list[dict], size: int, max_width: int) -> tuple[int, list]:
    """Berechnet die Gesamthöhe aller Blöcke bei Schriftgröße `size`."""
    laid_out, total = [], 0
    for b in blocks:
        if b["type"] == "space":
            h = int(size * b.get("factor", 0.8))
            laid_out.append(("space", h, None))
            total += h
            continue

        fsize = size if b["type"] != "small" else int(size * 0.55)
        font = _font(fsize)
        line_h = int(fsize * 1.28)

        if b["type"] == "bullet":
            # Hängender Einzug: Folgezeilen stehen unter dem Text, nicht unter dem Punkt.
            indent = int(fsize * 1.1)
            prefix = "•  "
            prefix_w = int(draw.textlength(prefix, font=font))
            raw = _wrap(draw, b["text"], font, max_width - indent - prefix_w)
            lines = [(prefix + raw[0], indent)] if raw else []
            lines += [(ln, indent + prefix_w) for ln in raw[1:]]
        else:
            lines = [(ln, 0) for ln in _wrap(draw, b["text"], font, max_width)]

        block_h = line_h * len(lines)
        laid_out.append((b["type"], block_h, (lines, font, line_h)))
        total += block_h
    return total, laid_out


def render_slide(blocks: list[dict], out_path: str, base_size: int = 68,
                 footer: str | None = None, page: str | None = None) -> str:
    """
    Rendert eine Slide. `blocks` ist eine Liste aus:
      {"type": "head"|"text"|"bullet"|"small", "text": "..."}  oder
      {"type": "space", "factor": 0.8}

    Die Schriftgröße wird automatisch verkleinert, bis der Inhalt passt —
    so kann der Generator beliebig lange Texte bekommen, ohne dass etwas abgeschnitten wird.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    max_width = WIDTH - 2 * MARGIN_X
    usable_h = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

    # Schrift automatisch an die Textmenge anpassen: erst verkleinern bis es passt,
    # dann vergrößern bis die Fläche gut gefüllt ist. Ergebnis: kurze Slides wirken
    # plakativ (große Typo), lange Slides bleiben lesbar — ohne Handarbeit.
    size = base_size
    total, laid_out = _measure(draw, blocks, size, max_width)
    while total > usable_h and size > 26:
        size -= 2
        total, laid_out = _measure(draw, blocks, size, max_width)
    while total < usable_h * 0.80 and size < MAX_FONT:
        probe_size = size + 2
        probe_total, probe_layout = _measure(draw, blocks, probe_size, max_width)
        if probe_total > usable_h:
            break
        size, total, laid_out = probe_size, probe_total, probe_layout
    if total > usable_h:
        log.warning("Slide-Text zu lang, wird bei Größe %d trotzdem gerendert: %s",
                    size, out_path)

    # vertikal mittig, leicht nach oben versetzt (wirkt optisch ausgewogener)
    y = MARGIN_TOP + max(0, (usable_h - total) // 2) - 20

    for kind, block_h, payload in laid_out:
        if kind == "space" or payload is None:
            y += block_h
            continue
        lines, font, line_h = payload
        color = DIM if kind == "small" else FG
        for ln, x_off in lines:
            draw.text((MARGIN_X + x_off, y), ln, font=font, fill=color)
            y += line_h

    if footer:
        f = _font(32)
        draw.text((MARGIN_X, HEIGHT - 72), footer, font=f, fill=DIM)
    if page:
        f = _font(32)
        w = draw.textlength(page, font=f)
        draw.text((WIDTH - MARGIN_X - w, HEIGHT - 72), page, font=f, fill=DIM)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)
    return out_path


# ── Skript -> Slides ───────────────────────────────────────────────────────────
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def slides_from_script(script: dict, handle: str = "") -> list[list[dict]]:
    """
    Baut aus einem vorhandenen Skript (hook/body/cta) eine Slide-Folge.
    Nutzt bewusst KEINEN zusätzlichen KI-Aufruf — das Skript ist schon bezahlt.

    Aufbau nach dem Muster, das in der Nische funktioniert:
      1  Hook (groß, allein)
      2+ je ein Gedanke pro Slide, nummeriert als "Schritt N" wenn es eine
         Anleitung ist, sonst als Fließtext
      n  CTA + Handle
    """
    hook = (script.get("hook") or "").strip()
    body = (script.get("body") or "").strip()
    cta = (script.get("cta") or "").strip()
    bullets = script.get("bullets") or []

    sentences = [s.strip() for s in _SENT_SPLIT.split(body) if s.strip()]
    slides: list[list[dict]] = []

    # Slide 1 — Hook
    slides.append([{"type": "head", "text": hook or script.get("topic", "")}])

    # Mittelteil — je 1-2 Sätze pro Slide, damit Typo groß bleibt
    step = 1
    i = 0
    while i < len(sentences):
        chunk = sentences[i:i + 2]
        blocks: list[dict] = [{"type": "head", "text": f"Schritt {step}"},
                              {"type": "space", "factor": 0.6}]
        for s in chunk:
            blocks.append({"type": "text", "text": s})
            blocks.append({"type": "space", "factor": 0.45})
        slides.append(blocks)
        step += 1
        i += 2

    # Optionale Aufzählungs-Slide
    if bullets:
        blocks = [{"type": "head", "text": script.get("bullets_title", "Das Wichtigste:")},
                  {"type": "space", "factor": 0.7}]
        for b in bullets:
            blocks.append({"type": "bullet", "text": str(b)})
            blocks.append({"type": "space", "factor": 0.25})
        slides.append(blocks)

    # Letzte Slide — CTA
    last = [{"type": "head", "text": cta or "Speicher dir das."}]
    if handle:
        last += [{"type": "space", "factor": 1.2}, {"type": "small", "text": handle}]
    slides.append(last)

    return slides


def make_carousel(script: dict, out_dir: str | Path, handle: str = "",
                  max_slides: int = 8) -> list[str]:
    """Rendert die komplette Slide-Folge und gibt die Pfade in Reihenfolge zurück."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("slide_*.png"):
        old.unlink()

    slides = slides_from_script(script, handle)[:max_slides]
    paths = []
    for n, blocks in enumerate(slides, start=1):
        p = out_dir / f"slide_{n:02d}.png"
        page = None if n == 1 else f"{n}/{len(slides)}"
        render_slide(blocks, str(p), footer=handle if n == 1 and handle else None, page=page)
        paths.append(str(p))
    log.info("Karussell gerendert: %d Slides in %s", len(paths), out_dir)
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo = {
        "topic": "Faceless Account aufbauen",
        "hook": "So baust du eine Seite auf, die ohne dich läuft",
        "body": (
            "Wähle eine Nische, die dauerhaft gefragt ist. "
            "Finde die zehn stärksten Seiten darin und analysiere ihre besten Beiträge. "
            "Die KI schreibt die Texte, ein Generator baut die Bilder. "
            "Ein Planer veröffentlicht automatisch, Tag für Tag. "
            "Funktioniert eine Seite, baust du die nächste."
        ),
        "bullets": ["Business", "Künstliche Intelligenz", "Gesundheit", "Fitness"],
        "bullets_title": "Dauerhaft gefragte Themen:",
        "cta": "Speicher dir das, bevor du es wieder vergisst.",
    }
    out = make_carousel(demo, config.VIDEO_DIR / "carousels" / "demo", handle="@dein_account")
    print("\n".join(out))
