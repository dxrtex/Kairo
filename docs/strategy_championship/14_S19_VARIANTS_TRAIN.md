# 14 · S19-Varianten (Original / A / B / C) – nur Train 2008–2016

Status: **EXPLORATIV · DATENBESCHRÄNKT** (Tages-Proxy statt echter 4H-Kerzen; Größe per PIT-Proxy ADV ≥ 100 Mio. $ bzw. TODAY = heutige Börsenwert ≥ 10 Mrd. $ mit Rückschaufehler). Regeln vorab festgelegt in Protokoll v1.7. Validierung und Holdout unberührt.

Varianten: Original 2,5 Std + Volumen streng fallend · A 2,0 Std streng · B 2,5 Std + Volumen 2 von 3 · C 2,0 Std + 2 von 3.
Einstieg „trigger“ = 4H-Auslöser auf Tagesbasis nachgebildet; „open“ = Kauf zur nächsten Eröffnung, CRV am Signaltag geprüft.

| Variante · Einstieg · Größe | Signale/J | CRV ≥ 2 /J | Trades | Ø R netto | Ø R Stress | CAGR (2.000 €) | max. DD |
|---|---|---|---|---|---|---|---|
| S19 · trigger · PIT | 6.6 | 0.0 | 0 | – | – | +0.0% | 0.0% |
| S19 · open · PIT | 6.8 | 6.0 | 48 | -0.08 | -0.50 | -0.8% | -13.4% |
| S19-A · trigger · PIT | 55.3 | 1.3 | 12 | -0.62 | -0.83 | -0.7% | -6.7% |
| S19-A · open · PIT | 54.4 | 48.9 | 276 | -0.20 | -1.13 | -3.9% | -37.8% |
| S19-B · trigger · PIT | 30.3 | 0.2 | 2 | -0.40 | -0.56 | -0.1% | -1.4% |
| S19-B · open · PIT | 29.1 | 27.1 | 160 | -0.34 | -0.81 | -4.3% | -32.5% |
| S19-C · trigger · PIT | 169.2 | 1.7 | 15 | -0.53 | -0.75 | -0.7% | -7.6% |
| S19-C · open · PIT | 156.3 | 136.2 | 494 | -0.25 | -2.10 | -10.0% | -63.3% |
| S19 · trigger · TODAY | 21.1 | 0.2 | 2 | -1.11 | -1.38 | -0.2% | -2.0% |
| S19 · open · TODAY | 21.0 | 19.8 | 117 | -0.20 | -0.65 | -1.8% | -30.4% |
| S19-A · trigger · TODAY | 159.5 | 2.9 | 26 | -0.46 | -0.70 | -0.9% | -8.2% |
| S19-A · open · TODAY | 155.8 | 137.8 | 501 | -0.40 | -2.58 | -12.6% | -73.6% |
| S19-B · trigger · TODAY | 100.1 | 1.3 | 12 | +0.83 | +0.42 | +0.6% | -2.4% |
| S19-B · open · TODAY | 95.9 | 88.2 | 358 | -0.45 | -2.39 | -11.4% | -66.3% |
| S19-C · trigger · TODAY | 493.3 | 4.8 | 43 | -0.15 | -0.44 | -0.6% | -10.2% |
| S19-C · open · TODAY | 455.9 | 390.4 | 740 | -0.45 | -2.43 | -23.0% | -91.3% |

## Ergebnis

- **Keine Variante hat im Train-Zeitraum einen positiven Erwartungswert, der sich belegen lässt.** 15 von 16 Kombinationen liegen netto bei Ø R < 0.
- Lockerere Regeln bringen **mehr Signale, aber schlechtere Trades**. Am deutlichsten C · open · TODAY: 740 Trades, Ø −0,45 R, DD −91 %.
- Einzige Ausnahme: S19-B · trigger · TODAY mit +0,83 R (Stress +0,42 R). Das sind aber nur **12 Trades in 9 Jahren**, mit Rückschaufehler bei der Größe – statistisch wertlos (NICHT BELASTBAR). Die PIT-Variante derselben Regel liegt bei −0,40 R (2 Trades).
- Der eigentliche Engpass bleibt das CRV ≥ 2 nach dem Auslöser. Bei geringerer Überdehnung liegt das EMA20-Ziel näher, also wird CRV ≥ 2 seltener erreicht.

## Folgerung

S19 und die Varianten B/C laufen nur noch im **Papier-Test** (echte 4H-Kerzen) weiter, wie mit dem Nutzer vereinbart. Für echtes Geld gibt es keine Empfehlung. Keine weitere Parameter-Suche auf Train, sonst droht Überanpassung.
