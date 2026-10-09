# 10.000 € / Monat in 10 Monaten — Faceless Content System

**Stand:** 09.10.2026 · **Zielmonat:** August 2027 · **Betreiber:** Kai Schmieder
**Basis:** vorhandene Pipeline `mindset-tiktok-bot` (Skript → TTS → Video → Auto-Upload)

---

## 0. Zieldefinition (beide Lesarten abgedeckt)

| Ziel | Zeitpunkt |
|---|---|
| **10.000 € kumuliert** verdient | Monat 7 (Mai 2027) |
| **10.000 € Umsatz pro Monat** | Monat 10 (August 2027) |
| Netto nach Kosten & Steuern bei 10k Umsatz | ca. 5.200–5.800 € |

Beides kommt aus demselben Aufbau. Der Plan steuert auf die monatliche Zahl; die kumulierte fällt unterwegs ab.

---

## 1. Realitäts-Check: woher 10.000 € NICHT kommen

Das muss zuerst stehen, sonst baust du 10 Monate auf der falschen Säule.

**Plattform-Ausschüttungen tragen das Ziel nicht.**

| Quelle | Realität Deutschland 2026 |
|---|---|
| TikTok Creator Rewards | 0,60–0,90 € pro 1.000 **qualifizierte** Views (nicht alle Views zählen). Voraussetzung: 10k Follower + 100k Views/30 Tage, nur Videos > 60 Sek. → 10.000 € bräuchten ~13 Mio. qualifizierte Views/Monat. Unerreichbar in 10 Monaten. |
| Instagram Reels | Kein Pay-per-View in DE. Bonus-Programm nur auf Einladung, Reels Play seit 2023 geschlossen. Gifts: 0,01 $ pro Stern. → Praktisch 0 €. |
| YouTube Shorts | ~0,03–0,08 €/1.000 Views DE. Nebenbei-Geld, keine Säule. |

**Konsequenz:** Reichweite ist **Traffic**, nicht Umsatz. Das Geld entsteht erst dort, wo der Traffic hingeleitet wird. Jedes Video ohne Weg zu einem Angebot ist unbezahlte Arbeit.

Das Konzept aus den Screenshots ("Marken bezahlen dich für Werbeposts") ist die **langsamste und unzuverlässigste** Monetarisierung — transaktional, nicht wiederkehrend, und bei faceless Accounts 30–50 % günstiger bepreist als bei Gesichts-Creators. Es bleibt im Plan, aber als Schicht 4 von 5, nicht als Hauptmotor.

---

## 2. Die Umsatz-Architektur (Monat 10)

Fünf Beine. Keines muss ein Wunder vollbringen.

| # | Stream | Monat 10 | Wie |
|---|---|---:|---|
| 1 | **Eigenes Digitalprodukt** | 5.200 € | 35 Verkäufe × 149 € — Kurs/System "Faceless Automation DE" |
| 2 | **Done-for-you Service** | 1.800 € | 3 Retainer × 600 € — lokale Unternehmen Trier, du lieferst mit dem Bot |
| 3 | **Affiliate (recurring)** | 1.100 € | KI-Tools, Hosting, Automation — 20–30 % wiederkehrend |
| 4 | **Markenkooperationen** | 1.200 € | 2–3 gesponserte Posts/Monat bei 80–120k Followern |
| 5 | **TikTok Creator Rewards** | 630 € | ~900k qualifizierte Views × 0,70 €/1k |
| | **Summe** | **9.930 €** | |

**Warum diese Reihenfolge funktioniert:**
Stream 2 bringt **ab Monat 2 Cash** (du hast das Produkt schon gebaut — der Bot läuft). Stream 1 ist der Skalierungs-Hebel (Grenzkosten ≈ 0). Streams 3–5 sind Aufsatz, keine Grundlast.

### Kostenseite (Monat 10)
| Posten | € / Monat |
|---|---:|
| VPS + Backups | 20 |
| ElevenLabs / TTS | 25 |
| KI-APIs (Claude, Bild-Gen) | 90 |
| E-Mail-Tool (Brevo/MailerLite) | 30 |
| Zahlungsanbieter (Digistore24/Stripe ~7 %) | 370 |
| Puffer Tools/Stock | 60 |
| **Gesamt** | **~595 €** |

---

## 3. Das Content-System

