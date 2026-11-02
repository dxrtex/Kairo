# RSI-Signallinie: Impuls, Rücksetzer, Divergenz – Ergebnis

Vorab festgelegt 02.11.2026 (research/reversal/rsisig.py). Hauptmaß: Ø Ertrag 10 Handelstage ab Kauf zur Eröffnung,
verglichen mit einem zufälligen Kauf NACH einem Abverkauf (K-ABV). Benjamini-Hochberg über alle Prüfungen.

## main · train (2887 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 9027 | +0.36 % | +0.52 % | +0.82 % | 55 % | +0.32 % | -0.02 Pkt. | 0.5012 |
| R2 | 27193 | -0.05 % | +0.03 % | +0.49 % | 53 % | -0.17 % | -0.51 Pkt. | 0.8311 |
| R3 | 10794 | +0.25 % | +0.80 % | +1.60 % | 56 % | +0.60 % | +0.26 Pkt. | 0.2324 |
| R1+TREND | 1629 | +0.33 % | +0.67 % | +1.29 % | 56 % | +0.47 % | +0.13 Pkt. | 0.4053 |
| R1+UNTER | 7296 | +0.38 % | +0.52 % | +0.73 % | 55 % | +0.32 % | -0.03 Pkt. | 0.5197 |
| R1+VOL | 3171 | +0.42 % | +0.47 % | +0.93 % | 56 % | +0.27 % | -0.07 Pkt. | 0.5712 |
| R1+BREIT | 4628 | +0.39 % | +0.69 % | +1.24 % | 56 % | +0.49 % | +0.15 Pkt. | 0.3968 |
| R3+TREND | 1252 | +0.35 % | +0.67 % | +1.51 % | 56 % | +0.46 % | +0.12 Pkt. | 0.3983 |
| R3+UNTER | 9423 | +0.24 % | +0.82 % | +1.60 % | 56 % | +0.62 % | +0.28 Pkt. | 0.2384 |
| R3+VOL | 2879 | +0.17 % | +0.88 % | +1.56 % | 57 % | +0.68 % | +0.34 Pkt. | 0.2204 |
| R3+BREIT | 5101 | +0.18 % | +0.46 % | +1.24 % | 55 % | +0.26 % | -0.08 Pkt. | 0.5787 |
| A5 | 159510 | +0.47 % | +0.68 % | +1.31 % | 56 % | +0.48 % | +0.14 Pkt. | 0.3953 |
| K-ABV | 26846 | +0.27 % | +0.54 % | +1.06 % | 55 % | +0.34 % | – | – |
| K | 27084 | +0.15 % | +0.39 % | +0.81 % | 54 % | +0.19 % | -0.15 Pkt. | 0.7121 |

## main · val (2887 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 6380 | +0.72 % | +1.07 % | +1.70 % | 57 % | +0.87 % | +0.35 Pkt. | 0.084 |
| R2 | 20250 | +0.55 % | +0.89 % | +2.50 % | 56 % | +0.69 % | +0.17 Pkt. | 0.3433 |
| R3 | 6695 | +0.43 % | +0.79 % | +1.38 % | 56 % | +0.59 % | +0.07 Pkt. | 0.4313 |
| R1+TREND | 1480 | -0.18 % | +0.44 % | +0.55 % | 54 % | +0.24 % | -0.28 Pkt. | 0.8041 |
| R1+UNTER | 4786 | +1.00 % | +1.21 % | +1.99 % | 58 % | +1.00 % | +0.49 Pkt. | 0.043 |
| R1+VOL | 1972 | +0.24 % | +0.44 % | +1.13 % | 54 % | +0.24 % | -0.28 Pkt. | 0.7806 |
| R1+BREIT | 4557 | +0.14 % | +0.64 % | +0.64 % | 54 % | +0.43 % | -0.08 Pkt. | 0.5827 |
| R3+TREND | 1293 | +0.24 % | +0.67 % | +0.87 % | 55 % | +0.47 % | -0.05 Pkt. | 0.5162 |
| R3+UNTER | 5300 | +0.48 % | +0.86 % | +1.55 % | 56 % | +0.66 % | +0.14 Pkt. | 0.3868 |
| R3+VOL | 1870 | -0.03 % | +0.16 % | +0.86 % | 52 % | -0.04 % | -0.56 Pkt. | 0.922 |
| R3+BREIT | 4883 | +0.35 % | +0.83 % | +1.07 % | 56 % | +0.63 % | +0.11 Pkt. | 0.4023 |
| A5 | 125973 | +0.32 % | +0.55 % | +0.96 % | 56 % | +0.35 % | -0.17 Pkt. | 0.6682 |
| K-ABV | 20198 | +0.33 % | +0.72 % | +1.72 % | 57 % | +0.52 % | – | – |
| K | 21196 | +0.27 % | +0.57 % | +1.29 % | 55 % | +0.37 % | -0.15 Pkt. | 0.6452 |

