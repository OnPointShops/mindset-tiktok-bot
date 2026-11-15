"""
Der Eingang auf dem Mac: Video-Aufträge aus der Handy-App werden hier zu Videos.

Der Weg eines Auftrags:
  1. Kai sagt in der App "Mach ein Video über ..." (oder gibt Bilder dazu).
  2. Eine Claude-Sitzung (die Nachtschicht oder ein Chat) holt den Auftrag ab und
     legt ihn als content/eingang/<id>.json ins Repo, Bilder daneben.
  3. Der Mac holt beim nächsten Update den neuen Stand (git pull) und dieses Modul
     baut das Video mit der vorhandenen Pipeline (make_video.py).
  4. Das fertige Video liegt in videos/, Kai bekommt eine Mitteilung.

Warum der Mac die Auftragsdateien nie löscht oder verschiebt: Sie gehören dem Repo.
Würde der Mac sie anfassen, käme beim nächsten git pull ein Konflikt, und die
Updates blieben hängen. Was erledigt ist, merkt sich deshalb das Gedächtnis.

Gepostet wird ein solches Video NICHT automatisch: Kai hat es bestellt, Kai
entscheidet, wo es hingeht. Es liegt fertig bereit.

Aufbau einer Auftragsdatei:
  {"id": "e-123", "art": "video", "thema": "...", "text": "", "lang": false,
   "bilder": ["e-123_1.jpg"], "erstellt": "2026-11-15T20:00:00Z"}
  "text" wird wörtlich gesprochen; ohne "text" schreibt die KI zum "thema".

Aufruf:
    python3 eingang.py           # offene Aufträge abarbeiten
    python3 eingang.py --liste   # zeigen, was wartet und was fertig ist
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import brain
import config

log = logging.getLogger("eingang")

ORDNER = config.CONTENT_DIR / "eingang"
MAX_JE_LAUF = 2          # ein Video braucht 1-3 Minuten; der Autopilot soll nicht ewig laufen
MAX_VERSUCHE = 3


def _status() -> dict:
    s = brain.personal("eingang_auftraege")      # Personalakte als kleiner Schlüssel-Wert-Speicher
    try:
        return json.loads(s.get("grund") or "{}")
    except json.JSONDecodeError:
        return {}


def _merke(st: dict):
    brain.personal_setze("eingang_auftraege", "aktiv", json.dumps(st, ensure_ascii=False))


def auftraege() -> list[dict]:
    if not ORDNER.exists():
        return []
    aus = []
    for p in sorted(ORDNER.glob("*.json")):
        try:
            a = json.loads(p.read_text(encoding="utf-8"))
            a.setdefault("id", p.stem)
            aus.append(a)
        except Exception as e:  # noqa: BLE001
            log.warning("Auftrag %s unlesbar: %s", p.name, e)
    return aus


def offene() -> list[dict]:
    st = _status()
    return [a for a in auftraege() if a.get("art", "video") == "video"
            and st.get(a["id"], {}).get("status") != "fertig"
            and st.get(a["id"], {}).get("versuche", 0) < MAX_VERSUCHE]


def _baue(a: dict) -> Path:
    """Ruft make_video.py auf — dieselbe Pipeline wie beim Bau per Hand."""
    befehl = [sys.executable, str(config.BASE_DIR / "make_video.py")]
    text = " ".join(str(a.get("text") or "").split())
    if text:
        befehl += ["--text", text]
    else:
        befehl += ["--theme", str(a.get("thema") or a.get("auftrag") or "")[:400]]
    if a.get("lang"):
        befehl.append("--lang")
    vorher = set(config.VIDEO_DIR.glob("custom_*.mp4"))
    r = subprocess.run(befehl, cwd=config.BASE_DIR, capture_output=True, text=True, timeout=1800)
    neu = sorted(set(config.VIDEO_DIR.glob("custom_*.mp4")) - vorher, key=lambda p: p.stat().st_mtime)
    if r.returncode != 0 or not neu:
        zeilen = (r.stdout + r.stderr).strip().splitlines()
        raise RuntimeError(zeilen[-1] if zeilen else "unbekannter Fehler")
    return neu[-1]


def abarbeiten() -> list[str]:
    """Baut bis zu MAX_JE_LAUF offene Videos. Gibt eine Zeile je Ergebnis zurück."""
    fertig = []
    for a in offene()[:MAX_JE_LAUF]:
        st = _status()
        eintrag = st.setdefault(a["id"], {"versuche": 0})
        if not (a.get("text") or a.get("thema") or a.get("auftrag")):
            eintrag.update(status="fertig", fehler="Auftrag ohne Thema und ohne Text")
            _merke(st)
            continue
        eintrag["versuche"] += 1
        _merke(st)
        start = time.monotonic()
        try:
            video = _baue(a)
            eintrag.update(status="fertig", video=str(video.name))
            _merke(st)
            zeile = f"Video fertig: {video.name}"
            brain.event("eingang_video", zeile, {"auftrag": a["id"]})
            brain.team_log("eingang", "video", f"{a['id']}: {video.name}", dauer_s=time.monotonic() - start)
            fertig.append(zeile)
        except Exception as e:  # noqa: BLE001
            meldung = " ".join(str(e).split())[:200]
            eintrag["fehler"] = meldung
            _merke(st)
            brain.log_error("eingang", f"Auftrag {a['id']}: {meldung}")
            if eintrag["versuche"] >= MAX_VERSUCHE:
                brain.frage_kai(f"Das Video aus deinem Auftrag „{str(a.get('thema') or a.get('text'))[:60]}“ "
                                "klappt nicht. Soll ich es mit einem anderen Thema versuchen?", meldung)
    return fertig


def liste() -> str:
    st = _status()
    z = []
    for a in auftraege():
        s = st.get(a["id"], {})
        if a.get("art", "video") != "video":
            zustand = "kein Video, erledigt die Cloud"
        else:
            zustand = "fertig: " + s["video"] if s.get("video") else s.get("fehler") or "wartet"
        z.append(f"{a['id']:<18} {str(a.get('thema') or a.get('text'))[:50]:<52} {zustand}")
    return "\n".join(z) or "Keine Aufträge."


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    print(liste() if "--liste" in sys.argv else "\n".join(abarbeiten()) or "Nichts zu tun.")
