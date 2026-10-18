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

## Nachtrag: Kostenmodell Scalable PRIME+ (Nutzer-Tarif; ab 250 € Orderwert gebührenfrei, sonst 0,99 €)

Rohdaten c5_prime_train.json (Stress: 1,99 € unter 250 €, doppelter Spread, Slippage, FX). CAGR Basis / Stress, größter Rückgang.

| Variante | 2.000 € | 5.000 € | 10.000 € |
|---|---|---|---|
| T1 Momentum Top 10 | +16,8 % / −1,6 % · −36 % | +18,8 % / +14,5 % · −36 % | +18,9 % / +14,6 % · −36 % |
| **T1 Momentum Top 5** | **+18,9 % / +14,2 % · −38 %** | +18,8 % / +14,2 % · −38 % | +18,7 % / +14,0 % · −38 % |
| T1-A1 Top 10 | +14,7 % / +11,1 % · −31 % | +15,8 % / +12,4 % · −31 % | +15,9 % / +12,6 % · −31 % |
| T1-A2 Top 10 | +9,8 % / +7,0 % · −21 % | +10,6 % / +8,4 % · −21 % | +10,6 % / +8,4 % · −21 % |
| M2 / M3 nur bei roter Ampel (A1) | −24 … −26 % | +0,2 / −1,5 % | +1,4 / +0,3 % |
| Hybride H1/H2-A1 | −24 … −32 % | +10,7 / +12,2 % | +11,6 / +13,7 % |

Befund unverändert: Mean Reversion bringt auch ohne Ordergebühren ≈ 0 % und macht jede Kombination schlechter als Momentum
allein. PRIME+ macht dagegen Momentum mit 5 Titeln schon ab ≈ 1.300 € Trading-Kapital nahezu gebührenfrei (Positionen ≥ 250 €).
Top 5 ist eine neue, nicht vorregistrierte Variante → nur Kandidat für den Papier-Test, keine Validierung verbraucht.
