# Was DU machen musst — Startliste

Alles, was automatisierbar war, ist gebaut. Hier steht nur noch, was ein Mensch
mit Ausweis, Kreditkarte oder Telefon erledigen muss.

**Gesamtaufwand: ca. 6–8 Stunden**, verteilbar über zwei Wochenenden.
Reihenfolge einhalten — Schritt 5 braucht Schritt 3, Schritt 8 braucht alles davor.

---

## ⚠️ Schritt 0 — ZUERST, vor allem anderen (15 Minuten)

**Anruf bei deinem Insolvenzverwalter oder Anwalt. Eine Frage:**
> „Wann wird mir die Restschuldbefreiung erteilt, und ab wann kann ich ein
> Gewerbe anmelden, ohne das Verfahren zu gefährden?"

**Warum das zuerst kommt:** Du bist auf den letzten Metern eines 3,5-Jahre-Verfahrens.
Einnahmen aus selbstständiger Tätigkeit sind anzeigepflichtig, und ein ungemeldetes
Gewerbe in den letzten Wochen wäre der teuerste Fehler dieses ganzen Plans.

**Das blockiert NICHT:** Accounts anlegen, Content posten, Technik aufsetzen, Reichweite
aufbauen. All das verursacht keine Einnahmen und kann sofort starten.
**Das blockiert:** Gewerbeanmeldung, erste Rechnung, Zahlungsanbieter.

Nach dem Beschluss: Gewerbeanmeldung Gemeinde Thomm bzw. VG Ruwer, ca. 20–30 €.

---

## Schritt 1 — Server (30 Minuten, ~5 €/Monat)

Der Bot muss 24/7 laufen; dein Mac reicht dafür nicht, wenn du morgens zur Arbeit fährst.

- Hetzner Cloud CX22 (Nürnberg, ~4,50 €/Monat) oder Netcup — beide DSGVO-sauber in DE
- Ubuntu 24.04, SSH-Key statt Passwort
- Danach:
  ```bash
  git clone <dieses-repo> && cd mindset-tiktok-bot
  pip install -r requirements.txt --break-system-packages
  sudo apt install ffmpeg espeak-ng -y
  ./install_tiktok_uploader.sh
  ```

**Für Instagram zusätzlich:** Domain (~10 €/Jahr) + Caddy, der den Ordner `public/`
ausliefert. Instagram holt sich Videos und Bilder von dort ab.
```bash
sudo apt install caddy -y
# /etc/caddy/Caddyfile:
#   cdn.deine-domain.de {
#       root * /pfad/zum/projekt/public
#       file_server
#   }
```

---

## Schritt 2 — Accounts anlegen (90 Minuten)

Drei Marken, keine Privatnamen, keine Verbindung zu „Kai Schmieder" in Bio oder Handle.

| Account | TikTok | Instagram | YouTube |
|---|---|---|---|
| **mindset** | ✓ | ✓ | ✓ |
| **ki** | ✓ | ✓ | — |
| **nebenverdienst** | ✓ | ✓ | — |

Pro Instagram-Konto:
1. Konto anlegen, **auf „Business" umstellen** (Einstellungen → Kontotyp)
2. Mit einer **Facebook-Seite verbinden** — ohne das funktioniert die API nicht
3. Bio: eine Zeile Nutzenversprechen + Link
4. **Zwei-Faktor-Authentisierung aktivieren.** Ein gekapertes Konto mit 50.000
   Followern bekommst du praktisch nie zurück.

Alle Zugangsdaten in einen Passwort-Manager (Bitwarden, kostenlos). Nicht in Notizen.

---

## Schritt 3 — accounts.json ausfüllen (15 Minuten)

Datei: `content/accounts.json` (liegt schon da, mit dem Portfolio aus der Strategie).
Eintragen: `tiktok_account_name` und `link_in_bio` je Account. Sonst nichts —
Secrets kommen in `.env`, nie in diese Datei.

Prüfen mit:
```bash
python3 accounts.py
```
Zeigt pro Account, was fällig ist und welche Plattformen wirklich verbunden sind.

---

## Schritt 4 — Instagram-API freischalten (60 Minuten, einmalig)

Der unangenehmste Schritt. Danach nie wieder.

1. developers.facebook.com → **App erstellen** → Typ „Business"
2. Produkt **„Instagram Graph API"** hinzufügen
3. Berechtigungen: `instagram_basic`, `instagram_content_publish`,
   `pages_show_list`, `pages_read_engagement`
4. **Graph API Explorer** → Token generieren → in ein **langlebiges Token**
   umwandeln (60 Tage, verlängert sich bei Nutzung automatisch)
5. `GET /me/accounts` aufrufen → bei jeder Seite steht
   `instagram_business_account.id` → das ist die lange Zahl, die du brauchst
6. In `.env` eintragen:
   ```
   IG_ACCESS_TOKEN=EAAG...
   IG_USER_ID_MINDSET=17841...
   IG_USER_ID_KI=17841...
   IG_USER_ID_NEBEN=17841...
   MEDIA_HOST=local
   MEDIA_BASE_URL=https://cdn.deine-domain.de
   ```

**Für den ersten Monat genügt der Entwicklungsmodus** — du postest auf deine eigenen
Konten, dafür braucht es keine App-Prüfung durch Meta.

---

## Schritt 5 — YouTube freischalten (30 Minuten, nur Account „mindset")

