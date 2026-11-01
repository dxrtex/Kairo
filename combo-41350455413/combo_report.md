# Kombinations-Test: 11 Kriterien + X (2008–2026)

Vorab festgelegt (01.11.2026, vor dem ersten Lauf). Alle B60-Trades 2008–2026 (korrigierte Engine, je Trade, Stress-Kosten).
Je Hypothese: Ø R der Trades MIT Merkmal gegen OHNE Merkmal (nur Trades, bei denen das Merkmal bestimmbar ist).

Insider (nur USA, SEC Formular 4, offene Marktkäufe Code P; zählt nur, wenn bis zum Signaltag GEMELDET – kein Blick voraus):
  H1 ins_buy      mindestens ein Insider-Kauf in den 90 Tagen vor dem Signal
  H2 ins_cluster  mindestens zwei verschiedene Insider kauften
  H3 ins_officer  ein Vorstand/Officer (CEO, CFO, President …) kaufte
  H4 ins_big      Kaufsumme ≥ 100.000 $
Kurs und Volumen (alle Regionen):
  H5 sma200_up    Schluss über der 200-Tage-Linie (Rücksetzer im langfristigen Aufwärtstrend)
  H6 deep_dd      ≥ 40 % unter dem 52-Wochen-Hoch
  H7 vol_spike    Volumen am Signaltag ≥ 2 × Ø der 50 Tage davor (Kapitulation)
  H8 drop5        Wochenverlust (5 Tage) ≤ −10 %
Quartalszahlen (nur USA, SEC 8-K Punkt 2.02 bis zum Signaltag angenommen):
  H9 earn_recent  Quartalszahlen in den 10 Handelstagen vor dem Signal
Paare: P1 ins_buy+deep_dd · P2 vol_spike+index_u200 · P3 sma200_up+index_u200

Entscheidungsregel: Ein Merkmal ist „Kandidat für den Depot-Test“ (als Verstärker: bevorzugt kaufen, oder als Filter:
weglassen), wenn der Unterschied in Train, Validierung UND Holdout dasselbe Vorzeichen hat und jeweils |Δ| ≥ 0,05 R beträgt
UND der Benjamini-Hochberg-q-Wert über alle 12 Tests ≤ 0,10 ist. Kein Kandidat ändert die Regel – nächster Schritt wäre ein
Depot-Test (Rangfolge/Filter vs. B60, alle Raster), danach Schattentest und Freigabe.

Teil 2 (vorab festgelegt 01.11.2026 nach Teil 1, vor dem eigenen Lauf; nur USA, SEC-Daten zeitgenau):
Grund des Rückgangs (8-K-Meldungen mit Annahmedatum in den 20 Handelstagen bis zum Signal; Chan 2003: Rückgänge OHNE
Nachricht erholen sich eher, Rückgänge MIT Nachricht setzen sich eher fort):
  N1 no_news      keine 8-K-Meldung
  N2 news_earn    Quartalszahlen-Meldung (8-K Punkt 2.02)
  N3 news_other   andere wesentliche Meldung (8-K ohne 2.02, nicht nur Anhänge 9.01)
Qualität (XBRL, nur bis zum Signaltag veröffentlichte Berichte, höchstens 200 Tage alt):
  Q1 profitable   Jahresüberschuss der letzten 12 Monate > 0
  Q2 gp_quality   Bruttogewinn / Bilanzsumme ≥ 0,20
  Q3 em_pos       letzter Quartalsgewinn über dem Vorjahresquartal
  Q4 low_lev      Eigenkapital / Bilanzsumme ≥ 0,40
Paare: no_news+profitable · news_earn+em_neg · profitable+deep_dd
Gleiche Entscheidungsregel, Benjamini-Hochberg innerhalb von Teil 2; zusätzlich der q-Wert über Teil 1 + 2 zusammen.

**13.241 B60-Trades**. davon USA 9.792 · Ø R Stress -0.030

| Merkmal | mit X (Anteil) | Ø R Stress mit | ohne | Δ Train | Δ Validierung | Δ Holdout | q (BH) | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| Insider-Kauf (90 T.) | 1529 (16% von 9789) | +0.006 | -0.011 | -0.017 (537) | +0.031 (415) | +0.042 (577) | 0.810 | **kein beständiger Effekt** |
| ≥ 2 Insider kauften | 535 (5% von 9789) | -0.169 | +0.001 | -0.047 (184) | -0.246 (146) | -0.221 (205) | 0.165 | **kein beständiger Effekt** |
| Vorstand/Officer kaufte | 670 (7% von 9789) | -0.077 | -0.003 | -0.057 (248) | -0.063 (181) | -0.094 (241) | 0.642 | **kein beständiger Effekt** |
| Insider-Käufe ≥ 100.000 $ | 1047 (11% von 9789) | +0.019 | -0.012 | -0.013 (321) | -0.067 (293) | +0.134 (433) | 0.810 | **kein beständiger Effekt** |
| über der 200-Tage-Linie | 2506 (19% von 13241) | -0.090 | -0.016 | +0.144 (781) | -0.135 (761) | -0.212 (964) | 0.247 | **kein beständiger Effekt** |
| ≥ 40 % unter 52-Wochen-Hoch | 1149 (9% von 13241) | +0.103 | -0.043 | +0.319 (320) | -0.177 (296) | +0.232 (533) | 0.219 | **kein beständiger Effekt** |
| Volumen ≥ 2 × Ø (Kapitulation) | 557 (4% von 13241) | -0.185 | -0.023 | -0.063 (185) | -0.223 (143) | -0.194 (229) | 0.165 | **kein beständiger Effekt** |
| Wochenverlust ≤ −10 % | 68 (1% von 13241) | +0.137 | -0.031 | +0.113 (16) | -0.127 (17) | +0.345 (35) | 0.642 | **kein beständiger Effekt** |
| Quartalszahlen ≤ 10 Tage davor | 1215 (12% von 9789) | -0.115 | +0.007 | +0.126 (395) | -0.463 (295) | -0.095 (525) | 0.165 | **kein beständiger Effekt** |
| Insider-Kauf (90 T.) UND ≥ 40 % unter 52-Wochen-Hoch | 170 (2% von 9789) | +0.361 | -0.015 | +0.741 (55) | -0.242 (44) | +0.485 (71) | 0.341 | **kein beständiger Effekt** |
| Volumen ≥ 2 × Ø (Kapitulation) UND Markt der Region unter 200-Tage-Linie | 172 (1% von 13241) | -0.060 | -0.029 | -0.045 (89) | -0.043 (30) | +0.054 (53) | 0.810 | **kein beständiger Effekt** |
| über der 200-Tage-Linie UND Markt der Region unter 200-Tage-Linie | 483 (4% von 13241) | +0.175 | -0.038 | +0.196 (231) | +0.065 (78) | +0.353 (174) | 0.165 | **kein beständiger Effekt** |

## Ergebnis

**Keine Kombination bringt beständig und nach Mehrfachtest-Korrektur mehr** – B60 bleibt unverändert.
