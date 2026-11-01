# Mean-Reversion-Meisterschaft – Ergebnis

Vorab festgelegt (01./02.11.2026, vor dem ersten Lauf). Gleiche Bedingungen für alle: korrigierte Engine
(research/strategy_championship/engine.py), Universum USA + Europa (eingefroren 16.10.2026, Grundfilter des Scanners:
≥ 5 Mio. $ Tagesumsatz, Kurs ≥ 1, ≥ 300 Tage Historie), Kauf zur nächsten Eröffnung nach dem Signal, Kosten „normal“
(Scalable PRIME+) und „Stress“ (doppelter Spread, Schlupf, FX), Kapital 10.000 € und 20.000 €, Zeiträume Train 2008–2016,
Validierung 2017–2021, Holdout 2022–2026. Kein Parameter wird nach dem Lauf angepasst.

Familie A – klassische kurzfristige Mean Reversion (Gewicht je Position 1/N, kein Stop, Zeitlimit):
  A1 RSI2-10   RSI(2) < 10 und Schluss über 200-Tage-Linie · Ausstieg Schluss über 5-Tage-Linie · max. 10 Tage
  A2 RSI2-5    wie A1, RSI(2) < 5
  A3 RSI2-OHNE RSI(2) < 10 ohne Trendfilter
  A4 IBS       Schluss im unteren 15 % der Tagesspanne, über 200-Tage-Linie · Ausstieg Schluss über Vortageshoch · max. 10 T.
  A5 3TAGE     drei Verlust-Schlusskurse in Folge, über 200-Tage-Linie · Ausstieg Schluss über 5-Tage-Linie · max. 10 T.
  A6 ZSCORE    (Schluss − 20-Tage-Schnitt)/Schwankung < −2, über 200-Tage-Linie · Ausstieg Schluss über 20-Tage-Schnitt · max. 15 T.
  A7 WOCHE     jeden Freitag die 10 schwächsten Aktien der Woche (≤ −5 %) · 5 Tage halten (Short-Term-Reversal)
  A8 RSI2-LIQ  wie A1, nur Aktien mit ≥ 50 Mio. $ Tagesumsatz (kleinere Spreads)
  A9 RSI2-STOP wie A1, mit Stop 2,5 ATR unter Kauf und Positionsgröße nach Risiko (1 % je Trade)
  Rangfolge bei mehr Signalen als Plätzen: stärkster Ausschlag zuerst (niedrigster RSI/IBS/Z, schwächste Woche).
Familie B – B60 mit anderen Ausstiegen/Aufbau (gleiche Treffer und Einstiege wie B60):
  B0 B60       unverändert (Referenz)
  B1 SMA5      Ausstieg Schluss über 5-Tage-Linie (Stop bleibt), max. 10 Tage
  B2 VORHOCH   Ausstieg erster Schluss über dem Vortageshoch (Stop bleibt), max. 10 Tage
  B3 TAG10     Zeitausstieg Schluss Tag 10 (Stop bleibt)
  B4 GROSS     nur Treffer mit ≥ 50 Mio. $ Tagesumsatz
  B5 PANIK     doppeltes Risiko, wenn der Markt der Region unter seiner 200-Tage-Linie liegt
  B6–B11       Robustheit der Basis: 3 / 7 Kerzen, Spanne 1,0 / 2,0 ATR, Wartezeit 5 / 15 Tage (je ein Parameter)
Familie C – ETF-Mean-Reversion (kleinste Kosten): C1 RSI2-ETF – A1-Regel auf den Index-ETFs des Datensatzes.

Raster: Familie A/C mit 5 und 10 Plätzen (Gewicht 20 % bzw. 10 %; A9: 5 × 1 % bzw. 10 × 0,5 % Risiko), Familie B mit 5 × 1 % und
20 × 0,25 % Risiko (wie B60).

Entscheidungsregel: Ein Herausforderer „schlägt B60“, wenn er mit Stress-Kosten in Validierung UND Holdout bei 10.000 € UND
20.000 € (jeweils bestes eigenes Raster gegen bestes B60-Raster, Raster vorab je Familie festgelegt = das mit der höheren
Train-Rendite) eine höhere Jahresrendite hat, der größte Rückgang nicht mehr als 5 Prozentpunkte schlechter ist und der
einseitige Block-Bootstrap der Monatsrenditen (Validierung + Holdout, Holm über alle Herausforderer) p < 0,10 ergibt.
Zusätzlich wird jede Variante gegen den Welt-ETF (ACWI) gezeigt. Gewinner = Schattentest, keine Regeländerung.

