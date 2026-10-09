"""
Orchestriert alle Accounts des Portfolios.

Früher: ein Account, ein Video pro Tag, ein Cron-Lauf am Abend.
Jetzt:   mehrere Accounts, mehrere Posting-Zeitpunkte pro Tag, zwei Formate
         (Video / Karussell), drei Plattformen (TikTok / Instagram / YouTube).

Gedacht für einen STÜNDLICHEN Cron-Lauf. Jeder Lauf fragt: welcher Account hat
gerade einen fälligen Posting-Zeitpunkt, der noch nicht bedient wurde? Nur
dafür wird gearbeitet. Verpasste Slots (Server aus, API-Fehler) holt der
nächste Lauf nach — besser spät posten als den Tag auslassen.

    crontab:  5 * * * * cd /pfad/zum/projekt && /usr/bin/python3 scheduler.py >> logs/cron.log 2>&1
"""
import json
import logging
import sys
from datetime import datetime

import accounts as accounts_mod
import config
import content_generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(config.LOGS_DIR / f"{datetime.now():%Y-%m-%d}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduler")


# ── Queue ──────────────────────────────────────────────────────────────────────
def _load_queue() -> list[dict]:
    if config.QUEUE_FILE.exists():
        return json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
    return []


def _save_queue(queue: list[dict]):
    config.QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def _pending_for(queue: list[dict], account_id: str) -> list[int]:
    """Indizes der offenen Skripte dieses Accounts. Altbestand ohne Account-Feld
    gehört dem ersten Account (Abwärtskompatibilität mit der Ein-Account-Queue)."""
    first = (accounts_mod.enabled() or [None])[0]
    default_id = first.id if first else ""
    return [i for i, q in enumerate(queue)
            if q.get("account", default_id) == account_id
            and q.get("status") not in ("posted", "failed")]


def ensure_queue_filled(acc, min_pending: int = 2):
    """Hält je Account immer einen kleinen Vorrat an Skripten bereit."""
    queue = _load_queue()
    pending = _pending_for(queue, acc.id)
    if len(pending) >= min_pending:
        return

    need = min_pending - len(pending) + acc.posts_per_day
    logger.info("[%s] Queue knapp (%d offen) -> generiere %d Skripte", acc.id, len(pending), need)

    known_topics = {q.get("topic") for q in queue}
    new_items = []
    for _ in range(need * 3):
        if len(new_items) >= need:
            break
        # Jedes dritte Video-Skript wird Langform (>60 Sek.). Nur solche Videos
        # zählen für die TikTok Creator Rewards — siehe STRATEGIE_10K.md, Abschnitt 2.
        # Das muss bei der Generierung entschieden werden, nicht beim Rendern.
        want_long = acc.content_format != "carousel" and len(new_items) % 3 == 2
        try:
            script = content_generator.generate_script(
                theme_hint=acc.niche, length="long" if want_long else "normal")
        except Exception as e:  # noqa: BLE001
            logger.error("[%s] Skript-Generierung fehlgeschlagen: %s", acc.id, e)
            continue
        if script.get("topic") in known_topics:
            continue
        known_topics.add(script.get("topic"))
        script["account"] = acc.id
        script["length"] = "long" if want_long else "normal"
        new_items.append(script)
        logger.info("[%s] Skript generiert: %s", acc.id, script.get("topic"))

    if new_items:
        _save_queue(queue + new_items)


# ── Produktion ─────────────────────────────────────────────────────────────────
def _slug(script: dict, acc) -> str:
    raw = f"{acc.id}_{script.get('topic', 'clip')}"
    return "".join(c if c.isalnum() else "_" for c in raw)[:40]


def _build_video(script: dict, acc) -> str:
    import tts_engine
    import video_builder
    slug = _slug(script, acc)
    audio_path = str(config.AUDIO_DIR / f"{slug}.wav")
    video_path = str(config.VIDEO_DIR / f"{slug}.mp4")
    tts_engine.synthesize(script["full_voiceover_text"], audio_path)
    video_builder.build_video(script, audio_path, video_path)
    return video_path


def _build_carousel(script: dict, acc) -> list[str]:
    import carousel
    handle = f"@{acc.tiktok_account_name}" if acc.tiktok_account_name else ""
    return carousel.make_carousel(script, config.VIDEO_DIR / "carousels" / _slug(script, acc),
                                  handle=handle)