### 3.1 Portfolio statt Einzelwette
**Drei Accounts parallel ab Tag 1.** Kein Account ist planbar viral; ein Portfolio ist es statistisch.

| Account | Nische | Format | Begründung |
|---|---|---|---|
| **A** | Mindset / Disziplin (DE) | Video-Reels (bestehende Pipeline) | Läuft bereits, größte Reichweite, niedrigster CPM |
| **B** | KI & Automatisierung fürs Business (DE) | Text-Karussells (schwarz/weiß, siehe Screenshots) + Reels | **Höchster Geldwert pro Follower** — das ist die Zielgruppe für Produkt + Service |
| **C** | Selbstständigkeit / Nebeneinkommen (DE) | Mix | Brücke zwischen A und B, Testfeld |

Produktionskosten pro Karussell: ~0 € und ~20 Sekunden Rechenzeit. Das ist das günstigste Format überhaupt — und exakt das, was in deinen Screenshots performt.

### 3.2 Posting-Volumen
| | pro Tag | pro Monat |
|---|---:|---:|
| Account A | 3 | 90 |
| Account B | 3 | 90 |
| Account C | 2 | 60 |
| **Netzwerk** | **8** | **240** |

Cross-Posting: jedes Reel geht ohne Mehraufwand auf TikTok + Instagram + YouTube Shorts. Effektive Ausspielungen: ~720/Monat.

### 3.3 Hook-Bank (das Einzige, was wirklich zählt)
Die ersten 3 Sekunden entscheiden über 90 % der Reichweite. `content_generator.py` bekommt eine feste Hook-Typen-Rotation, `improver.py` misst, welcher Typ gewinnt:

1. **Zahl + Zeit** — "In 90 Tagen von 0 auf 50.000 Follower — ohne Gesicht."
2. **Widerspruch** — "Mehr posten ist der Grund, warum dein Account nicht wächst."
3. **Verlust** — "Ich habe 2 Jahre verschwendet, weil mir das keiner gesagt hat."
4. **Schritt-Liste** (dein Screenshot-Format) — "Schritt 1: Wähle eine Nische"
5. **Gegner benennen** — "Agenturen nehmen 2.000 € für das, was dieses Tool für 0 € macht."
6. **Beweis** — Screenshot/Zahl im Bild, Text nennt sie nicht.

Regel: **nie mehr als 2 Hook-Typen pro Tag und Account.** Sonst ist die Messung wertlos.

### 3.4 Kill-Kriterien (verhindert, dass du 10 Monate an einer Leiche arbeitest)
| Zeitpunkt | Schwelle | Konsequenz |
|---|---|---|
| Woche 6 | Account < 15.000 Views gesamt | Nische wechseln, Account behalten (Rebrand) |
| Woche 10 | Account < 2.000 Follower | Account einstellen, Slot an Gewinner geben |
| Woche 16 | Account < 10.000 Follower | Posting auf 1/Tag, Ressourcen zum Gewinner |
| Laufend | Ein Account > 3× Durchschnitt | Posting-Frequenz dort verdoppeln |

---

## 4. Der Funnel (hier entsteht das Geld)

```
Video / Karussell
   └─> Profil-Besuch              ~1,5 % der Views
        └─> Link in Bio           ~8 % der Profilbesuche
             └─> Freebie-Seite    (DSGVO-konformes Double-Opt-In)
                  └─> E-Mail-Liste  ~35 % Eintragungsrate
                       ├─> Produkt 149 €      ~4 % der Liste
                       └─> Affiliate-Empfehlungen  (recurring)
```

**Rechnung Monat 10:** 1,5 Mio. Netzwerk-Views → 22.500 Profilbesuche → 1.800 Klicks → 630 neue E-Mails → 25 Produktverkäufe + 10 Direktkäufe = 35.

**Die E-Mail-Liste ist das einzige Asset, das dir gehört.** Accounts können gesperrt werden (siehe Risiko 7.1) — die Liste nicht. Ziel Monat 10: **4.500 Abonnenten**.

**Freebie (Lead-Magnet):** "Die 50 Hooks, die 2026 auf deutschem TikTok funktionieren" — PDF, aus deinen eigenen Performance-Daten in `stats_scraper.py` erzeugt. Echte Daten, kein Recycling. Das ist dein unfairer Vorteil.