WELLE 2 (vorab festgelegt 02.11.2026 nach Welle 1, vor dem eigenen Lauf – klar getrennt berichtet):
Welle 1 zeigte: Schnelle Mean Reversion hat mit normalen Kosten einen großen Vorteil, mit Stress-Kosten Totalverlust.
Darum je Variante ein Kostenraster (Spread × 1 / 1,5 / 2, Schlupf 0 / 0,05 %, FX-Aufschlag 0 / 0,05 / 0,1 % je Seite;
Gebühr 0,99 € unter 250 €), die Kostenschwelle (höchste geprüfte Kosten, bei denen Validierung UND Holdout den Welt-ETF
schlagen) und der Brutto-Ertrag je Trade (ohne Kosten). Neue liquide Varianten (≥ 100 Mio. $ Tagesumsatz):
  A5L 3 Verlusttage + Trend, liquide · A7L Wochen-Verlierer, liquide · A1L RSI(2) < 10 + Trend, liquide · A6L Z-Score, liquide

WELLE 3 (vorab festgelegt 02.11.2026 nach Welle 2 – ACHTUNG: dieselben Daten wurden schon zweimal ausgewertet, die Ergebnisse
sind deshalb nur Hinweise; der eigentliche Beweis ist der Schattentest auf neuen Daten). Ziel: Kosten senken, A5 robuster machen.
  W1 A5 mit Kauf-Limit 1 % unter dem Signal-Schluss (gilt einen Tag) · W2 A5 mit Kauf-Limit 0,5 ATR unter dem Schluss
  W3 4 Verlusttage + Trend (seltener, stärker) · W4 A5 nur bei RSI(2) < 15 (weniger Trades)
  Depot-Kombination im Bericht: 90 % Welt-ETF + 10 % Strategie und 70/30, monatlich ausgeglichen (A5, W-Varianten, C1, B60).

**Welt-ETF (ACWI, ohne Kosten):** Train +3.9% · Validierung +14.4% · Holdout +10.3%

