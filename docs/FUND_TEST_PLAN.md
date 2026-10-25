# Fundamentaldaten für Kairo-Treffer (vorab festgelegt 25.10.2026)

Daten: Kairo-Trades nach heutiger Regel (R netto bei 5.000 € PRIME+), nur US-Aktien (SEC-Zahlen), Signale bis 31.03.2026.
Fundamentaldaten zeitpunktgenau: nur Berichte, die am Signaltag schon veröffentlicht waren (SEC `avail` ≤ Signaltag).

## Merkmale
- **Q Qualität:** Gewinn der letzten 12 Monate > 0 UND operativer Cashflow > 0 UND Bruttogewinn/Bilanzsumme ≥ 0,25.
- **V Günstig für ihre Verhältnisse:** KGV am Signaltag unter dem Median des eigenen KGV der 5 Jahre davor
  (Monatswerte, mindestens 36 Monate mit positivem Gewinn). Börsenwert = Kurs × Aktienzahl (Splits berücksichtigt).
- **QV:** beides.

## Test 1: Besseres Ø R mit Merkmal?
Bestanden, wenn Trades mit Merkmal in Train, Validierung UND Holdout ein höheres Ø R haben als ohne,
und gepoolt (Validierung+Holdout) Permutations-p ≤ 0,05/3.

## Test 2: Fehlsignal bei guter Firma trotzdem halten? (Idee von Jonny)
Für Q-Trades: statt Stop/Ausstieg die Aktie 12 Monate (252 Handelstage) halten.
Vergleich in % pro Trade gegen (a) die Kairo-Regel und (b) den S&P 500 (SPY) im gleichen Zeitraum,
(c) zufällige Kaufzeitpunkte derselben Q-Aktien (zeigt, ob das Kairo-Timing etwas bringt).
Bestanden, wenn „halten“ den SPY im gleichen Zeitraum in allen drei Abschnitten schlägt UND besser ist als zufälliges Timing.
Warnung vorab: Die Kursdaten enthalten keine Pleitefirmen. Das begünstigt „ohne Stop halten“ stark.

## Test 3: Positionsgröße
Nur wenn ein Merkmal Test 1 besteht: 1,5-faches Risiko bei Merkmal, 0,75-faches sonst; Summe R pro Abschnitt und
größter Rückgang in R gegenüber gleichem Risiko.
