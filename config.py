"""
Zentrale Konfiguration. Lädt alles aus .env — nichts wird hier hardcoded.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# --- TikTok ---
TIKTOK_ACCOUNT_NAME = os.getenv("TIKTOK_ACCOUNT_NAME", "mindset_daily_de")
PROXY_RAW = os.getenv("PROXY", "").strip()

def get_proxy():
    """Parst PROXY=server:port:user:pass -> dict für tiktokautouploader, oder None."""
    if not PROXY_RAW:
        return None
    parts = PROXY_RAW.split(":")
    if len(parts) == 2:
        server, port = parts
        return {"server": f"{server}:{port}"}
    if len(parts) == 4:
        server, port, user, pw = parts
        return {"server": f"{server}:{port}", "username": user, "password": pw}
    return None

# --- Scheduling ---
POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "1"))
POST_TIME = os.getenv("POST_TIME", "18:30")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")

# --- Pfade ---
CONTENT_DIR = BASE_DIR / "content"
VIDEO_DIR = BASE_DIR / "videos"
AUDIO_DIR = BASE_DIR / "audio"
ASSETS_DIR = BASE_DIR / "assets"
COOKIES_DIR = BASE_DIR / "cookies"
LOGS_DIR = BASE_DIR / "logs"
TRENDS_FILE = CONTENT_DIR / "current_trends.json"
QUEUE_FILE = CONTENT_DIR / "post_queue.json"

for d in (CONTENT_DIR, VIDEO_DIR, AUDIO_DIR, ASSETS_DIR, COOKIES_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Video-Format (TikTok Standard) ---
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# --- Kokoro TTS ---
KOKORO_VOICE = "af_heart"   # warme, klare weibliche Stimme (EN) — af/bf Reihe = beste Qualität
KOKORO_LANG = "de"          # Kokoro unterstützt DE über espeak-Backend

def validate(require_anthropic=False, require_pexels=False):
    """Prüft ob die essenziellen Keys gesetzt sind, bevor ein Pipeline-Schritt läuft."""
    missing = []
    if require_anthropic and not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if require_pexels and not PEXELS_API_KEY:
        missing.append("PEXELS_API_KEY")
    if missing:
        raise RuntimeError(
            f"Fehlende Keys in .env: {', '.join(missing)}. "
            f"Siehe .env.example für Anleitung."
        )
