"""
Hörproben ALLER deutschen Edge-Männerstimmen (kostenlos, kein Key, keine Karte).
Jede Stimme wird zweimal gespielt:  (A) normaler Jarvis-Effekt   (B) "deep" – tiefer & mehr Raum.
Merk dir Stimme + Variante und trag sie in .env ein. Aufruf:  python3 edge_voice_test.py
"""
import asyncio
import os
import subprocess
import sys

import edge_tts

import config
import tts_engine as T

SAMPLE = ("Motivation ist eine Lüge. Disziplin ist die Entscheidung, "
          "es trotzdem zu tun. Fang heute an, nicht wenn du bereit bist.")


async def list_male():
    voices = await edge_tts.list_voices()
    de = [v for v in voices if v["Locale"].startswith("de-") and v["Gender"] == "Male"]
    # Multilingual-Stimmen (klingen am besten) nach vorn
    de.sort(key=lambda v: (0 if "Multilingual" in v["ShortName"] else 1, v["ShortName"]))
    return de


async def render(voice, pitch, rate, out):
    comm = edge_tts.Communicate(SAMPLE, voice, rate=rate, pitch=pitch)
    await comm.save(out)


def main():
    de = asyncio.run(list_male())
    if not de:
        sys.exit("Keine deutschen Männerstimmen gefunden (Internet an?).")
    print("Gefundene deutsche Männerstimmen:")
    for v in de:
        print("  ", v["ShortName"])
    print("\nJetzt Hörproben — je Stimme: [A]=normal, [B]=deep\n")

    for v in de:
        name = v["ShortName"]
        for label, pitch, rate, fxpitch in [("A-normal", "-6Hz", "-4%", "0.96"),
                                            ("B-deep", "-18Hz", "-7%", "0.90")]:
            mp3 = str(config.AUDIO_DIR / f"evt_{name}_{label}.mp3")
            wav = mp3.replace(".mp3", ".wav")
            try:
                asyncio.run(render(name, pitch, rate, mp3))
            except Exception as e:  # noqa: BLE001
                print(f"-- {name} {label}: übersprungen ({e})")
                continue
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                            "-ac", "1", "-ar", "24000", wav], check=True)
            os.environ["VOICE_PITCH"] = fxpitch
            import importlib
            importlib.reload(T)  # FX-Pitch neu einlesen
            T._apply_voice_fx(wav)
            print(f">> {name}   [{label}]")
            subprocess.run(["afplay", wav])
    print("\nFavorit? In .env eintragen, z.B.:")
    print("  EDGE_VOICE=de-DE-ConradNeural")
    print("  Für 'deep':  EDGE_PITCH=-18Hz   EDGE_RATE=-7%   VOICE_PITCH=0.90")


if __name__ == "__main__":
    main()
