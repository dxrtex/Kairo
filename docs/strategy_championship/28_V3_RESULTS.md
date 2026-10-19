# 28 · Ergebnisse Protokoll v3.0 – Fundamental-, Ereignis- und Insider-Strategien (+ 4H-Nebenanalyse)

Stand 19.10.2026 · Regeln: `27_PROTOCOL_V3.md` (Commit `faf27da`, vor jedem Lauf festgeschrieben) · Hauptlauf
`research_v3.yml` Run 39299518972 (Commit `bfa50e4`) · Ergebnisdateien: Entwurfs-Release `research-v3-39299518972`
(`v3_results.json`, Tageskurven, Signal-Listen) · Daten: Release `research-data-v1` (Kurse), `research-sec-v3`
(SEC-Tabellen + Yahoo-Splits). **Bias-Label: DATENBESCHRÄNKT (Survivorship)** – nur heute gelistete Firmen ≥ 2 Mrd. USD.

## Kurzfassung

**Keiner der vier Kandidaten besteht.** Alle vier sind nach Kosten in Train und Validierung positiv, liegen aber in der
Validierung 2017–2021 **unter ACWI** und sind **nicht besser als zufällig gewählte Aktien** aus demselben Pool
(p = 0,41 … 0,81; nötig wären ≤ 0,0125). Ihr hoher Train-Wert ist zum großen Teil der Survivorship-Effekt, den auch die
Zufalls-Depots haben (Median +14 … +17 % p. a.). Dual Momentum S16-B bleibt die beste Strategie im Vergleich – auch nach
Steuern.

## 1. Ergebnisse (5.000 €, Stress-Kosten PRIME+, Netto-CAGR in EUR)

| Strategie | Train 2010–16 | Validierung 2017–21 | 2010–21 nach Steuern | max. Rückgang 2010–21 | Sharpe 2010–21 | Holdout 2022–26 (Hinweis) |
|---|---|---|---|---|---|---|
| K1 Quality + Earnings Momentum | +19,0 % | +11,2 % | +12,0 % | −44,3 % | 0,74 | +21,9 % |
| K2 Multi-Faktor | +15,6 % | +6,9 % | +9,1 % | −52,8 % | 0,60 | +13,1 % |
| K3 PEAD | +11,1 % | +9,9 % | +9,4 % | −47,6 % | 0,61 | +12,1 % |
| K4 Insider-Cluster | +13,6 % | +6,5 % | +8,6 % | −52,8 % | 0,57 | +13,9 % |
| ACWI halten | +10,8 % | +11,6 % | +9,6 % | −28,5 % | 0,69 | +9,7 % |
| Dual Momentum S16-B | +16,6 % | +19,3 % | +14,9 % | −30,3 % | 0,90 | +11,6 % |
| 70 % ACWI / 30 % Nasdaq-100 | +14,2 % | +16,1 % | +13,5 % | −31,5 % | 0,84 | +10,7 % |

20.000 € verhält sich gleich (Abweichungen ≤ 1,5 Prozentpunkte, Datei `v3_results.json`). „Nach Steuern“ = Abgeltungsteuer
26,375 %, Teilfreistellung 30 % für Aktien-ETFs, Vorabpauschale ab 2018, ohne Sparerpauschbetrag, Verkauf aller Positionen
am 31.12.2021.

## 2. Entscheidung nach den vorab festgelegten Regeln (§7)

| Kandidat | Basis-Kosten 2010–21 | Zufall Median (5.–95. Perzentil) | p vs. Zufall | 1 | 2 | 3 | 4 | 5 | Urteil |
|---|---|---|---|---|---|---|---|---|---|
| K1 | +17,9 % | +17,2 % (+12,0 … +21,5 %) | 0,41 | ✓ | ✗ | ✗ | ✓ | ✓ | **nicht bestanden** |
| K2 | +14,3 % | +16,4 % (+12,4 … +22,5 %) | 0,81 | ✓ | ✗ | ✗ | ✗ | ✓ | **nicht bestanden** |
| K3 | +14,5 % | +14,8 % (+9,9 … +19,9 %) | 0,57 | ✓ | ✗ | ✗ | ✗ | ✓ | **nicht bestanden** |
| K4 | +13,3 % | +14,4 % (+10,5 … +18,6 %) | 0,65 | ✓ | ✗ | ✗ | ✗ | ✓ | **nicht bestanden** |

Kriterien: 1 Stress-CAGR > 0 in Train und Validierung · 2 Stress-CAGR > ACWI in Train **und** Validierung · 3 p ≤ 0,0125
(Bonferroni für 4) · 4 nach Steuern 2010–21 > ACWI nach Steuern · 5 Mindestumfang in Train. 200 Zufalls-Depots je Kandidat
(K1/K2: 10 zufällige Titel je Monat aus demselben Pool mit Kennzahlen; K3/K4: gleich viele zufällige Titel an denselben
Signaltagen, gleiche 60-Tage-Haltedauer).

## 3. Einordnung

