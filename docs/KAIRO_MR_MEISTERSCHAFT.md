# Kairo – Strategie-Forschung 01.11.2026: Kombinationen, Meta-Modell, Mean-Reversion-Meisterschaft

Alle Tests: korrigierte Engine, 13.241 B60-Trades bzw. das gleiche Universum (USA + Europa, eingefroren 16.10.2026),
Train 2008–2016 · Validierung 2017–2021 · Holdout 2022–2026, Regeln je Test **vor** dem Lauf festgelegt, Korrektur für
Mehrfachtests. Ergebnisse auf Branch `claude/reversal-out` (Ordner `learn-*`, `combo-*`, `meta-*`, `mrc-*`, `mrc2-*`, `mrc3-*`).
Keine Regel wurde geändert. B60 bleibt Champion bis zu einer Freigabe.

## 1. Kombinationen „11 Kriterien + X“ (combo-41349959025, combo-41350455413)

| Merkmal | Ø R Stress mit / ohne | Δ Train / Val / Holdout | Ergebnis |
|---|---|---|---|
| Insider-Kauf 90 Tage (SEC Form 4) | +0,006 / −0,011 | −0,02 / +0,03 / +0,04 | kein Effekt |
| ≥ 2 Insider | −0,169 / +0,001 | −0,05 / −0,25 / −0,22 | eher schlechter, q 0,17 |
| Vorstand kaufte | −0,077 / −0,003 | −0,06 / −0,06 / −0,09 | eher schlechter, q 0,64 |
| über 200-Tage-Linie UND Markt darunter | +0,175 / −0,038 | +0,20 / +0,07 / +0,35 | knapp, q 0,17 → live beobachtet |
| Kapitulations-Volumen | −0,185 / −0,023 | −0,06 / −0,22 / −0,19 | knapp, q 0,17 → live beobachtet |
| Quartalszahlen im Rückgang (8-K 2.02) | −0,127 / +0,056 | **+0,21** / −0,44 / −0,30 | seit 2017 stark schlechter, 2008–16 umgekehrt → nicht bestanden |
| Bruttogewinn/Bilanzsumme ≥ 0,20 | +0,115 / −0,007 | +0,10 / +0,12 / +0,12 | beständig besser, q 0,17 → knapp nicht bestanden |

Datenlücke: Der SEC-Datensatz enthält nur 8-K-Quartalsmeldungen – „Rückgang ganz ohne Nachricht“ ist damit nicht testbar.

## 2. Meta-Labeling – ein Modell aus allen Merkmalen (meta-41350820407)

Ridge-Regression, zeitlich getrennt. Validierung ρ −0,056, Holdout ρ +0,157 (oberes Drittel +0,21 R, unteres −0,29 R).
Im Depot schlägt weder Modell-Rangfolge noch Modell-Filter B60 durchgängig → **nicht bestanden**.

## 3. Mean-Reversion-Meisterschaft – 26 Varianten (mrc-41351756989, mrc2-41352654108)

Jahresrendite (CAGR), 10.000 €, bestes Raster nach Train. „normal“ = Scalable PRIME+ (Spread je Aktie, 0,99 € unter 250 €),
„Stress“ = doppelter Spread + 0,05 % Schlupf + 0,1 % FX je Seite. Welt-ETF (ACWI, ohne Kosten): Train +3,9 %, Val +14,4 %, Holdout +10,3 %.

| Variante | normal Train / Val / Holdout | größter Rückgang (normal) | Stress Val / Holdout | Brutto je Trade | Kostenschwelle* |
|---|---|---|---|---|---|
| **A5 3 Verlusttage + Aufwärtstrend** (5 Plätze) | **+16,1 % / +35,0 % / +11,9 %** | −38 % | −1,6 % / −76 % | +0,5 % | 0,09 % je Seite |
| A7 Wochen-Verlierer (10 Plätze) | −7,5 % / +26,4 % / +23,9 % | −79 % | −23 % / Totalverlust | +0,5 % | 0,14 % |
| A3 RSI(2) < 10 ohne Trend (5) | +29,6 % / +26,4 % / +3,9 % | −54 % | −7 % / −18 % | +0,6 % | – |
| A8 RSI(2) nur liquide (5) | +14,5 % / +20,6 % / +5,4 % | −53 % | −72 % / Totalverlust | +0,4 % | – |
| C1 RSI(2) auf Index-ETFs (5) | +8,9 % / +8,3 % / +8,0 % | **−20 %** | +2,1 % / +1,3 % | +0,5 % | – |
| A5L 3 Verlusttage, nur liquide (10) | – / +12,4 % / +6,2 % | – | −12 % / −14 % | +0,4 % | – |
| **B0 B60 (Referenz, 5 × 1 %)** | +18,2 % / −8,6 % / +1,8 % | −58 % | −12 % / −4 % | +0,3 % | – |
| B0 B60 (20 × 0,25 %) | +7,6 % / +4,1 % / +4,5 % | −31 % | −2 % / −6 % | | |
| B-Varianten (Ausstiege 5-Tage-Linie / Vortageshoch / Tag 10, nur liquide, Panik-Risiko, Basis 3/7 Kerzen, Spanne 1,0/2,0, Wartezeit 5/15) | durchweg nicht besser als B60 | | | | |

