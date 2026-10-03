"""
Fallback-Dauerprozess für den Fall, dass kein System-Cron verfügbar ist
(z.B. auf manchen Managed-Hosting-Plattformen). Empfohlen ist trotzdem Cron
(siehe README) — dieser Prozess muss durchgehend laufen (z.B. via systemd,
pm2, oder `nohup python3 main.py &`), sonst verpasst er Zeitfenster.
"""
import time
import logging
import schedule as sched_lib

import config
import scheduler
import trend_research

logger = logging.getLogger("main")


def job_daily_post():
    scheduler.run_daily_cycle()


def job_weekly_trends():
    trend_research.refresh_trends()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Startprozess läuft. Posting täglich um %s, Trend-Refresh montags 06:00.",
                config.POST_TIME)

    sched_lib.every().day.at(config.POST_TIME).do(job_daily_post)
    sched_lib.every().monday.at("06:00").do(job_weekly_trends)

    # Einmal sofort beim Start prüfen, ob Trends fehlen (erster Lauf überhaupt)
    if not config.TRENDS_FILE.exists():
        job_weekly_trends()

    while True:
        sched_lib.run_pending()
        time.sleep(30)