1. **Der Vorteil ist nicht die Auswahl, sondern das Universum.** Zufällige Aktien aus dem heutigen Universum hätten
   2010–2021 im Median +14 bis +17 % p. a. gebracht – genauso viel wie die Kandidaten. Das ist der Survivorship-Bias: Firmen,
   die es heute mit ≥ 2 Mrd. USD gibt, waren rückblickend gute Käufe. Ein echter Faktor-Vorteil müsste sich **gegen diesen
   Zufall** zeigen; das tut er bei keinem der vier.
2. **K1 (Qualität + Earnings Momentum) ist der stärkste der vier** (Train +19 %, Holdout +22 %), verliert aber in der
   Validierung gegen ACWI und liegt nur knapp über dem Zufalls-Median. Ergebnis: kein belegbarer Vorteil.
3. **Value/Multi-Faktor (K2) und Insider-Cluster (K4)** brechen in der Validierung ein (+6–7 % p. a., Rückgang −53 %
   im Corona-Crash März/April 2020). Das passt zur Literatur seit 2017 (schwacher Value-Faktor).
4. **PEAD (K3)** mit Kursreaktion ≥ 5 % als Überraschung: positiv, aber im Rahmen des Zufalls. Viele Signale (≈ 650/Jahr),
   die 10 Plätze sind fast immer voll – die Strategie ist eher „Momentum nach Zahlen“ als ein eigener Effekt.
5. **Steuern** verschärfen das Bild: Einzelaktien-Strategien realisieren laufend Gewinne (Umschlag 3–4× pro Jahr), der
   ETF-Kern schiebt die Steuer bis zum Verkauf. ACWI verliert durch Steuern ≈ 1,4 Pp. p. a., K1 ≈ 4 Pp.
6. **Benchmarks:** Dual Momentum S16-B war 2010–2021 vor und nach Steuern die beste getestete Variante (+14,9 % nach
   Steuern, Sharpe 0,90); 70/30 ACWI/Nasdaq-100 liegt dazwischen (+13,5 %). Beide sind nur Benchmarks – kein neuer Test.

## 4. Daten und Abdeckung

- **SEC** (über den PC des Nutzers, User-Agent mit Kontakt): 1.943 von 1.944 US-Titeln einem CIK zugeordnet; 2,9 Mio.
  XBRL-Werte; PIT-Kennzahlen für 1.609 Firmen (ausländische Emittenten mit IFRS/20-F fehlen). Pool K1 je Monatsende:
  617 Titel (2010) → 1.306 (2021), Median 892. 76.698 8-K-Quartalsmeldungen (Item 2.02) → 7.785 K3-Signale 2010–21.
  187.686 Insider-Käufe (Code P) → 1.259 K4-Cluster 2010–21 (Insider-Daten nur bis 2026 Q1).
- **Splits** (Yahoo, für K2-Börsenwert): 872 Splits bei 540 Titeln; Prüfung bestätigt split-bereinigte Kurse im Datensatz v1.
- **Fundamentaldaten erst ab dem Tag nach der Einreichung**, je Kennzahl der damals bekannte Wert (Restatements erst ab
  ihrem Datum). Beispiel Apple: GJ 2009 zuerst mit 5,70 Mrd. USD Gewinn gemeldet (Okt. 2009), nach der Umstellung der
  Umsatzrealisierung 8,24 Mrd. (Jan. 2010) – der Backtest sieht bis Jan. 2010 nur 5,70.
- Engine-Prüfungen (Kasse, keine negative Kasse, PnL = Equity) in allen Läufen bestanden.

## 5. Nebenanalyse N1 – 4H-Einstieg für Kairo-Signale

**Noch offen.** Dukascopy liefert Aktien-Stundenkerzen erst ab Januar 2017 (2015/16 gibt es dort nicht), für 527 der
Universums-Titel. Dukascopy blockiert Kommandozeilen- und Cloud-Abrufe; der Abruf läuft daher langsam über den eingebauten
Browser auf dem PC des Nutzers und wurde nach ≈ 1.700 von ≈ 41.600 Monatsdateien vorübergehend gedrosselt (HTTP 503).
Code (`v3/h4_side.py`) und Regeln (Protokoll §8) stehen fest; das Ergebnis wird hier nachgetragen, sobald die Daten
vollständig sind.

## 6. Grenzen

Survivorship-Bias (s. o.) betrifft Kandidaten **und** Zufall gleich – der Vergleich gegen Zufall ist daher aussagekräftiger
als der gegen ACWI. US-ETFs als Proxy für UCITS-ETFs; Quellensteuer als voll anrechenbar angenommen; Vorabpauschale vor
2018 vereinfacht 0. Holdout 2022–2026 war seit v2.1 geöffnet und zählt nur als Hinweis (dort liegen K1–K4 vor ACWI –
im Einklang mit dem Survivorship-Effekt, nicht als Beleg).

## 7. Konsequenz

Mit den jetzt verfügbaren kostenlosen Fundamental-, Earnings- und Insider-Daten gibt es **keine Strategie, die den Test
besteht**. Die bisherige Empfehlung bleibt: Welt-ETF als Kern, Dual Momentum als bester Kandidat für den Trading-Teil
(Papier-Test läuft). Keine weiteren Varianten von K1–K4 (Protokoll §9).
