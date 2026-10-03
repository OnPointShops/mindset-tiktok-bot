"""
TTS-Engine mit drei Backends — alle kostenlos nutzbar:

1. PIPER (default, EMPFOHLEN für Deutsch) — 100% lokal, 0€, native deutsche Stimme
   (Thorsten-Voice), klingt wie ein echter Sprecher. Läuft auf jedem CPU ohne GPU.
   → TTS_BACKEND=piper (Standard)

2. Kokoro (lokal, kostenlos, ONNX) — sehr schnell (~2s), aber Englisch-Modell;
   Deutsch mit hörbarem Akzent. Gut für EN-Inhalte.
   → TTS_BACKEND=kokoro

3. Fish Audio S2 Pro (Cloud, ~15€/1M Zeichen) — native deutsche Stimmen,
   Premium-Qualität. Braucht API-Key.
   → TTS_BACKEND=fish

Default: Piper (beste kostenlose DE-Qualität). Nur .env ändern zum Umschalten.

Piper-Setup (einmalig, läuft dann lokal):
  pip install piper-tts
  Stimmmodell herunterladen:
    mkdir -p assets/piper
    cd assets/piper
    wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx
    wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json
  Fertig — alles läuft danach offline.
"""
import os
import subprocess
import logging
import requests
import soundfile as sf
from pathlib import Path

import config

logger = logging.getLogger("tts_engine")

TTS_BACKEND = os.getenv("TTS_BACKEND", "edge")  # "google" | "edge" | "piper" | "kokoro" | "fish"
GOOGLE_TTS_API_KEY = os.getenv("GOOGLE_TTS_API_KEY", "")
GOOGLE_VOICE = os.getenv("GOOGLE_VOICE", "de-DE-Chirp3-HD-Charon")
GOOGLE_RATE = float(os.getenv("GOOGLE_RATE", "0.95"))
# ConradNeural klingt von Haus aus älter/tiefer als Florian -> bessere Basis für die
# "hat-selbst-gelitten"-Erzähler-Stimme. Pitch/Rate hier bewusst MILD: die Tiefe/Rauheit
# kommt aus der FX-Kette (Bass/EQ/Kompressor/Hall) unten, nicht aus starkem Pitch-Shift -
# zu viel Pitch-Shift an der Quelle + nochmal in der FX-Kette hat vorher Artefakte/Verzerrung
# erzeugt ("Ton schlecht").
EDGE_VOICE = os.getenv("EDGE_VOICE", "de-DE-ConradNeural")  # alt: de-DE-KillianNeural, de-DE-FlorianMultilingualNeural
EDGE_RATE = os.getenv("EDGE_RATE", "-6%")    # leicht langsamer, bedeutungsvoller, aber artefaktarm
EDGE_PITCH = os.getenv("EDGE_PITCH", "-6Hz")
FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "")

# Piper-Stimmmodell (Thorsten-Voice, native Deutsch)
PIPER_MODEL = config.ASSETS_DIR / "piper" / "de_DE-thorsten-high.onnx"
PIPER_CONFIG = config.ASSETS_DIR / "piper" / "de_DE-thorsten-high.onnx.json"

_kokoro_instance = None


# ── Piper Backend ──────────────────────────────────────────────────────────────


# --- Stimm-Veredelung ---
# "grimdark" -> tief, rau, narbig, episch (jemand, der selbst gelitten hat)   [DEFAULT]
# "jarvis"   -> tiefer, ruhiger, warm, leichter Raum (der alte, saubere Sound)
# "off"      -> Original-Stimme unbearbeitet
VOICE_FX = os.getenv("VOICE_FX", "grimdark")
# <1 = zusätzlicher Pitch-Shift in der FX-Kette, ZUSÄTZLICH zu EDGE_PITCH oben.
# Default 1.0 = AUS, weil EDGE_PITCH die Tiefe schon sauber an der Quelle erzeugt -
# zwei Pitch-Shifts hintereinander (asetrate/atempo ist ein Resample-Trick, kein echter
# Pitch-Shifter) haben vorher hörbare Artefakte/Verzerrung produziert.
VOICE_PITCH = float(os.getenv("VOICE_PITCH", "1.0"))


