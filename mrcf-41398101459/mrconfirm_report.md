# Mean Reversion – Bestätigung auf unabhängigen Daten

Vorab festgelegt 02.11.2026 (research/reversal/mrconfirm.py). Vorzeit = USA/Europa 1999–2007, Asien = 2008–2026.
Beide Universen sind von heute aus gewählt → alle Kauf-Strategien sehen zu gut aus; maßgeblich ist der Abstand zur Kontrolle.

## Vorzeit 1999–2007 (1727 Aktien)

| Variante | Signale | gefüllt | Brutto je Trade | netto 0,05 % | netto 0,10 % | netto 0,25 % | Ø Tage | Depot 0,10 %: Rendite p. a. (Rückgang) | 1. / 2. Hälfte | Depot 0,25 % |
|---|---|---|---|---|---|---|---|---|---|---|
| A5 | 104894 | 1.0 | +0.6 % | +0.5 % | +0.4 % | +0.1 % | 4.62 | +42.5 % (-23.8 %) | +53.4 % / +32.2 % | +16.0 % |
| W2 | 104945 | 0.407 | +0.9 % | +0.8 % | +0.7 % | +0.4 % | 5.43 | +39.4 % (-16.5 %) | +53.4 % / +26.8 % | +23.2 % |
| W2-250 | 104945 | 0.407 | +0.9 % | +0.8 % | +0.7 % | +0.4 % | 5.43 | +39.4 % (-16.5 %) | +53.4 % / +26.8 % | +23.2 % |
| W2-VH | 104933 | 0.407 | +0.9 % | +0.8 % | +0.7 % | +0.4 % | 5.62 | +32.2 % (-18.8 %) | +37.7 % / +27.0 % | +17.2 % |
| W2-BREITE | 104945 | 0.407 | +0.9 % | +0.8 % | +0.7 % | +0.4 % | 5.43 | +30.0 % (-16.8 %) | +34.5 % / +25.8 % | +16.3 % |
| CTRL | 104642 | 1.0 | +0.3 % | +0.2 % | +0.1 % | -0.2 % | 3.43 | +9.3 % (-51.3 %) | +16.1 % / +2.9 % | -25.9 % |
| CTRL-L | 104700 | 0.408 | +0.6 % | +0.5 % | +0.4 % | +0.1 % | 4.36 | +19.1 % (-20.0 %) | +21.8 % / +16.8 % | +1.0 % |

Gleichgewichtetes Universum (kaufen und halten, ohne Kosten): +21.9 % p. a., Rückgang -28.0 %

- Brutto je Trade W2-CTRL-L: Δ +0.38 Prozentpunkte, Bootstrap p 0.000
- Brutto je Trade A5-CTRL: Δ +0.35 Prozentpunkte, Bootstrap p 0.000
- Brutto je Trade W2-A5: Δ +0.30 Prozentpunkte, Bootstrap p 0.000

## Asien 2008–2026 (2756 Aktien)

| Variante | Signale | gefüllt | Brutto je Trade | netto 0,05 % | netto 0,10 % | netto 0,25 % | Ø Tage | Depot 0,10 %: Rendite p. a. (Rückgang) | 1. / 2. Hälfte | Depot 0,25 % |
|---|---|---|---|---|---|---|---|---|---|---|
| A5 | 335486 | 1.0 | +0.5 % | +0.4 % | +0.3 % | +0.0 % | 4.74 | +37.3 % (-51.7 %) | +43.3 % / +31.3 % | +13.0 % |
| W2 | 335828 | 0.366 | +0.8 % | +0.7 % | +0.6 % | +0.3 % | 5.59 | +29.4 % (-41.1 %) | +32.0 % / +26.6 % | +15.1 % |
| W2-250 | 335828 | 0.366 | +0.8 % | +0.7 % | +0.6 % | +0.3 % | 5.59 | +29.4 % (-41.1 %) | +32.0 % / +26.6 % | +15.1 % |
| W2-VH | 335828 | 0.366 | +0.8 % | +0.7 % | +0.6 % | +0.3 % | 5.75 | +24.6 % (-37.3 %) | +28.4 % / +20.7 % | +11.2 % |
| W2-BREITE | 335828 | 0.366 | +0.8 % | +0.7 % | +0.6 % | +0.3 % | 5.59 | +22.9 % (-37.8 %) | +29.2 % / +16.8 % | +11.6 % |
| CTRL | 335854 | 1.0 | +0.2 % | +0.1 % | +0.0 % | -0.3 % | 3.56 | -4.1 % (-67.8 %) | -9.0 % / +1.1 % | -36.2 % |
| CTRL-L | 335972 | 0.4 | +0.4 % | +0.3 % | +0.2 % | -0.1 % | 4.47 | +5.1 % (-47.7 %) | +5.1 % / +5.1 % | -10.2 % |

Gleichgewichtetes Universum (kaufen und halten, ohne Kosten): +17.2 % p. a., Rückgang -54.1 %

- Brutto je Trade W2-CTRL-L: Δ +0.45 Prozentpunkte, Bootstrap p 0.000
- Brutto je Trade A5-CTRL: Δ +0.30 Prozentpunkte, Bootstrap p 0.000
- Brutto je Trade W2-A5: Δ +0.26 Prozentpunkte, Bootstrap p 0.000

## Entscheidung (vorab festgelegt)

- **W2** gegen CTRL-L: bestätigt (pre: ja, asia: ja)
- **A5** gegen CTRL: bestätigt (pre: ja, asia: ja)
- **W2-250** besser als W2: nein ([False, False])
- **W2-VH** besser als W2: nein ([False, False])
- **W2-BREITE** besser als W2: nein ([False, False])
