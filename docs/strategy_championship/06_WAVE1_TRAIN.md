# 06 — Zwischenbericht Welle 1 (Train 2008–2016, Protokoll v1.1)

**Status: EXPLORATIV · DATENBESCHRÄNKT · NUR ENTWICKLUNGSZEITRAUM.** Lauf `research_c1.yml` #39126419341 (Commit `d071297`),
Datensatz v1. Validierung und Holdout nicht geladen. 92 neue Registereinträge (`04_EXPERIMENT_LOG.jsonl`, C1-…),
Rohzahlen `c1_results_train.json`. Bilanzprüfungen in allen Läufen bestanden; einzige Ausnahme: ein Stresslauf (S11-A,
Totalverlust), in dem der Verkauf einer Rest-Position weniger einbrachte als die Gebühr (Cash −0,74 €).

## 1. Übersicht (5.000 €, 1 % Risiko bzw. Gewicht; netto)

| Variante | CAGR | Max. DD | Sharpe | Kostenstress | p vs. Zufall | ohne Top 1 % Trades | positive Jahre |
|---|---|---|---|---|---|---|---|
| **S13-ETF** (Baseline) | **+9,6 %** | **−22 %** | **0,71** | — | — | — | — |
| ACWI Halten (Baseline) | +7,8 % | −46 % | 0,44 | — | — | — | — |
| **S05-B** Momentum 6-1 Top 10 | **+19,7 %** | −53 % | 0,67 | **+13,2 %** | **0,010** | **+14.235 €** | 5/9 |
| S05-A Momentum 12-1 Top 10 | +10,3 % | −67 % | 0,44 | +4,7 % | 0,180 | −992 € | 6/9 |
| S02-B Trend-Pullback ohne Momentum | +10,7 % | −43 % | 0,41 | −5,8 % | 0,010 | −3.373 € | 5/9 |
| S01-B Kairo, EMA20-Ausstieg | +6,6 % | −37 % | 0,43 | −9,2 % | (S01-A: 0,175) | −478 € | 7/9 |
| S01-A Kairo, Tag 20 | +4,8 % | −28 % | 0,34 | −12,1 % | 0,175 | −1.101 € | 7/9 |
| S08-B Ausbruch 20 T. | +1,7 % | −42 % | 0,18 | −4,1 % | 0,775 | −2.001 € | 6/9 |
| S02-A Trend-Pullback + Momentum | +1,2 % | −43 % | 0,16 | −15,9 % | 0,520 | −4.010 € | 5/9 |
| S13-S Aktien-Trendfolge | +0,3 % | −68 % | 0,18 | −2,2 % | 0,690 | −7.897 € (ein Trade: VIPS ×9) | 4/9 |
| S08-A Ausbruch 55 T. | −1,4 % | −46 % | 0,01 | −9,3 % | 0,915 | −2.837 € | 4/9 |
| S03-P Qualitäts-Rücksetzer (Proxy) | −3,8 % | −51 % | −0,13 | −16,0 % | 0,945 | −2.738 € | 3/9 |
| S04-M Markt-Verlierer 5 T. | −18,3 % | −84 % | −1,82 | −56 % | 0,335 | −5.374 € | 0/9 |
| S11-B RSI(2) < 5 | −26,6 % | −94 % | −2,50 | −57 % | 0,000* | −5.915 € | 1/9 |
| S11-A RSI(2) < 10 | −52,5 % | −100 % | −3,87 | −100 % | 0,060* | −5.813 € | 0/9 |

\* Zufalls-Gegenstück ebenso ruinös (−54 … −55 % p. a.): der p-Wert sagt hier nichts über Brauchbarkeit.
„p vs. Zufall“ = Anteil der 200 Zufalls-Depots mit gleichen Regeln, die mindestens dieselbe CAGR erreichen.

Mit 20.000 € (max. 10 Positionen) liegen die Werte meist etwas besser (Gebühren relativ kleiner): S05-B +21,0 %,
S02-B +14,7 %, S01-B +10,0 % (90 %-Band +0,9 … +20,4 %), S08-A +7,3 %, S04-M −4,1 %, S11-A −8,3 %.

## 2. Befunde

1. **Kurzfrist-Strategien mit vielen Trades (S04, S11) scheitern an den Kosten.** RSI(2) verdient vor Kosten ≈ +0,26 % je
   Trade, zahlt bei 5.000 € aber ≈ 1 % (fixe Gebühr auf kleine Positionen). Für Jonnys Kapital **ungeeignet**.
2. **Einzige Variante, die Zufall, Kostenstress und den Ausreißer-Test besteht: S05-B (Momentum 6-1, Top 10, monatlich).**
   Aber: Max. Drawdown −53 % (2008/09) und nur 5 von 9 positiven Jahren; risikoadjustiert (Sharpe 0,67) **nicht besser als
   S13-ETF** (0,71 bei −22 % DD).
3. **S02-B und S01 (Kairo) hängen an wenigen Gewinnern:** Ohne die besten 1 % der Trades (5–8 Stück) sind beide negativ, unter
   Kostenstress verlieren beide. S02-B schlägt Zufall (p = 0,01), S01 nicht (p = 0,175).
4. **Ausbruch (S08), Qualitäts-Rücksetzer-Proxy (S03), Aktien-Trendfolge (S13-S)** zeigen keinen Vorteil gegenüber Zufall.
5. **Mehrfachtests:** 13 Varianten in Welle 1 (+ 2 S01). Bei Bonferroni-Korrektur (0,05/13 ≈ 0,004) ist **keine** Variante
   signifikant besser als Zufall; die Auflösung mit 200 Seeds ist 0,005. S05-B und S02-B sind daher **Kandidaten, keine Belege**.
6. **Zufalls-Depots sind im Datensatz selbst profitabel** (z. B. 10 zufällige Aktien monatlich +6,1 % p. a.) — Hinweis auf den
   Survivorship-Effekt (nur heute noch gelistete Titel).
7. Nach den Auswahlregeln (§7: Max. DD ≤ 20 % [Sensitivität 30 %], positiv nach Kostenstress, schlägt Zufall **und** ACWI
   risikoadjustiert) erfüllt **keine** Aktienstrategie alle Bedingungen; nur die Baseline **S13-ETF** liegt im Rahmen.

## 3. Vorschlag für Gate C (Validierung 2017–2021, einmalige Öffnung für wenige Kandidaten)

| Kandidat | Grund |
|---|---|
| **S13-ETF** | stärkste Baseline, robust; Kern-Kandidat |
| **S05-B** | einzige Aktienstrategie, die alle Robustheitstests in Train besteht; DD-Problem → in Phase D als Satellit mit Begrenzung |
| **S01-B** (Kairo) | amtierende Strategie, Referenz; zeigt, ob der Train-Befund „kein Vorteil“ sich bestätigt |
| S02-B (optional) | schlägt Zufall, aber Ausreißer-abhängig und kostenstress-negativ → nur als „explorativ“ |

Nicht weiter: S02-A, S03-P, S04-M, S08-A/B, S11-A/B, S13-S, S05-A (schwächer als S05-B, gleiche Familie).

Alternative vor Gate C: **Welle 2** (übrige Familien laut 01, eigene Protokollversion v1.2) erst im Train screenen und
danach die Validierung **einmal gemeinsam** für alle Finalisten öffnen (weniger „Blicke“ in die Validierung).
