# Start hier

Eine Seite. Keine Fachbegriffe. Lies die, der Rest kann warten.

---

## Was wir bauen — als Bild

Stell dir eine Werkstatt vor.

- **Die Maschine** produziert Teile. Bei uns: Videos und Bildbeiträge, jeden Tag,
  von allein. Die steht schon und läuft.
- **Das Auftragsbuch** hält fest, was bestellt wurde, was schiefging, was sich
  bewährt hat. Bei uns heißt das **Gedächtnis**. Das ist neu.
- **Der Meister** geht fünfmal am Tag durch die Halle: Läuft alles? Was klemmt?
  Was sollten wir als Nächstes machen? Bei uns heißt der **Autopilot**. Auch neu.
- **Du** entscheidest. Reden mit Kunden, unterschreiben, Richtung vorgeben.
  Das kann keine Maschine, und das soll sie auch nicht.

Mehr ist es nicht.

---

## Was jetzt neu auf deinem Mac läuft

**Fünfmal am Tag, ohne dass du etwas tust:**

| Uhrzeit | Was passiert |
|---|---|
| 07:00 | Alles prüfen · Fehler selbst reparieren · posten · Zahlen messen · online nach neuen Möglichkeiten suchen · den nächsten Schritt planen |
| 11:00 | Prüfen · reparieren · posten |
| 14:00 | dasselbe |
| 17:00 | dasselbe |
| 20:00 | Voller Durchgang wie morgens |

Verschläft dein Mac einen Termin, holt er ihn beim Aufwachen nach.

**Du bekommst eine Mitteilung aufs Display.** Darin steht:
eine Ampel, drei Zahlen, ein Satz was du tun sollst. Mehr nicht.

---

## Wie du es bedienst

**Doppelklick auf `JK24.command`.** Das ist alles.

Dann siehst du:
- 🟢 🟡 🔴 — läuft es, oder klemmt was?
- Wie viel heute gepostet wurde
- **Einen** nächsten Schritt für dich
- Offene Fragen, die du direkt dort beantworten kannst

Kein Terminal, keine Befehle. Wenn du mehr wissen willst:
Datei `brain/GEDAECHTNIS.md` öffnen — da steht alles drin, was wir je herausgefunden haben.

---

## Das Gedächtnis — das, was du dir gewünscht hast

Eine einzige Datei auf deinem MacBook: `brain/brain.db`.
Sie verlässt deinen Rechner nicht. Sie kommt nicht ins Internet, nicht ins Git-Repo,
nicht zu einem Cloud-Anbieter. Sicher dein MacBook mit Time Machine, dann ist auch
das Gedächtnis gesichert.

Darin steht:
- **Ideen** — bewertet und sortiert: was bringt am meisten Geld pro Stunde Aufwand
- **Entscheidungen** — mit Begründung, damit wir nie dieselbe Diskussion zweimal führen
- **Erkenntnisse** — was funktioniert hat, was nicht, wie oft bestätigt
- **Fehler** — jeder mit Fingerabdruck: wie oft, seit wann, womit behoben
- **Zahlen** — Views, Follower, Umsatz über die Zeit
- **Fragen an dich** — alles, was der Autopilot nicht allein entscheiden darf

Es ist schon gefüllt: 9 Ideen, 9 Erkenntnisse, 7 Entscheidungen aus unserer bisherigen Arbeit.

---

## Eine Grenze, die ich bewusst eingebaut habe

**Der Autopilot darf seinen eigenen Programmcode nicht ändern.**

Er darf reparieren (fehlendes Paket nachinstallieren, volle Platte aufräumen,
einen Lauf wiederholen), messen, forschen und vorschlagen. Aber nicht sich selbst
umbauen.

Warum: Ein System, das sich nachts unbeaufsichtigt umschreibt, ist irgendwann
kaputt — und niemand weiß wann oder warum. Du hast zweimal erlebt, was passiert,
wenn man die Kontrolle über etwas verliert, das funktioniert hat. Das baue ich
nicht noch einmal nach.

Stattdessen sammelt er Vorschläge im Gedächtnis. Wenn wir zusammen in einer
Sitzung sind, arbeite ich sie ab. Das ist langsamer und bleibt jederzeit erklärbar.

---

## Was die Recherche ergeben hat — ehrlich

Du wolltest wissen, welche automatischen KI-Programme finanziell unabhängig machen.
Ich habe GitHub, Foren und Fachseiten durchsucht. Das Ergebnis:

**Es gibt keinen Bauplan, der von allein Geld druckt.** Die bekannten Projekte sind
echt und technisch gut — [PraisonAI](https://github.com/MervinPraison/PraisonAI)
(9.200 Sterne, selbstverbessernde Agenten mit Gedächtnis),
[awesome-n8n-templates](https://github.com/enescingoz/awesome-n8n-templates)
(25.800 Sterne, 280 fertige Automatisierungen), dazu mehrere
Faceless-Video-Baukästen. Was ihnen allen fehlt: **ein einziger belegter
Einkommensnachweis.** Kein Repo, kein Forum, keine Fallstudie mit nachprüfbaren Zahlen.

Was sich dagegen durchgängig zeigt: **Geld verdient nicht, wer die Automatisierung
baut, sondern wer sie verkauft.** Der Betrieb in Trier, der keine Zeit für Instagram
hat, zahlt 600 € im Monat für etwas, das dich zwei Stunden kostet, weil die Maschine
schon läuft. Das ist kein Trick. Das ist dieselbe Rechnung wie damals im Handwerk:
Du verkaufst nicht die Maschine, du verkaufst, was sie kann.

Deshalb steht der Punkt **„Zwei lokale Betriebe ansprechen"** ganz oben im Gedächtnis —
Bewertung 200, höher als alles andere. 6 Stunden Aufwand, 1.200 € im Monat.
Das Hauptprodukt für 149 € kommt auf 65, weil es 40 Stunden kostet.

Die Maschine ist der Hebel. Der erste Kunde ist der Beweis.

---

## Deine nächsten drei Dinge

1. **Ein Anruf** beim Insolvenzverwalter: Wann kommt die Restschuldbefreiung?
   (Steht als offene Frage im Gedächtnis, Dringlichkeit hoch.)
2. **Das System auf deinem Mac einrichten** — ein Befehl, Anleitung unten.
3. **Zwei Betriebe ansprechen.** Gesprächsleitfaden steht in `TODO_KAI.md`.

Punkt 1 und 3 kann ich nicht für dich machen. Alles andere schon.

---

## Einrichten (einmalig, 10 Minuten)

Terminal öffnen, diese Zeilen nacheinander:

```bash
cd ~/jk24-autopilot          # oder wo das Projekt liegt
pip3 install -r requirements.txt --break-system-packages
python3 brain_seed.py        # Gedächtnis füllen
./install_autopilot_mac.sh   # Autopilot einschalten
```

Danach einmal testen:
```bash
python3 autopilot.py
```

Wenn das durchläuft, bist du fertig. Ab dann macht er es allein.
