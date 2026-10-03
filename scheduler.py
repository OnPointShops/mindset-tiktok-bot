"""
Orchestriert den kompletten täglichen Zyklus:

  1. Falls Queue leer/knapp: neue Skripte generieren (content_generator)
  2. Für jedes fällige Skript: TTS -> Video-Build -> Upload
  3. Queue-Eintrag als "posted" markieren, Fehler werden geloggt (nicht verworfen
     -> nächster Lauf versucht es erneut, bevor ein neues Skript generiert wird)

Gedacht für Aufruf über Cron (empfohlen, siehe README) ODER als Dauerprozess
mit der 'schedule'-Library (Fallback, falls kein Cron verfügbar ist).
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import config
import content_generator
import tts_engine
import video_builder
import uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / f"{datetime.now():%Y-%m-%d}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduler")


def _load_queue() -> list[dict]:
    if config.QUEUE_FILE.exists():
        return json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
    return []


def _save_queue(queue: list[dict]):
    config.QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_queue_filled(min_pending: int = 2):
    """Stellt sicher, dass immer mindestens min_pending unveröffentlichte Skripte da sind."""
    queue = _load_queue()
    pending = [q for q in queue if q.get("status") not in ("posted", "failed")]
    if len(pending) < min_pending:
        need = min_pending - len(pending) + config.POSTS_PER_DAY
        logger.info("Queue knapp (%d pending) -> generiere %d neue Skripte", len(pending), need)
        content_generator.generate_batch(need)


def process_one_pending() -> bool:
    """Verarbeitet genau ein pending Skript komplett (TTS -> Video -> Upload). True wenn erfolgreich."""
    queue = _load_queue()
    pending_idx = next(
        (i for i, q in enumerate(queue)
         if q.get("status") not in ("posted", "failed")), None)
    if pending_idx is None:
        logger.info("Keine offenen Skripte in der Queue.")
        return False

    script = queue[pending_idx]
    topic_slug = "".join(c if c.isalnum() else "_" for c in script.get("topic", "clip"))[:30]
    audio_path = str(config.AUDIO_DIR / f"{topic_slug}.wav")
    video_path = str(config.VIDEO_DIR / f"{topic_slug}.mp4")

    try:
        logger.info("Verarbeite Skript: %s", script.get("topic"))
        tts_engine.synthesize(script["full_voiceover_text"], audio_path)
        video_builder.build_video(script, audio_path, video_path)
        result = uploader.post_video(script, video_path)

        script["status"] = "posted" if result == "Completed" else "error"
        script["posted_at"] = datetime.now().isoformat()
        script["upload_result"] = result
        queue[pending_idx] = script
        _save_queue(queue)

        return result == "Completed"
    except Exception:
        logger.exception("Fehler bei Verarbeitung von Skript '%s'", script.get("topic"))
        script["errors"] = script.get("errors", 0) + 1
        script["status"] = "failed" if script["errors"] >= 3 else "error"
        queue[pending_idx] = script
        _save_queue(queue)
        return False


def run_daily_cycle():
    """Ein kompletter Tages-Durchlauf: Queue auffüllen, POSTS_PER_DAY Videos posten."""
    logger.info("=== Täglicher Zyklus startet (%s) ===", datetime.now().isoformat())
    ensure_queue_filled(min_pending=2)

    success_count = 0
    for _ in range(config.POSTS_PER_DAY):
        if process_one_pending():
            success_count += 1

    logger.info("=== Zyklus fertig: %d/%d Videos erfolgreich gepostet ===",
                success_count, config.POSTS_PER_DAY)
    return success_count


if __name__ == "__main__":
    # Direkter Aufruf = genau EIN Zyklus (das ist der Cron-freundliche Modus,
    # siehe README für die crontab-Zeile).
    run_daily_cycle()