### Angebots-Treppe
| Stufe | Preis | Was |
|---|---:|---|
| 0 | 0 € | Hook-PDF (Lead-Magnet) |
| 1 | 29 € | Prompt- & Vorlagen-Paket |
| 2 | **149 €** | **Hauptprodukt:** komplettes Faceless-System (Video-Kurs + dein Workflow + Vorlagen) |
| 3 | 600 €/Mon. | Done-for-you: du betreibst den Content für ein Unternehmen |
| 4 | 2.500 € | Setup des Systems beim Kunden (einmalig, Monat 8+) |

---

## 5. Roadmap — 10 Monate

### Phase 1 · Monate 1–2 (Okt–Nov 2026): Maschine & erster Cash
**Umsatzziel: M1 = 0 €, M2 = 400 €**

- [ ] Multi-Account-Fähigkeit in `config.py` / `uploader.py` (siehe Abschnitt 6)
- [ ] Karussell-Generator bauen (Format der Screenshots: 1080×1350, schwarz, Serif weiß)
- [ ] Instagram- und YouTube-Shorts-Upload ergänzen
- [ ] 3 Accounts anlegen, Bio + Link-in-Bio + **Impressum** (Pflicht, §5 DDG)
- [ ] 30 Tage Content vorproduzieren, dann Cron scharfstellen
- [ ] **Parallel, nicht danach:** 2 lokale Unternehmen in Trier als DFY-Kunden ansprechen (Heers-&-Peters-Netzwerk, JK24-Standortpartner). Angebot: 600 €/Monat, 20 Posts. Erster Kunde = Beweis + Cashflow.
- **Gate:** 240 Posts live, 1 zahlender Kunde, ≥ 50.000 Netzwerk-Views

### Phase 2 · Monate 3–4 (Dez–Jan): Signal finden
**Umsatzziel: M3 = 900 €, M4 = 1.600 €**

- [ ] Kill-Kriterien Woche 10 anwenden — gnadenlos
- [ ] `improver.py` auf Hook-Typ-Performance umbauen (nicht nur Views: **Profilbesuche pro View**)
- [ ] Freebie + Landingpage + E-Mail-Automation live
- [ ] Affiliate-Programme aufsetzen (KI-Tools mit Recurring-Provision)
- [ ] Produkt v1 **aufnehmen während du es ohnehin machst** — jeder Arbeitsschritt wird Kursmodul
- [ ] 2. DFY-Kunde
- **Gate:** 1 Account > 10.000 Follower, 400 E-Mails, Produkt fertig aufgenommen

### Phase 3 · Monate 5–6 (Feb–Mär): Produkt-Launch
**Umsatzziel: M5 = 2.600 €, M6 = 3.900 € → kumuliert ~9.400 €**

- [ ] Launch Hauptprodukt 149 € an die Liste (Launch-Woche: 5 E-Mails, 7 Story-Sequenzen)
- [ ] Nach-Launch: Evergreen-Funnel (automatisierte 7-Tage-Mailsequenz nach Eintragung)
- [ ] TikTok Creator Rewards aktivieren, sobald 10k Follower + 100k Views/30d (nur > 60 Sek. Videos — eigene Content-Linie dafür)
- [ ] Erste Markenanfragen beantworten: **Preisliste vorher festlegen**, nicht im Gespräch erfinden
- **Gate:** 50 Produktverkäufe gesamt, 1.500 E-Mails, 3.000 € Monatsumsatz

### Phase 4 · Monate 7–8 (Apr–Mai): Skalieren
**Umsatzziel: M7 = 5.300 €, M8 = 6.900 €**

- [ ] Gewinner-Account auf 5 Posts/Tag
- [ ] 4. Account im Gewinner-Format starten (Portfolio-Logik wiederholen)
- [ ] Setup-Angebot 2.500 € einführen
- [ ] Preis Hauptprodukt testen: 149 € → 197 €
- [ ] **Migration auf offizielle APIs** (TikTok Content Posting API, Instagram Graph API) — bevor das Geschäft groß genug ist, dass eine Sperre weh tut
- **Gate:** 6.000 € Monatsumsatz, 3 DFY-Kunden

### Phase 5 · Monate 9–10 (Jun–Aug): 10k
**Umsatzziel: M9 = 8.500 €, M10 = 10.000 €**

