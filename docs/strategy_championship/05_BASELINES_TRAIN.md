# 05 — Baselines im Entwicklungszeitraum (Train 2008–2016)

**Status: EXPLORATIV · DATENBESCHRÄNKT** (Survivorship, split-bereinigte Kurse, keine historische Marktkapitalisierung — siehe 03 §4).
Lauf `research_b2.yml` #39120774730, Commit `b22fceb`, Datensatz v1 (prices SHA-256 `e405016e…`). Validierung (2017–2021)
und Holdout (2022–2026) wurden **nicht** geladen. Alle Läufe stehen im Register `04_EXPERIMENT_LOG.jsonl` (B2-001 … B2-024),
Rohzahlen in `b2_results_train.json`.

Grundlage: 2.266 Titel mit Kursen im Zeitraum, **16.154 S01-Signale** (11/11, unveränderter Scanner), davon ≈ 4.250 mit
Basis-Einstieg. Kosten Basisfall: 0,99 €/Order, Spread 0,10 % US / 0,15 % EU / 0,30 % bei < 20 Mio. USD Tagesumsatz.
Stress: 1,99 €, Spread ×2, +0,05 % Slippage, +0,1 % FX.

## 1. Depot-Ergebnisse (netto, EUR, 2008-01-02 – 2016-12-30)

| Strategie | Kapital | Risiko | CAGR | 90 %-Band CAGR | Max. DD | Sharpe | Trades | Endwert |
|---|---|---|---|---|---|---|---|---|
| **S01-A** (Tag 20) | 5.000 € | 1,0 % | **+5,0 %** | −3,5 … +15,2 % | −29,0 % | 0,35 | 827 | 7.739 € |
| S01-A | 5.000 € | 0,5 % | +0,6 % | −6,2 … +7,5 % | −21,2 % | 0,11 | 889 | 5.260 € |
| S01-A | 20.000 € | 1,0 % | +2,9 % | −4,8 … +11,8 % | −31,2 % | 0,24 | 1.102 | 25.788 € |
| S01-A | 20.000 € | 0,5 % | +3,3 % | −4,3 … +11,0 % | −21,9 % | 0,29 | 1.384 | 26.791 € |
| S01-A | 1.000 € | 1,0 % | −49,6 % | | −99,8 % | −2,26 | 550 | 2 € |
| S01-A · Kostenstress | 5.000 € | 1,0 % | −13,1 % | −20,5 … −4,5 % | −72,8 % | −0,68 | 824 | 1.416 € |
| **S01-B** (EMA20 ab Tag 10) | 5.000 € | 1,0 % | +3,7 % | −5,2 … +13,2 % | −34,4 % | 0,29 | 825 | 6.956 € |
| S01-B | 5.000 € | 0,5 % | +3,6 % | −3,7 … +11,4 % | −27,4 % | 0,32 | 865 | 6.886 € |
| S01-B | 20.000 € | 1,0 % | +7,0 % | −2,2 … +16,8 % | −28,1 % | 0,46 | 1.087 | 36.780 € |
| S01-B | 20.000 € | 0,5 % | +5,0 % | −3,3 … +14,0 % | −23,9 % | 0,39 | 1.364 | 30.908 € |
| S01-B | 1.000 € | 1,0 % | −47,7 % | | −99,7 % | −2,29 | 557 | 3 € |
| S01-B · Kostenstress | 5.000 € | 1,0 % | −13,7 % | −21,7 … −5,1 % | −75,1 % | −0,73 | 799 | 1.329 € |
| **S13-ETF** (ACWI > SMA 10 Mon.) | 5.000 € | — | **+9,6 %** | +4,4 … +14,8 % | **−22,0 %** | **0,71** | 4 | 11.398 € |
| **ACWI Kaufen & Halten** | 5.000 € | — | +7,8 % | +0,2 … +16,0 % | −45,8 % | 0,44 | 1 | 9.848 € |

(1.000 €/20.000 € bei S13/ACWI praktisch gleich: 9,5–9,6 % bzw. 7,8 %.)

## 2. Kairo gegen Zufall (Null-Strategie, 200 Seeds, 5.000 €)

Gleiche Anzahl Signale je Tag, zufällige handelbare Aktien desselben Tages, **identische** Einstiegs-/Ausstiegsregeln und Kosten.

| Risiko | S01-A CAGR | Zufall Median | Zufall 5–95 % | Anteil Zufall ≥ S01-A (p) |
|---|---|---|---|---|
| 1,0 % | +5,0 % | +0,6 % | −7,1 … +7,9 % | **0,155** |
| 0,5 % | +0,6 % | +0,4 % | −5,2 … +5,6 % | **0,465** |

## 3. Trade-Qualität (5.000 €, nur volle Positionen)

| | Trades voll | Ø R netto | Ø R vor Kosten | Trefferquote |
|---|---|---|---|---|
| S01-A 1 % | 518 | +0,07 | +0,18 | 32 % |
| S01-A 0,5 % | 833 | −0,01 | +0,15 | 31 % |
| S01-B 1 % | 489 | +0,05 | +0,16 | 34 % |
| S01-B 0,5 % | 809 | +0,06 | +0,22 | 33 % |

Ausgewiesen nur Positionen mit Risiko ≥ 50 % des geplanten (Grund: Rest-Positionen, siehe 03 §6).

## 4. Lesart (vorläufig, nur Train)

1. **Kein belastbarer Vorteil von S01 (1D) gegen Zufall.** Bei 1 % Risiko schneiden 15,5 % der Zufalls-Depots mindestens
   so gut ab, bei 0,5 % fast die Hälfte. Das bisherige Kairo-Plus kommt in diesem Zeitraum überwiegend aus den
   Einstiegs-/Ausstiegsregeln und der Marktphase, nicht aus der Aktienauswahl.
2. **Kosten sind entscheidend.** Vor Kosten ≈ +0,15 … +0,22 R je Trade, nach Kosten ≈ 0. Mit Stress-Kosten verliert jede
   S01-Variante deutlich (−13 … −14 % p. a.).
3. **1.000 € sind mit fester Ordergebühr nicht tragfähig** (−48 … −50 % p. a. bis zum Totalverlust): 10 € Risiko je Trade
   gegen ≈ 2 € Gebühren. Gilt für jede Swing-Strategie mit vielen Trades.
4. **Der einfache ETF-Trendfilter S13 ist die stärkste Baseline:** +9,6 % p. a. bei −22 % Max. DD — besser als ACWI-Halten
   (+7,8 %, −46 % DD) und besser als jede S01-Variante, risikoadjustiert deutlich.
5. Die 4H-Bestätigung ist hier **NICHT GETESTET** (keine historischen 4H-Daten); sie kann nur vorwärts geprüft werden.
6. Alle Aussagen gelten nur für 2008–2016 und sind wegen Survivorship eher zu optimistisch (für S01 **und** Zufall).
