# 17 · Welle 3 Position-Trading (Protokoll v1.9) – Train 2008–2016, Kosten Scalable PRIME+

Status: **EXPLORATIV · DATENBESCHRÄNKT** (Survivorship – auch Zufalls-Depots verdienen hier +10,4 % p. a.). Rohdaten c6_train.json.

| Variante (5.000 €) | CAGR | Stress | Max. DD | Sharpe | p vs. Zufall | positive Jahre | ohne beste 1 % Trades |
|---|---|---|---|---|---|---|---|
| **T1-top5** Momentum 6-1/Vol | **+18,8 %** | **+14,2 %** | −38 % | 0,68 | 0,05 | 7/8 | +9.663 € |
| P1 52-Wochen-Hoch | +7,7 % | +2,3 % | −36 % | 0,41 | 0,69 | 5/8 | +1.133 € |
| P2 Momentum + 52W | +0,6 % | −4,2 % | −57 % | 0,15 | 0,99 | 4/8 | −1.570 € |
| P3 Momentum + Vol-Steuerung | +14,2 % | +10,3 % | −38 % | 0,61 | 0,19 | 6/8 | +5.324 € |
| P4 Momentum + EMA200 je Titel | +15,4 % | +11,0 % | −40 % | 0,59 | 0,18 | 7/8 | +6.007 € |

Zufall (5 zufällige zulässige Titel monatlich, 100 Seeds): Median +10,4 %, 90-%-Quantil +17,6 %.
2.000 € und 10.000 € liefern praktisch dieselben Werte (PRIME+: Orders ≥ 250 € gebührenfrei). Alle Bilanzprüfungen bestanden.

**Ergebnis nach Regel v1.9:** Kein Kandidat schlägt T1-top5 → **T1-top5 bleibt einziger Kandidat** für die Validierung.
Die einfache Momentum-Regel war besser als jede „Verfeinerung“ – ein Hinweis, dass Zusatzfilter hier eher schaden.
