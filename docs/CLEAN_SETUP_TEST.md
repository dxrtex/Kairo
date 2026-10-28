# Saubere Setups (28.10.2026)

Frage (Jonny): Bringen nur „saubere“ Setups – ruhige Konsolidierung nach dem Abverkauf, wenig Hin und Her – bessere Trades?
Daten: 13.241 Kairo-Trades (heutige Regel, R netto bei 5.000 € PRIME+), Merkmale am Tag vor dem Kauf.
Skript: `tools/research/clean_setup_test.py`. Regel vorab: sauberstes Fünftel in allen drei Abschnitten besser und p ≤ 0,05/7.

| Merkmal | Train | Validierung | Holdout | p | vorab bestanden |
|---|---|---|---|---|---|
| tight: Spanne 5 Tage / ATR (klein) | +0,10 / +0,11 | +0,34 / +0,22 | +0,24 / +0,05 | 0,005 | knapp nein (Train) |
| chop: Hin und Her 10 Tage (klein) | +0,18 / +0,09 | +0,23 / +0,25 | +0,30 / +0,03 | 0,007 | knapp nein (Validierung) |
| hug, wicks, vdry | gemischt | | | > 0,4 | nein |
| selloff / speed: starker Abverkauf | schlechter | schlechter | schlechter | > 0,99 | nein – eher Nachteil |

Nachträglich (nicht vorab festgelegt): Spanne ≤ 1,5 ATR **und** Hin und Her ≤ 1,65 (je Median), etwa ein Viertel der Trades:

| | Train | Validierung | Holdout |
|---|---|---|---|
| sauber | +0,12 R | +0,34 R | +0,26 R |
| Rest | +0,11 R | +0,22 R | +0,03 R |

Folge: In der App bekommt jeder Treffer das Kennzeichen „sauber“ oder „unruhig“; die Top-Setups zeigen standardmäßig nur
saubere. Die 11 Kriterien bleiben unverändert. Weil die Schwellen nachträglich gewählt sind, läuft die Live-Bilanz mit.
Überraschung: Ein besonders starker oder schneller Abverkauf davor macht Trades nicht besser, eher schlechter.