| Variante | Raster | Train | Validierung | Holdout | gesamt (größter Rückgang) | Sharpe gesamt | Trades | normal: Val / Hold |
|---|---|---|---|---|---|---|---|---|
| A1 RSI(2) < 10 + Trend | 10 | -8.5% | -74.0% | -24.7% | -37.7% (-100.0%) | -1.43 | 7624 | +23.4% / +0.6% |
| A2 RSI(2) < 5 + Trend | 10 | -9.4% | -74.7% | +0.0% | -33.8% (-100.0%) | -1.60 | 6762 | +18.2% / +1.8% |
| A3 RSI(2) < 10 ohne Trend | 5 | -3.3% | -7.3% | -18.0% | -8.1% (-84.9%) | 0.01 | 5893 | +26.4% / +3.9% |
| A4 IBS < 0,15 + Trend | 5 | -12.6% | -100.0% | – | -100.0% (-100.0%) | -0.85 | 3544 | -10.5% / -8.9% |
| A5 3 Verlusttage + Trend | 5 | -12.4% | -1.6% | -76.2% | -35.1% (-100.0%) | -1.26 | 5813 | +35.0% / +11.9% |
| A6 Z-Score < −2 + Trend | 5 | +6.9% | +4.5% | -6.8% | +2.6% (-42.7%) | 0.22 | 1964 | +15.3% / +1.7% |
| A7 Wochen-Verlierer (Reversal) | 10 | -57.2% | -23.2% | +0.0% | -37.9% (-100.0%) | -1.18 | 2493 | +26.4% / +23.9% |
| A8 RSI(2) nur liquide | 10 | -6.7% | -72.0% | +0.0% | -31.0% (-99.9%) | -1.66 | 7124 | +18.1% / +2.6% |
| A9 RSI(2) mit Stop | 5 | -22.5% | -87.2% | +0.0% | -48.8% (-100.0%) | -1.46 | 3367 | +5.3% / -0.6% |
| B0 B60 (Referenz) | 5x1 | +7.6% | -12.4% | -3.7% | -0.9% (-70.6%) | 0.05 | 1460 | -8.6% / +1.8% |
| B1 B60, Ausstieg 5-Tage-Linie | 20x025 | -51.7% | -30.1% | +0.0% | -35.8% (-100.0%) | -2.11 | 3187 | -7.2% / -60.9% |
| B2 B60, Ausstieg Vortageshoch | 20x025 | -50.1% | -29.6% | +0.0% | -34.7% (-100.0%) | -2.09 | 3241 | -3.9% / -6.0% |
| B3 B60, Ausstieg Tag 10 | 5x1 | -3.7% | -6.3% | -13.7% | -7.1% (-76.6%) | -0.28 | 2290 | +11.3% / +1.4% |
| B4 B60 nur liquide | 5x1 | +4.2% | +5.0% | -17.0% | -1.5% (-61.2%) | 0.00 | 1162 | +9.1% / -12.5% |
| B5 B60, doppeltes Risiko im Ausverkauf | 5x1 | -0.1% | -11.5% | +2.8% | -2.6% (-74.2%) | -0.01 | 1294 | -3.6% / +7.4% |
| B6 B60 Basis 3 Kerzen | 20x025 | -4.5% | -6.4% | -77.6% | -34.3% (-100.0%) | -1.71 | 4952 | +4.6% / +4.2% |
| B7 B60 Basis 7 Kerzen | 20x025 | +1.3% | +0.8% | -7.2% | -1.0% (-42.1%) | -0.06 | 3013 | +7.7% / -1.5% |
| B8 B60 Spanne 1,0 ATR | 5x1 | +1.3% | -8.7% | -10.1% | -4.3% (-75.3%) | -0.22 | 821 | +0.3% / -1.8% |
| B9 B60 Spanne 2,0 ATR | 20x025 | +0.6% | -5.2% | -24.6% | -7.9% (-82.4%) | -0.47 | 5615 | +3.1% / +1.0% |
| B10 B60 Wartezeit 5 | 5x1 | +5.2% | -11.3% | -6.6% | -2.4% (-70.3%) | -0.03 | 1228 | -2.4% / +6.5% |
| B11 B60 Wartezeit 15 | 5x1 | +2.5% | -12.6% | +6.8% | -0.7% (-78.8%) | 0.08 | 1580 | -9.7% / +20.2% |
| C1 RSI(2) auf Index-ETFs | 5 | +3.5% | +2.1% | +1.3% | +2.6% (-26.4%) | 0.26 | 1695 | +8.3% / +8.0% |
| A5L 3 Verlusttage + Trend, liquide | 10 | +10.6% | -12.2% | -14.3% | -2.5% (-81.6%) | 0.09 | 10642 | +12.4% / +6.2% |
| A7L Wochen-Verlierer, liquide | 10 | -8.2% | -1.0% | -26.9% | -11.6% (-91.7%) | -0.16 | 7279 | +21.3% / +6.5% |
| A1L RSI(2) + Trend, liquide | 10 | -0.7% | -12.8% | -54.9% | -21.6% (-99.0%) | -1.06 | 9820 | +12.5% / +5.8% |
| A6L Z-Score, liquide | 5 | +0.3% | +0.3% | -5.8% | -1.3% (-57.7%) | 0.05 | 1785 | +9.9% / +2.5% |
| W1 A5 mit Limit 1 % unter Schluss | 10 | -0.8% | +4.0% | -10.4% | -2.0% (-71.5%) | 0.01 | 9849 | +33.8% / +14.2% |
| W2 A5 mit Limit 0,5 ATR unter Schluss | 5 | +1.2% | +15.1% | -11.4% | +1.3% (-52.2%) | 0.17 | 4827 | +47.5% / +12.3% |
| W3 4 Verlusttage + Trend | 5 | -18.2% | -75.1% | +0.0% | -37.2% (-100.0%) | -1.52 | 3254 | +25.4% / +6.2% |
| W4 A5 nur RSI(2) < 15 | 5 | -10.4% | -4.0% | -74.5% | -33.7% (-100.0%) | -1.22 | 5906 | +30.2% / +15.1% |

*Werte: 10.000 €, Stress-Kosten, Jahresrendite (CAGR). Raster je Variante vorab nach Train gewählt.*

## Entscheidung (gegen B60, Stress-Kosten, 10.000 € und 20.000 €, Validierung und Holdout)

