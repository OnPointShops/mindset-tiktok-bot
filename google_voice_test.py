"""
Fragt bei Google alle deutschen MÄNNERSTIMMEN ab, erzeugt von den besten eine Hörprobe
(mit dem Jarvis-Effekt) und spielt sie nacheinander ab. Du merkst dir den Namen deiner Favoritin
und trägst ihn in .env ein:  GOOGLE_VOICE=<name>
Aufruf:  python3 google_voice_test.py        (benötigt GOOGLE_TTS_API_KEY in .env)
"""
import base64
import subprocess
import sys

import requests

import config
import tts_engine

KEY = tts_engine.GOOGLE_TTS_API_KEY
SAMPLE = ("Disziplin schlägt Motivation. Jeden Tag. Auch wenn du keine Lust hast. "
          "Fang heute an, nicht wenn du bereit bist.")
PRIORITY = ["Chirp3-HD", "Studio", "Neural2", "Wavenet"]  # Qualität absteigend (Chirp 3 HD: 1 Mio Zeichen gratis)


def main():
    if not KEY:
        sys.exit("GOOGLE_TTS_API_KEY fehlt in .env")
    r = requests.get("https://texttospeech.googleapis.com/v1/voices",
                     params={"languageCode": "de-DE", "key": KEY}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google meldet Fehler {r.status_code}: {r.text[:400]}")
    male = [v for v in r.json().get("voices", []) if v.get("ssmlGender") == "MALE"]
    if not male:
        sys.exit("Keine männlichen Stimmen gefunden.")

    def rank(v):
        for i, t in enumerate(PRIORITY):
            if t.lower() in v["name"].lower():
                return i
        return len(PRIORITY)
    male.sort(key=lambda v: (rank(v), v["name"]))
    chosen = male[:8]
    print("Gefundene deutsche Männerstimmen (beste zuerst):")
    for v in male:
        print("  ", v["name"])
    print()
    for v in chosen:
        name = v["name"]
        out = str(config.AUDIO_DIR / f"voicetest_{name}.wav")
        body = {"input": {"text": SAMPLE},
                "voice": {"languageCode": "de-DE", "name": name},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}
        rr = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize",
                           params={"key": KEY}, json=body, timeout=60)
        if rr.status_code != 200:
            print(f"-- {name}: übersprungen ({rr.status_code})")
            continue
        open(out, "wb").write(base64.b64decode(rr.json()["audioContent"]))
        tts_engine._apply_voice_fx(out)
        print(f">> Spiele: {name}")
        subprocess.run(["afplay", out])
    print("\nFavorit gefunden? Dann in .env:  GOOGLE_VOICE=<Name>   und   TTS_BACKEND=google")


if __name__ == "__main__":
    main()
