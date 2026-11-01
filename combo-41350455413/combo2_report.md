# Kombinations-Test Teil 2 (Nachrichten-Grund, Qualität): 11 Kriterien + X (2008–2026)

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
| kein 8-K im Rückgang (keine Nachricht) | 6331 (65% von 9789) | +0.056 | -0.127 | -0.211 (1953) | +0.443 (1859) | +0.300 (2519) | 0.000 | **kein beständiger Effekt** |
| Quartalszahlen im Rückgang (8-K 2.02) | 3458 (35% von 9789) | -0.127 | +0.056 | +0.211 (1087) | -0.443 (949) | -0.300 (1422) | 0.000 | **kein beständiger Effekt** |
| andere Meldung im Rückgang | 0 (0% von 9789) | – | -0.008 | – (0) | – (0) | – (0) | – | **kein beständiger Effekt** |
| profitabel (12 Monate) | 6288 (84% von 7466) | +0.016 | +0.034 | -0.251 (1497) | +0.066 (1944) | +0.019 (2847) | 0.815 | **kein beständiger Effekt** |
| Bruttogewinn/Bilanzsumme ≥ 0,20 | 3540 (69% von 5134) | +0.115 | -0.007 | +0.095 (794) | +0.123 (1197) | +0.117 (1549) | 0.168 | **kein beständiger Effekt** |
| Gewinn über Vorjahresquartal | 4379 (59% von 7456) | +0.051 | -0.027 | +0.107 (983) | +0.137 (1432) | +0.013 (1964) | 0.238 | **kein beständiger Effekt** |
| Eigenkapitalquote ≥ 40 % | 3757 (49% von 7597) | +0.025 | +0.042 | +0.036 (1000) | +0.123 (1191) | -0.155 (1566) | 0.815 | **kein beständiger Effekt** |
| kein 8-K im Rückgang (keine Nachricht) UND profitabel (12 Monate) | 3677 (49% von 7466) | +0.159 | -0.117 | -0.089 (829) | +0.481 (1182) | +0.313 (1666) | 0.000 | **kein beständiger Effekt** |
| Quartalszahlen im Rückgang (8-K 2.02) UND Gewinn unter Vorjahresquartal | 1340 (18% von 7456) | -0.187 | +0.064 | -0.005 (326) | -0.394 (392) | -0.278 (622) | 0.000 | **kein beständiger Effekt** |
| profitabel (12 Monate) UND ≥ 40 % unter 52-Wochen-Hoch | 345 (5% von 7466) | +0.142 | +0.012 | +0.742 (43) | -0.372 (99) | +0.260 (203) | 0.596 | **kein beständiger Effekt** |

## Ergebnis

**Keine Kombination bringt beständig und nach Mehrfachtest-Korrektur mehr** – B60 bleibt unverändert.

Gemeinsamer q-Wert über Teil 1 + 2: kein 8-K im Rückgang (keine Nachricht) 0.000, Quartalszahlen im Rückgang (8-K 2.02) 0.000, profitabel (12 Monate) 0.815, Bruttogewinn/Bilanzsumme ≥ 0,20 0.196, Gewinn über Vorjahresquartal 0.278, Eigenkapitalquote ≥ 40 % 0.815, kein 8-K im Rückgang (keine Nachricht) UND profitabel (12 Monate) 0.000, Quartalszahlen im Rückgang (8-K 2.02) UND Gewinn unter Vorjahresquartal 0.000, profitabel (12 Monate) UND ≥ 40 % unter 52-Wochen-Hoch 0.632
