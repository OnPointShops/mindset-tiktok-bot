"""
Emotionale Hintergrundmusik, 100% lizenzfrei & lokal:
  1) Eigene Tracks aus assets/music/*.mp3|*.wav  (du darfst eigene freie Musik reinlegen)
  2) Sonst: selbst erzeugtes Klangbett (warmes Piano-Pad, Moll, langsamer Puls)
Wird in video_builder LEISE unter die Stimme gemischt (Ducking).
Quellen für eigene freie Tracks (CC0/lizenzfrei, kommerziell nutzbar):
  - pixabay.com/music   - freemusicarchive.org   - incompetech.com (Attribution beachten)
"""
import logging
import os
import random
from pathlib import Path

import numpy as np
import soundfile as sf

import config

logger = logging.getLogger("music")
MUSIC_DIR = config.ASSETS_DIR / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_ENABLED = os.getenv("MUSIC", "on") != "off"
MUSIC_GAIN_DB = float(os.getenv("MUSIC_GAIN_DB", "-18"))  # wie leise unter der Stimme

SR = 24000
# Emotionale Moll-Progressionen (Grundfrequenzen der Akkorde in Hz, je 4 Akkorde)
PROGRESSIONS = [
    [220.00, 174.61, 130.81, 196.00],  # Am F C G
    [196.00, 146.83, 174.61, 130.81],  # Gm ... warm
    [246.94, 185.00, 146.83, 220.00],  # Bm G ...
]


def _pad_chord(root, dur):
    """Ein weicher Akkord (Grundton + Quinte + Oktave) mit sanftem Ein/Ausklang."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    freqs = [root, root * 1.5, root * 2.0]  # Grundton, Quinte, Oktave
    wave = sum(np.sin(2 * np.pi * f * t) * g for f, g in zip(freqs, (1.0, 0.5, 0.35)))
    # leichtes Vibrato + weicher Attack/Release
    wave *= 1 + 0.02 * np.sin(2 * np.pi * 5 * t)
    env = np.ones_like(t)
    a = int(SR * 0.4)
    env[:a] = np.linspace(0, 1, a)
    env[-a:] = np.linspace(1, 0, a)
    return wave * env


def _generate_bed(duration, seed_text):
    seed = abs(hash(seed_text)) % (2**32)
    rng = random.Random(seed)
    prog = rng.choice(PROGRESSIONS)
    chord_dur = 4.0
    bed = []
    i = 0
    while sum(len(b) for b in bed) < int(SR * (duration + chord_dur)):
        bed.append(_pad_chord(prog[i % len(prog)], chord_dur))
        i += 1
    audio = np.concatenate(bed)[: int(SR * duration)]
    # sanfter Sub-Bass-Puls (Herzschlag-Gefühl)
    t = np.linspace(0, duration, len(audio), endpoint=False)
    pulse = 0.12 * np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
    audio = audio * 0.18 + pulse
    audio /= max(np.max(np.abs(audio)), 1e-6)
    out = str(config.AUDIO_DIR / "_musicbed.wav")
    sf.write(out, (audio * 0.8).astype("float32"), SR)
    return out


def get_music_track(duration, seed_text):
    """Pfad zu einem Musik-File (eigenes aus assets/music, sonst selbst erzeugt). None wenn aus."""
    if not MUSIC_ENABLED:
        return None
    own = [p for p in MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")]
    if own:
        chosen = str(random.choice(own))
        logger.info("Musik: eigener Track %s", Path(chosen).name)
        return chosen
    logger.info("Musik: selbst erzeugtes Klangbett (lege eigene Tracks in assets/music/)")
    return _generate_bed(duration, seed_text)