\* Kostenschwelle = höchste geprüfte Kosten je Seite, bei denen Validierung UND Holdout den Welt-ETF schlagen.

### Was das bedeutet

1. **B60 ist nicht die stärkste Mean-Reversion-Regel.** Mit normalen Kosten hat „3 Verlusttage + Aufwärtstrend“ (A5) in **allen
   drei** Zeiträumen deutlich mehr verdient als B60 und als der Welt-ETF.
2. **Aber: Der Vorteil hängt fast vollständig an den Handelskosten.** Brutto bringt jeder Trade ~0,5 % in ~4 Tagen. Ab etwa
   0,09 % Kosten je Seite (A5) bzw. 0,14 % (A7) schlägt die Strategie den ETF nicht mehr; mit Stress-Kosten folgt ein Totalverlust.
   Die Variante nur mit sehr liquiden Aktien (A5L, kleine Spreads) schlägt den ETF **nicht** – der Vorteil kommt also gerade aus
   den weniger liquiden Werten, wo echte Spreads höher sind als modelliert. Das spricht dafür, dass die realen Kosten den Vorteil
   eher auffressen.
3. **Gebührenfalle:** Nach einem tiefen Rückgang werden Positionen kleiner als 250 € → 0,99 € je Order bei ~440 Trades im Jahr →
   das Konto schrumpft weiter. Darum die abrupten Totalverluste bei leicht höheren Kosten.
4. **ETF-Mean-Reversion (C1)** ist die robusteste Variante (+8–9 % in allen Zeiträumen, Rückgang −20 %, auch mit Stress-Kosten
   positiv), bleibt aber unter dem Welt-ETF.
5. Nach der vorab festgelegten Regel (Stress-Kosten) **besteht kein Herausforderer**.

### Empfehlung

- **Kein Echtgeld auf A5/A7**, solange die realen Kosten unbekannt sind.
- **A5 als Challenger in den Schattentest** (Papier, mit den echten Geld-/Briefkursen bei Scalable zum Handelszeitpunkt). Messgröße:
  Kosten je Seite. Liegen sie über 3 Monate dauerhaft unter ~0,08 %, ist A5 ein ernsthafter Kandidat – sonst nicht.
- **Der verlässlichste Weg zu mehr Vermögen bleibt der Welt-ETF** (90/10-Profil); der Trading-Teil ist Forschung mit begrenztem
  Einsatz.

## 4. Welle 3 – Kosten senken, A5 robuster (mrc3-41354218063)

Achtung: dieselben Daten wurden zum dritten Mal ausgewertet. Die Ergebnisse sind Hinweise, kein Beweis – den liefert nur der
Schattentest auf neuen Daten.

| Variante | normal Val / Holdout | Stress Val / Holdout | Brutto je Trade | Kostenschwelle |
|---|---|---|---|---|
| A5 (Referenz) | +35,0 % / +11,9 % | −1,6 % / −76 % | +0,5 % | 0,09 % |
| W1 A5 mit Kauf-Limit 1 % unter Schluss | +33,8 % / +14,2 % | +4,0 % / −10,4 % | +0,6 % | 0,09 % |
| **W2 A5 mit Kauf-Limit 0,5 ATR unter Schluss** | **+47,5 % / +12,3 %** | **+15,1 % / −11,3 %** | +0,7 % | 0,09 % |
| W3 4 Verlusttage | +25,4 % / +6,2 % | −75 % / Totalverlust | +0,4 % | – |
| W4 A5 nur RSI(2) < 15 | +30,2 % / +15,1 % | −4,0 % / −74,5 % | +0,5 % | 0,09 % |

**Depot-Mischung (monatlich ausgeglichen, 10.000 €, gesamt 2008–2026):**

| Mischung | normal | Stress | größter Rückgang (normal) |
|---|---|---|---|
| 100 % Welt-ETF | +8,5 % p. a. | +8,5 % | −52 % |
| 90 % ETF + 10 % W2 | +10,5 % | +7,9 % | −48 % |
| 70 % ETF + 30 % W2 | +14,4 % | +6,7 % | −39 % |
| 90 % ETF + 10 % C1 (ETF-RSI2) | +8,7 % | +8,1 % | −48 % |
| 90 % ETF + 10 % B60 | +8,4 % | +7,7 % | −49 % |