# ── Veröffentlichung ───────────────────────────────────────────────────────────
def _publish(script: dict, acc, fmt: str, asset) -> dict:
    """Postet auf allen Plattformen, für die der Account Zugangsdaten hat.
    Gibt {plattform: 'ok'|Fehlertext} zurück. Ein Fehler stoppt die anderen nicht."""
    results: dict[str, str] = {}

    for platform in acc.targets():
        try:
            if platform == "tiktok":
                if fmt != "video":
                    continue                       # Foto-Posts kann der TikTok-Uploader nicht
                import uploader
                r = uploader.post_video(script, asset, account=acc)
                results["tiktok"] = "ok" if r == "Completed" else str(r)

            elif platform == "instagram":
                import uploader_instagram
                if fmt == "carousel":
                    uploader_instagram.post_carousel(script, asset, acc)
                else:
                    uploader_instagram.post_reel(script, asset, acc)
                results["instagram"] = "ok"

            elif platform == "youtube":
                if fmt != "video":
                    continue
                import uploader_youtube
                uploader_youtube.post_short(script, asset, acc)
                results["youtube"] = "ok"

        except Exception as e:  # noqa: BLE001
            logger.error("[%s] %s fehlgeschlagen: %s", acc.id, platform, e)
            results[platform] = f"Fehler: {e}"

    return results


def process_slot(acc, slot_index: int) -> bool:
    """Produziert und postet genau einen Beitrag für einen fälligen Slot."""
    ensure_queue_filled(acc)
    queue = _load_queue()
    pending = _pending_for(queue, acc.id)
    if not pending:
        logger.warning("[%s] Kein Skript verfügbar für Slot %d", acc.id, slot_index)
        return False

    idx = pending[0]
    script = queue[idx]
    fmt = acc.format_for_slot(slot_index)
    logger.info("[%s] Slot %d | Format=%s (%s) | Thema=%s", acc.id, slot_index, fmt,
                script.get("length", "normal"), script.get("topic"))

    try:
        asset = _build_carousel(script, acc) if fmt == "carousel" else _build_video(script, acc)
    except Exception:
        logger.exception("[%s] Produktion fehlgeschlagen: %s", acc.id, script.get("topic"))
        script["errors"] = script.get("errors", 0) + 1
        script["status"] = "failed" if script["errors"] >= 3 else "error"
        queue[idx] = script
        _save_queue(queue)
        return False

    results = _publish(script, acc, fmt, asset)
    success = any(v == "ok" for v in results.values())

    script["status"] = "posted" if success else "error"
    script["format_used"] = fmt
    script["posted_at"] = datetime.now().isoformat()
    script["upload_results"] = results
    if not success:
        script["errors"] = script.get("errors", 0) + 1
        if script["errors"] >= 3:
            script["status"] = "failed"
    queue[idx] = script
    _save_queue(queue)

    if success:
        accounts_mod.mark_posted(acc, slot_index)
        logger.info("[%s] Veröffentlicht: %s", acc.id, results)
    return success


# ── Einstiegspunkte ────────────────────────────────────────────────────────────
def run_cycle(now: datetime | None = None) -> int:
    """Ein Cron-Lauf: bedient alle gerade fälligen Slots aller Accounts."""
    now = now or datetime.now()
    logger.info("=== Zyklus %s ===", now.isoformat(timespec="minutes"))

    total = 0
    for acc in accounts_mod.enabled():
        if not acc.targets():
            logger.warning("[%s] Keine Plattform-Zugangsdaten hinterlegt — übersprungen", acc.id)
            continue
        for slot in accounts_mod.due_slots(acc, now):
            if process_slot(acc, slot):
                total += 1

    try:
        import media_host
        media_host.cleanup()
    except Exception as e:  # noqa: BLE001
        logger.debug("Medien-Aufräumen übersprungen: %s", e)

    logger.info("=== Zyklus fertig: %d Beitrag/Beiträge veröffentlicht ===", total)
    return total


def run_daily_cycle() -> int:
    """Alter Name — bleibt erhalten, weil daily_run.py ihn aufruft."""
    return run_cycle()


if __name__ == "__main__":
    run_cycle()