def _apply_voice_fx(wav_path: str) -> str:
    """Veredelt die Rohstimme per ffmpeg. Bei Fehler: Original bleibt unangetastet."""
    if VOICE_FX == "off":
        return wav_path
    import shutil
    if not shutil.which("ffmpeg"):
        logger.warning("ffmpeg fehlt — Stimme bleibt unbearbeitet")
        return wav_path
    try:
        sr = sf.info(wav_path).samplerate
    except Exception:  # noqa: BLE001
        sr = 22050

    pitch_stage = ""
    if abs(VOICE_PITCH - 1.0) > 0.001:
        pitch_stage = f"asetrate={int(sr * VOICE_PITCH)},aresample={sr},atempo={1 / VOICE_PITCH:.4f},"

    if VOICE_FX == "grimdark":
        # Kein Bit-Crush mehr (klang kaputt statt episch). Tiefe/Rauheit kommen aus:
        # Brust-Resonanz anheben, harte Zischlaute dämpfen, strammer Kompressor (Nähe/Druck),
        # lange dunkle Hallfahne (episch). Klingt gewichtig & narbig, bleibt aber klar verständlich.
        af = (
            f"{pitch_stage}"
            "highpass=f=65,bass=g=6:f=90,"
            "equalizer=f=350:t=q:w=1.0:g=2.5,equalizer=f=3200:t=q:w=1.0:g=-2.5,"
            "acompressor=threshold=0.08:ratio=4:attack=4:release=150:makeup=3,"
            "aecho=0.85:0.82:70:0.18,loudnorm=I=-15:TP=-1.3:LRA=9"
        )
    else:  # "jarvis" — der bisherige, saubere Sound
        af = (
            f"{pitch_stage}"
            "highpass=f=70,bass=g=4:f=110,equalizer=f=3000:t=q:w=1.2:g=1.5,"
            "acompressor=threshold=0.1:ratio=3:attack=5:release=90:makeup=2,"
            "aecho=0.85:0.8:55:0.14,loudnorm=I=-16:TP=-1.5:LRA=9"
        )

    tmp = wav_path + ".fx.wav"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-af", af, "-ar", str(sr), "-ac", "1", tmp],
                       capture_output=True, timeout=120)
    if r.returncode != 0 or not Path(tmp).exists():
        logger.warning("Voice-FX fehlgeschlagen, nehme Original: %s", r.stderr.decode(errors="replace")[:200])
        return wav_path
    os.replace(tmp, wav_path)
    return wav_path


def _tts_piper(text: str, out_path: str) -> str:
    """
    Piper TTS — native deutsche Stimme (Thorsten), 100% lokal, 0 Kosten.
    Ruft den installierten 'piper'-Befehl via subprocess auf.
    """
    if not PIPER_MODEL.exists():
        raise RuntimeError(
            f"Piper-Modell fehlt: {PIPER_MODEL}\n"
            "Setup:\n"
            "  pip install piper-tts\n"
            "  mkdir -p assets/piper && cd assets/piper\n"
            "  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "de/de_DE/thorsten/high/de_DE-thorsten-high.onnx\n"
            "  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json"
        )

    # Auf dem Mac verifiziert: "python3 -m piper -m <modell> -f <wav>" (Config wird automatisch gefunden)
    import sys
    cmd = [sys.executable, "-m", "piper", "-m", str(PIPER_MODEL), "-f", out_path]

    result = subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Piper fehlgeschlagen (exit {result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )

    logger.info("Piper TTS fertig: %s", out_path)
    return _apply_voice_fx(out_path)


# ── Kokoro Backend ─────────────────────────────────────────────────────────────

def _get_kokoro():
    global _kokoro_instance
    if _kokoro_instance is None:
        from kokoro_onnx import Kokoro
        model_path = config.ASSETS_DIR / "kokoro-v1.0.onnx"
        voices_path = config.ASSETS_DIR / "voices-v1.0.bin"
        if not model_path.exists() or not voices_path.exists():
            raise RuntimeError(
                "Kokoro-Modelldateien fehlen in assets/. "
                "kokoro-v1.0.onnx + voices-v1.0.bin nötig."
            )
        _kokoro_instance = Kokoro(str(model_path), str(voices_path))
        logger.info("Kokoro TTS-Modell geladen.")
    return _kokoro_instance


def _tts_kokoro(text: str, out_path: str, lang="de", voice=None, speed=1.0):
    kokoro = _get_kokoro()
    voice = voice or config.KOKORO_VOICE
    samples, sr = kokoro.create(text, voice=voice, speed=speed, lang=lang)
    sf.write(out_path, samples, sr)
    return out_path


# ── Fish Audio Backend ─────────────────────────────────────────────────────────

def _tts_fish(text: str, out_path: str):
    if not FISH_API_KEY:
        raise RuntimeError("FISH_API_KEY fehlt in .env — nötig für TTS_BACKEND=fish")
    resp = requests.post(
        "https://api.fish.audio/v1/tts",
        headers={"Authorization": f"Bearer {FISH_API_KEY}"},
        json={
            "text": text,
            "reference_id": FISH_VOICE_ID or None,
            "format": "wav",
        },
        timeout=60,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


# ── Öffentliche API ────────────────────────────────────────────────────────────


def _tts_edge(text: str, out_path: str) -> str:
    """Microsoft-Edge-Neuralstimmen via edge-tts: kostenlos, kein Key, deutlich natürlicher als Piper."""
    import asyncio
    import shutil
    import edge_tts

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg fehlt (für mp3->wav)")
    mp3 = out_path + ".mp3"

    words = []

    async def _go():
        words.clear()
        try:
            comm = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH,
                                        boundary="WordBoundary")
        except TypeError:  # ältere edge-tts ohne boundary-Option
            comm = edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH)

        async def _stream():
            with open(mp3, "wb") as f:
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        f.write(ch["data"])
                    elif ch["type"] == "WordBoundary":
                        words.append({"word": ch["text"], "start": ch["offset"] / 1e7,
                                      "end": (ch["offset"] + ch["duration"]) / 1e7})
        await asyncio.wait_for(_stream(), timeout=90)

    last = None
    for attempt in range(3):  # Dienst ist gelegentlich zickig -> 3 Versuche
        try:
            asyncio.run(_go())
            break
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning("edge-tts Versuch %d fehlgeschlagen: %s", attempt + 1, e)
    else:
        raise RuntimeError(f"edge-tts nicht erreichbar: {last}")

    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "24000", out_path],
                       capture_output=True, timeout=120)
    Path(mp3).unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError("mp3->wav fehlgeschlagen: " + r.stderr.decode(errors="replace")[:200])
    import json as _json
    wj = Path(out_path + ".words.json")
    if words:
        wj.write_text(_json.dumps(words, ensure_ascii=False), encoding="utf-8")
    else:
        wj.unlink(missing_ok=True)  # keine Timings -> video_builder schätzt/transkribiert
    logger.info("Edge TTS fertig (%s, %d Wort-Timings): %s", EDGE_VOICE, len(words), out_path)
    return _apply_voice_fx(out_path)



