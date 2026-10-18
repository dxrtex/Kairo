# 11 — Phase D: Ergebnis Kern + Satellit (2008–2021)

**Status: EXPLORATIV (Train + Validierung kombiniert, kein Out-of-Sample) · DATENBESCHRÄNKT.** Plan: `10_PHASE_D_PLAN.md`
(vorab). Lauf lokal mit `d_run.py` (Commit `35a115c`), Rohzahlen `d_results_trainval.json`. Alle 190 Topf-Läufe: Bilanzprüfungen
bestanden. Holdout versiegelt.

## 1. Ergebnis der vorab festgelegten Auswahlregel

**Keine Mischung erfüllt alle Bedingungen** (Max. DD ≤ 20 % bei 5.000 €, ≤ 22 % unter Kostenstress, CAGR > reiner Kern).
Grund: **schon der ruhigste Kern (S13-ETF) hat 2008–2021 einen Max. DD von −22 %** (Finanzkrise 2008, bevor das Signal auf
Cash dreht). Mit reinen Aktien-/Aktien-ETF-Bausteinen ist das 20-%-Budget über diesen Zeitraum nicht sicher einzuhalten.

## 2. Die knappsten Kandidaten (netto, 2008–2021)

| Mischung | Kapital | CAGR | Max. DD | Sharpe | Stress CAGR | Stress DD |
|---|---|---|---|---|---|---|
| S13-ETF rein | 5 k€ | +8,7 % | −22,0 % | 0,67 | +8,4 % | −22,6 % |
| **S13-ETF + 20 % S07-B-T** | 5 k€ | +9,0 % | **−19,8 %** | 0,67 | +6,7 % | −23,0 % |
| **S13-ETF + 20 % S07-B-T** | 10 k€ | **+10,5 %** | −20,4 % | 0,72 | +8,1 % | −21,3 % |
| **S13-ETF + 20 % S07-B-T** | 20 k€ | +11,1 % | −20,5 % | 0,74 | +9,2 % | −20,5 % |
| S13-ETF + 30 % S07-B-T | 10 k€ | +11,9 % | −21,5 % | 0,74 | +9,0 % | −21,3 % |
| S16-B + 40 % S07-B-T | 10 k€ | +16,7 % | −23,4 % | 0,88 | +14,2 % | −24,5 % |
| S16-B rein | 5 k€ | +16,4 % | −30,4 % | 0,82 | +15,5 % | −30,5 % |
| ACWI rein (Vergleich) | 5 k€ | +9,0 % | −45,9 % | 0,51 | +9,0 % | −46,0 % |

## 3. Befunde

1. **Der Marktfilter für den Satelliten wirkt:** S07-B-T (nur investiert, wenn ACWI > SMA 10) senkt den Max. DD des Momentum-
   Topfs von −47 % auf −32 % bei etwas weniger Rendite (+17–18 % statt +21–22 % p. a.).
2. **Bei 5.000 € lohnt der Satellit kaum:** Ein 1.000-€-Topf mit 10 Positionen à 100 € zahlt ≈ 2 % Kosten je Kauf+Verkauf; unter
   Kostenstress ist die Mischung **schlechter** als der reine Kern (+6,7 % vs. +8,4 %). Ab 10.000 € bringt er +1,5…+3 %-Punkte p. a.
3. **S16-B-Mischungen** haben die höchsten Renditen (+16–19 %), reißen das 20-%-Budget aber in der Validierung (2020: −23…−36 %) —
   und tragen den QQQ-Vorbehalt.
4. **Für ein hartes 20-%-Budget fehlt ein Puffer-Baustein** (Cash/Tagesgeld/kurze Anleihen als fester Anteil). Er war nicht
   vorab registriert und wurde daher **nicht** gerechnet.

## 4. Optionen (Entscheidung Nutzer)

- **A:** Budget-Toleranz auf ≈ 22 % festlegen → Kandidat **S13-ETF + 20 % S07-B-T** (ab 10.000 €) in den Holdout.
- **B:** Puffer-Variante als Protokoll v1.4 vorab registrieren (z. B. 15 % fest in kurzen Anleihen/SHY bzw. Cash), auf 2008–2021
  rechnen, dann Holdout. Mehr Versuche auf denselben Daten → etwas mehr Überanpassungsrisiko, Holdout bleibt sauber.
- **C:** Die zwei knappsten Kandidaten (S13-ETF + 20 % S07-B-T; S16-B + 40 % S07-B-T) **so wie sie sind** in den Holdout, ohne
  weitere Anpassung — als ehrlicher Test, auch wenn das Budget in 2008–2021 knapp verfehlt wurde.