| Variante | schlägt B60 in allen 4 Prüfungen | Bootstrap p | Holm p | Ergebnis |
|---|---|---|---|---|
| C1 RSI(2) auf Index-ETFs | ja | 0.066 | 1.000 | nicht bestanden |
| B5 B60, doppeltes Risiko im Ausverkauf | nein | 0.088 | 1.000 | nicht bestanden |
| W2 A5 mit Limit 0,5 ATR unter Schluss | nein | 0.103 | 1.000 | nicht bestanden |
| A6 Z-Score < −2 + Trend | nein | 0.138 | 1.000 | nicht bestanden |
| A6L Z-Score, liquide | nein | 0.212 | 1.000 | nicht bestanden |
| B7 B60 Basis 7 Kerzen | nein | 0.212 | 1.000 | nicht bestanden |
| B11 B60 Wartezeit 15 | nein | 0.223 | 1.000 | nicht bestanden |
| W1 A5 mit Limit 1 % unter Schluss | nein | 0.244 | 1.000 | nicht bestanden |
| B4 B60 nur liquide | nein | 0.417 | 1.000 | nicht bestanden |
| B10 B60 Wartezeit 5 | nein | 0.557 | 1.000 | nicht bestanden |
| B8 B60 Spanne 1,0 ATR | nein | 0.586 | 1.000 | nicht bestanden |
| A7 Wochen-Verlierer (Reversal) | nein | 0.590 | 1.000 | nicht bestanden |
| A7L Wochen-Verlierer, liquide | nein | 0.633 | 1.000 | nicht bestanden |
| A3 RSI(2) < 10 ohne Trend | nein | 0.637 | 1.000 | nicht bestanden |
| B3 B60, Ausstieg Tag 10 | nein | 0.725 | 1.000 | nicht bestanden |
| A5L 3 Verlusttage + Trend, liquide | nein | 0.776 | 1.000 | nicht bestanden |
| B1 B60, Ausstieg 5-Tage-Linie | nein | 0.804 | 1.000 | nicht bestanden |
| B2 B60, Ausstieg Vortageshoch | nein | 0.836 | 1.000 | nicht bestanden |
| A5 3 Verlusttage + Trend | nein | 0.913 | 1.000 | nicht bestanden |
| W4 A5 nur RSI(2) < 15 | nein | 0.917 | 1.000 | nicht bestanden |
| A9 RSI(2) mit Stop | nein | 0.933 | 1.000 | nicht bestanden |
| W3 4 Verlusttage + Trend | nein | 0.936 | 1.000 | nicht bestanden |
| A1L RSI(2) + Trend, liquide | nein | 0.945 | 1.000 | nicht bestanden |
| A2 RSI(2) < 5 + Trend | nein | 0.947 | 1.000 | nicht bestanden |
| A1 RSI(2) < 10 + Trend | nein | 0.952 | 1.000 | nicht bestanden |
| B9 B60 Spanne 2,0 ATR | nein | 0.952 | 1.000 | nicht bestanden |
| A4 IBS < 0,15 + Trend | nein | 0.956 | 1.000 | nicht bestanden |
| A8 RSI(2) nur liquide | nein | 0.960 | 1.000 | nicht bestanden |
| B6 B60 Basis 3 Kerzen | nein | 0.976 | 1.000 | nicht bestanden |

## Fazit

**Kein Herausforderer schlägt B60 durchgängig und statistisch abgesichert.** Die Tabelle zeigt trotzdem, welche Variante in welchem Zeitraum vorn lag.

## Welle 2 – Kosten entscheiden: Brutto-Ertrag und Kostenschwelle (10.000 €)

Kostenschwelle = höchste geprüfte Kosten je Seite (Spread-Hälfte + Schlupf + FX), bei denen die Variante in Validierung UND Holdout den Welt-ETF schlägt. Je höher, desto robuster gegen echte Handelskosten.

