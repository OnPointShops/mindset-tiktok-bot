"""
Emotionale, EPISCHE & DUNKLE Hintergrundmusik, 100% lizenzfrei & lokal erzeugt:
  1) Eigene Tracks aus assets/music/*.mp3|*.wav  (du darfst eigene freie Musik reinlegen)
  2) Sonst: selbst synthetisiertes Klangbett (Moll-Akkorde, Sub-Bass-Pulse wie ferne
     Kriegstrommeln, langsamer Intro-Riser, einfacher Hall) — kein Sample, kein
     Download, daher zu 100% lizenzfrei, egal wie oft/wo das Video läuft.
Wird in video_builder LEISE unter die Stimme gemischt (Ducking).

Eigene freie Tracks (CC0/lizenzfrei, kommerziell nutzbar) kannst du zusätzlich ablegen:
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
MUSIC_GAIN_DB = float(os.getenv("MUSIC_GAIN_DB", "-16"))  # wie leise unter der Stimme
MUSIC_STYLE = os.getenv("MUSIC_STYLE", "epic_dark")  # "epic_dark" | "soft_pad" (alter Sound)

SR = 24000
SEMITONE = 2 ** (1 / 12)

# Dunkle Moll-Grundtöne (Hz) je Progression — tiefer gelegt als vorher für mehr Gewicht
PROGRESSIONS = [
    [110.00, 87.31, 65.41, 98.00],   # Am F C G (eine Oktave tiefer)
    [98.00, 73.42, 87.31, 65.41],    # Gm ...
    [123.47, 92.50, 73.42, 110.00],  # Bm G ...
]


def _minor_chord(root, dur, intensity=1.0):
    """Moll-Akkord (Grundton, kleine Terz, Quinte, Oktave) mit mehreren leicht
    verstimmten Schichten je Ton -> voller, chorartiger 'epischer' Klang."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    ratios_amp = [(1.0, 1.0), (SEMITONE ** 3, 0.65), (SEMITONE ** 7, 0.55), (2.0, 0.4)]
    wave = np.zeros_like(t)
    for ratio, amp in ratios_amp:
        f = root * ratio
        # 2 leicht verstimmte Schichten pro Ton (Detune) -> dichter, "Chor"-artiger Klang
        wave += amp * 0.6 * np.sin(2 * np.pi * f * t)
        wave += amp * 0.4 * np.sin(2 * np.pi * f * 1.004 * t)
    wave *= intensity
    wave *= 1 + 0.015 * np.sin(2 * np.pi * 4.5 * t)  # dezentes Vibrato
    env = np.ones_like(t)
    a = int(SR * 0.5)
    env[:a] = np.linspace(0, 1, a)
    env[-a:] = np.linspace(1, 0, a)
    return wave * env


def _distant_drums(duration, bpm=46):
    """Ferne, tiefe Kriegstrommel-Pulse (Sub-Bass-Hits) statt weichem Herzschlag —
    episch statt sanft. Dichte/Lautstärke nimmt zum Ende leicht zu (Spannungsbogen)."""
    n = int(SR * duration)
    audio = np.zeros(n)
    hit_len = int(SR * 0.5)
    t_hit = np.linspace(0, 0.5, hit_len, endpoint=False)
    hit = np.sin(2 * np.pi * 58 * t_hit) * np.exp(-t_hit * 7.5)
    beat_interval = 60.0 / bpm
    t = 0.0
    i = 0
    while t < duration:
        progress = t / max(duration, 1e-6)
        strength = 0.55 + 0.45 * progress  # wird zum Ende hin kraftvoller
        start = int(t * SR)
        end = min(start + hit_len, n)
        length = end - start
        if length > 0:
            audio[start:end] += hit[:length] * strength
        i += 1
        t += beat_interval * (1.0 if i % 4 else 0.5)  # alle 4 Schläge ein Doppelschlag
    return audio


def _intro_riser(duration):
    """Leiser, ansteigender Rausch-Riser in den ersten ~3s — klassischer Trailer-Einstieg."""
    n = int(SR * duration)
    riser_len = min(int(SR * 3.0), n)
    noise = np.random.default_rng(7).normal(0, 1, riser_len)
    # grobe Tiefpass-Glättung (gleitender Mittelwert) -> weniger "weißes Rauschen", mehr "Wind"
    kernel = np.ones(40) / 40
    noise = np.convolve(noise, kernel, mode="same")
    env = np.linspace(0, 1, riser_len) ** 2
    out = np.zeros(n)
    out[:riser_len] = noise * env * 0.25
    return out


def _simple_hall(audio, decay=0.32, taps=4, delay_s=0.09):
    """Günstige Annäherung an Hallraum: mehrere verzögerte, leiser werdende Kopien addieren."""
    delay = int(SR * delay_s)
    out = audio.copy()
    layer = audio.copy()
    for _ in range(taps):
        layer = np.concatenate([np.zeros(delay), layer[:-delay]]) * decay
        out = out + layer
    return out


def _generate_bed(duration, seed_text):
    seed = abs(hash(seed_text)) % (2**32)
    rng = random.Random(seed)
    prog = rng.choice(PROGRESSIONS)
    chord_dur = 5.0
    bed = []
    i = 0
    total_len = int(SR * (duration + chord_dur))
    while sum(len(b) for b in bed) < total_len:
        # Intensität steigt im Verlauf leicht -> emotionaler Spannungsbogen statt Dauerschleife
        progress = min(sum(len(b) for b in bed) / max(total_len, 1), 1.0)
        intensity = 0.65 + 0.35 * progress
        bed.append(_minor_chord(prog[i % len(prog)], chord_dur, intensity=intensity))
        i += 1
    pad = np.concatenate(bed)[: int(SR * duration)]

    if MUSIC_STYLE == "epic_dark":
        drums = _distant_drums(duration)
        riser = _intro_riser(duration)
        audio = pad * 0.22 + drums * 0.5 + riser
        audio = _simple_hall(audio, decay=0.3, taps=3, delay_s=0.11)
    else:  # "soft_pad" — der alte, ruhige Sound als Alternative
        t = np.linspace(0, duration, len(pad), endpoint=False)
        pulse = 0.12 * np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
        audio = pad * 0.18 + pulse

    audio /= max(np.max(np.abs(audio)), 1e-6)
    out = str(config.AUDIO_DIR / "_musicbed.wav")
    sf.write(out, (audio * 0.85).astype("float32"), SR)
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
    logger.info("Musik: selbst erzeugtes episches Klangbett (Stil: %s)", MUSIC_STYLE)
    return _generate_bed(duration, seed_text)