## main · hold (2887 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 8706 | +0.50 % | +1.36 % | +2.53 % | 58 % | +1.16 % | +0.40 Pkt. | 0.01 |
| R2 | 25104 | +0.25 % | +1.07 % | +1.89 % | 56 % | +0.87 % | +0.11 Pkt. | 0.3268 |
| R3 | 9819 | +0.40 % | +1.15 % | +2.58 % | 56 % | +0.95 % | +0.19 Pkt. | 0.2589 |
| R1+TREND | 1378 | +0.45 % | +0.88 % | +1.29 % | 56 % | +0.68 % | -0.08 Pkt. | 0.5697 |
| R1+UNTER | 7236 | +0.48 % | +1.40 % | +2.76 % | 58 % | +1.20 % | +0.44 Pkt. | 0.005 |
| R1+VOL | 3017 | +0.38 % | +1.49 % | +2.94 % | 58 % | +1.29 % | +0.53 Pkt. | 0.016 |
| R1+BREIT | 5184 | +0.49 % | +0.73 % | +1.01 % | 54 % | +0.53 % | -0.23 Pkt. | 0.7151 |
| R3+TREND | 1050 | +0.33 % | +1.07 % | +2.40 % | 57 % | +0.87 % | +0.11 Pkt. | 0.3933 |
| R3+UNTER | 8677 | +0.39 % | +1.13 % | +2.58 % | 56 % | +0.93 % | +0.17 Pkt. | 0.2874 |
| R3+VOL | 2935 | +0.07 % | +0.93 % | +2.29 % | 55 % | +0.73 % | -0.03 Pkt. | 0.5607 |
| R3+BREIT | 5681 | +0.07 % | +0.32 % | +1.31 % | 51 % | +0.12 % | -0.64 Pkt. | 0.926 |
| A5 | 143996 | +0.33 % | +0.58 % | +1.26 % | 53 % | +0.38 % | -0.38 Pkt. | 0.8576 |
| K-ABV | 25130 | +0.53 % | +0.96 % | +1.94 % | 55 % | +0.76 % | – | – |
| K | 24169 | +0.30 % | +0.62 % | +1.20 % | 53 % | +0.42 % | -0.34 Pkt. | 0.9065 |

Depot main (5 Plätze, 10 Tage, 0,10 % je Seite): R1 +2.1 % p. a. (Rückgang -69 %) · R2 +5.5 % p. a. (Rückgang -74 %) · R3 +4.6 % p. a. (Rückgang -67 %) · R1+TREND +1.5 % p. a. (Rückgang -37 %) · R3+TREND +3.2 % p. a. (Rückgang -42 %) · A5 +11.0 % p. a. (Rückgang -62 %) · K-ABV +5.9 % p. a. (Rückgang -74 %)

