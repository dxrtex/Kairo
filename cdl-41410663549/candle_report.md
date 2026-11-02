# Bullische Kerzen- und Chartformationen – Ergebnis

Vorab festgelegt 02.11.2026 (research/reversal/candle.py).

## A. Formation während der Bodenbildung → besseres B60-Setup?

R je Trade mit Stress-Kosten, 13.241 B60-Trades 2008–26. Δ = mit minus ohne Formation.

| Formation | Anteil der Setups | Ø R mit | Ø R ohne | Δ Train | Δ Validierung | Δ Holdout | q | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| ENGULF | 35 % | +0.026 | -0.060 | +0.173 | -0.218 | +0.233 | 0.1827 | kein beständiger Effekt |
| HAMMER | 37 % | -0.075 | -0.003 | -0.049 | -0.100 | -0.067 | 0.18555 | kein beständiger Effekt |
| PIERCE | 9 % | -0.114 | -0.022 | +0.029 | -0.129 | -0.159 | 0.20844 | kein beständiger Effekt |
| HARAMI | 33 % | -0.063 | -0.013 | +0.156 | -0.218 | -0.104 | 0.33831 | kein beständiger Effekt |
| MSTAR | 4 % | +0.063 | -0.034 | +0.283 | +0.121 | -0.113 | 0.39302 | kein beständiger Effekt |
| SOLDIERS | 1 % | +0.108 | -0.032 | +0.217 | +0.104 | +0.126 | 0.51254 | kein beständiger Effekt |
| KERZE | 78 % | -0.031 | -0.026 | +0.217 | -0.282 | +0.036 | 0.91621 | kein beständiger Effekt |
| WBODEN | 63 % | -0.055 | +0.012 | +0.055 | -0.011 | -0.196 | 0.20844 | kein beständiger Effekt |
| CUP | 3 % | +0.250 | -0.040 | +0.529 | +0.652 | -0.236 | 0.17937 | kein beständiger Effekt |

## B. Formation allein als Kaufsignal (Ertrag 10 Tage)

### Train (2887 Aktien)

| Signal | Anzahl | Ø 10 T. | im Plus | netto | Δ gegen Kontrolle | p |
|---|---|---|---|---|---|---|
| ENGULF | 10262 | +0.67 % | 54 % | +0.46 % | +0.20 Pkt. (K-ABV) | 0.1679 |
| HAMMER | 15051 | +0.45 % | 53 % | +0.25 % | -0.01 Pkt. (K-ABV) | 0.4943 |
| PIERCE | 2685 | +0.04 % | 52 % | -0.16 % | -0.42 Pkt. (K-ABV) | 0.8716 |
| HARAMI | 13174 | +1.04 % | 56 % | +0.84 % | +0.58 Pkt. (K-ABV) | 0.0415 |
| MSTAR | 1301 | -1.10 % | 51 % | -1.30 % | -1.57 Pkt. (K-ABV) | 0.7966 |
| SOLDIERS | 477 | +0.12 % | 54 % | -0.08 % | -0.34 Pkt. (K-ABV) | 0.7971 |
| KERZE | 41351 | +0.60 % | 54 % | +0.39 % | +0.13 Pkt. (K-ABV) | 0.2799 |
| WBODEN | 16606 | +0.15 % | 54 % | -0.05 % | -0.31 Pkt. (K-ABV) | 0.7986 |
| CUP | 6771 | +0.17 % | 52 % | -0.03 % | -0.24 Pkt. (K-TREND) | 0.9505 |
| K-ABV | 41055 | +0.46 % | 55 % | +0.26 % | – | – |
| K-TREND | 41015 | +0.42 % | 55 % | +0.22 % | – | – |

### Validierung (2887 Aktien)

