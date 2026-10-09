"""
Instagram-Upload über die offizielle Graph API — Reels und Karussells.

Bewusste Entscheidung gegen Browser-Automation: Instagram erkennt sie deutlich
zuverlässiger als TikTok, und bei einem Konto, an dem Umsatz hängt, ist eine
Sperre kein Ärgernis, sondern ein Geschäftsausfall. Die offizielle API ist
langweiliger, aber sie hält.

Voraussetzungen (einmalig, siehe TODO_KAI.md Schritt 4):
  - Instagram-Konto auf "Business" umgestellt und mit einer Facebook-Seite verbunden
  - Meta-App mit den Rechten instagram_basic, instagram_content_publish,
    pages_show_list, pages_read_engagement
  - Langlebiges Seiten-Token  -> .env: IG_ACCESS_TOKEN
  - IG-Business-User-ID je Account -> .env: IG_USER_ID_<ACCOUNT>

Limits der API (Stand 2026): 50 veröffentlichte Beiträge pro Konto / 24 Stunden,
Karussell 2-10 Bilder. Beides liegt weit über dem Plan (3/Tag).
"""
from __future__ import annotations

import logging
import os
import time

import requests

import media_host

log = logging.getLogger("uploader_instagram")

GRAPH_VERSION = os.getenv("IG_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")

TIMEOUT = 60
MAX_WAIT_SECONDS = 300      # Videoverarbeitung bei Instagram dauert i.d.R. 20-90 Sek.


class InstagramError(RuntimeError):
    pass


def _post(path: str, data: dict) -> dict:
    data = {**data, "access_token": ACCESS_TOKEN}
    r = requests.post(f"{GRAPH}/{path}", data=data, timeout=TIMEOUT)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400 or "error" in body:
        msg = body.get("error", {}).get("message", r.text[:300])
        raise InstagramError(f"Graph-API-Fehler ({r.status_code}) bei {path}: {msg}")
    return body


def _get(path: str, params: dict) -> dict:
    params = {**params, "access_token": ACCESS_TOKEN}
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=TIMEOUT)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400 or "error" in body:
        msg = body.get("error", {}).get("message", r.text[:300])
        raise InstagramError(f"Graph-API-Fehler ({r.status_code}) bei {path}: {msg}")
    return body


def _wait_ready(container_id: str):
    """Wartet, bis Instagram das Medium fertig verarbeitet hat. Ohne das schlägt Publish fehl."""
    waited = 0
    while waited < MAX_WAIT_SECONDS:
        status = _get(container_id, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise InstagramError(f"Instagram-Verarbeitung fehlgeschlagen: {status.get('status')}")
        time.sleep(5)
        waited += 5
    raise InstagramError(f"Zeitüberschreitung: Container {container_id} nach "
                         f"{MAX_WAIT_SECONDS}s nicht fertig verarbeitet.")


def _caption(script: dict, account) -> str:
    """Caption + Hashtags + Pflicht-Hinweis bei Werbung."""
    parts = [script.get("caption") or script.get("hook", "")]
    if script.get("is_ad"):
        parts.insert(0, "Werbung")          # UWG: Kennzeichnung ganz oben, lesbar, deutsch
    if account is not None and account.link_in_bio:
        parts.append("Mehr dazu: Link in der Bio")
    tags = list(script.get("hashtags", []))
    if account is not None:
        tags += [t for t in account.base_hashtags if t not in tags]
    if tags:
        parts.append(" ".join(f"#{t.lstrip('#')}" for t in tags[:12]))
    return "\n\n".join(p for p in parts if p)


def post_reel(script: dict, video_path: str, account) -> str:
    """Lädt ein Video als Reel hoch. Gibt die Medien-ID zurück."""
    ig_user = account.instagram_user_id
    if not (ACCESS_TOKEN and ig_user):
        raise InstagramError(f"IG_ACCESS_TOKEN oder {account.instagram_user_env} fehlt in .env")

    video_url = media_host.publish(video_path)
    log.info("Reel-Container wird erstellt (Account %s)", account.id)
    container = _post(f"{ig_user}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": _caption(script, account),
        "share_to_feed": "true",
    })
    _wait_ready(container["id"])
    published = _post(f"{ig_user}/media_publish", {"creation_id": container["id"]})
    log.info("Reel veröffentlicht: %s", published.get("id"))
    return published.get("id", "")


def post_carousel(script: dict, image_paths: list[str], account) -> str:
    """Lädt 2-10 Bilder als Karussell hoch. Gibt die Medien-ID zurück."""
    ig_user = account.instagram_user_id
    if not (ACCESS_TOKEN and ig_user):
        raise InstagramError(f"IG_ACCESS_TOKEN oder {account.instagram_user_env} fehlt in .env")
    if not 2 <= len(image_paths) <= 10:
        raise InstagramError(f"Karussell braucht 2-10 Bilder, bekommen: {len(image_paths)}")

    children = []
    for p in image_paths:
        url = media_host.publish(p)
        child = _post(f"{ig_user}/media", {"image_url": url, "is_carousel_item": "true"})
        children.append(child["id"])

    container = _post(f"{ig_user}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": _caption(script, account),
    })
    _wait_ready(container["id"])
    published = _post(f"{ig_user}/media_publish", {"creation_id": container["id"]})
    log.info("Karussell veröffentlicht: %s (%d Slides)", published.get("id"), len(children))
    return published.get("id", "")


def remaining_quota(account) -> int | None:
    """Wie viele Beiträge sind in den nächsten 24h noch erlaubt? None = unbekannt."""
    try:
        data = _get(f"{account.instagram_user_id}/content_publishing_limit",
                    {"fields": "quota_usage,config"})
        entry = (data.get("data") or [{}])[0]
        return int(entry.get("config", {}).get("quota_total", 50)) - int(entry.get("quota_usage", 0))
    except Exception as e:  # noqa: BLE001
        log.warning("Quota nicht abrufbar: %s", e)
        return None
