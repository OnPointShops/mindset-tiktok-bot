"""
Wrapper um tiktokautouploader. Kapselt Cookie-Handling, Proxy-Konfiguration
und Logging an einem Ort, damit der Rest der Pipeline nichts von den
Upload-Details wissen muss.

WICHTIG (einmalig, manuell): Beim allerersten Aufruf für einen neuen Account
öffnet tiktokautouploader ein sichtbares Browserfenster (headless=False wird
dafür intern erzwungen) und wartet auf manuellen Login. Das MUSS auf einer
Maschine mit GUI/Display passieren (nicht in diesem Cloud-Sandbox-Container).
Danach liegen Cookies in TK_cookies_<accountname>.json und alles läuft headless.
"""
import logging
from pathlib import Path

from tiktokautouploader import upload_tiktok

import config

logger = logging.getLogger("uploader")


def post_video(script: dict, video_path: str, schedule_time: str | None = None,
               schedule_day: int | None = None) -> str:
    """
    Postet ein fertiges Video. Gibt 'Completed' oder 'Error' zurück
    (so wie es tiktokautouploader selbst zurückgibt).
    """
    hashtags = script.get("hashtags", [])
    description = script.get("caption", script.get("hook", ""))

    logger.info(
        "Upload startet | Account=%s | Video=%s | Schedule=%s",
        config.TIKTOK_ACCOUNT_NAME, video_path, schedule_time,
    )

    # Cookie-Datei liegt per Lib-Konvention im aktuellen Arbeitsverzeichnis —
    # wir wechseln kontrolliert dorthin, damit sie in cookies/ landet statt im Projekt-Root.
    import os
    prev_cwd = os.getcwd()
    os.chdir(config.COOKIES_DIR)
    try:
        result = upload_tiktok(
            video=str(Path(video_path).resolve()),
            description=description,
            accountname=config.TIKTOK_ACCOUNT_NAME,
            hashtags=hashtags,
            schedule=schedule_time,
            day=schedule_day,
            headless=True,
            stealth=True,
            proxy=config.get_proxy(),
            suppressprint=False,
        )
    finally:
        os.chdir(prev_cwd)

    if result == "Completed":
        logger.info("Upload erfolgreich: %s", script.get("topic"))
    else:
        logger.error("Upload fehlgeschlagen: %s | Ergebnis=%s", script.get("topic"), result)
    return result


def first_time_login_instructions() -> str:
    return f"""
Einmaliger manueller Schritt (kann ich nicht für dich automatisieren — TikTok
verlangt hier bewusst einen Menschen):

1. Auf einer Maschine MIT Bildschirm (dein Laptop/PC, NICHT dieser Cloud-Container):
   pip install tiktokautouploader
   phantomwright_driver install chromium

2. Einmal ausführen:
   python3 -c "from tiktokautouploader import upload_tiktok; upload_tiktok(
       video='irgendein_test.mp4', description='test',
       accountname='{config.TIKTOK_ACCOUNT_NAME}', headless=False)"

3. Browser öffnet sich -> bei TikTok mit dem Account "{config.TIKTOK_ACCOUNT_NAME}" einloggen.

4. Die entstandene Datei TK_cookies_{config.TIKTOK_ACCOUNT_NAME}.json
   in den Ordner cookies/ dieses Projekts kopieren.

Danach läuft alles headless und automatisch — kein weiterer manueller Login nötig,
außer TikTok verlangt irgendwann eine Re-Authentifizierung (dann wiederholst du
nur Schritt 2-4).
"""


def do_first_time_login():
    """Öffnet Browser für einmaligen TikTok-Login. Läuft auf Mac/PC mit Display."""
    import os
    prev_cwd = os.getcwd()
    os.chdir(config.COOKIES_DIR)
    try:
        print(f"\nBrowser öffnet sich — logge dich bei TikTok ein als '{config.TIKTOK_ACCOUNT_NAME}'")
        print("Nach dem Login einfach das Browserfenster schließen.\n")
        # Dummy-Video nötig, damit die Lib den Browser öffnet
        dummy = config.COOKIES_DIR / "_login_dummy.mp4"
        dummy.touch()
        upload_tiktok(
            video=str(dummy.resolve()),
            description="login",
            accountname=config.TIKTOK_ACCOUNT_NAME,
            headless=False,   # sichtbarer Browser für Login
            stealth=True,
        )
        dummy.unlink(missing_ok=True)
    finally:
        os.chdir(prev_cwd)
    print("✓ Login gespeichert. Ab jetzt läuft alles automatisch.")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if "--login" in sys.argv:
        do_first_time_login()
    else:
        print(first_time_login_instructions())
