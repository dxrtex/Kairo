# 10 — Phase D: Kern + Satellit (vorab festgelegt)

**Freigaben:** Gate C (Validierung geöffnet); Nutzer-Drawdown-Budget **20 %** (18.10.2026: „Ja weiter mit 20%“).
Rechenzeitraum: **Train + Validierung 2008-01-01 – 2021-12-31** in einem durchgehenden Lauf (Bericht auch je Abschnitt).
Holdout 2022–2026 bleibt versiegelt. Keine kostenpflichtigen Daten, keine Orders.

## Bausteine (Regeln unverändert aus Phase C)

- **Kern:** K1 = S13-ETF (ACWI > SMA 10 M., sonst Cash) · K2 = ACWI Kaufen & Halten · K3 = S16-B (Dual Momentum SPY/EFA/QQQ → SHY; mit Vorbehalt Rückschaufehler)
- **Satellit:** M1 = S07-B (Momentum 6-1 / Vol 6 M., Top 10, monatlich) ·
  M2 = **S07-B-T**: wie M1, aber nur investiert, wenn ACWI (EUR) am Monatsende über seiner SMA 10 Monate liegt (dieselbe Regel
  wie S13-ETF); sonst alle Satellit-Positionen zur nächsten Eröffnung verkaufen. *Neue Kombination zweier bereits validierter
  Regeln — gilt als Phase-D-Variante, nicht als validiert.*

## Mischungen

- Satellit-Anteil **20 %, 30 %, 40 %** des Startkapitals; Rest Kern. Getrennte Töpfe, **keine Umschichtung** (realistisch bei
  kleinem Kapital, keine Zusatzgebühren). Zusätzlich die reinen Bausteine (0 % / 100 %).
- Startkapital **5.000 €, 10.000 €, 20.000 €** (Kosten wie v1.1, Basis + Stress; Mindestgröße 50 %).
- 3 Kerne × 2 Satelliten × 3 Anteile = 18 Mischungen je Kapital.

## Auswahlregel (vorab)

1. Max. Drawdown (täglich, gesamt 2008–2021) **≤ 20 %** bei 5.000 € und Basiskosten; unter Kostenstress ≤ 22 %.
2. CAGR netto > reiner Kern derselben Familie (sonst lohnt der Satellit nicht).
3. Unter den verbleibenden: höchste CAGR; bei < 0,5 %-Punkt Unterschied die mit höherem Sharpe.
4. Bericht zusätzlich je Abschnitt (Train / Validierung) und für 10.000 € / 20.000 €.

Ergebnis: **höchstens zwei** Kandidaten (bester mit K1/K2, bester mit K3) gehen in den finalen Holdout — erst nach
„FINALEN HOLDOUT FREIGEGEBEN“. Turbo-/Hebel-Szenarien: in diesem Schritt **NICHT GETESTET** (folgen als reines Modell).
