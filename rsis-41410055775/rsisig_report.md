# RSI-Signallinie: Impuls, Rücksetzer, Divergenz – Ergebnis

Vorab festgelegt 02.11.2026 (research/reversal/rsisig.py). Hauptmaß: Ø Ertrag 10 Handelstage ab Kauf zur Eröffnung,
verglichen mit einem zufälligen Kauf NACH einem Abverkauf (K-ABV). Benjamini-Hochberg über alle Prüfungen.

## main · train (2887 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 1629 | +0.33 % | +0.67 % | +1.29 % | 56 % | +0.47 % | -0.11 Pkt. | 0.6482 |
| R2 | 4521 | -0.14 % | +0.29 % | +1.03 % | 56 % | +0.09 % | -0.50 Pkt. | 0.9635 |
| R3 | 1252 | +0.35 % | +0.67 % | +1.51 % | 56 % | +0.46 % | -0.12 Pkt. | 0.6827 |
| R1+TREND | 1629 | +0.33 % | +0.67 % | +1.29 % | 56 % | +0.47 % | -0.11 Pkt. | 0.6482 |
| R1+VOL | 579 | +0.44 % | +0.66 % | +1.30 % | 58 % | +0.46 % | -0.13 Pkt. | 0.6012 |
| R1+BREIT | 1275 | +0.24 % | +0.60 % | +1.47 % | 55 % | +0.40 % | -0.19 Pkt. | 0.7021 |
| R3+TREND | 1252 | +0.35 % | +0.67 % | +1.51 % | 56 % | +0.46 % | -0.12 Pkt. | 0.6827 |
| R3+VOL | 375 | +0.53 % | +0.89 % | +1.29 % | 60 % | +0.68 % | +0.10 Pkt. | 0.3948 |
| R3+BREIT | 1053 | +0.28 % | +0.70 % | +1.67 % | 56 % | +0.50 % | -0.09 Pkt. | 0.6277 |
| A5 | 159510 | +0.47 % | +0.68 % | +857291.09 % | 56 % | +0.48 % | -0.11 Pkt. | 0.7211 |
| K-ABV | 4835 | +0.27 % | +0.79 % | +1.32 % | 59 % | +0.59 % | – | – |
| K | 5016 | +0.17 % | +0.38 % | +0.86 % | 54 % | +0.18 % | -0.41 Pkt. | 0.988 |

## main · val (2887 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 1480 | -0.18 % | +0.44 % | +0.55 % | 54 % | +0.24 % | +0.37 Pkt. | 0.1649 |
| R2 | 3984 | -0.34 % | -0.73 % | +0.12 % | 48 % | -0.93 % | -0.80 Pkt. | 0.927 |
| R3 | 1293 | +0.24 % | +0.67 % | +0.87 % | 55 % | +0.47 % | +0.60 Pkt. | 0.06 |
| R1+TREND | 1480 | -0.18 % | +0.44 % | +0.55 % | 54 % | +0.24 % | +0.37 Pkt. | 0.1649 |
| R1+VOL | 494 | -0.35 % | -0.01 % | +0.84 % | 50 % | -0.21 % | -0.08 Pkt. | 0.6017 |
| R1+BREIT | 1235 | -0.13 % | +0.39 % | +0.53 % | 53 % | +0.19 % | +0.32 Pkt. | 0.2529 |
| R3+TREND | 1293 | +0.24 % | +0.67 % | +0.87 % | 55 % | +0.47 % | +0.60 Pkt. | 0.06 |
| R3+VOL | 360 | -0.60 % | +0.02 % | +0.22 % | 50 % | -0.18 % | -0.05 Pkt. | 0.5527 |
| R3+BREIT | 1057 | +0.46 % | +0.91 % | +1.20 % | 55 % | +0.70 % | +0.84 Pkt. | 0.07 |
| A5 | 125973 | +0.32 % | +0.55 % | +0.97 % | 56 % | +0.35 % | +0.48 Pkt. | 0.1474 |
| K-ABV | 4181 | +0.12 % | +0.07 % | +0.19 % | 54 % | -0.13 % | – | – |
| K | 4070 | +0.23 % | +0.44 % | +0.90 % | 55 % | +0.24 % | +0.37 Pkt. | 0.1919 |

