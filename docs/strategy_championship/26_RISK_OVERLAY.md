# 26 – Risikosteuerung und Hebel (Protokoll v2.9)

Stand 19.10.2026 · Basis: Tageskurven v2.8 mit Stress-Kosten · Holdout bereits geöffnet → **kein unberührter Beleg**.
Ergebnis-Datei: `risk_overlay_result.json`.

| 70 % ACWI + 30 % DM | Gesamt CAGR | max. Rückgang | Sharpe |
|---|---|---|---|
| ungehebelt | +10,9 % | −31 % | 0,64 |
| statisch 1,25 | +11,5 % | −39 % | 0,58 |
| statisch 1,5 | +11,8 % | −47 % | 0,53 |
| Zielvola 12 %, max 1,0 | +7,6 % | −17 % | 0,64 |
| **Zielvola 12 %, max 1,5 (Haupt)** | +7,0 % | −18 % | 0,56 |
| Zielvola 15 %, max 1,5 | +8,4 % | −22 % | 0,57 |

Reiner ACWI: ungehebelt +9,1 % / −46 %; mit 1,5-fach +9,0 % / −64 %.

**Entscheidung:** Hauptvariante nicht bestanden (CAGR in keinem Abschnitt höher, Sharpe niedriger).

**Einordnung:** Hebel bringt nach Finanzierungskosten (6 % p. a.) kaum Mehrrendite, aber deutlich tiefere Rückgänge – beim
reinen ETF sogar weniger Rendite. Zielvolatilität halbiert den Rückgang (−17 % statt −31 %), kostet aber gut 3 Prozentpunkte
Rendite je Jahr bei gleicher Sharpe – eine Option nur für jemanden, der große Rückgänge nicht aushält, kein Renditehebel.
Ergebnis: **ETF + Dual Momentum ungehebelt bleibt die beste gefundene Kombination.** Keine weiteren Varianten.
