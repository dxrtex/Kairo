# Lern-Test historisch: Was macht B60-Trades schlechter?

Statt Monate auf genug Live-Trades zu warten, prüft dieser Lauf dieselben Merkmale an allen B60-Trades 2008–2026
(Treffer 11/11, korrigierte Engine, je Trade ohne Kapitalgrenze, R mit Basis- und Stress-Kosten):

  eng         Stop näher als 1 ATR am Kauf          weit       Stop weiter als 2,5 ATR
  momentum    Vormomentum (Monat −6…−1) über +25 %   unruhig    ATR über 5 % des Kurses
  index_u200  Markt der Region unter 200-Tage-Linie  sektor_u50 Sektor unter 50-Tage-Linie
  (Markt/Sektor = gleichgewichteter Index aus allen Aktien der Region bzw. des Sektors im Universum – ohne Zukunftsdaten)
  Erklärung hinterher (kein Filter): markt_fiel = Markt der Region fiel von Kauf bis Verkauf um ≥ 3 %.

Vorab festgelegte Entscheidungsregel (vor dem Lauf, 01.11.2026): Ein Merkmal wird „Kandidat für den Depot-Test“, wenn
mit Stress-Kosten das Ø-R der Trades MIT Merkmal in Train, Validierung UND Holdout jeweils um mindestens 0,05 R unter dem
Ø-R ohne Merkmal liegt und das 95-%-Bootstrap-Intervall des Unterschieds (gesamt) unter 0 liegt. Kein Kandidat ändert die
Regel: Nächster Schritt wäre der Depot-Test (Filter weglassen vs. B60, alle Raster), danach Schattentest und Freigabe.

**13.241 B60-Trades** · Ø R Basis +0.118 · Stress -0.030 · Gewinnquote 31%

| Merkmal | Anteil | Ø R Stress mit | ohne | Δ Train | Δ Validierung | Δ Holdout | 95-%-Intervall Δ | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| Stop näher als 1 ATR | 40% (5310) | -0.042 | -0.022 | -0.013 (1697) | -0.184 (1452) | +0.096 (2161) | -0.101 … +0.058 | **kein beständiger Schaden** |
| Stop weiter als 2,5 ATR | 0% (0) | – | -0.030 | – (0) | – (0) | – (0) | – | **kein beständiger Schaden** |
| Vormomentum über +25 % | 13% (1722) | -0.139 | -0.014 | -0.047 (432) | -0.093 (538) | -0.207 (752) | -0.228 … -0.019 | **kein beständiger Schaden** |
| ATR über 5 % des Kurses | 15% (1966) | +0.189 | -0.068 | -0.072 (539) | +0.134 (560) | +0.552 (867) | +0.146 … +0.379 | **kein beständiger Schaden** |
| Markt der Region unter 200-Tage-Linie | 36% (4730) | +0.178 | -0.146 | -0.110 (2103) | +0.666 (986) | +0.591 (1641) | +0.243 … +0.401 | **kein beständiger Schaden** |
| Sektor unter 50-Tage-Linie | – (0) | – | – | – (0) | – (0) | – (0) | – | **keine Daten** |

## Erklärung hinterher: Markt der Region fiel in der Haltezeit (≥ 3 %)

Bei Verlusten 7%, bei Gewinnen 7%. Ø R mit fallendem Markt -0.158, sonst -0.020. Das ist nicht vorher erkennbar – erklärt aber, wie viel der Verluste der Markt verursacht.

## Fünftel der stetigen Merkmale (Ø R Stress)

- **Stop-Abstand in ATR:** 0.52–0.81: -0.004 (2649) · 0.81–1.00: -0.083 (2648) · 1.00–1.18: -0.033 (2648) · 1.18–1.39: +0.028 (2648) · 1.39–1.96: -0.058 (2648)
- **Vormomentum:** -0.73–-0.09: +0.002 (2649) · -0.09–-0.01: +0.069 (2648) · -0.01–0.07: -0.062 (2648) · 0.07–0.18: -0.059 (2648) · 0.18–16.95: -0.099 (2648)
- **ATR in % des Kurses:** 0.01–0.02: -0.149 (2649) · 0.02–0.03: -0.144 (2648) · 0.03–0.04: -0.039 (2648) · 0.04–0.05: +0.059 (2648) · 0.05–0.22: +0.123 (2648)

## Ergebnis

**Kein Merkmal schadet beständig** in allen drei Zeiträumen – kein Filter, B60 bleibt unverändert.
