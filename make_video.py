"""
Erzeugt EIN Video zu einem selbst vorgegebenen Thema (statt zufälligem Trend-Thema).
Nutzt dieselbe kostenlose Pipeline wie fulltest.py: Gemini-Skript -> Edge-Stimme ->
Video (Pixabay/prozedural + Musik) -> Titelbild. Lädt NICHTS zu TikTok hoch.

Aufruf:
  python3 make_video.py "Dein Thema/Briefing hier als ein String"          # Kurzform (20-30s)
  python3 make_video.py "Dein Thema/Briefing" --lang                        # Langform (40-60s)
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Nutzung: python3 make_video.py "Thema/Briefing"')
        sys.exit(1)

    theme_hint = sys.argv[1]
    length = "long" if "--lang" in sys.argv else "normal"
    stamp = int(time.time())

    print("1/4  Skript holen (Gemini, Thema vorgegeben) ...")
    script = content_generator.generate_script(theme_hint=theme_hint, length=length)
    src = script.get("source", "gemini/claude")
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