- [ ] Order-Bump (+29 €) und Upsell (+97 €) im Checkout
- [ ] Affiliate-Programm für dein eigenes Produkt (30 % — andere verkaufen für dich)
- [ ] Hauptjob-Entscheidung: bei 3 Monaten > 7.000 € Umsatz in Folge wird Heers & Peters zur Option, nicht zur Notwendigkeit
- **Gate: 10.000 € Monatsumsatz**

### Umsatz-Verlauf
| Monat | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Umsatz € | 0 | 400 | 900 | 1.600 | 2.600 | 3.900 | 5.300 | 6.900 | 8.500 | 10.000 |
| Kumuliert € | 0 | 400 | 1.300 | 2.900 | 5.500 | 9.400 | **14.700** | 21.600 | 30.100 | **40.100** |

---

## 6. Technische Backlog — was am bestehenden Code fehlt

Priorisiert, mit Bezug auf vorhandene Dateien.

| Prio | Aufgabe | Datei | Aufwand |
|---|---|---|---|
| 1 | **Multi-Account**: `TIKTOK_ACCOUNT_NAME` → Account-Profile (eigene Cookies, Nische, Stimme, Posting-Zeit) | `config.py`, `uploader.py`, `scheduler.py` | 1 Tag |
| 2 | **Karussell-Generator**: Text-Posts im Screenshot-Stil, 1080×1350, Serif, 5–8 Slides | neu `carousel.py` (nutzt `cover.py`/`backgrounds.py`) | 1 Tag |
| 3 | **Instagram-Upload** via Graph API (Business-Account + FB-Seite, Reels + Karussell) | neu `uploader_instagram.py` | 1–2 Tage |
| 4 | **YouTube-Shorts-Upload** via Data API v3 (offiziell, kein Graubereich) | neu `uploader_youtube.py` | 1 Tag |
| 5 | **Funnel-Tracking**: Profilbesuche & Link-Klicks pro Post in die Performance-Daten | `stats_scraper.py`, `improver.py` | 1 Tag |
| 6 | **Hook-Typ-Rotation + A/B-Auswertung** | `content_generator.py`, `improver.py` | 1 Tag |
| 7 | **>60-Sek.-Content-Linie** für Creator Rewards | `content_generator.py` | 0,5 Tage |
| 8 | **API-Migration** TikTok offiziell (Audit 2–4 Wochen → früh beantragen) | `uploader.py` | Monat 7 |

Realistisch: **Punkte 1–4 in den ersten 3 Wochen**, parallel zum Tagesjob. Punkte 5–7 in Phase 2.

---

## 7. Risiken — und was dagegen getan wird

**7.1 Account-Sperre (höchstes Risiko).**
Die aktuelle Upload-Automatisierung (`tiktokautouploader`) ist Browser-Automation und bewegt sich laut TikTok-ToS in der Grauzone. Bei 8 Posts/Tag über 3 Accounts steigt das Risiko überproportional.
→ *Gegenmaßnahme:* Portfolio-Ansatz (kein Single-Point-of-Failure), **alle Inhalte lokal archivieren**, E-Mail-Liste als sperrfestes Asset, API-Migration in Phase 4, Posting-Zeiten randomisieren.

**7.2 Plattform-Algorithmus ändert sich.**
→ Drei Plattformen, drei Accounts, Content-Format-Mix. Kein Bein trägt mehr als 40 % des Umsatzes.

**7.3 Zeitbudget.**
Du hast Vollzeitjob + Familie + JK24. Verfügbar: realistisch **10–12 h/Woche**.
→ Der Bot produziert. Du machst nur: Strategie (2h), Verkauf/Kunden (4h), Produkt (4h), Auswertung (1h). **Wenn du anfängst, Videos manuell zu schneiden, ist der Plan gescheitert.**

**7.4 Konflikt mit JK24.**
→ Das hier ist kein Konkurrenzprojekt, sondern der **Vertriebskanal**: Account B (KI & Automatisierung) ist zugleich die Bühne, auf der JK24 als Fallstudie läuft. Doppelnutzen, kein Ressourcenkonflikt.

**7.5 Produkt verkauft sich nicht.**
→ Deshalb Launch erst in Monat 5, nach echtem Publikum und echten Daten. Und deshalb der DFY-Service ab Monat 2: er validiert die Zahlungsbereitschaft, bevor du 4 Wochen in ein Produkt steckst.

