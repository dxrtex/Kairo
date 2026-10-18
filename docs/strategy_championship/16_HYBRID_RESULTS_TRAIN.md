# 16 · Hybrid Trend + Mean Reversion – Ergebnisse Train 2008–2016

Status: **EXPLORATIV · DATENBESCHRÄNKT** (Survivorship: Universum = heute gelistete Titel; begünstigt Mean Reversion eher).
Plan: 15_HYBRID_PLAN.md. Rohdaten: c5_hybrid_train.json. Ampel „gut“: A1 73 % der Tage, A2 48 %.
Bilanzprüfung in 134 von 135 Läufen bestanden (Ausnahme H3-A1 · 10.000 € · Stress, ohnehin Verlierer).

## CAGR netto (Basis / Stress), größter Rückgang (Basis)

| Variante | 2.000 € | 5.000 € | 10.000 € | ohne Kosten (5k) |
|---|---|---|---|---|
| T1 Momentum ohne Ampel | +13,1 % / −2,7 % · −40 % | +16,9 % / +10,0 % · −38 % | +18,1 % / +12,5 % · −37 % | +20,7 % |
| T1-A1 (nur bei S&P > EMA200) | +11,4 % / +2,6 % · −35 % | +14,4 % / +9,4 % · −33 % | +15,2 % / +11,1 % · −32 % | +17,1 % |
| T1-A2 (zusätzlich ruhiger Markt) | +7,5 % / +0,8 % · −21 % | +9,4 % / +5,9 % · −21 % | +10,1 % / +7,2 % · −21 % | +11,5 % |
| M2 RSI(2) nur bei roter Ampel (A1) | −24,0 % · −92 % | −3,5 % / −20,8 % · −51 % | −0,9 % / −7,4 % · −43 % | +2,2 % |
| M3 Verlierer 5 T. nur bei roter Ampel (A1) | −26,3 % · −94 % | −6,9 % / −26,3 % · −53 % | −2,7 % / −14,1 % · −32 % | +2,4 % |
| H1-A1 = T1-A1 + M2 | −23,9 % · −92 % | +5,0 % / −24,2 % · −48 % | +8,9 % / −1,3 % · −42 % | +13,6 % |
| H2-A1 = T1-A1 + M3 | −32,1 % · −97 % | +6,4 % / −47,3 % · −44 % | +10,6 % / −2,7 % · −42 % | +16,8 % |

(A2-Hybride und H3 noch schlechter, siehe JSON.)

## Befund

1. **Die Hybrid-Idee (Mean Reversion bei schlechter Stimmung) besteht auf Train nicht.** Jede Kombination ist schlechter als
   Momentum allein – auch **ohne Kosten** (H1/H2 +13,6/+16,8 % gegenüber T1-A1 +17,1 %).
2. Mean Reversion verdient vor Kosten nur +2 … +9 % p. a. und verliert nach Kosten deutlich (H2-A1 bei 5.000 €: 2.467 € Kosten
   auf 936 Trades, −2.505 € Ergebnis des MR-Teils).
3. **Die Ampel macht Momentum ruhiger, nicht besser:** A1 senkt den Rückgang von −38 % auf −33 %, A2 auf −21 % – bei
   deutlich weniger Rendite. Bei 2.000 € kippt Momentum unter Stresskosten fast auf null.
4. Folgerung: Aktiver Kurzfrist-Handel (Tage) passt nicht zu kleinem Kapital mit fixen Ordergebühren; nur Strategien mit
   wenig Umschlag (Wochen–Monate) haben eine Chance. Kein Kandidat für die Validierung aus dieser Runde.
