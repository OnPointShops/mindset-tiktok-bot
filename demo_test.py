"""
Testlauf OHNE API-Keys: Beispiel-Skript -> Stimme -> Video (+ Titelbild).
Ergebnis: videos/demo.mp4 und videos/demo_cover.png  (öffnet sich automatisch auf dem Mac)
Aufruf:  python3 demo_test.py            oder      python3 demo_test.py 2   (anderes Beispiel)
"""
import logging
import subprocess
import sys

import config
import cover
import tts_engine
import video_builder

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

DEMOS = [
    {
        "topic": "Disziplin schlägt Motivation",
        "hook": "Motivation ist eine Lüge.",
        "full_voiceover_text": (
            "Motivation ist eine Lüge. Sie kommt und geht, wie das Wetter. "
            "Disziplin ist die Entscheidung, es trotzdem zu tun. Auch wenn du keine Lust hast. "
            "Vor allem dann. Fang heute an, nicht wenn du bereit bist."
        ),
        "visual_query": "man running sunrise",
    },
    {
        "topic": "Der erste Schritt",
        "hook": "Du wartest auf den perfekten Moment?",
        "full_voiceover_text": (
            "Du wartest auf den perfekten Moment? Er kommt nie. "
            "Jeder, der heute vorn steht, hat unvorbereitet angefangen. "
            "Der perfekte Plan schlägt keinen unperfekten Start. Mach den ersten Schritt. Jetzt."
        ),
        "visual_query": "mountain climbing",
    },
]

if __name__ == "__main__":
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 0
    script = DEMOS[idx % len(DEMOS)]
    wav = str(config.AUDIO_DIR / "demo.wav")
    mp4 = str(config.VIDEO_DIR / "demo.mp4")
    png = str(config.VIDEO_DIR / "demo_cover.png")

    print("1/3 Stimme erzeugen ...")
    tts_engine.synthesize(script["full_voiceover_text"], wav)
    print("2/3 Video bauen (dauert 1-3 Minuten) ...")
    video_builder.build_video(script, wav, mp4)
    print("3/3 Titelbild ...")
    cover.make_cover(script, png)
    print("\nFERTIG:\n ", mp4, "\n ", png)
    try:
        subprocess.run(["open", "-a", "Preview", png]); subprocess.run(["open", "-a", "QuickTime Player", mp4])
    except Exception:  # noqa: BLE001
        pass
