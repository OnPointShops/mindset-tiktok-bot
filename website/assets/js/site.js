/* JK24 – das gesamte JavaScript der Seite.
   Zwei Aufgaben: die Schritt-für-Schritt-Darstellung am Automaten und der Rechner.
   Es wird nichts gespeichert und nichts übertragen. Ohne JavaScript bleibt die
   Seite lesbar; nur diese beiden Elemente stehen dann still. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- Automat ---------- */
  var machine = $("machine");
  if (machine) {
    var PICK = 7;               // neutral nummeriertes Beispielfach
    var slots = $("m-slots");
    for (var i = 1; i <= 20; i++) {
      var d = document.createElement("div");
      d.className = "m-slot";
      d.textContent = (i < 10 ? "0" : "") + i;
      slots.appendChild(d);
    }
    var step = 0, fail = false;
    var parts = { reader: $("m-reader"), pay: $("m-pay"), flap: $("m-flap") };
    // Je Schritt: Anzeige (2 Zeilen), leuchtendes Bauteil, Erklärtext.
    var STEPS = [
      { a: "FACH 07 GEWÄHLT", b: "BITTE ALTER PRÜFEN", on: null,
        t: "Am Anfang steht die Auswahl eines Fachs. Die Fächer sind nummeriert. Geöffnet wird noch nichts." },
      { a: "ALTER BESTÄTIGT", b: "WEITER ZUR ZAHLUNG", on: "reader",
        t: "Vor jeder Ausgabe prüft der Automat das Alter, <span class=\"offen\">per Ausweis oder Bankkarte</span>. <span class=\"offen\">Ist die Prüfung bestanden, geht es weiter zur Zahlung.</span>" },
      { a: "BITTE BEZAHLEN", b: "KARTE AUFLEGEN", on: "pay",
        t: "<span class=\"offen\">Erst nach bestandener Prüfung lässt sich bezahlen. Gezahlt wird bargeldlos.</span>" },
      { a: "FACH 07 OFFEN", b: "BITTE ENTNEHMEN", on: "flap",
        t: "<span class=\"offen\">Nach der Zahlung gibt der Automat genau das gewählte Fach frei. Alle anderen Fächer bleiben verschlossen.</span>" }
    ];
    var FAIL = { a: "KEINE FREIGABE", b: "VORGANG BEENDET", on: "reader",
      t: "<span class=\"offen\">Ist die Prüfung nicht bestanden, endet der Vorgang hier. Es wird nicht bezahlt und kein Fach öffnet sich.</span>" };

    var render = function () {
      var failed = fail && step >= 1;
      if (failed) step = 1;
      var s = failed ? FAIL : STEPS[step];
      machine.setAttribute("data-res", failed ? "no" : (step >= 1 ? "ok" : ""));
      $("m-s1").textContent = "SCHRITT " + (step + 1) + " VON 4";
      $("m-s2").textContent = s.a;
      $("m-s3").textContent = s.b;
      Object.keys(parts).forEach(function (k) { parts[k].classList.toggle("is-on", s.on === k); });
      slots.children[PICK - 1].classList.toggle("is-pick", !failed);
      $("demo-text").innerHTML = s.t;   // Texte stehen fest oben im Code, keine Eingaben von außen
      for (var n = 0; n < 4; n++) {
        var b = $("step-" + n);
        if (n === step) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
        b.disabled = fail && n > 1;
      }
      $("demo-next").textContent = (failed || step === 3) ? "Von vorn" : "Nächster Schritt";
    };
    $("steps").addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b || b.disabled) return;
      step = +b.getAttribute("data-step"); render();
    });
    $("demo-next").addEventListener("click", function () {
      step = (fail && step >= 1) || step === 3 ? 0 : step + 1; render();
    });
    $("demo-fail").addEventListener("change", function (e) { fail = e.target.checked; if (fail) step = 1; render(); });

    render();
  }

  /* ---------- Rechner ---------- */
  var form = $("calc");
  if (form) {
    var eur = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
    var num = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });
    var v = function (id) { return parseFloat($(id).value) || 0; };
    // Reine Rechnung, getrennt von der Anzeige, damit man sie nachprüfen kann.
    var rechne = function (sales, price, sharePct, days, watt, ct, standortZahltStrom) {
      var brutto = sales * price * days;
      var netto = brutto / 1.19;
      var anteil = netto * sharePct / 100;
      var strom = standortZahltStrom ? watt / 1000 * 24 * days * ct / 100 : 0;
      return { brutto: brutto, netto: netto, anteil: anteil, strom: strom, ergebnis: anteil - strom };
    };
    var calc = function () {
      var me = $("c-pw-me").checked;
      $("pw-fields").hidden = !me;
      var a = [v("c-sales"), v("c-price"), v("c-share"), v("c-days"), v("c-watt"), v("c-kwh"), me];
      var r = rechne.apply(null, a);
      $("o-sales").textContent = num.format(a[0]);
      $("o-price").textContent = eur.format(a[1]);
      $("o-share").textContent = num.format(a[2]) + " %";
      $("o-days").textContent = num.format(a[3]);
      $("o-watt").textContent = num.format(a[4]) + " W";
      $("o-kwh").textContent = num.format(a[5]) + " ct";
      $("r-gross").textContent = eur.format(r.brutto);
      $("r-net").textContent = eur.format(r.netto);
      $("r-share").textContent = eur.format(r.anteil);
      $("r-power").textContent = me ? "− " + eur.format(r.strom) : "trägt JK24";
      $("r-sum").textContent = eur.format(r.ergebnis);
      $("r-half").textContent = eur.format(rechne(a[0] / 2, a[1], a[2], a[3], a[4], a[5], me).ergebnis);
      $("r-double").textContent = eur.format(rechne(a[0] * 2, a[1], a[2], a[3], a[4], a[5], me).ergebnis);
    };
    form.addEventListener("input", calc);
    calc();
  }
})();