---

## 8. Recht & Steuern (Deutschland, Stand 10/2026)

**Mit Steuerberater final abstimmen — aber das ist der Rahmen:**

| Thema | Was gilt |
|---|---|
| **Privatinsolvenz** | Läuft bis Oktober 2026 aus. **Bis zur erteilten Restschuldbefreiung nichts riskieren**: Einnahmen aus selbstständiger Tätigkeit sind dem Treuhänder anzuzeigen. Empfehlung: Gewerbeanmeldung und erste Rechnungen **nach** Zustellung des Beschlusses. Das kostet dich maximal 2–4 Wochen — Aufbau und Content laufen währenddessen bereits. |
| **Struktur** | Eigenes Einzelunternehmen, **getrennt von JK24**. Lesson learned OnPoint: keine gemeinsame Kasse ohne wasserdichten Vertrag. |
| **Kleinunternehmer §19 UStG** | Grenze seit 2025: 25.000 € Vorjahr / 100.000 € laufendes Jahr. Im Gründungsjahr zählt die 25.000-€-Grenze für das laufende Jahr — die reißt du planmäßig in Monat 8. **Empfehlung: von Anfang an Regelbesteuerung.** Spart den Bruch mitten im Jahr und du ziehst Vorsteuer auf Tools und Technik. |
| **Digitalprodukt-Verkauf EU** | B2C-Digitalverkäufe ins EU-Ausland → OSS-Verfahren. Vereinfachung: erst nur DE/AT/CH bewerben, OSS ab Monat 6 registrieren. Digistore24 als Reseller nimmt dir das komplett ab — bei 149 €-Produkt die sauberste Lösung. |
| **Werbekennzeichnung** | Affiliate-Links und bezahlte Posts **müssen** als „Werbung"/„Anzeige" gekennzeichnet werden (UWG). Nicht im Hashtag-Dschungel verstecken — erste Zeile, deutsch, lesbar. Abmahnrisiko ist real. |
| **Impressum** | Geschäftliche Accounts brauchen ein Impressum (§5 DDG). Zwei-Klick-Lösung über Link-in-Bio ist zulässig, direkt erreichbar. |
| **DSGVO** | E-Mail-Liste nur mit **Double-Opt-In**, Datenschutzerklärung auf der Landingpage, AV-Vertrag mit dem E-Mail-Anbieter. |
| **Urheberrecht** | Pexels/Pixabay: kommerziell frei, aber Prüfung bei erkennbaren Personen. Musik: **nur** TikTok Commercial Sound Library für Business-Accounts. KI-Bilder: keine Markenlogos, keine real existierenden Personen. |
| **Rücklage** | 35 % jeder Einnahme auf ein separates Konto. Nicht verhandelbar. |

---

## 9. Wochen-Cockpit

Jeden Sonntag, 20 Minuten. Diese sechs Zahlen, sonst nichts:

| KPI | Quelle | Zielkorridor M10 |
|---|---|---|
| Netzwerk-Views / Woche | `stats_scraper.py` | 350.000 |
| Profilbesuche pro 1.000 Views | Plattform-Insights | > 15 |
| Neue E-Mails / Woche | E-Mail-Tool | 150 |
| Umsatz / Woche | Digistore/Stripe | 2.300 € |
| Umsatz pro 1.000 Views | berechnet | > 6,50 € |
| Posts geliefert vs. geplant | `briefing/latest.md` | 100 % |

**Die wichtigste Zahl ist „Umsatz pro 1.000 Views".** Sie sagt dir, ob du ein Medium oder ein Geschäft betreibst. Steigt sie nicht, hilft mehr Reichweite nicht.

---

## 10. Die drei Sätze, auf die es ankommt

1. **Reichweite ist nicht das Produkt.** Der Funnel ist das Produkt. Jedes Video ohne Weg zum Angebot ist Hobby.
2. **Cash vor Skalierung.** Der DFY-Service ab Monat 2 finanziert und validiert alles andere — er braucht keine 100.000 Follower, nur zwei Unternehmer in Trier.
3. **Die E-Mail-Liste gehört dir, die Accounts nicht.** Nach den Erfahrungen mit The Jeffrey und OnPoint ist das keine Theorie: baue nichts auf, was dir ein Dritter über Nacht abschalten kann.