## pre · all (1727 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 5307 | +0.56 % | +1.18 % | +1.76 % | 56 % | +0.98 % | +0.36 Pkt. | 0.036 |
| R2 | 15621 | +0.38 % | +0.82 % | +1.69 % | 54 % | +0.62 % | +0.01 Pkt. | 0.5212 |
| R3 | 5770 | +0.52 % | +1.12 % | +1.75 % | 57 % | +0.91 % | +0.30 Pkt. | 0.1069 |
| R1+TREND | 1167 | +0.25 % | +0.46 % | +1.42 % | 54 % | +0.26 % | -0.36 Pkt. | 0.7596 |
| R1+UNTER | 4019 | +0.66 % | +1.45 % | +1.94 % | 57 % | +1.25 % | +0.64 Pkt. | 0.0055 |
| R1+VOL | 2053 | +0.35 % | +0.88 % | +1.64 % | 55 % | +0.68 % | +0.06 Pkt. | 0.4138 |
| R1+BREIT | 3540 | +0.32 % | +0.42 % | +0.80 % | 54 % | +0.21 % | -0.40 Pkt. | 0.8131 |
| R3+TREND | 923 | +0.39 % | +1.06 % | +1.72 % | 57 % | +0.86 % | +0.24 Pkt. | 0.2549 |
| R3+UNTER | 4704 | +0.56 % | +1.18 % | +1.79 % | 57 % | +0.97 % | +0.36 Pkt. | 0.1194 |
| R3+VOL | 1768 | +0.61 % | +1.33 % | +1.93 % | 57 % | +1.13 % | +0.51 Pkt. | 0.0435 |
| R3+BREIT | 3808 | +0.34 % | +0.65 % | +1.02 % | 55 % | +0.45 % | -0.17 Pkt. | 0.6707 |
| A5 | 104585 | +0.60 % | +0.98 % | +1.54 % | 57 % | +0.78 % | +0.16 Pkt. | 0.3168 |
| K-ABV | 15810 | +0.44 % | +0.82 % | +1.81 % | 54 % | +0.62 % | – | – |
| K | 15982 | +0.35 % | +0.70 % | +1.34 % | 55 % | +0.50 % | -0.11 Pkt. | 0.6792 |

Depot pre (5 Plätze, 10 Tage, 0,10 % je Seite): R1 +20.1 % p. a. (Rückgang -38 %) · R2 +4.1 % p. a. (Rückgang -55 %) · R3 +16.7 % p. a. (Rückgang -48 %) · R1+TREND +1.8 % p. a. (Rückgang -29 %) · R3+TREND +7.3 % p. a. (Rückgang -28 %) · A5 +34.8 % p. a. (Rückgang -33 %) · K-ABV +35.5 % p. a. (Rückgang -45 %)

## asia · all (2756 Aktien)

| Variante | Signale | 5 T. | 10 T. | 20 T. | im Plus (10 T.) | netto 10 T. | Δ gegen K-ABV | p |
|---|---|---|---|---|---|---|---|---|
| R1 | 21614 | +0.42 % | +0.87 % | +1.52 % | 55 % | +0.67 % | -0.07 Pkt. | 0.7026 |
| R2 | 64995 | +0.48 % | +1.01 % | +2.15 % | 54 % | +0.81 % | +0.08 Pkt. | 0.3183 |
| R3 | 20855 | +0.56 % | +0.84 % | +1.53 % | 54 % | +0.64 % | -0.10 Pkt. | 0.6912 |
| R1+TREND | 3356 | +0.65 % | +1.19 % | +1.43 % | 55 % | +0.99 % | +0.25 Pkt. | 0.1754 |
| R1+UNTER | 17745 | +0.35 % | +0.80 % | +1.54 % | 54 % | +0.60 % | -0.14 Pkt. | 0.8416 |
| R1+VOL | 6242 | +0.37 % | +0.81 % | +1.32 % | 54 % | +0.60 % | -0.13 Pkt. | 0.7771 |
| R1+BREIT | 11660 | +0.38 % | +0.60 % | +0.84 % | 52 % | +0.40 % | -0.34 Pkt. | 0.9325 |
| R3+TREND | 2161 | +0.59 % | +0.91 % | +1.31 % | 53 % | +0.71 % | -0.03 Pkt. | 0.5392 |
| R3+UNTER | 18284 | +0.55 % | +0.83 % | +1.59 % | 54 % | +0.63 % | -0.11 Pkt. | 0.7011 |
| R3+VOL | 5174 | +0.59 % | +0.72 % | +1.46 % | 53 % | +0.52 % | -0.21 Pkt. | 0.8461 |
| R3+BREIT | 11558 | +0.46 % | +0.55 % | +0.97 % | 52 % | +0.34 % | -0.39 Pkt. | 0.9415 |
| A5 | 335304 | +0.54 % | +0.83 % | +1.58 % | 52 % | +0.63 % | -0.11 Pkt. | 0.6752 |
| K-ABV | 64638 | +0.49 % | +0.94 % | +1.63 % | 54 % | +0.74 % | – | – |
| K | 65045 | +0.29 % | +0.62 % | +1.26 % | 51 % | +0.42 % | -0.31 Pkt. | 0.9775 |

