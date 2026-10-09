"""
Mehrere Accounts aus einer Pipeline.

Bisher kannte das Projekt genau einen TikTok-Account (config.TIKTOK_ACCOUNT_NAME).
Für den 10k-Plan braucht es ein PORTFOLIO: drei Accounts, verschiedene Nischen,
verschiedene Formate — denn kein einzelner Account ist planbar erfolgreich,
ein Portfolio ist es statistisch.

Konfiguriert wird das in content/accounts.json (wird beim ersten Lauf aus den
Defaults unten angelegt). Secrets stehen NIE hier drin, sondern in .env —
die JSON verweist nur auf die Namen der .env-Variablen.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date

import config

log = logging.getLogger("accounts")

ACCOUNTS_FILE = config.CONTENT_DIR / "accounts.json"
SLOTLOG_FILE = config.CONTENT_DIR / "posted_slots.json"


# ── Standard-Portfolio (Strategie siehe STRATEGIE_10K.md, Abschnitt 3.1) ────────
DEFAULT_ACCOUNTS = [
    {
        "id": "mindset",
        "name": "Mindset / Disziplin",
        "enabled": True,
        "platforms": ["tiktok"],
        "niche": "Mindset, Disziplin, Stoizismus, mentale Härte",
        "content_format": "video",
        "posts_per_day": 3,
        "post_times": ["07:20", "12:40", "18:30"],
        "tiktok_account_name": "mindset_daily_de",
        "instagram_user_env": "IG_USER_ID_MINDSET",
        "youtube_token_env": "YT_REFRESH_TOKEN_MINDSET",
        "voice_id": "",
        "visual_style": "street_bw",
        "link_in_bio": "",
        "base_hashtags": ["mindset", "disziplin", "motivation"],
    },
    {
        "id": "ki",
        "name": "KI & Automatisierung fürs Business",
        "enabled": True,
        "platforms": ["instagram", "tiktok"],
        "niche": (
            "KI-Tools und Automatisierung für Selbstständige und kleine Unternehmen: "
            "konkrete Workflows, Zeitersparnis in Stunden, Tools mit Namen, keine Buzzwords"
        ),
        "content_format": "carousel",
        "posts_per_day": 3,
        "post_times": ["08:10", "13:20", "19:10"],
        "tiktok_account_name": "",
        "instagram_user_env": "IG_USER_ID_KI",
        "youtube_token_env": "",
        "voice_id": "",
        "visual_style": "street_bw",
        "link_in_bio": "",
        "base_hashtags": ["ki", "automatisierung", "selbststaendigkeit"],
    },
    {
        "id": "nebenverdienst",
        "name": "Selbstständigkeit / Nebeneinkommen",
        "enabled": True,
        "platforms": ["tiktok", "instagram"],
        "niche": (
            "Nebeneinkommen und Selbstständigkeit in Deutschland: realistische Zahlen, "
            "Behörden, Steuern, erste Kunden — ehrlich statt Hochglanz"
        ),
        "content_format": "mixed",
        "posts_per_day": 2,
        "post_times": ["09:15", "17:40"],
        "tiktok_account_name": "",
        "instagram_user_env": "IG_USER_ID_NEBEN",
        "youtube_token_env": "",
        "voice_id": "",
        "visual_style": "street_bw",
        "link_in_bio": "",
        "base_hashtags": ["nebeneinkommen", "selbststaendig", "business"],
    },
]


@dataclass
class Account:
    id: str
    name: str = ""
    enabled: bool = True
    platforms: list = field(default_factory=lambda: ["tiktok"])
    niche: str = ""
    content_format: str = "video"          # video | carousel | mixed
    posts_per_day: int = 1
    post_times: list = field(default_factory=lambda: ["18:30"])
    tiktok_account_name: str = ""
    instagram_user_env: str = ""
    youtube_token_env: str = ""
    voice_id: str = ""
    visual_style: str = "street_bw"
    link_in_bio: str = ""
    base_hashtags: list = field(default_factory=list)

    # ── abgeleitete Werte ──────────────────────────────────────────────────────
    @property
    def instagram_user_id(self) -> str:
        """IG-Business-User-ID aus .env (nie in der JSON speichern)."""
        return os.getenv(self.instagram_user_env, "") if self.instagram_user_env else ""

    @property
    def youtube_refresh_token(self) -> str:
        return os.getenv(self.youtube_token_env, "") if self.youtube_token_env else ""

    def format_for_slot(self, slot_index: int) -> str:
        """Bei 'mixed' wechseln sich Video und Karussell ab — sonst immer dasselbe."""
        if self.content_format != "mixed":
            return self.content_format
        return "video" if slot_index % 2 == 0 else "carousel"

    def targets(self) -> list[str]:
        """Plattformen, für die wirklich Zugangsdaten hinterlegt sind."""
        live = []
        for p in self.platforms:
            if p == "tiktok" and self.tiktok_account_name:
                live.append(p)
            elif p == "instagram" and self.instagram_user_id:
                live.append(p)
            elif p == "youtube" and self.youtube_refresh_token:
                live.append(p)
        return live


# ── Laden / Speichern ──────────────────────────────────────────────────────────
def load() -> list[Account]:
    """Liest content/accounts.json; legt sie beim ersten Mal aus den Defaults an."""
    if not ACCOUNTS_FILE.exists():
        ACCOUNTS_FILE.write_text(
            json.dumps(DEFAULT_ACCOUNTS, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("accounts.json neu angelegt (%s) — bitte Namen/Links eintragen.", ACCOUNTS_FILE)

    raw = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    known = set(Account.__dataclass_fields__)
    return [Account(**{k: v for k, v in entry.items() if k in known}) for entry in raw]


def save(accs: list[Account]):
    ACCOUNTS_FILE.write_text(
        json.dumps([asdict(a) for a in accs], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def enabled() -> list[Account]:
    return [a for a in load() if a.enabled]


def get(account_id: str) -> Account | None:
    return next((a for a in load() if a.id == account_id), None)


# ── Slot-Logik: was ist JETZT fällig? ──────────────────────────────────────────
def _slotlog() -> dict:
    if SLOTLOG_FILE.exists():
        return json.loads(SLOTLOG_FILE.read_text(encoding="utf-8"))
    return {}


def _save_slotlog(data: dict):
    # Nur die letzten 14 Tage behalten, sonst wächst die Datei ewig
    keep = sorted(data.keys())[-14:]
    SLOTLOG_FILE.write_text(
        json.dumps({k: data[k] for k in keep}, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def due_slots(acc: Account, now: datetime | None = None, tolerance_min: int = 45) -> list[int]:
    """
    Gibt die Slot-Indizes zurück, die heute fällig und noch nicht gepostet sind.

    Gedacht für einen STÜNDLICHEN Cron-Lauf: jeder Lauf prüft, ob ein Posting-Zeitpunkt
    gerade erreicht ist. Verpasste Slots (Server war aus, Fehler) werden später am Tag
    nachgeholt, solange der Tag nicht vorbei ist — besser spät posten als gar nicht.
    """
    now = now or datetime.now()
    today = now.date().isoformat()
    done = set(_slotlog().get(today, {}).get(acc.id, []))

    due = []
    for i, t in enumerate(acc.post_times[: acc.posts_per_day]):
        if i in done:
            continue
        try:
            hh, mm = (int(x) for x in t.split(":"))
        except ValueError:
            log.warning("Ungültige Uhrzeit '%s' bei Account %s — übersprungen", t, acc.id)
            continue
        slot_minutes = hh * 60 + mm
        now_minutes = now.hour * 60 + now.minute
        # fällig ab Slot-Zeit (minus Toleranz), Nachholen bis Tagesende
        if now_minutes >= slot_minutes - tolerance_min:
            due.append(i)
    return due


def mark_posted(acc: Account, slot_index: int, when: datetime | None = None):
    when = when or datetime.now()
    today = when.date().isoformat()
    data = _slotlog()
    data.setdefault(today, {}).setdefault(acc.id, [])
    if slot_index not in data[today][acc.id]:
        data[today][acc.id].append(slot_index)
    _save_slotlog(data)


def posted_today(acc: Account, when: datetime | None = None) -> int:
    when = when or datetime.now()
    return len(_slotlog().get(when.date().isoformat(), {}).get(acc.id, []))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for a in load():
        state = "AN " if a.enabled else "AUS"
        print(f"[{state}] {a.id:16s} {a.posts_per_day}x/Tag  Format={a.content_format:8s} "
              f"Plattformen={','.join(a.targets()) or '— keine Zugangsdaten —'}  "
              f"fällig jetzt: {due_slots(a) if a.enabled else []}")
