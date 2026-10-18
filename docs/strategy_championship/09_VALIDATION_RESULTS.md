# 09 — Ergebnis Gate C: Validierung 2017–2021 (einmalig)

**Status: VALIDIERT nach vorab festgelegten Regeln (08) · DATENBESCHRÄNKT (Survivorship, Gratisdaten).**
Lauf `research_v.yml` #39133923449 (Commit `5b6473d`), Release `research-v-39133923449`, Rohzahlen `v_results_validation.json`,
Register jetzt mit Validierungseinträgen (V-…). Holdout 2022–2026 weiterhin versiegelt. Bilanzprüfungen in allen Läufen bestanden.
Gegenrechnung S01 (Engine vs. Altsimulator) im Validierungszeitraum: 97,4 % der Signale / 91,3 % der Trades identisch
(gleiches Abweichungsbild wie in Train).

## 1. Ergebnis nach den Bestehensregeln

Bezug: #1–#6 5.000 €, #7–#8 20.000 €; Stop-Strategien 1 % Risiko. Vergleich S13-ETF: Sharpe 0,58. ACWI Halten: +11,9 %, DD −30,8 %, Sharpe 0,71.

| Finalist | CAGR | Stress | Max. DD | Sharpe | p vs. Zufall | Regel 1 | Regel 2 | Regel 3 | **Urteil** |
|---|---|---|---|---|---|---|---|---|---|
| **S07-B** Momentum 6-1 / Vol, Top 10 | +27,9 % | +20,9 % | −46,6 % | 0,89 | 0,000 | ✓ | ✓ | ✓ | **BESTANDEN** |
| **S16-B** Dual Momentum SPY/EFA/QQQ | +20,2 % | +19,3 % | −30,3 % | 0,93 | 0,025 | ✓ | ✓ | ✓ | **BESTANDEN** |
| **S05-B** Momentum 6-1, Top 10 | +52,4 % | +46,4 % | −55,5 % | 1,00 | 0,000 | ✓ | ✓ | ✓ | **BESTANDEN (formal) — ausreißergetrieben** |
| S08-A Ausbruch 55 T. (20 k€) | +13,9 % | +7,1 % | −32,2 % | 0,74 | 0,220 | ✓ | ✗ | ✓ | NICHT BESTANDEN |
| S16-A Dual Momentum SPY/EFA | +8,0 % | +7,1 % | −31,8 % | 0,52 | 0,385 | ✓ | ✗ | ✗ | NICHT BESTANDEN |
| S13-ETF ACWI > SMA 10 | +6,7 % | +6,2 % | −17,5 % | 0,58 | — | ✓ | — | ✗ (Sharpe < ACWI) | NICHT BESTANDEN (bleibt Kern-Referenz) |
| S01-B Kairo, EMA20-Ausstieg | −3,9 % | −16,8 % | −26,0 % | −0,16 | 0,850 | ✗ | ✗ | ✗ | NICHT BESTANDEN |
| S02-B Trend-Pullback (20 k€) | +2,7 % | −12,6 % | −51,4 % | 0,23 | 0,665 | ✗ | ✗ | ✗ | NICHT BESTANDEN |

Bonferroni (0,05/8 ≈ 0,006) erfüllen nur S07-B und S05-B.

## 2. Robustheit (zusätzlich, nicht Teil der Bestehensregeln)

| | Netto-PnL 5 k€ | ohne beste 1 % Trades | ohne beste 5 Trades | Haupttreiber |
|---|---|---|---|---|
| S07-B | +11.730 € | **+3.308 €** | **+1.906 €** | breit (RIOT, CHRD, CLSK, GME, SINCH, ENPH, NIO …) |
| S05-B | +35.558 € | −4.409 € | **−9.096 €** | GME (×13,6, +20.111 €), MARA (×12,2, +13.587 €) |
| S16-B | +7.233 € | — (10 Trades) | ≈ 0 € | ein QQQ-Trade 11/2019–09/2021 (+5.072 €) |
| S08-A (20 k€) | +16.175 € | +6.496 € | +2.746 € | breit |

## 3. Lesart

1. **S07-B ist der klarste Kandidat:** besteht alle Regeln, schlägt Zufall deutlich (auch nach Bonferroni), bleibt ohne die
   größten Gewinner positiv und unter Kostenstress zweistellig. **Aber:** Max. Drawdown −47 % (2020) — als Alleinanlage für
   kleines Kapital zu riskant; nur als begrenzter Satellit denkbar.
2. **S16-B** hat das beste Rendite/Risiko-Verhältnis, hängt aber an sehr wenigen Wechseln und am Technologie-Boom (QQQ) —
   genau der in 07 benannte Rückschaufehler. Die Kontrolle S16-A (ohne QQQ) besteht **nicht**. → als Kern nur mit Vorbehalt.
3. **S05-B besteht formal, ist aber nicht robust:** der Gewinn kommt aus zwei Spekulationswellen 2020/21 (Meme-Aktien, Krypto-
   Miner). Ohne Volatilitätsbereinigung landet die Strategie zwangsläufig in solchen Titeln. S07-B ist dieselbe Idee mit
   Vol-Bereinigung und deutlich breiter verteilt → S07-B ersetzt S05-B.
4. **Kairo (S01-B) besteht nicht** — wie schon im Train: kein Vorteil gegenüber Zufall, nach Kosten negativ.
5. **Hybride Mean Reversion (S02-B) und Einzelaktien-Trendfolge (S08-A) bestehen nicht.** S08-A war mit 20 k€ positiv
   (+13,9 %), aber nicht besser als zufällige Aktien mit denselben Regeln (p = 0,22).
6. **Der einfache ETF-Trendfilter (S13-ETF)** hatte 2017–2021 (Bullenmarkt) weniger Rendite als ACWI-Halten, aber den
   kleinsten Drawdown aller Varianten (−17,5 %).

## 4. Konsequenz für Phase D

Weiter mit: **S07-B** (Satellit), **S16-B** (Kern-Kandidat, mit Vorbehalt), **S13-ETF** und **ACWI** (Kern-Referenzen).
S05-B nur als Kontrolle. Phase D (nur Train + Validierung): Kern/Satellit-Mischungen, Positions- und Drawdown-Begrenzung,
Kosten bei 1–20 k€; Turbo-/Hebel-Szenarien nur als Modell. Der Holdout entscheidet danach **einmal**.
