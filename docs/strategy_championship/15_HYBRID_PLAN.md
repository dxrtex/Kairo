# 15 · Phase 2: Hybrid-System Trend + Mean Reversion (Plan, vorab festgelegt)

Stand 18.10.2026 · Status: **PLAN – NICHT GETESTET**. Ziel des Nutzers: langfristig das beste robuste System für die App.
Rahmen: Großteil des Kapitals im ETF (mit Trendfilter), Trading-Teil anfangs ca. 10 %, später ggf. 20–30 %.

## Grundsatz

Die laufenden Papier-Depots (S19, S19-B, S19-C, S20) bleiben unverändert. Das Schattenbuch (paper/shadow.py,
Protokoll v1.8) sammelt echte 4H-Daten zu Mindest-CRV und Ausstiegen. Phase 2 entwirft parallel ein Hybrid-System,
**nur auf Train 2008–2016**. Validierung 2017–2021 genau einmal für den Finalisten, Holdout nur nach „FINALEN HOLDOUT FREIGEGEBEN“.

## Marktampel (höchstens 2 Definitionen)

- A1: S&P 500 über/unter EMA200 (wie S19/S20).
- A2: zusätzlich Schwankung: realisierte 20-Tage-Volatilität des S&P über/unter ihrem 1-Jahres-Median.

## Module

| Modul | Regel (Kurzform) | Herkunft |
|---|---|---|
| T1 Trend | S07-B: Momentum 6-1 / Vol, Top 10, monatlich | Validierung bestanden |
| T2 Trend | S16-B: Dual Momentum SPY/EFA/QQQ | Validierung bestanden (QQQ-Rückschau-Hinweis) |
| M1 Mean Rev. | S19 wie vom Nutzer (Tages-Proxy) | Train negativ, nur Referenz |
| M2 Mean Rev. | Rücksetzer im Aufwärtstrend: große Aktie über SMA200, RSI(2) < 10 → Kauf nächste Eröffnung; Ausstieg Schluss > SMA5 oder nach 10 Tagen; Stop 2,5 ATR | bekannte Klasse aus der Literatur |
| M3 Mean Rev. | Kurzfrist-Umkehr: unter den großen Aktien die schwächsten 5-Tage-Verlierer (unterstes Zehntel), nur bei Ampel rot oder hoher Volatilität; Haltedauer 5 Tage | Kurzfrist-Reversal-Literatur |

Universum für M2/M3: wie S19-PIT (ADV ≥ 100 Mio. $), keine heutigen Börsenwerte.

## Kombinationen (fest, keine weiteren)

- H0: nur T1 (Vergleich) · H1: Ampel grün → T1, rot → M2 · H2: grün → T1, rot → M3 · H3: T1 immer + M2 als Zusatz
- Je mit A1 und A2 → höchstens 8 Hybrid-Läufe plus Referenzen ETF, T1, M1–M3 einzeln.

## Bewertung

- Kosten Basis und Stress (Protokoll v1.1), Mindestfüllung 50 %.
- Kapital des Trading-Teils: 2.000 / 5.000 / 10.000 €.
- Zufallsvergleich mit 200 Läufen, Block-Bootstrap nach Monaten.
- Mindestens 100 Trades je Mean-Reversion-Modul auf Train, sonst DATENBESCHRÄNKT.
- Bestanden nur, wenn netto (Stress) besser als H0 bei gleichem oder kleinerem größtem Rückgang.

## Wichtige Rahmenbedingung Kapital

Bei 2.000 € Gesamtkapital sind 10 % Trading-Teil nur 200 €. 0,99 € je Order sind dann 0,5 % pro Kauf bzw. Verkauf,
und viele Aktien kosten mehr als eine Positionsgröße. Aktives Trading ist dort rechnerisch kaum sinnvoll. Der
Papier-Test (je 2.000 € virtuell) ist die Lernphase, bis der Trading-Teil groß genug ist (Bewertung bei 2.000 / 5.000 / 10.000 €).
