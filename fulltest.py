"""
KOMPLETT-TEST der kostenlosen Pipeline, Ende zu Ende:
  Gemini-Skript -> Edge-Stimme -> Video (Pixabay/prozedural) -> Titelbild.
Nutzt KEINE TikTok-Verbindung, lädt NICHTS hoch. Nur zum Anschauen.
Aufruf:  python3 fulltest.py
"""
import json
import logging
import subprocess

import config
import content_generator
import cover
import tts_engine
import video_builder

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

if __name__ == "__main__":
    print("1/4  Skript holen (Gemini, sonst Vorrat) ...")
    script = content_generator.generate_script()
    src = script.get("source", "gemini/claude")
    print(f"     Thema: {script['topic']}   (Quelle: {src})")
    print(f"     Hook:  {script['hook']}")

    wav = str(config.AUDIO_DIR / "fulltest.wav")
    mp4 = str(config.VIDEO_DIR / "fulltest.mp4")
    png = str(config.VIDEO_DIR / "fulltest_cover.png")

    print("2/4  Stimme erzeugen ...")
    tts_engine.synthesize(script["full_voiceover_text"], wav)
    print("3/4  Video bauen (1-3 Min) ...")
    video_builder.build_video(script, wav, mp4)
    print("4/4  Titelbild ...")
    cover.make_cover(script, png)

    print("\nFERTIG:\n ", mp4, "\n ", png)
    (config.CONTENT_DIR / "fulltest_script.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        subprocess.run(["open", "-a", "Preview", png]); subprocess.run(["open", "-a", "QuickTime Player", mp4])
    except Exception:  # noqa: BLE001
        pass
