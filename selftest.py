"""
Selbsttest der kompletten Pipeline. Läuft täglich vor dem Posting.
Gibt (ok, report) zurück und schreibt logs/health.json.
Kritische Fehler stoppen das Posting, damit nie kaputte Videos live gehen.
"""
import json
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests

import config

logger = logging.getLogger("selftest")

MIN_MODEL_BYTES = 90_000_000  # Thorsten-high ~109 MB; kleiner = abgebrochener Download


def _check(name, fn, critical=True):
    try:
        detail = fn()
        return {"name": name, "ok": True, "critical": critical, "detail": detail or "ok"}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "ok": False, "critical": critical, "detail": str(e)[:300]}


def t_keys():
    config.validate(require_anthropic=False)
    return "Basis-Config ok"


def t_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg nicht im PATH")
    return "ffmpeg da"


def t_model():
    m = config.ASSETS_DIR / "piper" / "de_DE-thorsten-high.onnx"
    j = Path(str(m) + ".json")
    if not m.exists() or m.stat().st_size < MIN_MODEL_BYTES:
        raise RuntimeError("Piper-Modell fehlt oder unvollständig (Download wiederholen)")
    if not j.exists() or j.stat().st_size < 500:
        raise RuntimeError("Piper-Modell-Config fehlt")
    return f"{m.stat().st_size // 1_000_000} MB"


def t_tts():
    import tts_engine
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "t.wav")
        tts_engine.synthesize("Dies ist ein kurzer Test der Stimme.", out)
        if Path(out).stat().st_size < 10_000:
            raise RuntimeError("TTS-Ausgabe zu klein/leer")
    return "Piper spricht"


def t_pexels():
    if not config.PEXELS_API_KEY:
        return "übersprungen (kein Key nötig, prozeduraler Hintergrund aktiv)"
    r = requests.get("https://api.pexels.com/videos/search",
                     headers={"Authorization": config.PEXELS_API_KEY},
                     params={"query": "sunrise", "orientation": "portrait", "per_page": 1}, timeout=20)
    r.raise_for_status()
    if not r.json().get("videos"):
        raise RuntimeError("Pexels lieferte keine Videos")
    return "Pexels ok"


def t_ai():
    import content_generator as C
    if C.AI_BACKEND == "offline":
        if not C.SCRIPT_BANK.exists():
            raise RuntimeError("Offline gewählt, aber script_bank.json fehlt")
        return "offline-Vorrat"
    if C.GEMINI_API_KEY:
        out = C.generate_llm("Antworte knapp.", "Sag nur: ok", max_tokens=10)
        return f"Gemini ok ({out.strip()[:10]})"
    if config.ANTHROPIC_API_KEY:
        out = C.generate_llm("Antworte knapp.", "Sag nur: ok", max_tokens=10)
        return f"Claude ok ({out.strip()[:10]})"
    raise RuntimeError("Kein KI-Key (GEMINI_API_KEY) und kein Offline-Vorrat gewählt")


def t_imports():
    import moviepy, faster_whisper, tiktokautouploader  # noqa: F401,E401
    return "Imports ok"


def t_cookies():
    if not any(config.COOKIES_DIR.glob("*")):
        raise RuntimeError("Kein TikTok-Login gespeichert: python3 uploader.py --login")
    return "Login-Cookies vorhanden"


def t_disk():
    free = shutil.disk_usage(config.BASE_DIR).free // 1_000_000_000
    if free < 3:
        raise RuntimeError(f"Nur {free} GB frei")
    return f"{free} GB frei"


def cleanup_old_files(keep_days=7):
    """Räumt alte Videos/Audio auf, damit die Platte nicht vollläuft."""
    cutoff = datetime.now().timestamp() - keep_days * 86400
    n = 0
    for d in (config.VIDEO_DIR, config.AUDIO_DIR):
        for f in d.glob("*"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                n += 1
    return n


def run_selftest():
    checks = [
        _check("API-Keys", t_keys),
        _check("ffmpeg", t_ffmpeg),
        _check("Python-Pakete", t_imports),
        _check("Piper-Modell", t_model),
        _check("Piper-Stimme (Live-Test)", t_tts),
        _check("Pexels-API", t_pexels),
        _check("KI (Skripte)", t_ai),
        _check("TikTok-Login", t_cookies),
        _check("Speicherplatz", t_disk, critical=False),
    ]
    cleaned = cleanup_old_files()
    ok = all(c["ok"] or not c["critical"] for c in checks)
    report = {"time": datetime.now().isoformat(), "ok": ok, "cleaned_files": cleaned, "checks": checks}
    (config.LOGS_DIR / "health.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in checks:
        logger.log(logging.INFO if c["ok"] else logging.ERROR, "%s %s: %s",
                   "✓" if c["ok"] else "✗", c["name"], c["detail"])
    return ok, report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ok, rep = run_selftest()
    print("\nGESAMT:", "ALLES GRÜN ✓" if ok else "FEHLER ✗ (siehe oben)")