| Signal | Anzahl | Ø 10 T. | im Plus | netto | Δ gegen Kontrolle | p |
|---|---|---|---|---|---|---|
| ENGULF | 7656 | +0.62 % | 56 % | +0.42 % | -0.11 Pkt. (K-ABV) | 0.6727 |
| HAMMER | 10897 | -0.62 % | 54 % | -0.82 % | -1.36 Pkt. (K-ABV) | 0.9775 |
| PIERCE | 1873 | +1.35 % | 59 % | +1.15 % | +0.62 Pkt. (K-ABV) | 0.0515 |
| HARAMI | 9321 | +0.89 % | 57 % | +0.69 % | +0.16 Pkt. (K-ABV) | 0.3633 |
| MSTAR | 978 | -0.39 % | 53 % | -0.58 % | -1.12 Pkt. (K-ABV) | 0.8926 |
| SOLDIERS | 295 | +1.80 % | 58 % | +1.60 % | +1.07 Pkt. (K-ABV) | 0.0855 |
| KERZE | 30203 | +0.35 % | 56 % | +0.15 % | -0.38 Pkt. (K-ABV) | 0.8771 |
| WBODEN | 12607 | +0.40 % | 54 % | +0.19 % | -0.34 Pkt. (K-ABV) | 0.7706 |
| CUP | 4693 | +0.42 % | 53 % | +0.22 % | -0.06 Pkt. (K-TREND) | 0.5887 |
| K-ABV | 30980 | +0.73 % | 57 % | +0.53 % | – | – |
| K-TREND | 33738 | +0.48 % | 55 % | +0.28 % | – | – |

### Holdout (2887 Aktien)

| Signal | Anzahl | Ø 10 T. | im Plus | netto | Δ gegen Kontrolle | p |
|---|---|---|---|---|---|---|
| ENGULF | 12004 | +0.92 % | 56 % | +0.72 % | -0.01 Pkt. (K-ABV) | 0.4863 |
| HAMMER | 12445 | +1.16 % | 56 % | +0.96 % | +0.23 Pkt. (K-ABV) | 0.1064 |
| PIERCE | 2703 | +1.11 % | 56 % | +0.91 % | +0.18 Pkt. (K-ABV) | 0.3028 |
| HARAMI | 10793 | +1.02 % | 56 % | +0.82 % | +0.08 Pkt. (K-ABV) | 0.3728 |
| MSTAR | 957 | +1.22 % | 56 % | +1.02 % | +0.28 Pkt. (K-ABV) | 0.2819 |
| SOLDIERS | 573 | -0.30 % | 46 % | -0.50 % | -1.24 Pkt. (K-ABV) | 0.974 |
| KERZE | 38576 | +1.02 % | 56 % | +0.82 % | +0.09 Pkt. (K-ABV) | 0.2569 |
| WBODEN | 17042 | +0.63 % | 54 % | +0.43 % | -0.30 Pkt. (K-ABV) | 0.7961 |
| CUP | 6107 | +0.24 % | 50 % | +0.03 % | -0.24 Pkt. (K-TREND) | 0.8961 |
| K-ABV | 38307 | +0.94 % | 55 % | +0.73 % | – | – |
| K-TREND | 35338 | +0.47 % | 52 % | +0.27 % | – | – |

### Vorzeit 99–07 (1727 Aktien)

| Signal | Anzahl | Ø 10 T. | im Plus | netto | Δ gegen Kontrolle | p |
|---|---|---|---|---|---|---|
| ENGULF | 6506 | +0.93 % | 55 % | +0.73 % | +0.16 Pkt. (K-ABV) | 0.1899 |
| HAMMER | 9604 | +1.18 % | 56 % | +0.98 % | +0.42 Pkt. (K-ABV) | 0.017 |
| PIERCE | 1751 | +0.70 % | 54 % | +0.50 % | -0.06 Pkt. (K-ABV) | 0.6112 |
| HARAMI | 7066 | +1.17 % | 55 % | +0.96 % | +0.40 Pkt. (K-ABV) | 0.0165 |
| MSTAR | 715 | +1.08 % | 56 % | +0.88 % | +0.32 Pkt. (K-ABV) | 0.2204 |
| SOLDIERS | 363 | +0.48 % | 51 % | +0.27 % | -0.29 Pkt. (K-ABV) | 0.6907 |
| KERZE | 25269 | +1.08 % | 55 % | +0.87 % | +0.31 Pkt. (K-ABV) | 0.0085 |
| WBODEN | 9564 | +0.35 % | 53 % | +0.15 % | -0.42 Pkt. (K-ABV) | 0.928 |
| CUP | 4770 | +0.37 % | 53 % | +0.17 % | -0.22 Pkt. (K-TREND) | 0.8916 |
| K-ABV | 25264 | +0.76 % | 54 % | +0.56 % | – | – |
| K-TREND | 25411 | +0.59 % | 55 % | +0.39 % | – | – |