1. console.cloud.google.com → Projekt anlegen → **YouTube Data API v3** aktivieren
2. OAuth-Client erstellen, Typ **„Fernseher und Geräte mit begrenzter Eingabe"**
3. `YT_CLIENT_ID` / `YT_CLIENT_SECRET` in `.env`
4. Auf dem Server:
   ```bash
   python3 uploader_youtube.py --auth
   ```
   → zeigt eine URL und einen Code, du bestätigst am Handy
   → ausgegebenen Token als `YT_REFRESH_TOKEN_MINDSET` in `.env`

**Grenze beachten:** 6 Uploads pro Tag und Projekt. Für einen Kanal reicht das.

---

## Schritt 6 — TikTok-Erstlogin (20 Minuten, braucht Bildschirm)

Muss auf deinem Mac passieren, nicht auf dem Server — TikTok will hier einen Menschen.

```bash
python3 uploader.py --login     # pro Account einmal, mit dem jeweiligen Namen in .env
```
Browser öffnet sich → einloggen → fertig. Die entstandene Cookie-Datei nach
`cookies/` auf den Server kopieren (per `scp`).

---

## Schritt 7 — Link-in-Bio + Impressum (45 Minuten)

**Pflicht, nicht optional.** Geschäftliche Accounts ohne Impressum sind abmahnfähig.

- Eine Seite auf deiner Domain (oder Lovable, du kennst das von jk24.lovable.app)
- Enthält: Freebie-Anmeldung, Impressum, Datenschutzerklärung
- E-Mail-Tool: **Brevo** (bis 300 Mails/Tag kostenlos, Server in der EU)
- **Double-Opt-In einschalten.** Ohne das ist die Liste rechtlich wertlos.

---

## Schritt 8 — Automatik scharfstellen (10 Minuten)

Stündlicher Cron — der Bot prüft selbst, welcher Posting-Zeitpunkt gerade fällig ist:

```bash
crontab -e
# Posting-Prüfung, stündlich:
5 * * * * cd /pfad/zum/projekt && /usr/bin/python3 scheduler.py >> logs/cron.log 2>&1
# Tagesbriefing + Selbstoptimierung, morgens:
0 6 * * * cd /pfad/zum/projekt && /usr/bin/python3 daily_run.py >> logs/cron.log 2>&1
# Trend-Auffrischung, montags:
0 5 * * 1 cd /pfad/zum/projekt && /usr/bin/python3 trend_research.py >> logs/cron.log 2>&1
```

Vorher einmal von Hand testen:
```bash
python3 scheduler.py
```

---

## Schritt 9 — Zwei Verkaufsgespräche (2 Stunden) — **der wichtigste Schritt**

Das ist der einzige Punkt in diesem Plan, der **ab Monat 2 Geld bringt**, statt erst
ab Monat 5. Und der einzige, den keine Software für dich erledigt.

**Zielkunden in Trier:** Handwerksbetriebe ohne Social Media, Fitnessstudios,
Physiotherapien, Restaurants, Autohäuser. Über Heers & Peters und die
JK24-Standortgespräche hast du den Zugang bereits.

**Angebot:** 20 Beiträge pro Monat, fertig produziert und veröffentlicht, **600 €/Monat**,
monatlich kündbar.

**Der Gesprächseinstieg** (nicht auswendig lernen, nur die Struktur):
> „Ich baue automatisierte Social-Media-Inhalte für Betriebe hier aus der Region.
> Zwanzig Beiträge im Monat, du musst nichts dafür tun und nichts freigeben, außer
> du willst. Sechshundert im Monat, monatlich kündbar. Ich zeig dir vier Beispiele,
> die ich für deine Branche gemacht habe — wenn's dir nichts bringt, lässt du's."

Vorher die vier Beispiele mit dem Bot produzieren. **Mit dem Produkt im Gespräch
sitzen, nicht mit einem Versprechen.** Du hast als Meister 20 Jahre lang erlebt,
wie dieser Unterschied wirkt.

---

## Schritt 10 — Steuerberater (1 Termin, nach Schritt 0)

Drei Fragen mitnehmen:
1. Kleinunternehmerregelung oder von Anfang an Regelbesteuerung? *(Empfehlung aus
   der Strategie: Regelbesteuerung — du reißt die 25.000-€-Grenze planmäßig in Monat 8,
   und der Wechsel mitten im Jahr ist lästiger als der Mehraufwand von Anfang an.)*
2. Digitalprodukt über Digistore24 als Reseller — spart mir das die OSS-Meldung?
3. Getrennt von JK24 führen — wie sauber trenne ich das buchhalterisch?

**Ab der ersten Einnahme: 35 % auf ein separates Konto.** Das ist keine Empfehlung.

---

# Was ich als Nächstes baue (du musst nichts tun)

| | Was | Wann |
|---|---|---|
| 1 | Funnel-Tracking: Profilbesuche und Link-Klicks pro Beitrag in die Auswertung | sobald die Accounts live sind |
| 2 | `improver.py` optimiert auf **Umsatz pro 1.000 Views**, nicht auf Views | mit den ersten echten Daten |
| 3 | Hook-Typ-Rotation mit automatischem A/B-Vergleich | nach 2 Wochen Datenlage |
| 4 | Landingpage + Freebie-PDF, automatisch aus deinen eigenen Performance-Daten erzeugt | Monat 2 |
| 5 | Produkt-Gliederung aus den Fragen, die unter deinen Beiträgen auftauchen | Monat 3 |
| 6 | Umstellung auf die offizielle TikTok Content Posting API (Prüfung dauert 2–4 Wochen → früh beantragen) | Monat 6 |

---

## Der eine Satz, an dem der Plan hängt

Technik ist fertig. **Schritt 9 entscheidet, ob daraus ein Geschäft wird oder ein Hobby.**
Zwei Gespräche. Mehr steht zwischen dir und dem ersten Euro nicht.
