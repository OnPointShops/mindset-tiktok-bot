"""
Einrichtungs-Assistent. Fragt Schritt für Schritt ab, was das System braucht,
prüft jeden Schlüssel sofort gegen die echte API und schreibt .env.

Gedacht für jemanden, der nicht programmiert: jede Frage erklärt, warum sie
gestellt wird, was es kostet, und wo man den Wert herbekommt. Alles lässt
sich mit Enter überspringen — das System läuft dann eben eingeschränkt
weiter statt gar nicht.

    python3 einrichten.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"

GRUEN, GELB, ROT, GRAU, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[0m"


def lies_env() -> dict:
    werte = {}
    if ENV.exists():
        for zeile in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in zeile and not zeile.strip().startswith("#"):
                k, _, v = zeile.partition("=")
                werte[k.strip()] = v.strip()
    return werte


def schreib_env(werte: dict):
    """Schreibt .env neu, behält Kommentare aus .env.example als Orientierung."""
    vorlage = (BASE / ".env.example").read_text(encoding="utf-8") if (BASE / ".env.example").exists() else ""
    zeilen, gesetzt = [], set()
    for zeile in vorlage.splitlines():
        m = re.match(r"^([A-Z0-9_]+)=", zeile)
        if m and m.group(1) in werte:
            zeilen.append(f"{m.group(1)}={werte[m.group(1)]}")
            gesetzt.add(m.group(1))
        else:
            zeilen.append(zeile)
    rest = {k: v for k, v in werte.items() if k not in gesetzt}
    if rest:
        zeilen += ["", "# --- zusätzlich beim Einrichten gesetzt ---"]
        zeilen += [f"{k}={v}" for k, v in rest.items()]
    ENV.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    ENV.chmod(0o600)        # nur du darfst die Datei lesen — da stehen Schlüssel drin


# ── Prüfungen: jeder Schlüssel wird sofort gegen die echte API getestet ───────
def pruef_gemini(key: str) -> tuple[bool, str]:
    import requests
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"key": key}, timeout=20)
    if r.status_code == 200:
        n = len(r.json().get("models", []))
        return True, f"{n} Modelle erreichbar"
    return False, f"HTTP {r.status_code}: {r.text[:120]}"


def pruef_elevenlabs(key: str) -> tuple[bool, str]:
    import requests
    r = requests.get("https://api.elevenlabs.io/v1/user",
                     headers={"xi-api-key": key}, timeout=20)
    if r.status_code == 200:
        d = r.json().get("subscription", {})
        rest = d.get("character_limit", 0) - d.get("character_count", 0)
        return True, f"{rest} Zeichen übrig diesen Monat"
    return False, f"HTTP {r.status_code}"


def pruef_pexels(key: str) -> tuple[bool, str]:
    import requests
    r = requests.get("https://api.pexels.com/videos/search",
                     headers={"Authorization": key}, params={"query": "city", "per_page": 1},
                     timeout=20)
    return (True, "ok") if r.status_code == 200 else (False, f"HTTP {r.status_code}")


def pruef_instagram(token: str) -> tuple[bool, str]:
    import requests
    r = requests.get("https://graph.facebook.com/v23.0/me/accounts",
                     params={"access_token": token}, timeout=20)
    if r.status_code != 200:
        return False, r.json().get("error", {}).get("message", f"HTTP {r.status_code}")[:120]
    seiten = r.json().get("data", [])
    return True, f"{len(seiten)} Facebook-Seite(n) gefunden"


FRAGEN = [
    {
        "key": "GEMINI_API_KEY",
        "titel": "KI für Texte und Recherche",
        "warum": "Schreibt alle Skripte und sucht täglich nach neuen Möglichkeiten.\n"
                 "Ohne diesen Schlüssel läuft das System nur aus dem Textvorrat.",
        "kosten": "KOSTENLOS, keine Kreditkarte",
        "wo": "https://aistudio.google.com/apikey  →  'Create API key'",
        "pflicht": True,
        "pruefen": pruef_gemini,
    },
    {
        "key": "ELEVENLABS_API_KEY",
        "titel": "Erzählerstimme",
        "warum": "Echte deutsche Stimme für die Videos. Ohne sie wird die lokale\n"
                 "Stimme genutzt — die klingt brauchbar, aber hörbar künstlicher.",
        "kosten": "KOSTENLOS bis 10.000 Zeichen/Monat (~13 Videos)",
        "wo": "https://elevenlabs.io  →  Konto  →  API Keys",
        "pflicht": False,
        "pruefen": pruef_elevenlabs,
    },
    {
        "key": "PEXELS_API_KEY",
        "titel": "Stock-Videomaterial",
        "warum": "Hintergrundclips für die Videos. Ohne ihn werden Hintergründe\n"
                 "gerechnet statt gefilmt — sieht weniger filmisch aus.",
        "kosten": "KOSTENLOS, sofort",
        "wo": "https://www.pexels.com/api/",
        "pflicht": False,
        "pruefen": pruef_pexels,
    },
    {
        "key": "IG_ACCESS_TOKEN",
        "titel": "Instagram (Reels + Karussells)",
        "warum": "Ohne diesen Token postet das System nur auf TikTok.\n"
                 "Die Einrichtung dauert einmalig ca. 60 Minuten — siehe TODO_KAI.md Schritt 4.\n"
                 "Überspringen ist völlig in Ordnung; du kannst es jederzeit nachholen.",
        "kosten": "kostenlos",
        "wo": "developers.facebook.com → App → Graph API Explorer → langlebiges Token",
        "pflicht": False,
        "pruefen": pruef_instagram,
    },
]


def frage(text: str, vorgabe: str = "") -> str:
    hinweis = f" [{GRAU}{vorgabe[:12]}…{RESET}]" if vorgabe else ""
    try:
        return input(f"{text}{hinweis}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def run():
    werte = lies_env()
    print(f"\n{'═' * 66}")
    print("  EINRICHTUNG — JK24 Autopilot")
    print(f"{'═' * 66}")
    print("\nIch frage jetzt nacheinander ab, was das System braucht.")
    print("Jede Frage kannst du mit Enter überspringen.")
    print(f"Jeder Schlüssel wird sofort geprüft, damit kein Tippfehler durchrutscht.\n")

    for f in FRAGEN:
        vorhanden = werte.get(f["key"], "")
        pflicht = f"{ROT}nötig{RESET}" if f["pflicht"] else f"{GRAU}optional{RESET}"
        print(f"\n{'─' * 66}")
        print(f"  {f['titel']}  ({pflicht})")
        print(f"{'─' * 66}")
        print(f"{f['warum']}")
        print(f"\n  Kosten: {GRUEN}{f['kosten']}{RESET}")
        print(f"  Holen:  {f['wo']}\n")

        if vorhanden:
            ok, info = (False, "")
            try:
                ok, info = f["pruefen"](vorhanden)
            except Exception as e:  # noqa: BLE001
                info = str(e)[:80]
            if ok:
                print(f"  {GRUEN}✓ Bereits hinterlegt und gültig{RESET} ({info})")
                if frage("  Ersetzen? (j/N)").lower() not in ("j", "ja"):
                    continue
            else:
                print(f"  {GELB}! Hinterlegter Wert funktioniert nicht{RESET} ({info})")

        eingabe = frage("  Hier einfügen (Enter = überspringen)")
        if not eingabe:
            print(f"  {GRAU}übersprungen{RESET}")
            continue

        print("  prüfe…", end=" ", flush=True)
        try:
            ok, info = f["pruefen"](eingabe)
        except Exception as e:  # noqa: BLE001
            ok, info = False, str(e)[:100]
        if ok:
            werte[f["key"]] = eingabe
            print(f"{GRUEN}✓ funktioniert{RESET} ({info})")
        else:
            print(f"{ROT}✗ funktioniert nicht{RESET} ({info})")
            if frage("  Trotzdem speichern? (j/N)").lower() in ("j", "ja"):
                werte[f["key"]] = eingabe

    # ── Account-Namen ─────────────────────────────────────────────────────────
    print(f"\n{'─' * 66}")
    print("  Deine Account-Namen")
    print(f"{'─' * 66}")
    print("Die @-Namen deiner TikTok-Accounts (ohne @). Enter = später.\n")
    try:
        import accounts as accounts_mod
        accs = accounts_mod.load()
        geaendert = False
        for a in accs:
            neu = frage(f"  {a.name or a.id}", a.tiktok_account_name)
            if neu:
                a.tiktok_account_name = neu.lstrip("@")
                geaendert = True
        if geaendert:
            accounts_mod.save(accs)
            print(f"  {GRUEN}✓ gespeichert in content/accounts.json{RESET}")
    except Exception as e:  # noqa: BLE001
        print(f"  {GELB}übersprungen ({e}){RESET}")

    schreib_env(werte)
    print(f"\n{'═' * 66}")
    print(f"  {GRUEN}✓ Einrichtung gespeichert in .env{RESET}  (nur für dich lesbar, Rechte 600)")
    print(f"{'═' * 66}\n")

    fehlend = [f["titel"] for f in FRAGEN if f["pflicht"] and not werte.get(f["key"])]
    if fehlend:
        print(f"{GELB}Noch offen (nötig):{RESET} {', '.join(fehlend)}")
        print("Einfach nochmal `python3 einrichten.py` starten, wenn du den Schlüssel hast.\n")
    return not fehlend


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