| Variante | Raster | Brutto je Trade | Trades | Ø Tage | normal Val / Hold | Kostenschwelle je Seite | dort Val / Hold | ×2 Spread+0,05 % Schlupf+0,1 % FX: Val / Hold |
|---|---|---|---|---|---|---|---|---|
| A1 RSI(2) < 10 + Trend | 10 | +0.4% | 11661 | 3.9 | +23.4% / +0.6% | schlägt ETF bei keinen geprüften Kosten | – | -69.0% / -17.6% |
| A1L RSI(2) + Trend, liquide | 5 | +0.4% | 5345 | 3.9 | +12.9% / +1.1% | schlägt ETF bei keinen geprüften Kosten | – | -13.0% / -15.2% |
| A2 RSI(2) < 5 + Trend | 10 | +0.4% | 10790 | 3.9 | +18.2% / +1.8% | schlägt ETF bei keinen geprüften Kosten | – | -68.5% / -17.4% |
| A3 RSI(2) < 10 ohne Trend | 5 | +0.6% | 5886 | 4.0 | +26.4% / +3.9% | schlägt ETF bei keinen geprüften Kosten | – | -7.3% / -17.8% |
| A5 3 Verlusttage + Trend | 5 | +0.5% | 6114 | 3.8 | +35.0% / +11.9% | 0.09% | +35.0% / +11.9% | -1.2% / -34.3% |
| A5L 3 Verlusttage + Trend, liquide | 10 | +0.4% | 10631 | 3.8 | +12.4% / +6.2% | schlägt ETF bei keinen geprüften Kosten | – | -12.2% / -14.3% |
| A6 Z-Score < −2 + Trend | 5 | +0.8% | 1964 | 11.6 | +15.3% / +1.7% | schlägt ETF bei keinen geprüften Kosten | – | +4.5% / -6.8% |
| A6L Z-Score, liquide | 5 | +0.5% | 1786 | 11.3 | +9.9% / +2.5% | schlägt ETF bei keinen geprüften Kosten | – | +0.4% / -5.8% |
| A7 Wochen-Verlierer (Reversal) | 10 | +0.5% | 8290 | 5.0 | +26.4% / +23.9% | 0.14% | +20.3% / +18.5% | -20.1% / +0.0% |
| A7L Wochen-Verlierer, liquide | 5 | +0.5% | 3957 | 5.0 | +14.8% / +5.5% | schlägt ETF bei keinen geprüften Kosten | – | -3.9% / -17.0% |
| A8 RSI(2) nur liquide | 5 | +0.4% | 5651 | 3.9 | +20.6% / +5.4% | schlägt ETF bei keinen geprüften Kosten | – | -5.5% / -28.1% |
| B0 B60 (Referenz) | 5x1 | +0.3% | 1422 | 10.9 | -8.6% / +1.8% | schlägt ETF bei keinen geprüften Kosten | – | -12.4% / -3.7% |
| C1 RSI(2) auf Index-ETFs | 5 | +0.5% | 1697 | 3.6 | +8.3% / +8.0% | schlägt ETF bei keinen geprüften Kosten | – | +2.1% / +1.3% |
| W1 A5 mit Limit 1 % unter Schluss | 10 | +0.6% | 9857 | 4.5 | +33.8% / +14.2% | 0.09% | +33.8% / +14.2% | +4.0% / -10.4% |
| W2 A5 mit Limit 0,5 ATR unter Schluss | 5 | +0.7% | 4828 | 4.6 | +47.5% / +12.3% | 0.09% | +47.5% / +12.3% | +15.1% / -11.3% |
| W3 4 Verlusttage + Trend | 10 | +0.4% | 11184 | 3.8 | +19.8% / +3.3% | schlägt ETF bei keinen geprüften Kosten | – | -69.7% / +0.0% |
| W4 A5 nur RSI(2) < 15 | 5 | +0.5% | 6019 | 3.8 | +30.2% / +15.1% | 0.09% | +30.2% / +15.1% | -3.9% / -14.8% |

*Welt-ETF zum Vergleich: Validierung +14.4%, Holdout +10.3%.*

## Depot-Kombination: Welt-ETF + Strategie (monatlich ausgeglichen, 10.000 €)

