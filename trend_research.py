"""
Hält die Content-Pipeline aktuell: recherchiert wöchentlich, welche Hook-Stile,
Themen und Formate gerade in der Mindset/Motivation-Nische auf TikTok ziehen,
und schreibt das Ergebnis nach content/current_trends.json.

Nutzt Claude mit Web-Suche-fähigem Prompting-Ansatz: da dieses Skript ohne
Zugriff auf Anthropics eigene Web-Search-Tool-Integration läuft (das ist an
diese Konversation gebunden, nicht an eigenständige Skripte), verlässt es
sich auf das Trainingswissen + explizite Aufforderung, sich auf stabile,
nischen-typische Muster zu konzentrieren statt auf tagesaktuelle Ereignisse.

WICHTIG: Für ECHTE tagesaktuelle Trend-Daten (was diese Woche viral ging)
gibt es zwei robustere Wege, beide unten als Stubs vorbereitet:
  (A) TikTok Research API (kostenlos für Non-Profit/Academic, 24h-7 Tage
      Latenz, https://developers.tiktok.com/products/research-api/)
  (B) Ein Scraping-Tool wie Viralway/viralAPI (github.com/Viralway/viralAPI)
      gegen die Explore-Kategorie "motivation"/"self improvement"
Beide brauchen eigene Setup-Schritte, die ich nicht ungefragt für dich
einrichte (API-Antrag bzw. TikTok-Cookie-Abhängigkeit) — Stubs sind unten
mit TODO markiert, falls du das nachrüsten willst.
"""
import json
import logging
from datetime import datetime

from anthropic import Anthropic

import config

logger = logging.getLogger("trend_research")

TREND_PROMPT = """Du recherchierst für einen deutschsprachigen Mindset/Motivation \
TikTok-Kanal. Liste 10 Themen/Hook-Muster, die in dieser Nische nachweislich \
gut funktionieren (basierend auf etablierten, stabilen Mustern der Nische — \
Stoizismus, Disziplin-vs-Motivation, "harte Wahrheiten", Vergleich \
früher-ich-vs-jetzt-ich, 3am-Grind-Narrative, Anti-Opfer-Mentalität, etc.).

Für jedes Thema: ein kurzes Label + eine Notiz, WARUM es funktioniert \
(welcher psychologische Hebel).

Gib AUSSCHLIESSLICH valides JSON zurück:
{
  "themes": ["Label: kurze Begründung", ...],
  "hook_styles": ["Hook-Muster-Beschreibung", ...]
}
"""


def refresh_trends():
    """Generiert einen neuen Trend-Kontext und überschreibt current_trends.json."""
    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY fehlt — überspringe Trend-Refresh.")
        return

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        messages=[{"role": "user", "content": TREND_PROMPT}],
    )
    raw = response.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Trend-Response war kein valides JSON, überspringe Update.")
        return

    data["updated"] = datetime.now().isoformat()
    config.TRENDS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Trends aktualisiert: %d Themen, %d Hook-Stile",
                len(data.get("themes", [])), len(data.get("hook_styles", [])))


# --- TODO-Stubs für tagesaktuelle Daten (siehe Docstring oben) ---

def fetch_from_tiktok_research_api():
    """
    Stub. TikTok Research API: kostenlos, aber Antrag nötig (Approval-Prozess,
    nur für Forschungs-/Non-Profit-Zwecke zugelassen) + 24h-7 Tage Latenz.
    Nicht für ein kommerzielles Vending/Content-Business vorgesehen — daher
    hier nur als Hinweis, nicht implementiert.
    """
    raise NotImplementedError("Erfordert eigenen API-Antrag bei developers.tiktok.com")


def fetch_from_viral_scraper():
    """
    Stub. Anbindung an github.com/Viralway/viralAPI möglich, um echte
    aktuell-virale Videos der Kategorie 'motivation' zu ziehen (Titel, Views,
    Hashtags) und das als zusätzlichen Kontext in TREND_PROMPT einzuspeisen.
    Nicht aktiviert, weil es einen aktuellen msToken-Cookie von tiktok.com
    braucht, der manuell alle paar Wochen erneuert werden muss.
    """
    raise NotImplementedError("Optional nachrüstbar, siehe Docstring")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    refresh_trends()
    if config.TRENDS_FILE.exists():
        print(config.TRENDS_FILE.read_text(encoding="utf-8"))