### Was das bedeutet

1. Das **Kauf-Limit** ist der stärkste Hebel: Es kauft im Schnitt billiger, der Brutto-Ertrag je Trade steigt von 0,5 % auf 0,7 %
   und der Stress-Schaden halbiert sich ungefähr. Einschränkung: Im Backtest gilt „Tief berührt das Limit“ als Ausführung – live
   wird nicht jedes berührte Limit gefüllt. Das prüft der Schattentest.
2. **Als 10-%-Beimischung zum Welt-ETF** hebt W2 die Rendite mit normalen Kosten um ~2 Prozentpunkte im Jahr und senkt den
   größten Rückgang; mit Stress-Kosten kostet es ~0,6 Prozentpunkte. Das Risiko ist begrenzt, die Chance klar größer.
3. Weniger Trades (W3, W4) helfen nicht.
4. Nach der vorab festgelegten Regel besteht weiterhin **kein** Herausforderer gegen B60 statistisch abgesichert (W2: p 0,10, Holm 1,0).

### Entscheidung

- W2 läuft ab 01.11.2026 zusätzlich im Schattentest (backend/mrshadow.py), neben A5, ETF-RSI(2) und E2.
- Echtgeld frühestens nach ~3 Monaten Schattentest, und nur wenn die Limit-Füllung live funktioniert und die echten Kosten
  unter ~0,08 % je Seite liegen. Dann höchstens als 10-%-Satellit.

## 5. Bestätigung auf unabhängigen Daten (mrcf-41398101459, 02.11.2026)

Vorab festgelegt in `research/reversal/mrconfirm.py`. Daten, die A5/W2 nie gesehen haben: USA/Europa **1999–2007**
(1.727 Aktien) und **Asien 2008–2026** (2.756 Aktien). Weil beide Universen von heute aus gewählt sind (Überlebens-Verzerrung),
zählt der Abstand zu einer **Zufalls-Kontrolle** mit demselben Fehler: zufälliger Kauf an einem Tag im Aufwärtstrend, gleicher
Ausstieg – für W2 zusätzlich mit demselben Kauf-Limit. Gegenprobe auf Zufallskursen: kein Scheinvorteil (p 0,32).

| | Vorzeit: Brutto je Trade | Asien: Brutto je Trade | Vorzeit: Depot 0,10 % / 0,25 % je Seite | Asien: Depot 0,10 % / 0,25 % |
|---|---|---|---|---|
| **W2** (A5 + Kauf-Limit) | **+0,9 %** | **+0,8 %** | +39 % / +23 % p. a. (Rückgang −17 %) | +29 % / +15 % (−41 %) |
| A5 | +0,6 % | +0,5 % | +43 % / +16 % (−24 %) | +37 % / +13 % (−52 %) |
| Kontrolle mit Limit | +0,6 % | +0,4 % | +19 % / +1 % | +5 % / −10 % |
| Kontrolle ohne Limit | +0,3 % | +0,2 % | +9 % / −26 % | −4 % / −36 % |
| Universum kaufen und halten | | | +22 % p. a. | +17 % p. a. |

- **W2 gegen Kontrolle mit Limit:** +0,38 bzw. +0,45 Prozentpunkte je Trade, p < 0,001 in beiden Datensätzen → **bestätigt**.
- **A5 gegen Kontrolle:** +0,35 bzw. +0,30 Prozentpunkte, p < 0,001 → **bestätigt**.
- **W2 gegen A5:** je Trade +0,3 Prozentpunkte besser und kleinere Rückgänge; bei höheren Kosten (0,25 %) auch im Depot besser.
- Die absoluten Renditen sind durch die Überlebens-Verzerrung geschönt (schon „kaufen und halten“ bringt +17–22 % p. a.) –
  aussagekräftig ist nur der Abstand zur Kontrolle.
- W2-250, W2 mit Vortageshoch-Ausstieg, W2 mit Marktbreite-Filter: **nicht besser** → W2 bleibt unverändert.
- Einschränkung: Ausführung des Limits bei Berührung des Tagestiefs (eher optimistisch); Kosten pauschal je Seite.

**Folgerung:** Der Effekt „3 Verlusttage im Aufwärtstrend, mit Limit kaufen“ ist kein Zufallsfund aus einem Datensatz – er
besteht in drei unabhängigen Märkten/Zeiträumen. Die offene Frage ist allein die Umsetzung: echte Limit-Ausführung und echte
Kosten bei Scalable. Genau das misst der Schattentest.
