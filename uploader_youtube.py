"""
YouTube-Shorts-Upload über die offizielle Data API v3.

Dritte Plattform ohne Mehraufwand: dasselbe Video, das zu TikTok geht, läuft
hier gleich mit. Die Ausschüttung ist klein (~0,03-0,08 €/1000 Views in DE),
aber YouTube ist die einzige der drei Plattformen, die aus altem Content noch
nach Monaten Reichweite zieht. Das macht sie als Langzeit-Archiv wertvoll.

Bewusst ohne google-api-python-client: das Paket zieht einen großen
Abhängigkeitsbaum mit (siehe die Warnung zu tiktokautouploader in
requirements.txt). Der OAuth-Refresh und der resumable Upload sind zwei
HTTP-Aufrufe — die macht `requests` ohne jedes Risiko für den Rest der Umgebung.

Voraussetzungen (einmalig, siehe TODO_KAI.md Schritt 5):
  - Google-Cloud-Projekt, YouTube Data API v3 aktiviert
  - OAuth-Client (Desktop) -> YT_CLIENT_ID / YT_CLIENT_SECRET in .env
  - Refresh-Token je Kanal -> YT_REFRESH_TOKEN_<ACCOUNT> in .env
    (einmalig erzeugen mit: python3 uploader_youtube.py --auth)

Kontingent: Ein Upload kostet 1.600 Einheiten vom Tageslimit 10.000
-> maximal 6 Uploads pro Tag und Projekt. Für den Plan (3/Tag) ausreichend;
bei mehr Kanälen braucht jeder Kanal ein eigenes Cloud-Projekt oder du
beantragst eine Kontingenterhöhung.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

log = logging.getLogger("uploader_youtube")

CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TIMEOUT = 120


class YouTubeError(RuntimeError):
    pass


def _access_token(refresh_token: str) -> str:
    r = requests.post(TOKEN_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise YouTubeError(f"Token-Erneuerung fehlgeschlagen ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def _title(script: dict) -> str:
    """YouTube-Titel: max. 100 Zeichen, '#Shorts' sichert die Shorts-Einstufung."""
    base = (script.get("hook") or script.get("topic") or "Mindset").strip()
    base = base[:85].rstrip(" ,.;:-")
    return f"{base} #Shorts"


def _description(script: dict, account) -> str:
    parts = []
    if script.get("is_ad"):
        parts.append("Werbung")
    parts.append(script.get("caption") or script.get("hook", ""))
    if account is not None and account.link_in_bio:
        parts.append(account.link_in_bio)
    tags = list(script.get("hashtags", []))
    if account is not None:
        tags += [t for t in account.base_hashtags if t not in tags]
    if tags:
        parts.append(" ".join(f"#{t.lstrip('#')}" for t in tags[:8]))
    return "\n\n".join(p for p in parts if p)[:4900]


def post_short(script: dict, video_path: str, account, privacy: str = "public") -> str:
    """Lädt ein Video als YouTube Short hoch. Gibt die Video-ID zurück."""
    refresh = account.youtube_refresh_token
    if not (CLIENT_ID and CLIENT_SECRET and refresh):
        raise YouTubeError(
            f"YT_CLIENT_ID/YT_CLIENT_SECRET oder {account.youtube_token_env} fehlt in .env"
        )
    path = Path(video_path)
    if not path.exists():
        raise YouTubeError(f"Video fehlt: {path}")

    token = _access_token(refresh)
    metadata = {
        "snippet": {
            "title": _title(script),
            "description": _description(script, account),
            "tags": [t.lstrip("#") for t in script.get("hashtags", [])][:15],
            "categoryId": "22",          # People & Blogs
            "defaultLanguage": "de",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Schritt 1: Upload-Sitzung eröffnen (resumable — übersteht Verbindungsabbrüche)
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/*",
            "X-Upload-Content-Length": str(path.stat().st_size),
        },
        data=json.dumps(metadata).encode("utf-8"),
        timeout=TIMEOUT,
    )
    if init.status_code >= 400:
        raise YouTubeError(f"Upload-Start fehlgeschlagen ({init.status_code}): {init.text[:300]}")
    session_url = init.headers.get("Location")
    if not session_url:
        raise YouTubeError("YouTube hat keine Upload-URL zurückgegeben.")

    # Schritt 2: Datei in einem Rutsch senden (Shorts sind klein, < 100 MB)
    with path.open("rb") as fh:
        up = requests.put(
            session_url, data=fh,
            headers={"Content-Type": "video/*", "Content-Length": str(path.stat().st_size)},
            timeout=600,
        )
    if up.status_code >= 400:
        raise YouTubeError(f"Upload fehlgeschlagen ({up.status_code}): {up.text[:300]}")

    video_id = up.json().get("id", "")
    log.info("Short veröffentlicht: https://youtube.com/shorts/%s", video_id)
    return video_id


# ── Einmalige Token-Erzeugung ──────────────────────────────────────────────────
def interactive_auth():
    """
    Erzeugt den Refresh-Token für einen Kanal (Device-Flow — funktioniert auch
    auf einem Server ohne Browser: du bestätigst am Handy).
    """
    if not (CLIENT_ID and CLIENT_SECRET):
        raise SystemExit("YT_CLIENT_ID und YT_CLIENT_SECRET müssen in .env stehen.")

    r = requests.post("https://oauth2.googleapis.com/device/code",
                      data={"client_id": CLIENT_ID, "scope": SCOPE}, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    print(f"\n1. Öffne:  {d['verification_url']}")
    print(f"2. Code:   {d['user_code']}")
    print("3. Danach hier Enter drücken.\n")
    input()

    for _ in range(60):
        t = requests.post(TOKEN_URL, data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "device_code": d["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }, timeout=TIMEOUT)
        body = t.json()
        if "refresh_token" in body:
            print("\n✓ Fertig. Diese Zeile in .env eintragen:\n")
            print(f"YT_REFRESH_TOKEN_<ACCOUNT>={body['refresh_token']}\n")
            return
        if body.get("error") not in ("authorization_pending", "slow_down"):
            raise SystemExit(f"Fehler: {body}")
        import time
        time.sleep(d.get("interval", 5))
    raise SystemExit("Zeitüberschreitung — bitte nochmal versuchen.")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--auth" in sys.argv:
        interactive_auth()
    else:
        print(__doc__)
