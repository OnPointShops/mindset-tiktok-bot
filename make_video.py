"""
Erzeugt EIN Video zu einem selbst vorgegebenen Thema (statt zufälligem Trend-Thema).
Nutzt dieselbe kostenlose Pipeline wie fulltest.py: Gemini-Skript -> Edge-Stimme ->
Video (Pixabay/prozedural + Musik) -> Titelbild. Lädt NICHTS zu TikTok hoch.

Aufruf:
  python3 make_video.py --theme "Dein Thema"              # KI schreibt den Text (20-30s)
  python3 make_video.py --theme "Dein Thema" --lang       # Langform (40-60s)
  python3 make_video.py --text "Dein eigener Text"        # wird WORTWOERTLICH gesprochen
  python3 make_video.py --textfile mein_text.txt          # dasselbe aus einer Datei
"""
import json
import logging
import subprocess
import sys
import time

import config
import content_generator
import cover
import tts_engine
import video_builder

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


class _RedactKeys(logging.Filter):
    """Schwärzt API-Keys (…key=XYZ) in Logzeilen, damit sie nie im Terminal/Chat landen."""
    import re as _re
    _pat = _re.compile(r"(key=|xi-api-key[\"': ]+)[A-Za-z0-9_.\-]{12,}")

    def filter(self, record):
        record.msg = self._pat.sub(r"\1***", str(record.getMessage()))
        record.args = ()
        return True


for _h in logging.getLogger().handlers:
    _h.addFilter(_RedactKeys())

if __name__ == "__main__":
    argv = sys.argv[1:]

    def _opt(name):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return None

    # Eigener Sprechtext, wortwoertlich: --text "..."  oder  --textfile pfad.txt
    own_text = _opt("--text")
    tf = _opt("--textfile")
    if tf:
        own_text = open(tf, encoding="utf-8").read()
    own_text = " ".join(own_text.split()) if own_text else None

    flag_vals = {_opt(f) for f in ("--theme", "--text", "--textfile", "--visuals")}
    positional = [a for a in argv if not a.startswith("--") and a not in flag_vals]
    theme_hint = _opt("--theme") or (positional[0] if positional else None)
    if not theme_hint and own_text:
        theme_hint = own_text[:200]
    if not theme_hint:
        print('Nutzung: python3 make_video.py --theme "Thema"   oder   --text "eigener Sprechtext"')
        sys.exit(1)

    long_text = own_text and len(own_text.split()) > 60
    length = "long" if ("--lang" in argv or long_text) else "normal"
    stamp = int(time.time())

    if own_text:
        theme_hint = (
            "Der Sprechtext steht bereits fest und wird WORTWOERTLICH vorgelesen:\n\"" + own_text +
            "\"\nErzeuge passend dazu Hook (max. 6 Woerter, Kernsatz aus diesem Text), cover_slogan, "
            "Caption/Hashtags und visual_queries, die dem Verlauf dieses Textes folgen.")

    print("1/4  Skript holen (Gemini, Thema vorgegeben) ...")
    script = content_generator.generate_script(theme_hint=theme_hint, length=length)
    if own_text:
        script["full_voiceover_text"] = own_text
    # Eigene Bild-Suchen erzwingen: --visuals "suche 1 | suche 2 | suche 3" (englisch, je Segment eine)
    qs_raw = _opt("--visuals")
    if qs_raw:
        qs = [q.strip() for q in qs_raw.split("|") if q.strip()]
        if qs:
            script["visual_queries"] = qs
            content_generator._normalize_visual_queries(script)
    src = script.get("source", "gemini/claude")
    if src == "offline":
        print("\nABBRUCH: Die KI war nicht erreichbar, das Offline-Skript passt NICHT zu deinem Thema.\n"
              "Starte den gleichen Befehl in 1-2 Minuten nochmal (Gemini ist dann meist wieder frei).")
        sys.exit(2)
    print(f"     Thema: {script['topic']}   (Quelle: {src})")
    print(f"     Hook:  {script['hook']}")

    wav = str(config.AUDIO_DIR / f"custom_{stamp}.wav")
    mp4 = str(config.VIDEO_DIR / f"custom_{stamp}.mp4")
    png = str(config.VIDEO_DIR / f"custom_{stamp}_cover.png")

    print("2/4  Stimme erzeugen ...")
    tts_engine.synthesize(script["full_voiceover_text"], wav)
    print("3/4  Video bauen (1-3 Min) ...")
    video_builder.build_video(script, wav, mp4)
    print("4/4  Titelbild ...")
    cover.make_cover(script, png)

    print("\nFERTIG:\n ", mp4, "\n ", png)
    (config.CONTENT_DIR / f"custom_{stamp}_script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        subprocess.run(["open", "-a", "Preview", png])
        subprocess.run(["open", "-a", "QuickTime Player", mp4])
    except Exception:  # noqa: BLE001
        pass