## main · hold (2887 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 1378 | +0.45 % | +0.88 % | +1.29 % | 56 % | +0.68 % | +0.12 Pkt. | 0.3493 |
| R2 | 3984 | +0.55 % | +1.20 % | +1.59 % | 57 % | +1.00 % | +0.44 Pkt. | 0.0885 |
| R3 | 1050 | +0.33 % | +1.07 % | +2.40 % | 57 % | +0.87 % | +0.31 Pkt. | 0.2074 |
| R1+TREND | 1378 | +0.45 % | +0.88 % | +1.29 % | 56 % | +0.68 % | +0.12 Pkt. | 0.3493 |
| R1+VOL | 484 | +0.41 % | +1.01 % | +1.59 % | 56 % | +0.80 % | +0.24 Pkt. | 0.2674 |
| R1+BREIT | 1050 | +0.59 % | +0.82 % | +0.88 % | 57 % | +0.62 % | +0.06 Pkt. | 0.4428 |
| R3+TREND | 1050 | +0.33 % | +1.07 % | +2.40 % | 57 % | +0.87 % | +0.31 Pkt. | 0.2074 |
| R3+VOL | 361 | +0.09 % | +0.80 % | +1.75 % | 55 % | +0.60 % | +0.04 Pkt. | 0.4673 |
| R3+BREIT | 773 | +0.20 % | +0.53 % | +1.34 % | 54 % | +0.33 % | -0.23 Pkt. | 0.6652 |
| A5 | 143996 | +0.33 % | +0.58 % | +1.26 % | 53 % | +0.38 % | -0.18 Pkt. | 0.7051 |
| K-ABV | 4392 | +0.52 % | +0.76 % | +1.62 % | 55 % | +0.56 % | – | – |
| K | 4233 | +0.20 % | +0.34 % | +0.85 % | 52 % | +0.14 % | -0.42 Pkt. | 0.8706 |

Depot main (5 Plätze, 10 Tage, 0,10 % je Seite): R1 +1.5 % p. a. (Rückgang -37 %) · R2 -5.5 % p. a. (Rückgang -77 %) · R3 +3.2 % p. a. (Rückgang -42 %) · R1+TREND +1.5 % p. a. (Rückgang -37 %) · R3+TREND +3.2 % p. a. (Rückgang -42 %) · A5 +11.0 % p. a. (Rückgang -62 %) · K-ABV +0.2 % p. a. (Rückgang -47 %)

## pre · all (1727 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 1167 | +0.25 % | +0.46 % | +1.42 % | 54 % | +0.26 % | +0.03 Pkt. | 0.5072 |
| R2 | 3189 | +0.09 % | +0.30 % | +0.85 % | 52 % | +0.10 % | -0.13 Pkt. | 0.6032 |
| R3 | 923 | +0.39 % | +1.06 % | +1.72 % | 57 % | +0.86 % | +0.63 Pkt. | 0.01 |
| R1+TREND | 1167 | +0.25 % | +0.46 % | +1.42 % | 54 % | +0.26 % | +0.03 Pkt. | 0.5072 |
| R1+VOL | 467 | +0.13 % | +0.46 % | +1.33 % | 56 % | +0.26 % | +0.03 Pkt. | 0.5262 |
| R1+BREIT | 986 | +0.16 % | +0.26 % | +1.07 % | 53 % | +0.06 % | -0.17 Pkt. | 0.6617 |
| R3+TREND | 923 | +0.39 % | +1.06 % | +1.72 % | 57 % | +0.86 % | +0.63 Pkt. | 0.01 |
| R3+VOL | 268 | +0.89 % | +1.89 % | +2.64 % | 61 % | +1.69 % | +1.46 Pkt. | 0.0005 |
| R3+BREIT | 808 | +0.33 % | +0.85 % | +1.57 % | 56 % | +0.65 % | +0.41 Pkt. | 0.095 |
| A5 | 104585 | +0.60 % | +0.98 % | +1.54 % | 57 % | +0.78 % | +0.55 Pkt. | 0.0285 |
| K-ABV | 3436 | +0.18 % | +0.43 % | +1.24 % | 55 % | +0.23 % | – | – |
| K | 3412 | +0.29 % | +0.59 % | +1.21 % | 56 % | +0.39 % | +0.16 Pkt. | 0.3053 |

Depot pre (5 Plätze, 10 Tage, 0,10 % je Seite): R1 +1.8 % p. a. (Rückgang -29 %) · R2 +1.6 % p. a. (Rückgang -36 %) · R3 +7.3 % p. a. (Rückgang -28 %) · R1+TREND +1.8 % p. a. (Rückgang -29 %) · R3+TREND +7.3 % p. a. (Rückgang -28 %) · A5 +34.8 % p. a. (Rückgang -33 %) · K-ABV -1.8 % p. a. (Rückgang -52 %)

