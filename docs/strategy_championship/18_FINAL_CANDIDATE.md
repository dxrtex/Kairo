# 18 · Bester Kandidat für den Trading-Teil – Stand 19.10.2026

Status: **Train + Validierung bestanden, Holdout 2022–2026 noch versiegelt** (Freigabe nur mit „FINALEN HOLDOUT FREIGEGEBEN“).
Alle Werte netto, Kostenmodell Scalable PRIME+ (ab 250 € Orderwert gebührenfrei). Datensatz mit Survivorship-Bias
(nur heute gelistete Aktien) → absolute Renditen eher zu hoch.

## Kandidat: Momentum 6-1 / Volatilität, Top 10, monatlich (S07-B)

Regel: Am letzten Handelstag jedes Monats alle liquiden Aktien (Ø-Umsatz ≥ 5 Mio. USD, Kurs ≥ 1 USD) nach
„Rendite der Monate −6 … −1 ÷ Schwankung 6 Monate“ sortieren, die besten 10 gleich gewichtet halten, zur nächsten Eröffnung
tauschen. Kein Stop, keine weiteren Filter.

## Warum dieser und kein anderer (30+ Varianten in 5 Runden geprüft)

| Familie | Ergebnis |
|---|---|
| Kurzfrist-Mean-Reversion (S19/B/C, RSI(2), Verlierer) | vor Kosten ≈ 0 … +9 %, nach Kosten negativ – auch mit PRIME+ |
| Hybrid Trend + Mean Reversion nach Marktampel | schlechter als Trend allein, auch ohne Kosten |
| Kairo-Setup, Trend-Rücksetzer, Ausbrüche, VCP (S20) | kein Vorteil gegenüber Zufall / Validierung nicht bestanden |
| 52-Wochen-Hoch, Momentum-Kombis, Vol-Steuerung, EMA200-Filter | alle schwächer als einfaches Momentum (Welle 3) |
| Sektor-Rotation | nicht besser als zufällige Sektoren |
| **Momentum Top 10** | **Train +16,9 % (p 0,015) · Validierung +27,9 % (p 0,000, Bonferroni bestanden, robust ohne Ausreißer)** |
| Momentum Top 5 | Validierung +21,8 %, aber −59 % Rückgang und abhängig von wenigen Gewinnern → verworfen |

## Gesamtsystem 2008–2021 (20.000 € Gesamtkapital, d2_trainval_top10.json)

| Aufteilung | CAGR (Basis / Stress) | größter Rückgang | Validierung 2017–21 |
|---|---|---|---|
| 100 % ACWI | +9,0 % | −46 % | +11,1 % |
| ACWI + 20 % Momentum | +13,8 % / +11,9 % | −41 % | +19,3 % / +16,3 % |
| ACWI + 30 % Momentum | +15,5 % / +12,9 % | −40 % | +21,9 % / +17,8 % |
| ETF mit Trendfilter + 20 % Momentum | +13,7 % / +11,6 % | −27 % | +16,6 % / +13,1 % |

**Mindestgröße:** Momentum braucht ≥ ≈ 2.500 € im Trading-Teil (10 Orders ≥ 250 € → gebührenfrei). Darunter frisst die
0,99-€-Gebühr den Vorteil (10.000 € gesamt mit 10 %: Stress +8,2 % < 100 % ACWI). Daher: bis dahin 100 % ETF.

## Offene Prüfungen

1. **Holdout 2022–2026 (versiegelt):** Plan – Momentum Top 10 allein gegen 100 Zufalls-Depots (10 Titel) und ACWI + 20/30 %
   Momentum gegen 100 % ACWI, 20.000 €, PRIME+ Basis und Stress. Bestanden, wenn der Momentum-Teil netto (Stress) besser ist
   als ACWI und p vs. Zufall ≤ 0,10. Erst nach Nutzer-Freigabe.
2. **Live-Papier-Test** MOM10 (läuft seit 19.10.2026) – Abgleich nach 6–12 Monaten.
3. Survivorship-freie Daten (kostenpflichtig, z. B. Norgate/Sharadar) würden die absolute Höhe klären – nur mit Freigabe.