def _tts_google(text: str, out_path: str) -> str:
    """Google Cloud Text-to-Speech (REST + API-Key). Chirp 3 HD: 1 Mio. Zeichen/Monat gratis."""
    import base64
    if not GOOGLE_TTS_API_KEY:
        raise RuntimeError("GOOGLE_TTS_API_KEY fehlt in .env")
    audio_cfg = {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}
    if GOOGLE_RATE != 1.0:
        audio_cfg["speakingRate"] = GOOGLE_RATE
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "-".join(GOOGLE_VOICE.split("-")[:2]), "name": GOOGLE_VOICE},
        "audioConfig": audio_cfg,
    }
    r = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize",
                      params={"key": GOOGLE_TTS_API_KEY}, json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Google TTS HTTP {r.status_code}: {r.text[:300]}")
    Path(out_path).write_bytes(base64.b64decode(r.json()["audioContent"]))
    logger.info("Google TTS fertig (%s): %s", GOOGLE_VOICE, out_path)
    return _apply_voice_fx(out_path)


def synthesize(text: str, out_path: str, lang="de") -> str:
    Path(out_path + ".words.json").unlink(missing_ok=True)  # keine veralteten Timings
    """
    Erzeugt eine WAV-Datei aus Text.
    Backend: TTS_BACKEND in .env — "piper" (default), "kokoro", oder "fish".
    """
    if TTS_BACKEND == "google":
        try:
            return _tts_google(text, out_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Google-TTS ausgefallen (%s) -> Fallback auf Edge", e)
            try:
                return _tts_edge(text, out_path)
            except Exception as e2:  # noqa: BLE001
                logger.warning("Edge-TTS ausgefallen (%s) -> Fallback auf Piper", e2)
                return _tts_piper(text, out_path)
    if TTS_BACKEND == "edge":
        try:
            return _tts_edge(text, out_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Edge-TTS ausgefallen (%s) -> Fallback auf Piper", e)
            return _tts_piper(text, out_path)
    if TTS_BACKEND == "fish":
        logger.info("TTS via Fish Audio (Cloud, native DE-Stimme)")
        return _tts_fish(text, out_path)
    if TTS_BACKEND == "kokoro":
        logger.info("TTS via Kokoro (lokal, EN-Modell mit DE-Fallback)")
        return _tts_kokoro(text, out_path, lang=lang)
    # Default: Piper
    logger.info("TTS via Piper/Thorsten-Voice (lokal, 0€, native Deutsch)")
    return _tts_piper(text, out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_text = (
        "Die meisten Menschen scheitern nicht am Ziel. "
        "Sie scheitern am ersten Schritt. Fang heute an."
    )
    path = synthesize(test_text, str(config.AUDIO_DIR / "test_de.wav"))
    print("TTS-Test gespeichert:", path)
