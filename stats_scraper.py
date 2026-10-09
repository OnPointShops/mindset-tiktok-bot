"""
Content-Analyse-Maschine, Teil 2: holt echte View-Zahlen vom eigenen (öffentlichen)
TikTok-Profil und schreibt sie in content/performance.csv. improver.py liest diese
Datei bereits und leitet daraus Lehren für die nächsten Skripte ab — damit schließt
sich der Kreislauf: posten -> echte Zahlen holen -> Strategie schärfen -> nächstes
Video besser.

Braucht KEINEN Login/Cookie: TikTok zeigt auf öffentlichen Profilen die View-Zahl
direkt im Thumbnail-Grid. Das ist deutlich robuster als die eingeloggte Studio-
Analytics-Seite (dort ändert sich das UI öfter + Captcha-Risiko bei Automatisierung).

Zuordnung: die N neuesten Grid-Videos werden den N neuesten "posted"-Einträgen aus
post_queue.json zugeordnet (beide chronologisch neu->alt). Funktioniert zuverlässig,
SOLANGE auf dem Account nur über diesen Bot gepostet wird (keine manuellen Extra-Posts
zwischengeschoben) - sonst verschiebt sich die Zuordnung. Bei Zweifel lieber einmal
händisch gegenprüfen, bevor du dich blind auf die Zahlen verlässt.

Aufruf:  python3 stats_scraper.py
Sinnvoll: einmal täglich VOR improver.py laufen lassen (z.B. in daily_run.py einbauen).
"""
import csv
import json
import logging
import time

import config

logger = logging.getLogger("stats_scraper")
PERF_FILE = config.CONTENT_DIR / "performance.csv"
FIELDS = ["topic", "format", "views", "likes", "comments", "shares", "scraped_at"]


def _parse_count(text: str) -> int:
    """TikTok zeigt '1.2M', '834K', '12' etc. -> in echte Zahl umrechnen."""
    text = text.strip().upper().replace(",", ".")
    if not text:
        return 0
    mult = 1
    if text.endswith("K"):
        mult, text = 1_000, text[:-1]
    elif text.endswith("M"):
        mult, text = 1_000_000, text[:-1]
    elif text.endswith("B"):
        mult, text = 1_000_000_000, text[:-1]
    try:
        return int(float(text) * mult)
    except ValueError:
        return 0


def fetch_profile_video_views(username: str, max_videos: int = 20) -> list[dict]:
    """Öffnet das öffentliche Profil und liest View-Zahlen aus dem Thumbnail-Grid.
    Gibt eine Liste [{"views": int}, ...] zurück, neuestes Video zuerst."""
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ))
        try:
            page.goto(f"https://www.tiktok.com/@{username}", timeout=30000)
            page.wait_for_timeout(2500)
            # Grid-Items: Links, die auf /video/ zeigen
            for _ in range(4):  # ein paar Mal scrollen, um mehr Videos zu laden
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(800)

            items = page.query_selector_all('div[data-e2e="user-post-item"]')
            for item in items[:max_videos]:
                count_el = item.query_selector('strong[data-e2e="video-views"]')
                views = _parse_count(count_el.inner_text()) if count_el else 0
                results.append({"views": views})
        finally:
            browser.close()
    return results


def _history():
    if config.QUEUE_FILE.exists():
        return json.loads(config.QUEUE_FILE.read_text(encoding="utf-8"))
    return []


def _already_scraped_topics() -> set:
    if not PERF_FILE.exists():
        return set()
    with PERF_FILE.open(encoding="utf-8") as f:
        return {row["topic"] for row in csv.DictReader(f)}


def update_performance() -> int:
    """Holt aktuelle View-Zahlen für ALLE TikTok-Accounts des Portfolios und
    ergänzt performance.csv um neue Zeilen. Gibt die Anzahl neuer Zeilen zurück."""
    import accounts as accounts_mod

    history = [h for h in _history() if h.get("status") == "posted"]
    if not history:
        logger.info("Keine geposteten Videos in der Historie — nichts zu tun.")
        return 0

    tiktok_accounts = [a for a in accounts_mod.enabled() if a.tiktok_account_name]
    if not tiktok_accounts:
        # Fallback auf die alte Ein-Account-Konfiguration aus .env
        tiktok_accounts = [type("A", (), {"id": "", "tiktok_account_name":
                                          config.TIKTOK_ACCOUNT_NAME})()]

    already = _already_scraped_topics()
    new_rows = []

    for acc in tiktok_accounts:
        if not acc.tiktok_account_name:
            continue
        posted = [h for h in history if h.get("account", acc.id) == acc.id]
        posted.sort(key=lambda h: h.get("posted_at", h.get("generated_at", "")), reverse=True)
        if not posted:
            continue

        try:
            video_stats = fetch_profile_video_views(acc.tiktok_account_name,
                                                    max_videos=len(posted))
        except Exception as e:  # noqa: BLE001
            logger.warning("Profil-Scrape für %s fehlgeschlagen (%s) — TikTok-UI evtl. geändert.",
                           acc.tiktok_account_name, e)
            continue

        if not video_stats:
            logger.warning("Keine Videos im Grid von %s — privat? noch nichts sichtbar?",
                           acc.tiktok_account_name)
            continue

        for queue_entry, stat in zip(posted, video_stats):
            topic = queue_entry.get("topic", "")
            if topic in already:
                continue  # schon erfasst, nicht doppelt schreiben
            already.add(topic)
            new_rows.append({
                "topic": topic,
                "format": queue_entry.get("format", ""),
                "views": stat["views"],
                "likes": "", "comments": "", "shares": "",  # im Grid nicht sichtbar
                "scraped_at": time.strftime("%Y-%m-%d %H:%M"),
            })

    if not new_rows:
        logger.info("Keine neuen Datenpunkte (alles schon erfasst).")
        return 0

    write_header = not PERF_FILE.exists()
    with PERF_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)

    logger.info("Performance-Daten aktualisiert: %d neue Zeile(n)", len(new_rows))
    return len(new_rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    update_performance()