| Mischung | Kosten | Train | Validierung | Holdout | gesamt | größter Rückgang |
|---|---|---|---|---|---|---|
| 100 % Welt-ETF | – | +4.1% | +14.6% | +10.7% | +8.5% | -51.7% |
| 90 % ETF + 10 % A5 3 Verlusttage + Trend | normal | +5.5% | +16.8% | +11.1% | +9.8% | -48.5% |
| 70 % ETF + 30 % A5 3 Verlusttage + Trend | normal | +8.2% | +21.0% | +11.6% | +12.4% | -41.6% |
| 90 % ETF + 10 % A5 3 Verlusttage + Trend | Stress | +2.6% | +13.1% | -1.3% | +4.2% | -49.4% |
| 70 % ETF + 30 % A5 3 Verlusttage + Trend | Stress | -0.5% | +10.0% | -22.8% | -4.2% | -74.0% |
| 90 % ETF + 10 % W1 A5 mit Limit 1 % unter Schluss | normal | +6.1% | +16.5% | +11.2% | +10.1% | -48.9% |
| 70 % ETF + 30 % W1 A5 mit Limit 1 % unter Schluss | normal | +10.0% | +20.5% | +12.1% | +13.2% | -42.9% |
| 90 % ETF + 10 % W1 A5 mit Limit 1 % unter Schluss | Stress | +3.8% | +13.6% | +8.6% | +7.5% | -49.6% |
| 70 % ETF + 30 % W1 A5 mit Limit 1 % unter Schluss | Stress | +2.9% | +11.6% | +4.3% | +5.5% | -45.2% |
| 90 % ETF + 10 % W2 A5 mit Limit 0,5 ATR unter Schluss | normal | +6.4% | +17.8% | +10.9% | +10.5% | -47.8% |
| 70 % ETF + 30 % W2 A5 mit Limit 0,5 ATR unter Schluss | normal | +10.9% | +24.2% | +11.2% | +14.4% | -39.2% |
| 90 % ETF + 10 % W2 A5 mit Limit 0,5 ATR unter Schluss | Stress | +4.0% | +14.8% | +8.3% | +7.9% | -48.5% |
| 70 % ETF + 30 % W2 A5 mit Limit 0,5 ATR unter Schluss | Stress | +3.8% | +15.2% | +3.7% | +6.7% | -41.6% |
| 90 % ETF + 10 % W3 4 Verlusttage + Trend | normal | +4.3% | +15.8% | +10.5% | +8.8% | -49.7% |
| 70 % ETF + 30 % W3 4 Verlusttage + Trend | normal | +4.5% | +18.2% | +9.9% | +9.4% | -45.5% |
| 90 % ETF + 10 % W3 4 Verlusttage + Trend | Stress | +1.7% | +2.3% | +9.7% | +3.8% | -50.4% |
| 70 % ETF + 30 % W3 4 Verlusttage + Trend | Stress | -3.2% | -19.7% | +7.6% | -5.4% | -84.6% |
| 90 % ETF + 10 % W4 A5 nur RSI(2) < 15 | normal | +5.7% | +16.3% | +11.4% | +9.9% | -48.2% |
| 70 % ETF + 30 % W4 A5 nur RSI(2) < 15 | normal | +8.7% | +19.7% | +12.6% | +12.5% | -40.7% |
| 90 % ETF + 10 % W4 A5 nur RSI(2) < 15 | Stress | +2.8% | +12.8% | -0.2% | +4.6% | -49.1% |
| 70 % ETF + 30 % W4 A5 nur RSI(2) < 15 | Stress | +0.1% | +9.2% | -20.1% | -3.3% | -66.9% |
| 90 % ETF + 10 % C1 RSI(2) auf Index-ETFs | normal | +4.9% | +14.0% | +10.5% | +8.7% | -47.9% |
| 70 % ETF + 30 % C1 RSI(2) auf Index-ETFs | normal | +6.4% | +12.9% | +10.1% | +9.0% | -39.6% |
| 90 % ETF + 10 % C1 RSI(2) auf Index-ETFs | Stress | +4.4% | +13.4% | +9.8% | +8.1% | -47.9% |
| 70 % ETF + 30 % C1 RSI(2) auf Index-ETFs | Stress | +4.7% | +10.9% | +8.0% | +7.2% | -39.7% |
| 90 % ETF + 10 % B0 B60 (Referenz) | normal | +5.7% | +12.2% | +10.0% | +8.4% | -49.4% |
| 70 % ETF + 30 % B0 B60 (Referenz) | normal | +8.7% | +7.5% | +8.4% | +8.2% | -44.7% |
| 90 % ETF + 10 % B0 B60 (Referenz) | Stress | +4.7% | +11.7% | +9.3% | +7.7% | -49.8% |
| 70 % ETF + 30 % B0 B60 (Referenz) | Stress | +5.7% | +6.1% | +6.5% | +6.0% | -46.0% |
