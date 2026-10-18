# 08 — Validierungsplan Gate C (vorab festgelegt, vor dem Öffnen der Daten 2017–2021)

**Freigabe:** Nutzer, 18.10.2026: „Gate C freigeben mit 8“. Validierung 2017-01-01 – 2021-12-31 wird **einmal** für genau diese
8 Finalisten gerechnet. Regeln unverändert aus Train (Protokoll v1.1/v1.2); danach keine Parameteränderung an diesen Varianten.
Holdout 2022–2026 bleibt versiegelt.

## Finalisten

| # | ID | Familie | Kapital-Bezug |
|---|---|---|---|
| 1 | S13-ETF | Trend (ETF) | Benchmark / Kern |
| 2 | S16-B | Dual Momentum SPY/EFA/QQQ | Kern-Alternative |
| 3 | S16-A | Dual Momentum SPY/EFA | Kontrolle zu #2 |
| 4 | S07-B | Momentum 6-1 / Vol, Top 10 | Satellit |
| 5 | S05-B | Momentum 6-1, Top 10 | Kontrolle zu #4 |
| 6 | S01-B | Kairo, EMA20-Ausstieg | Referenz |
| 7 | S02-B | Trend-Pullback (hybride Mean Reversion) | nachgereicht, Bezug 20.000 € |
| 8 | S08-A | Ausbruch 55 T. (Aktien-Trendfolge) | nachgereicht, Bezug 20.000 € |

Zusätzlich als Vergleich (kein Finalist): ACWI Kaufen & Halten.

## Rechnung

Je Finalist: 5.000 € und 20.000 €; Basis- und Stresskosten; Stop-Strategien mit 1 % und 0,5 % Risiko. Zufalls-Null mit denselben
Regeln (200 Seeds) bei 5.000 € **und** 20.000 € (Stop-Strategien mit 1 %). Indikatoren dürfen die Vorgeschichte vor 2017 nutzen;
Signale, Käufe und Bewertung nur 2017–2021. Offene Positionen werden am 31.12.2021 zum Schluss bewertet/geschlossen.

## Bestehensregeln (je Finalist, Bezugskapital: #1–#6 5.000 €, #7–#8 20.000 €; Stop-Strategien 1 % Risiko)

Ein Finalist **besteht** die Validierung nur, wenn **alle** zutreffen:

1. Netto-CAGR > 0 **und** CAGR unter Kostenstress > 0.
2. Besser als Zufall: p_cagr ≤ 0,05 gegen die eigene Null (gilt nicht für S13-ETF).
3. Risikoadjustiert mindestens so gut wie S13-ETF im selben Zeitraum: Sharpe ≥ Sharpe(S13-ETF).
   Für S13-ETF selbst: Sharpe ≥ Sharpe(ACWI Kaufen & Halten) und Max. DD kleiner als bei ACWI.

Zusatzangabe (kein Muss): Bonferroni-Schwelle 0,05/8 ≈ 0,006 für Regel 2; Max. DD ≤ 20/30 %.

Ergebnis je Finalist: **BESTANDEN / NICHT BESTANDEN**, mit Begründung. Phase D arbeitet nur mit bestandenen Finalisten
(plus S13-ETF als Kern-Referenz, auch falls er Regel 3 verfehlt).
