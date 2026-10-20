# Wie Kairo seine Strategie verbessert – ohne sich selbst zu täuschen

Ziel: aus den Papier-Tests Schritt für Schritt die beste **belegbare** Strategie bauen.
Gefahr: Wer nach jedem Monat einfach das übernimmt, was gerade am besten lief, baut eine Strategie,
die perfekt auf die Vergangenheit passt und in der Zukunft versagt (Überanpassung). Bei 20 Varianten
sieht fast immer eine glänzend aus – rein durch Zufall. Deshalb gelten diese Regeln.

## 1. Zwei Rollen: Ideen finden ≠ Ideen beweisen

- **Ideen finden:** Papier-Tests, Schatten-Matrix (Ausstieg EMA 20 / T5 / T10, CRV-Mindestwert, 4H vs. Tag),
  Backtests. Hier darf man alles anschauen.
- **Ideen beweisen:** nur mit Daten, die **nach** der Entscheidung entstehen. Ein Ergebnis, aus dem eine Idee
  stammt, zählt nie als Beweis für dieselbe Idee.

## 2. Wann ein Element „besser“ ist (Aufnahme-Regeln)

Ein Element (z. B. anderer Ausstieg, CRV-Filter, Analysten-Ziel) wird nur übernommen, wenn **alle** Punkte erfüllt sind:

1. **Genug Trades:** mindestens 30 abgeschlossene Trades in der Variante und in der Vergleichsgruppe (besser 50).
2. **Klarer Abstand:** Ø R nach Gebühren mindestens 0,15 R besser als die aktuelle Version.
3. **Kein Zufall:** Bootstrap-Test, Schwelle verschärft nach Zahl der gleichzeitig geprüften Varianten
   (5 % geteilt durch Anzahl Varianten).
4. **Passt zur Geschichte:** derselbe Effekt zeigt sich auch im 6-Jahres-Backtest (gleiche Richtung).
5. **Schlägt die Kontrollen:** besser als zufällige Einstiege mit denselben Regeln und – für das Gesamtsystem –
   besser als der Welt-ETF nach Kosten.

## 3. Wie geändert wird

- **Eine Änderung auf einmal**, höchstens eine pro Quartal.
- Jede Änderung ergibt eine **neue Version** (KAIRO v2, v3 …) mit eigenem Papier-Depot, Start bei null.
  Die alte Version läuft zum Vergleich weiter.
- Alles wird im Versionsprotokoll unten festgehalten: Datum, Änderung, Begründung, Zahlen zum Zeitpunkt der Entscheidung.
- Scanner-Kriterien und Score in der App ändern sich erst nach Freigabe durch Jonny.

## 4. Wann die Strategie als „belegt“ gilt

Eine Version gilt als belegt, wenn sie **mindestens 12 Monate unverändert** im Papier-Test gelaufen ist,
mindestens 50 Trades hat, nach Gebühren besser als der Welt-ETF ist und den Bootstrap-Test besteht.
Vorher steht in der App immer „im Test“ – nie „bewiesen“.

## 5. Monatliche Auswertung (jeweils um den 2. des Monats)

1. Stand aller Papier-Depots und der Schatten-Matrix, je Element: Trades, Ø R, Trefferquote, Abstand zur aktuellen Version.
2. Prüfen, ob ein Element die Aufnahme-Regeln erfüllt. Wenn nein: nichts ändern, nur berichten.
3. Kurzer Bericht an Jonny in einfacher Sprache.

## Versionsprotokoll

| Version | Start | Änderung | Begründung |
|---|---|---|---|
| KAIRO v1 | 15.10.2026 | Ausgangsregel: 11/11 Kriterien, 5 ruhige Tage, Stop unter der Seitwärtsphase, Ausstieg EMA 20 ab Tag 10, spätestens Tag 60 | Basis aus dem 6-Jahres-Backtest |
| KAIROZ / KAIROL | 10/2026 | Kairo-Ziel: Halten bis zum Analysten-Ziel (Varianten) | Idee von Jonny, Papier-Test |
