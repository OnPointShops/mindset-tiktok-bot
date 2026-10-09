"""
Öffentliche URLs für Medien — technische Voraussetzung für Instagram.

Die Instagram Graph API lädt KEINE Dateien hoch. Sie bekommt eine URL und holt
sich die Datei selbst ab. Das heißt: jedes Video und jedes Karussell-Bild muss
für ein paar Minuten öffentlich erreichbar sein.

Drei Wege, konfiguriert über MEDIA_HOST in .env:

  "local"  Datei wird nach public/ kopiert; du servierst den Ordner selbst
           (nginx/Caddy/Apache auf deinem VPS). MEDIA_BASE_URL zeigt darauf.
           Günstigster Weg, wenn der VPS ohnehin läuft.
  "s3"     S3-kompatibler Speicher (Cloudflare R2, Hetzner, AWS). Braucht boto3.
           Empfohlen, sobald mehrere Accounts parallel posten.
  "off"    Instagram-Upload ist deaktiviert (sauberer Fehler statt stiller Murks).

Die Dateien sind kurzzeitig öffentlich — also NIE etwas hier ablegen,
das nicht ohnehin veröffentlicht wird.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from pathlib import Path

import config

log = logging.getLogger("media_host")

MEDIA_HOST = os.getenv("MEDIA_HOST", "off").strip().lower()
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "").rstrip("/")
PUBLIC_DIR = Path(os.getenv("MEDIA_PUBLIC_DIR", str(config.BASE_DIR / "public")))

S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
S3_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET = os.getenv("S3_SECRET_KEY", "")
S3_REGION = os.getenv("S3_REGION", "auto")


class MediaHostError(RuntimeError):
    pass


def available() -> bool:
    if MEDIA_HOST == "local":
        return bool(MEDIA_BASE_URL)
    if MEDIA_HOST == "s3":
        return bool(S3_BUCKET and S3_KEY and S3_SECRET and MEDIA_BASE_URL)
    return False


def _s3_client():
    try:
        import boto3  # noqa: PLC0415  (optional: nur bei MEDIA_HOST=s3 nötig)
    except ImportError as e:
        raise MediaHostError("MEDIA_HOST=s3 gesetzt, aber boto3 fehlt: pip install boto3") from e
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT or None, region_name=S3_REGION,
        aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET,
    )


def publish(path: str | Path, keep_name: bool = False) -> str:
    """Macht eine lokale Datei öffentlich erreichbar und gibt ihre URL zurück."""
    path = Path(path)
    if not path.exists():
        raise MediaHostError(f"Datei existiert nicht: {path}")
    if not available():
        raise MediaHostError(
            "Kein Medien-Host konfiguriert. Für Instagram nötig: MEDIA_HOST=local|s3 "
            "plus MEDIA_BASE_URL in .env (siehe .env.example)."
        )

    name = path.name if keep_name else f"{uuid.uuid4().hex[:12]}{path.suffix}"

    if MEDIA_HOST == "local":
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, PUBLIC_DIR / name)
        url = f"{MEDIA_BASE_URL}/{name}"
    else:
        ctype = {".mp4": "video/mp4", ".png": "image/png",
                 ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower(),
                                                                  "application/octet-stream")
        _s3_client().upload_file(str(path), S3_BUCKET, name, ExtraArgs={"ContentType": ctype})
        url = f"{MEDIA_BASE_URL}/{name}"

    log.info("Medium veröffentlicht: %s", url)
    return url


def cleanup(older_than_hours: int = 24) -> int:
    """Räumt alte öffentliche Dateien weg. Instagram braucht sie nur wenige Minuten."""
    if MEDIA_HOST != "local" or not PUBLIC_DIR.exists():
        return 0
    cutoff = time.time() - older_than_hours * 3600
    removed = 0
    for f in PUBLIC_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        log.info("%d alte öffentliche Dateien entfernt", removed)
    return removed
