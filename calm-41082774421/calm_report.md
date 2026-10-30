# Ruhe-Test: B60 nur mit ruhigem Basis-Tag (Q1) gegen B60 (E0)

liegt, in Asien nicht darunter, UND die Depot-CAGR (Stress) bei 5.000 € (5 × 1 %) und 10.000 € (20 × 0,25 %) in
    Validierung UND Holdout über B60 liegt. Sonst: Ruhe-Prüfung bleibt aus (wie heute).

| Abschnitt | B60 Ø R (n) | nur ruhig Ø R (n) | Anteil behalten |
|---|---|---|---|
| Train | -0.071 (4214) | -0.023 (1483) | 35% |
| Validierung | +0.069 (3765) | +0.168 (1334) | 35% |
| Holdout | -0.068 (5262) | -0.006 (1797) | 34% |

Die aussortierten unruhigen Trades (Val + Holdout): Ø R -0.047 (n 6792).

Asien 2008–26 (je Trade):
```
asia E0: Ø R Stress +0.008 (n 14193) vs. E0 +0.008 (n 14193) → Δ +0.000
asia Q1: Ø R Stress +0.020 (n 4683) vs. E0 +0.008 (n 14193) → Δ +0.012
```

| Depot (Stress) | Abschnitt | B60 | nur ruhig |
|---|---|---|---|
| 5000 € 5x1 | Validierung | -15.3% (Rückgang -59%) | +0.4% (Rückgang -27%) |
| 5000 € 5x1 | Holdout | -2.7% (Rückgang -41%) | -4.0% (Rückgang -39%) |
| 5000 € 5x1 | gesamt | -1.4% (Rückgang -77%) | -0.8% (Rückgang -57%) |
| 10000 € 20x025 | Validierung | -1.9% (Rückgang -18%) | +2.2% (Rückgang -16%) |
| 10000 € 20x025 | Holdout | -5.7% (Rückgang -38%) | -8.5% (Rückgang -39%) |
| 10000 € 20x025 | gesamt | -1.3% (Rückgang -52%) | -1.7% (Rückgang -50%) |
| 10000 € 10x05 | Validierung | -8.6% (Rückgang -42%) | +0.9% (Rückgang -18%) |
| 10000 € 10x05 | Holdout | +1.9% (Rückgang -33%) | -8.0% (Rückgang -38%) |
| 10000 € 10x05 | gesamt | -0.8% (Rückgang -63%) | -0.8% (Rückgang -50%) |

**Urteil nach Regel: nicht besser – Ruhe-Prüfung bleibt aus, unruhige Setups bleiben drin.**