### Asien 08–26 (2756 Aktien)

| Signal | Anzahl | Ø 10 T. | im Plus | netto | Δ gegen Kontrolle | p |
|---|---|---|---|---|---|---|
| ENGULF | 28920 | +0.88 % | 54 % | +0.67 % | -0.09 Pkt. (K-ABV) | 0.6857 |
| HAMMER | 30656 | +0.67 % | 53 % | +0.47 % | -0.29 Pkt. (K-ABV) | 0.976 |
| PIERCE | 8149 | +0.50 % | 53 % | +0.30 % | -0.46 Pkt. (K-ABV) | 0.951 |
| HARAMI | 27910 | +1.14 % | 55 % | +0.94 % | +0.18 Pkt. (K-ABV) | 0.1204 |
| MSTAR | 2804 | +0.94 % | 54 % | +0.74 % | -0.02 Pkt. (K-ABV) | 0.5207 |
| SOLDIERS | 1626 | +0.74 % | 52 % | +0.53 % | -0.22 Pkt. (K-ABV) | 0.6867 |
| KERZE | 97408 | +0.86 % | 54 % | +0.66 % | -0.10 Pkt. (K-ABV) | 0.8756 |
| WBODEN | 37430 | +0.59 % | 52 % | +0.39 % | -0.37 Pkt. (K-ABV) | 0.9735 |
| CUP | 15398 | +0.87 % | 50 % | +0.67 % | +0.23 Pkt. (K-TREND) | 0.0225 |
| K-ABV | 97598 | +0.96 % | 54 % | +0.76 % | – | – |
| K-TREND | 97427 | +0.65 % | 51 % | +0.45 % | – | – |

### Entscheidung B

- **ENGULF**: nicht bestanden – besser als Kontrolle in 2/5, signifikant 0 (Train +0.20, Validierung -0.11, Holdout -0.01, Vorzeit 99–07 +0.16, Asien 08–26 -0.09)
- **HAMMER**: nicht bestanden – besser als Kontrolle in 2/5, signifikant 0 (Train -0.01, Validierung -1.36, Holdout +0.23, Vorzeit 99–07 +0.42, Asien 08–26 -0.29)
- **PIERCE**: nicht bestanden – besser als Kontrolle in 2/5, signifikant 0 (Train -0.42, Validierung +0.62, Holdout +0.18, Vorzeit 99–07 -0.06, Asien 08–26 -0.46)
- **HARAMI**: Hinweis – besser als Kontrolle in 5/5, signifikant 0 (Train +0.58, Validierung +0.16, Holdout +0.08, Vorzeit 99–07 +0.40, Asien 08–26 +0.18)
- **MSTAR**: nicht bestanden – besser als Kontrolle in 2/5, signifikant 0 (Train -1.57, Validierung -1.12, Holdout +0.28, Vorzeit 99–07 +0.32, Asien 08–26 -0.02)
- **SOLDIERS**: nicht bestanden – besser als Kontrolle in 1/5, signifikant 0 (Train -0.34, Validierung +1.07, Holdout -1.24, Vorzeit 99–07 -0.29, Asien 08–26 -0.22)
- **KERZE**: Hinweis – besser als Kontrolle in 3/5, signifikant 0 (Train +0.13, Validierung -0.38, Holdout +0.09, Vorzeit 99–07 +0.31, Asien 08–26 -0.10)
- **WBODEN**: nicht bestanden – besser als Kontrolle in 0/5, signifikant 0 (Train -0.31, Validierung -0.34, Holdout -0.30, Vorzeit 99–07 -0.42, Asien 08–26 -0.37)
- **CUP**: nicht bestanden – besser als Kontrolle in 1/5, signifikant 0 (Train -0.24, Validierung -0.06, Holdout -0.24, Vorzeit 99–07 -0.22, Asien 08–26 +0.23)