Depot asia (5 Plätze, 10 Tage, 0,10 % je Seite): R1 +5.8 % p. a. (Rückgang -60 %) · R2 +4.1 % p. a. (Rückgang -59 %) · R3 +2.8 % p. a. (Rückgang -52 %) · R1+TREND -1.0 % p. a. (Rückgang -58 %) · R3+TREND +5.7 % p. a. (Rückgang -39 %) · A5 +8.1 % p. a. (Rückgang -53 %) · K-ABV +2.0 % p. a. (Rückgang -68 %)

## Entscheidung (vorab festgelegt)

- **R1**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.02, Validierung 17–21 +0.35, Holdout 22–26 +0.40, Vorzeit 99–07 +0.36, Asien 08–26 -0.07)
- **R2**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.51, Validierung 17–21 +0.17, Holdout 22–26 +0.11, Vorzeit 99–07 +0.01, Asien 08–26 +0.08)
- **R3**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.26, Validierung 17–21 +0.07, Holdout 22–26 +0.19, Vorzeit 99–07 +0.30, Asien 08–26 -0.10)
- **R1+TREND**: nicht bestanden – besser als K-ABV in 2/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.13, Validierung 17–21 -0.28, Holdout 22–26 -0.08, Vorzeit 99–07 -0.36, Asien 08–26 +0.25)
- **R1+UNTER**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.03, Validierung 17–21 +0.49, Holdout 22–26 +0.44, Vorzeit 99–07 +0.64, Asien 08–26 -0.14)
- **R1+VOL**: nicht bestanden – besser als K-ABV in 2/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.07, Validierung 17–21 -0.28, Holdout 22–26 +0.53, Vorzeit 99–07 +0.06, Asien 08–26 -0.13)
- **R1+BREIT**: nicht bestanden – besser als K-ABV in 1/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.15, Validierung 17–21 -0.08, Holdout 22–26 -0.23, Vorzeit 99–07 -0.40, Asien 08–26 -0.34)
- **R3+TREND**: Hinweis – besser als K-ABV in 3/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.12, Validierung 17–21 -0.05, Holdout 22–26 +0.11, Vorzeit 99–07 +0.24, Asien 08–26 -0.03)
- **R3+UNTER**: Hinweis – besser als K-ABV in 4/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.28, Validierung 17–21 +0.14, Holdout 22–26 +0.17, Vorzeit 99–07 +0.36, Asien 08–26 -0.11)
- **R3+VOL**: nicht bestanden – besser als K-ABV in 2/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.34, Validierung 17–21 -0.56, Holdout 22–26 -0.03, Vorzeit 99–07 +0.51, Asien 08–26 -0.21)
- **R3+BREIT**: nicht bestanden – besser als K-ABV in 1/5 Prüfungen, davon signifikant 0 (Train 08–16 -0.08, Validierung 17–21 +0.11, Holdout 22–26 -0.64, Vorzeit 99–07 -0.17, Asien 08–26 -0.39)
- **A5**: nicht bestanden – besser als K-ABV in 2/5 Prüfungen, davon signifikant 0 (Train 08–16 +0.14, Validierung 17–21 -0.17, Holdout 22–26 -0.38, Vorzeit 99–07 +0.16, Asien 08–26 -0.11)
