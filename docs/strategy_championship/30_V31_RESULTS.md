# 30 · Ergebnisse Protokoll v3.1 – S19/S20 mit echten 4H-Kerzen und SEC-Fundamentaldaten

Stand 20.10.2026 · Regeln: `29_PROTOCOL_V3_1.md` (Commit `9ef6295`, vor dem Lauf festgeschrieben) · Lauf
`research_v31.yml` Run 39359195062 (Commit `1349594`, Hauptlauf + 16 Zufalls-Teilläufe à 25 Seeds) · Ergebnisdateien:
Entwurfs-Release `research-v31-39359195062` (`s1920_main.json`, `s1920_results.json`, `s1920_curves.csv.gz`,
`acwi_test.json`) · Daten: `research-data/v3` (SEC, Splits, Dukascopy-Stunden). **Bias-Label: DATENBESCHRÄNKT
(Survivorship)** – nur heute gelistete Firmen.

## Kurzfassung

**Keine der vier Varianten besteht.** In ihrer Originalform (echter 4H-Auslöser, Börsenwert und Marge zeitpunktgenau aus
der SEC) bleiben S19, S19-B und S19-C nahe null (−0,1 … +1,0 % p. a. nach Stress-Kosten) – sie handeln zu selten, um ein Depot
zu bewegen. S20 (Trendfolge/VCP) handelt sehr oft (~120 Trades pro Jahr) und verliert nach Stress-Kosten deutlich
(−8,7 % p. a.). Keine Variante liegt über ACWI (+11,6 %), keine ist signifikant besser als Zufall (Bonferroni p ≤ 0,0125).

## 1. Ergebnisse 2017–2021 (5.000 €, Netto-CAGR in EUR)

| Strategie | Basis PRIME+ | Stress | nach Steuern (Stress) | max. Rückgang | Trades | Ø R netto (Stress) | p vs. Zufall | Zufall-Median | besteht |
|---|---|---|---|---|---|---|---|---|---|
| S19 Hybride Mean Reversion | −0,1 % | −0,1 % | −0,1 % | −1 % | 1 | −1,23 | 0,56 | −0,0 % | nein |
| S19-B (Volumen 2 von 3) | +0,4 % | +0,2 % | +0,1 % | −2 % | 8 | +0,04 | 0,06 | −0,1 % | nein |
| S19-C (+ Überdehnung 2,0) | +2,1 % | +1,0 % | +0,7 % | −6 % | 54 | +0,08 | 0,04 | +0,2 % | nein |
| S20 Trendfolge/VCP | +7,6 % | −8,7 % | −9,1 % | −53 % | 604 | −0,07 | 0,25 | +5,0 % | nein |
| ACWI halten | +11,7 % | +11,6 % | +9,7 % | – | – | – | – | – | Vergleich |

Bestehensregeln (§6): 1 Stress > 0 · 2 > ACWI · 3 p ≤ 0,0125 · 4 nach Steuern > ACWI · 5 ≥ 30 Trades.
S19-C erfüllt 1 und 5, S19-B nur 1, S19 und S20 keine. Kapital 2.000 € / 20.000 € ändert das Bild nicht (S20 mit 2.000 €
Stress: −29,9 % p. a., mit 20.000 €: −6,8 %).

## 2. 2022–2026 (nur Hinweis, Holdout offen; ~30 % der Dukascopy-Monate fehlen)

| Strategie | Basis | Stress | Trades |
|---|---|---|---|
| S19 | +1,2 % | +1,0 % | 8 |
| S19-B | +0,3 % | −0,5 % | 31 |
| S19-C | +0,9 % | −1,1 % | 109 |
| S20 | −5,3 % | −14,3 % | 545 |

Der Hinweiszeitraum bestätigt die Testergebnisse: keine Variante ist dort brauchbar.

## 3. Einordnung

- **S19 ist zu selten:** Von 35 Tagessignalen (2017–21) führt nur eines zu einem Trade – der 4H-Auslöser plus CRV ≥ 2 zur EMA20
  filtert fast alles weg. Gelockerte Varianten (B, C) handeln öfter, verdienen pro Trade aber nach Kosten fast nichts
  (+0,04 … +0,08 R). S19-C ist mit p = 0,04 der knappste Fall, liegt aber deutlich über der Bonferroni-Schwelle und
  bringt +1 % p. a. bei nur ~10 % Kapitaleinsatz im Schnitt – als Depot-Baustein ohne Wirkung.
- **S20 frisst sich an den Kosten auf:** Brutto +7,6 % (unter ACWI, und nicht besser als zufällige Titel aus demselben
  Aufwärtstrend-Pool, Zufall-Median +5,0 %). Mit realistisch höheren Kosten (Stress) kippt es auf −8,7 %. Viele
  Ausstiege sind Stopps mit Kurslücke (170 von 604) – kleiner 1,5-ATR-Stop auf 4H ist für Einzelaktien zu eng.
- **Zusammen mit v3.0 (`28_V3_RESULTS.md`):** Weder die Fundamental-/Ereignis-Strategien K1–K4 noch der 4H-Einstieg für Kairo
  noch S19/S20 in Originalform schlagen ACWI oder den Zufall. **Dual Momentum S16-B bleibt die beste getestete
  Strategie** (Validierung 2017–21 +19,3 %, nach Steuern 2010–21 +14,9 % gegen +9,6 % ACWI).

## 4. Grenzen

Survivorship (heutige Liste), Dukascopy-Volumen ist Tick-Volumen, Kursniveau je Tag auf Yahoo skaliert, Lücken in den
Stundendaten (v. a. 2022–26), Branchen-ETF-Zuordnung über SIC grob. Diese Grenzen begünstigen eher die Strategien
(Survivorship) – an der Entscheidung ändern sie nichts.
