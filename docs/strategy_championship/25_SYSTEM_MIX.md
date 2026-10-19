# 25 – Systemtest Welt-ETF + Dual Momentum + Kairo-S (Protokoll v2.8)

Stand 19.10.2026 · Lauf `research_mix.yml` (Run 39259169699) · Daten v1, 2008–2026 · 20.000 € · PRIME+ · Rebalancing jährlich.
Ergebnis-Datei: `system_mix_result.json`. Datensatz mit Survivorship-Bias (nur heute gelistete Aktien) – betrifft Kairo-S, nicht die ETFs.

## Ergebnis (Stress-Kosten; CAGR · max. Rückgang · Sharpe)

| Mischung | Train 2008–16 | Validierung 2017–21 | Holdout 2022–26 | Gesamt |
|---|---|---|---|---|
| M0 100 % ACWI | +8,1 % · −46 % · 0,44 | +11,1 % · −28 % · 0,72 | +9,0 % · −17 % · 0,63 | +9,1 % · −46 % · 0,54 |
| **M1 70/15/15 (Haupt)** | +8,3 % · −34 % · 0,50 | +10,5 % · −25 % · 0,72 | +7,4 % · −18 % · 0,55 | +8,7 % · −34 % · 0,56 |
| M2 70/30 ACWI/DM | +10,1 % · −31 % · 0,56 | +13,8 % · −29 % · 0,81 | +9,6 % · −19 % · 0,65 | +10,9 % · −31 % · 0,64 |
| M3 70/30 ACWI/Kairo-S | +6,5 % · −38 % · 0,43 | +7,2 % · −22 % · 0,58 | +5,2 % · −17 % · 0,42 | +6,4 % · −38 % · 0,46 |
| M4 50/25/25 | +8,4 % · −26 % · 0,54 | +10,0 % · −24 % · 0,70 | +6,3 % · −18 % · 0,49 | +8,3 % · −26 % · 0,57 |

Basis-Kosten (Spread wie gemessen, 0,99 € unter 250 €): M1 gesamt +10,0 % · −34 % · Sharpe 0,63 (ACWI 0,54); M4 +10,6 % · −25 % · 0,70;
M3 +8,8 % · Sharpe 0,59. Korrelation der Tagesrenditen: ACWI–DM 0,73 · ACWI–Kairo-S 0,53 · DM–Kairo-S 0,45.

## Entscheidung (vorab festgelegt: M1 gegen M0, Stress)

- Sharpe in allen drei Abschnitten höher: **nein** (Validierung gleich, Holdout 0,55 < 0,63)
- Rückgang höchstens 2 Pp schlechter: ja (−34 % statt −46 %)
- Bootstrap p = 0,26 (> 0,05)

→ **Nicht bestanden.** Die Dreier-Mischung ist mit Stress-Kosten nicht belegbar besser als der reine Welt-ETF.

## Einordnung (beschreibend, kein Beleg)

1. **Kairo-S hängt an den Kosten:** mit Basis-Kosten verbessert es jede Mischung, mit Stress-Kosten verschlechtert es sie.
   Entscheidend sind also die *echten* Kosten (Spread/Ausführung bei Scalable) – das klären Papier-Depot und eigenes Journal.
2. **ACWI + Dual Momentum (M2)** war in allen drei Abschnitten auch mit Stress-Kosten besser (Sharpe und CAGR), bei kleinerem
   Rückgang. Das ist nur beschreibend (nicht Hauptmischung; DM allein im Holdout p 0,07) – passt aber zum bisherigen Bild:
   DM ist der stärkste Kandidat für den Trading-Teil.
3. Keine weiteren Mischungen (laut Protokoll). Entscheidung über echtes Geld: nach dem Papier-Test (12 Monate).