## asia · all (2756 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 3356 | +0.65 % | +1.19 % | +1.43 % | 55 % | +0.99 % | +0.42 Pkt. | 0.0505 |
| R2 | 8754 | +0.14 % | +0.78 % | +1.62 % | 52 % | +0.57 % | +0.01 Pkt. | 0.4708 |
| R3 | 2161 | +0.59 % | +0.91 % | +1.42 % | 53 % | +0.71 % | +0.14 Pkt. | 0.3273 |
| R1+TREND | 3356 | +0.65 % | +1.19 % | +1.43 % | 55 % | +0.99 % | +0.42 Pkt. | 0.0505 |
| R1+VOL | 1099 | +0.63 % | +0.93 % | +0.91 % | 53 % | +0.73 % | +0.16 Pkt. | 0.2859 |
| R1+BREIT | 2331 | +0.61 % | +0.95 % | +1.18 % | 53 % | +0.75 % | +0.18 Pkt. | 0.3043 |
| R3+TREND | 2161 | +0.59 % | +0.91 % | +1.42 % | 53 % | +0.71 % | +0.14 Pkt. | 0.3273 |
| R3+VOL | 600 | +0.42 % | +0.52 % | +1.51 % | 50 % | +0.32 % | -0.25 Pkt. | 0.7636 |
| R3+BREIT | 1617 | +0.50 % | +0.85 % | +1.38 % | 52 % | +0.65 % | +0.08 Pkt. | 0.4048 |
| A5 | 335304 | +0.54 % | +0.83 % | +5926.66 % | 52 % | +0.63 % | +0.06 Pkt. | 0.3913 |
| K-ABV | 10094 | +0.28 % | +0.77 % | +1.44 % | 52 % | +0.57 % | – | – |
| K | 9850 | +0.28 % | +0.62 % | +1.43 % | 51 % | +0.42 % | -0.15 Pkt. | 0.7646 |

Depot asia (5 Plätze, 10 Tage, 0,10 % je Seite): R1 -1.0 % p. a. (Rückgang -58 %) · R2 -6.0 % p. a. (Rückgang -77 %) · R3 +5.7 % p. a. (Rückgang -39 %) · R1+TREND -1.0 % p. a. (Rückgang -58 %) · R3+TREND +5.7 % p. a. (Rückgang -39 %) · A5 +8.1 % p. a. (Rückgang -53 %) · K-ABV +2.6 % p. a. (Rückgang -62 %)

## Entscheidung (vorab festgelegt)

- **R1**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.11, Validierung 17–21 +0.37, Holdout 22–26 +0.12, Vorzeit 99–07 +0.03, Asien 08–26 +0.42)
- **R2**: nicht bestanden – besser als K-ABV in 2/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.50, Validierung 17–21 -0.80, Holdout 22–26 +0.44, Vorzeit 99–07 -0.13, Asien 08–26 +0.01)
- **R3**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.12, Validierung 17–21 +0.60, Holdout 22–26 +0.31, Vorzeit 99–07 +0.63, Asien 08–26 +0.14)
- **R1+TREND**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.11, Validierung 17–21 +0.37, Holdout 22–26 +0.12, Vorzeit 99–07 +0.03, Asien 08–26 +0.42)
- **R1+VOL**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.13, Validierung 17–21 -0.08, Holdout 22–26 +0.24, Vorzeit 99–07 +0.03, Asien 08–26 +0.16)
- **R1+BREIT**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.19, Validierung 17–21 +0.32, Holdout 22–26 +0.06, Vorzeit 99–07 -0.17, Asien 08–26 +0.18)
- **R3+TREND**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.12, Validierung 17–21 +0.60, Holdout 22–26 +0.31, Vorzeit 99–07 +0.63, Asien 08–26 +0.14)
- **R3+VOL**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 1 (Train 08–16 +0.10, Validierung 17–21 -0.05, Holdout 22–26 +0.04, Vorzeit 99–07 +1.46, Asien 08–26 -0.25)
- **R3+BREIT**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.09, Validierung 17–21 +0.84, Holdout 22–26 -0.23, Vorzeit 99–07 +0.41, Asien 08–26 +0.08)
- **A5**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.11, Validierung 17–21 +0.48, Holdout 22–26 -0.18, Vorzeit 99–07 +0.55, Asien 08–26 +0.06)
