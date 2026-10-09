"""
Täglicher Autopilot:  Selbsttest -> Recherche/Verbesserung -> Posting -> Briefing.
Wird von launchd (Mac) einmal täglich gestartet, siehe install_automation.sh.
Jeder Schritt ist isoliert: ein Fehler stoppt nie den Rest, wird aber im Briefing gemeldet.
"""
import json
import logging
import subprocess
import sys
import traceback
from datetime import datetime

import config

BRIEF_DIR = config.BASE_DIR / "briefing"
BRIEF_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(config.LOGS_DIR / f"{datetime.now():%Y-%m-%d}.log"),
              logging.StreamHandler(sys.stdout)])
log = logging.getLogger("daily_run")


def notify(title, msg):
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "{title}"'], timeout=10)
    except Exception:  # noqa: BLE001
        pass



def self_update():
    """Holt neueste Code-Version per git pull (falls das Projekt ein git-Checkout ist)."""
    import subprocess
    if not (config.BASE_DIR / ".git").exists():
        return
    try:
        r = subprocess.run(["git", "-C", str(config.BASE_DIR), "pull", "--ff-only"],
                           capture_output=True, timeout=60, text=True)
        if "Already up to date" not in r.stdout:
            log.info("Code aktualisiert: %s", r.stdout.strip()[:200])
    except Exception as e:  # noqa: BLE001
        log.warning("Selbst-Update übersprungen: %s", e)



def main():
    self_update()
    problems, health, strategy, posted = [], None, {}, 0

    try:
        import stats_scraper
        new_rows = stats_scraper.update_performance()
        if new_rows:
            log.info("Performance-Daten aktualisiert: %d neue Zeile(n)", new_rows)
    except Exception as e:  # noqa: BLE001
        problems.append(f"Performance-Scrape fehlgeschlagen (TikTok-UI evtl. geändert): {e}")

    import selftest
    try:
        ok, health = selftest.run_selftest()
        if not ok:
            problems += [f"{c['name']}: {c['detail']}" for c in health["checks"] if not c["ok"] and c["critical"]]
    except Exception:  # noqa: BLE001
        ok = False
        problems.append("Selbsttest abgestürzt: " + traceback.format_exc(limit=1))

    try:
        import improver
        strategy = improver.run_improver()
    except Exception as e:  # noqa: BLE001
        problems.append(f"Verbesserungs-Recherche fehlgeschlagen: {e}")

    # Tagesziel = Summe aller Accounts im Portfolio
    import accounts as accounts_mod
    portfolio = accounts_mod.enabled()
    daily_target = sum(a.posts_per_day for a in portfolio) or config.POSTS_PER_DAY

    if ok:
        try:
            import scheduler
            scheduler.run_cycle()
            # Gezählt wird, was HEUTE über alle Accounts tatsächlich rausging —
            # nicht nur, was dieser eine Lauf geschafft hat (der Cron läuft stündlich).
            posted = sum(accounts_mod.posted_today(a) for a in portfolio)
            if posted < daily_target:
                problems.append(
                    f"Erst {posted}/{daily_target} Beiträge heute veröffentlicht "
                    f"(die späteren Slots laufen evtl. noch)")
        except Exception as e:  # noqa: BLE001
            problems.append(f"Posting-Zyklus fehlgeschlagen: {e}")
    else:
        problems.append("Posting übersprungen, weil der Selbsttest kritische Fehler hatte.")

    # Briefing schreiben
    q = json.loads(config.QUEUE_FILE.read_text(encoding="utf-8")) if config.QUEUE_FILE.exists() else []
    total_posted = len([x for x in q if x.get("status") == "posted"])
    lines = [f"# JK24 Mindset-Bot Briefing {datetime.now():%d.%m.%Y}", "",
             f"**Heute gepostet:** {posted}/{daily_target}  |  **Gesamt:** {total_posted}", ""]
    lines += ["| Account | heute | Ziel |", "|---|---:|---:|"]
    lines += [f"| {a.id} | {accounts_mod.posted_today(a)} | {a.posts_per_day} |" for a in portfolio]
    lines += [""]
    lines += ["## Probleme"] + ([f"- {p}" for p in problems] or ["- keine"]) + [""]
    if strategy:
        lines += ["## Neue Erkenntnisse"] + [f"- {x}" for x in strategy.get("lessons", [])] + [""]
        if strategy.get("rule_alerts"):
            lines += ["## Regel-Warnungen"] + [f"- {x}" for x in strategy["rule_alerts"]] + [""]
        lines += ["## Experiment für morgen", strategy.get("experiment_of_the_day", "-"), ""]
    lines += ["## Views",
              "Werden jetzt automatisch vom öffentlichen Profil abgegriffen (stats_scraper.py) - "
              "keine manuelle Eingabe mehr nötig. Falls oben ein Performance-Scrape-Fehler steht: "
              "TikTok hat vermutlich sein Profil-Layout geändert, kurz Bescheid geben, dann fixe ich das."]
    text = "\n".join(lines)
    (BRIEF_DIR / f"{datetime.now():%Y-%m-%d}.md").write_text(text, encoding="utf-8")
    (BRIEF_DIR / "latest.md").write_text(text, encoding="utf-8")
    notify("Mindset-Bot", f"{posted} Video(s) gepostet, {len(problems)} Problem(e). Briefing: briefing/latest.md")
    log.info("Briefing geschrieben.")


if __name__ == "__main__":
    main()
