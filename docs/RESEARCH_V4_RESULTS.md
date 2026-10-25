# Forschung v4 – Ergebnisse Index-Trendfolge mit Hebel (25.10.2026)

Plan: `RESEARCH_V4_PLAN.md` (vor dem Lauf festgelegt). Lauf: Workflow `research_v4.yml`, Run 40226133378. Daten Yahoo 1988–10/2026.
CAGR je Zeitraum, größter Rückgang (DD) über den Zeitraum. Kosten: Wechsel 0,25 %, ETF-Kosten, Finanzierung T-Bill + 0,5 %. Ohne Steuern.

| Variante | 1989–2007 | 2008–2016 | 2017–2026 | Gesamt | DD gesamt | Wechsel | Urteil |
|---|---|---|---|---|---|---|---|
| SP1 S&P 500 halten (Vergleich) | +11,5 % | +7,2 % | +15,0 % | +11,3 % | −55 % | – | – |
| SP1F S&P 500 nur über SMA200 | +8,6 % | +5,5 % | +9,8 % | +8,2 % | −26 % | 225 | nicht bestanden (weniger Rendite) |
| SP2 S&P 500 2× immer | +15,2 % | +8,5 % | +23,6 % | +15,6 % | −88 % | – | nicht bestanden (Rückgang) |
| **SP2F S&P 500 2× nur über SMA200** | **+12,5 %** | **+10,2 %** | **+16,6 %** | **+13,1 %** | **−45 %** | 225 | **knapp nicht bestanden** (SMA100: +7,7 %) |
| **SP3F S&P 500 3× nur über SMA200** | **+15,4 %** | **+14,1 %** | **+22,4 %** | **+16,9 %** | −60 % | 225 | **knapp nicht bestanden** (SMA100: +9,6 %) |
| NQ1 Nasdaq-100 halten | +15,0 % | +11,1 % | +20,9 % | +15,5 % | −82 % | – | nicht bestanden (Rückgang) |
| NQ2F Nasdaq-100 2× über SMA200 | +20,8 % | +8,5 % | +31,2 % | +20,2 % | −73 % | 257 | nicht bestanden (Rückgang) |
| NQ3F Nasdaq-100 3× über SMA200 | +22,7 % | +10,9 % | +42,4 % | +24,4 % | −89 % | 257 | nicht bestanden (Rückgang) |

Robustheit (Gesamt-CAGR mit anderer Linie, muss > +11,3 % sein): SP2F 100/150/250 Tage = +7,7 / +12,7 / +12,6 % ·
SP3F = +9,6 / +16,8 / +15,8 % · NQ2F = +17,1 / +16,3 / +20,7 %.

## Einordnung
1. **Zum ersten Mal schlägt eine einfache Regel den Index in allen drei Zeiträumen und hat dabei weniger Rückgang:**
   S&P 500 mit 2-fachem Hebel, nur wenn der Index über seiner 200-Tage-Linie liegt (sonst Geldmarkt). 37 Jahre, inklusive
   Dotcom-Crash, Finanzkrise und Corona – ohne Survivorship-Bias. Das deckt sich mit der Literatur (Gayed & Bilello 2016).
2. **Nach den vorab festgelegten Regeln trotzdem nicht bestanden:** Mit einer schnelleren Linie (100 Tage) wird die Strategie
   deutlich schlechter als der Index (viele Fehlsignale). Mit 150 und 250 Tagen funktioniert sie. Der Effekt hängt also an
   einer langsamen Linie – plausibel, aber ein Warnzeichen.
3. **Nicht im Test:** Steuern (≈ 6 Wechsel pro Jahr realisieren Gewinne – in Deutschland ein spürbarer Nachteil gegenüber
   Halten), Abweichungen echter gehebelter ETFs von der Rechnung, und ein Crash an einem einzigen Tag wie 1987 (−20 %):
   Die 200-Tage-Linie schützt davor nicht, mit 2× wären es −40 % an einem Tag.
4. Vergleich zum Welt-ETF: Der S&P 500 lag in diesem Zeitraum über dem Welt-Index – gegen ACWI wäre der Abstand größer.

## Entscheidung
Kein Kandidat für echtes Geld. **SP2F** (S&P 500 2× über SMA200) ist der beste Kandidat aller bisherigen Runden und kommt
in den Papier-Test, wenn Jonny zustimmt – Entscheidung über echtes Geld frühestens nach 12 Monaten Vorwärtstest.
