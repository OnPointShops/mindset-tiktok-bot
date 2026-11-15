# JK24-Website (Entwurf)

Die neue Website von JK24. Sie besteht nur aus fertigen Dateien: HTML, eine CSS-Datei,
eine JavaScript-Datei, drei Schriften, ein Symbol. Kein Baukasten, kein Programm, das
vorher laufen muss, kein Anbieter, an dem sie hängt. Wer den Ordner `website/` auf
einen Webspace kopiert, hat die Seite online.

**Stand: Entwurf. So darf sie noch nicht ins Netz** (siehe „Vor dem Start").

## Was im Ordner liegt

| Datei | Inhalt |
|---|---|
| `index.html` | Startseite: Angebot für Standortpartner, Ablauf, Rechner, Jugendschutz, Fragen, Kontakt |
| `jugendschutz.html` | Wie die Altersprüfung arbeitet und woran sich JK24 hält (für Behörden und Vermieter) |
| `impressum.html` | Impressum mit gelben Platzhaltern |
| `datenschutz.html` | Datenschutzerklärung mit gelben Platzhaltern |
| `assets/css/site.css` | Das gesamte Aussehen (Farben stehen ganz oben) |
| `assets/js/site.js` | Schritt-für-Schritt-Darstellung am Automaten und der Rechner |
| `assets/fonts/` | Drei Schriften samt Lizenztexten |
| `robots.txt` | Sagt Suchmaschinen im Moment: nicht aufnehmen |

Ansehen am eigenen Rechner: `index.html` doppelt anklicken. Oder im Terminal
`cd website && python3 -m http.server 8000`, dann im Browser `http://localhost:8000`.

## Online stellen: drei Wege

1. **Klassischer Webspace mit Domain** (z. B. IONOS, Strato, all-inkl, Hetzner; wenige
   Euro im Monat). Im Kundenmenü die Domain bestellen, dann den **Inhalt** von
   `website/` per FTP-Programm (FileZilla) oder im Dateimanager des Anbieters in das
   Hauptverzeichnis der Domain kopieren. Vorteil: Server in Deutschland, Vertrag zur
   Auftragsverarbeitung gibt es im Kundenmenü. Das ist der empfohlene Weg.
2. **Netlify oder Cloudflare Pages** (kostenlos für kleine Seiten). Konto anlegen, den
   Ordner `website/` ins Browserfenster ziehen, eigene Domain verbinden. Vorteil:
   schnell. Nachteil: Anbieter aus den USA; in der Datenschutzerklärung muss das stehen.
3. **GitHub Pages** (kostenlos). Die Seite wird direkt aus diesem Repo ausgeliefert.
   Nachteil wie bei 2, und das Repo müsste dafür passend eingerichtet werden.

Für alle drei gilt: Die Domain (z. B. `jk24.de`, falls frei) bestellt und bezahlt Kai
selbst. Von hier aus wurde nichts bestellt, nichts veröffentlicht und niemand angeschrieben.

## Vor dem Start (Pflicht)

1. Alle **gelben Platzhalter** in `impressum.html`, `datenschutz.html`,
   `jugendschutz.html` und im Kontaktbereich von `index.html` durch echte Angaben ersetzen.
2. Alle **gepunktet unterstrichenen Aussagen** prüfen (Liste unten). Stimmt eine nicht,
   ändern oder streichen.
3. Die Texte einmal einem Anwalt für Wettbewerbsrecht zeigen (siehe „Rechtlich offen").
4. Entwurf abschalten:
   - in allen vier HTML-Dateien `<body class="entwurf">` zu `<body>` ändern
     (Balken und Unterstreichungen verschwinden),
   - in allen vier HTML-Dateien die Zeile `<meta name="robots" content="noindex">` löschen,
   - in `robots.txt` aus `Disallow: /` ein `Allow: /` machen.
5. Bei E-Mail und Telefon im Kontaktbereich Links setzen, z. B.
   `<a href="mailto:info@beispiel.de">info@beispiel.de</a>` und
   `<a href="tel:+49651000000">0651 000000</a>`.

## Was Kai noch liefern muss

- **Impressum:** Vor- und Nachname des Inhabers, Anschrift (kein Postfach), Telefon,
  E-Mail, USt-IdNr. (falls vorhanden), Handelsregister (falls eingetragen).
- **Rechtsform:** Einzelunternehmen einer Person oder gemeinsamer Betrieb von zweien?
  Bei zwei Beteiligten gehören beide ins Impressum.
- **Ansprechpartner für Behörden** (Name, E-Mail, Telefon) für `jugendschutz.html`.
- **Automat:** Hersteller, Typ, Datenblatt, Nachweis zur Altersprüfung. Erst danach
  dürfen die Aussagen zur Prüfung endgültig stehen bleiben.
- **Hoster:** Name, Anschrift, Speicherdauer der Protokolle, abgeschlossener Vertrag
  zur Auftragsverarbeitung.
- **Entscheidung zur Domain.**
- **Fotos** (optional): ein eigenes Foto eines aufgestellten Automaten ohne erkennbare
  Produkte, Marken und Personen. Bis dahin kommt die Seite ohne Fotos aus.
- **Logo** (optional): Das Zeichen „JK24" im Kopf ist ein Entwurf aus Schrift. Gibt es
  ein vorhandenes Logo, wird es dort eingesetzt.

## Von Kai zu bestätigen

Diese Aussagen stehen auf der Seite, sind aber Annahmen aus der Beschreibung des
Geschäfts. Im Entwurf sind sie gepunktet unterstrichen (`class="offen"`).

- JK24 übernimmt Aufstellung, Befüllung, Wartung und Abrechnung.
- Die Altersprüfung läuft per Ausweis **oder** Bankkarte.
- Bezahlt wird bargeldlos.
- Standortpartner erhalten eine Umsatzbeteiligung **oder** eine feste Miete.
- Standortpartner brauchen kein eigenes Personal und kaufen keine Ware ein.
- Die Abrechnung ist für den Partner nachprüfbar und kommt regelmäßig.
- Der Automat bleibt Eigentum von JK24; der Partner kauft oder mietet ihn nicht.
- JK24 liefert, stellt auf, schließt an, reinigt, wartet und behebt Störungen.
- JK24 arbeitet in Trier und im Umland (die Karte nennt Konz, Saarburg, Schweich,
  Wittlich, Bitburg, Hermeskeil nur zur Orientierung).
- Bei Störungen kümmert sich JK24 um die Behebung; am Automaten steht, wie man JK24 erreicht.
- Es gibt schon einen Automaten im Betrieb (sonst „betreiben" in „werden betreiben" ändern).
- Am Gerät kommt die Altersprüfung **vor** der Zahlung, bei **jedem** Kauf; ohne bestandene
  Prüfung wird nicht bezahlt; es öffnet sich nur das gewählte Fach (laut Datenblatt prüfen).
- Der Rechner zieht 19 % Umsatzsteuer ab. Das stimmt nur bei Regelbesteuerung, nicht als
  Kleinunternehmer.
- Aufstellung nur mit schriftlichem Vertrag, nur mit schriftlicher Zustimmung des
  Eigentümers, auf öffentlichem Grund nur mit Sondernutzungserlaubnis; Nachfrage bei der
  Behörde im Zweifel.

Ohne Markierung, aber ebenfalls eine Zusage, die im Alltag stimmen muss: Das Datenblatt
des Geräts gibt es, bevor der Partner etwas zusagt.

## Bestandsaufnahme der alten Seite

Die alte Seite `jk24.lovable.app` war aus der Arbeitsumgebung **nicht erreichbar**
(die Netzwerkregeln der Umgebung haben die Adresse gesperrt). Es wurde deshalb nichts
von ihr übernommen. Inhalte, Aussagen und Kontaktwege der alten Seite sind nicht geprüft.
Wer sie neben die neue legt, sollte auf drei Dinge achten: Stehen dort Zahlen oder
Versprechen, die hier fehlen und belegbar sind? Stehen dort Kontaktdaten, die hier in
die Platzhalter gehören? Steht dort etwas, das nach Produktwerbung aussieht? Das bleibt weg.

## Rechtlich offen

Die Vorprüfung stammt vom Agenten `recht` (15.11.2026). Er ist kein Anwalt. Seine
Einstufung für die Seite in dieser Form: **vertretbar, aber nicht sicher.** Die
Gesetzestexte konnte er nicht im Original lesen (gesetze-im-internet.de war aus der
Arbeitsumgebung gesperrt); seine Aussagen stützen sich auf Sekundärquellen und Erinnerung.

### Offen / unklar (wörtlich von `recht`)

- Die Gesetzestexte (TabakerzG §§ 2, 19, 20a; JuSchG § 10; DDG § 5; TDDDG § 25; VSBG § 36) wurden nicht im Original geprüft; der Abgleich mit gesetze-im-internet.de steht aus.
- Ob eine sachliche B2B-Unternehmensseite eines Vape-Automatenbetreibers "Werbung" nach § 19 Abs. 3 TabakerzG ist, ist nicht höchstrichterlich entschieden.
- Stand Einweg-Verbot, Aromenverbot und Tabaksteuer-Lücke im November 2026 ist nicht abschließend bestätigt. Die Seite macht dazu keine Aussagen.
- Abstandsregeln zu Schulen in RLP/Trier: keine gefunden, nicht bei Stadt oder Ordnungsamt verifiziert.
- Erfüllung der ElektroG-Rücknahmepflicht an unbemannten Automaten ist ungeklärt.
- Rechtsform bei zweitem Beteiligten (Einzelunternehmen oder GbR) ist offen. Davon hängt das Impressum ab.
- Impressum und Datenschutzerklärung enthalten Platzhalter. Kein öffentlicher Betrieb vor Vervollständigung.
- Aussagen zur Altersprüfung sind erst nach Vorlage der Herstellerdokumentation des Automaten final.

### Fall für einen Anwalt (wörtlich von `recht`)

- Einmalige wettbewerbsrechtliche Prüfung der fertigen Texte und der Kaufablauf-Darstellung auf das Werbeverbot (§ 19 Abs. 3 TabakerzG, § 3a UWG) vor Livegang.
- Zulässigkeit und Gestaltung der Automaten im Außenbereich (§ 20a TabakerzG, § 10 Abs. 2 JuSchG), inklusive sichtbarer Produktanzeige.
- Rücknahme- und Informationspflichten nach ElektroG und Batterierecht für Automatenbetreiber und Standortpartner.
- Standortpartner-Vertrag (Beteiligung, Haftung für Jugendschutzverstöße, Laufzeit) und Absicherung der Rechner-Angaben gegen Haftung aus Vertragsverhandlungen.
- Gesellschaftsvertrag bzw. Rechtsformwahl, falls eine zweite Person beteiligt wird.
- Sofort bei Abmahnung, Anhörung oder Bußgeldbescheid: Die Fristen sind kurz.

Unterlagen für den Termin: fertige Seitentexte und Bildschirmfotos, Datenblatt und
Prüfnachweis der Altersprüfung, Fotos eines Automaten am Standort, Entwurf des
Standortvertrags, Gewerbeanmeldung.

### Gegenprüfung der fertigen Texte (wörtlich von `recht`)

Gesamturteil nach Einarbeitung seiner Pflichtänderungen: **vertretbar**. Die
Gesetzestexte konnte er auch hier nicht im Original lesen; vor Veröffentlichung
§ 10 JuSchG und § 5 DDG einmal gegen den Originaltext lesen.

Ergänzungen zu „Offen / unklar":

- Existiert bereits ein betriebener Automat? Davon hängt die Gegenwartsform 'betreibt' ab.
- Regelbesteuerung oder Kleinunternehmer (§ 19 UStG)? Davon hängt die 19-%-Angabe im Rechner ab; an `steuern`.
- Reihenfolge Prüfung/Zahlung und Prüfung bei jedem Kauf laut Hersteller-Datenblatt.
- Datenschutzhinweis am Automaten selbst (Art. 13 DSGVO), falls bei Ausweis- oder Kartenprüfung Daten verarbeitet werden; nicht Teil der Website.
- Aufstellerangaben am Gerät nach § 14 Abs. 3 GewO (Name, Anschrift); nicht am Original geprüft.

Ergänzung zu „Fall für einen Anwalt":

- Standortvertrag: Haftungs- und Freistellungsklausel für Jugendschutzverstöße und Bußgelder gegen den Standortinhaber. Die Website verweist an neun Stellen auf diesen Vertrag; er muss halten, was sie ankündigt.

### Woran sich die Seite deshalb hält

- Sie spricht nur Standortpartner, Vermieter und Behörden an, nie Käufer.
- Das Sortiment wird einmal sachlich genannt. Keine Produkte, Marken, Preise, Bilder.
- Kein Standortfinder, keine Liste von Automaten.
- Die Darstellung am Automaten zeigt die Prüfung und den Fall „nicht bestanden".
- Der Rechner hat keine Vorgabewerte und nennt kein Ergebnis als Versprechen.
- Keine Aussagen wie „gesetzeskonform", „garantiert", „100 % sicher", „zugelassen".
- Keine Aussagen zu Steuern, Aromen, Einwegprodukten oder Rücknahme.
- Kein „24/7" und keine Uhr als Botschaft, dass man jederzeit kaufen kann.

**Diese Regeln gelten auch für jede spätere Änderung an den Texten.**

## Technik in Kürze

- Keine Cookies, kein Speicher im Browser, keine Tracker, keine fremden Server. Deshalb
  kein Cookie-Banner. Wer später Statistik, Karten, Videos oder Schriften von fremden
  Servern einbaut, braucht eine Einwilligung und eine neue Datenschutzerklärung.
- Hell und dunkel richten sich nach der Einstellung des Geräts.
- Ohne JavaScript bleibt alles lesbar; nur Automat und Rechner stehen dann still.
- Farben ändern: die ersten Zeilen von `assets/css/site.css` (`--amber`, `--bg` usw.).

## Später ein Kontaktformular anschließen

Ein Formular braucht einen Server, der die Nachricht entgegennimmt. Drei Möglichkeiten:

1. **Formular-Skript des Hosters.** Viele Webspace-Anbieter bringen ein PHP-Mailskript
   mit. Daten bleiben beim eigenen Hoster. Das ist der sauberste Weg.
2. **Formulardienst** (z. B. Formspree, Netlify Forms). Schnell, aber die Daten gehen an
   einen Dritten: Vertrag zur Auftragsverarbeitung und Ergänzung der Datenschutzerklärung nötig.
3. **Kein Formular.** E-Mail und Telefon reichen für Anfragen von Standortpartnern meist aus.

In jedem Fall: Pflichtfelder sparsam halten, Hinweis auf die Datenschutzerklärung am
Formular, Schutz gegen Spam ohne Dienste wie reCAPTCHA (z. B. ein verstecktes Feld).

## Lizenzen

| Was | Quelle | Lizenz |
|---|---|---|
| Schrift Archivo | Omnibus-Type, über das npm-Paket `@fontsource-variable/archivo` 5.3.0 | SIL Open Font License 1.1, gewerbliche Nutzung erlaubt |
| Schrift Instrument Sans | Instrument, `@fontsource-variable/instrument-sans` 5.3.0 | SIL Open Font License 1.1 |
| Schrift Doto | Óliver Lalan, `@fontsource-variable/doto` 5.3.0 | SIL Open Font License 1.1 |
| Automat, Karte, Symbol, Zeichen „JK24" | für diese Seite selbst gebaut (HTML, CSS, SVG) | gehört JK24 |

Die Lizenztexte liegen in `assets/fonts/`. Fotos, fremde Symbole oder fremde Logos
werden nicht verwendet. Die Karte ist frei gezeichnet und stammt aus keinem Kartenwerk.
