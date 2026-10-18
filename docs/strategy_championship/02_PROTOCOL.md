# 02 — Vorregistriertes Forschungsprotokoll (Version 1, eingefroren vor jedem Screening)

**Erstellt:** 18.10.2026, **vor** Einsicht in irgendein neues Strategie-Ergebnis. Änderungen nur als neue Version mit Begründung im Experiment-Register (`04_EXPERIMENT_LOG.jsonl`); alte Versionen bleiben im Git-Verlauf.
**Freigabe:** Gate A durch Nutzer („du darfst alles machen“, 18.10.2026). Kostenpflichtige Daten/Dienste: **nicht** freigegeben → nur Gratisdaten.

## 1. Daten

| Punkt | Festlegung |
|---|---|
| Quelle | Yahoo Finance (yfinance), `auto_adjust=False`: unbereinigte OHLC (Splits eingerechnet) + `AdjClose` (Dividenden). |
| Version | **Datensatz v1** (Workflow `research_data.yml`), Manifest `MANIFEST_v1.json` mit SHA-256; nur diese Dateien werden verwendet. Gesichert als Artefakt (90 Tage) und Entwurfs-Release `research-data-v1`. |
| Universum | Eingefrorene Liste `research/strategy_championship/data/universe_frozen_2026-10-16.csv`: **US (2.036, inkl. 92 Toronto) + Europa (917) = 2.953 Aktien**. Asien/Pazifik ausgeschlossen: für einen Scalable-Kunden überwiegend nicht handelbar, dazu Zeitzonen-/FX-Rauschen. |
| Bias-Label | **`DATENBESCHRÄNKT (Survivorship)`** für alle Aktienergebnisse: nur heute existierende Firmen ≥ 2 Mrd. USD. |
| Zeitpunktgenaue Filter (je Tag, nur Vergangenheit) | Kurs ≥ 1 EUR-Gegenwert, Ø 20 T. Dollarvolumen ≥ 5 Mio. USD (historische FX-Reihen), ≥ 300 Kerzen Historie. **Börsenwert-Filter entfällt** (nicht zeitpunktgenau verfügbar) — für S01 identisch zum bisherigen Backtest, wo er faktisch „unbekannt = bestanden“ war. |
| Währung | Alle Ergebnisse in **EUR** (FX-Reihen `EURxxx=X`, GBp = Pence/100). |
| Benchmarks | Weltaktien: **ACWI** (USD, ab 2008) in EUR umgerechnet = Haupt-Proxy (Total Return über AdjClose; TER im Kurs enthalten); Gegenprobe IWDA.AS/EUNL.DE (EUR, ab 2009/2011). US: SPY. Europa: ^STOXX (Kursindex). |
| Nicht verwendet | Fundamentaldaten, Earnings, historische Sektoren, Intraday (nicht zeitpunktgenau vorhanden). |

## 2. Zeitliche Aufteilung (disjunkt, vor der Forschung festgelegt)

| Abschnitt | Zeitraum (Signaldatum) | Zweck |
|---|---|---|
| Aufwärmen | 2005-01-01 – 2007-12-31 | nur Indikatoren (EMA200, 300 Kerzen); keine Trades |
| **Entwicklung (Train)** | 2008-01-01 – 2016-12-31 | Varianten-Screening, Parameterwahl, Kostenkalibrierung |
| **Validierung** | 2017-01-01 – 2021-12-31 | Walk-Forward-Prüfung, Auswahl der Finalisten (Phase D) |
| **Finaler historischer Holdout (versiegelt)** | 2022-01-01 – 2026-10-16 | genau **einmal** in Phase E; Code verweigert Zugriff ohne `KAIRO_HOLDOUT_UNSEALED=1` |
| **Vorwärts-Paper-Trading** | ab Einfrieren der Regeln | einzige wirklich unberührte Periode |

Embargo: Trades, deren Haltedauer in den nächsten Abschnitt reicht, werden dem Abschnitt ihres **Einstiegs** zugeordnet und dort zu Ende simuliert; zwischen Train und Validierung zusätzlich 60 Handelstage Embargo für Parameterwahl (kein Signal der letzten 60 Train-Tage beeinflusst die Wahl).

**Vorbelastung (offen ausgewiesen):** S01 und alle bisherigen Kairo-Varianten (4H, Ausstiege, „ruhigste zuerst“, Risiko) wurden 2017–2026 entwickelt → Validierung und Holdout sind **für S01 vorbelastet**. Der Train-Abschnitt 2008–2016 wurde für S01 **nie** genutzt → dort ist S01 mit eingefrorenen Regeln quasi ein echter Außer-Stichproben-Test. Für S02–S18 sind alle Abschnitte bisher unberührt (bis auf allgemeine Literaturkenntnis).
**4H:** Stundenkerzen nur ab ~Okt. 2024 → liegen vollständig im versiegelten Holdout → **keine 4H-Forschung** vor Phase E; 4H wird ausschließlich im Vorwärts-Paper-Trading geprüft.

## 3. Ausführung und Kosten

| Punkt | Festlegung |
|---|---|
| Entscheidung | nach Schluss von Tag t, Ausführung zur Eröffnung des nächsten Handelstags des Titels. |
| Stops | Eröffnung ≤ Stop → zur Eröffnung, sonst Tief ≤ Stop → zum Stop; Stop und Ziel am selben Tag = Stop. |
| Gebühr | 0,99 € je Order (Scalable Free Broker, Annahme). Stress: 1,99 €. |
| Spread (volle Spanne, je Seite die Hälfte) | US-Werte 0,10 %, Europa 0,15 %; Titel mit Ø-Dollarvolumen < 20 Mio. USD: 0,30 %. Stress: ×2. |
| Slippage | 0 im Basisfall (Ausführung zur Eröffnung bzw. zum Stop); Stress: 0,05 % je Seite. |
| FX | Umrechnung zum Tages-Schlusskurs ohne Zusatzgebühr (EUR-Handel an gettex); Stress: +0,1 % je Seite für Nicht-EUR-Titel. |
| Cash | 0 % Zins (vorsichtig); Variante: Geldmarkt über ^IRX für ETF-Vergleiche. |
| Hebel/Turbos | **nicht** im Screening (Phase D, nur Modellszenarien). |
| Steuern | Vorsteuerlich; Steuerszenario DE (26,375 % + ggf. KiSt, Teilfreistellung 30 % für Aktien-ETF, Verlustverrechnung Aktien getrennt) erst in Phase E, deutlich gekennzeichnet. |

## 4. Kapital und Risiko

- Sleeve-Größen: **1.000 €, 5.000 €, 20.000 €** (Kostensensitivität).
- Risiko je Trade (Stop-Strategien): **0,5 %** (Referenz laut Auftrag) und 1,0 % (bisheriges Kairo) — je Strategie beide.
- Gewichtsstrategien (S05, S13, S16): gleichgewichtet, voll investiert gemäß Regel.
- Max. offene Positionen: 5 (1.000/5.000 €), 10 (20.000 €).
- Drawdown-Budgets 10/20/30 %: Bericht, ob historisch eingehalten, plus Stressszenario; Reduktionsregeln (10 % → halbes Risiko, 15 % → Viertel, 20 % → keine neuen Positionen) als **Hypothese H-DD**, Kalibrierung nur auf Train/Validierung.

## 5. Vorregistrierte Kandidaten Welle 1 (höchstens 2–3 Varianten je Familie)

Alle: Long-only, Aktien direkt, Universum/Filter wie oben, Kosten wie oben. „Ranking“ bei mehr Signalen als freien Plätzen: vorab festgelegt je Strategie.

| ID | Variante(n) | Einstieg | Stop | Ausstieg | Ranking |
|---|---|---|---|---|---|
| **S01** | S01-A: **unverändert** (Code `9624040`, `scanner.evaluate`, Basis-Einstieg `QRULE`) · S01-B: dasselbe mit EMA20-Ausstieg ab Tag 10, max. 40 | Basis: ≤ 10 T. nach Signal 5 Tage Spanne ≤ 1,5 ATR, nächste Eröffnung in der Basis | Basistief − 0,25 ATR | A: Tag 20 · B: Schluss < EMA20 ab Tag 10, sonst Tag 40 | ruhigste zuerst (ATR %), wie produktiv |
| **Null** | S01-Zufall: gleiche Anzahl Signale je Tag, zufällige zulässige Aktien desselben Tages, **identische** Einstiegs-/Ausstiegsregeln; 200 Seeds | wie S01-A | wie S01-A | wie S01-A | zufällig |
| **S02** | S02-A: Trend-Pullback (Kurs ≥ 15 % über EMA200, −8 %…0 % zur EMA50, RSI 35–50, Momentum 12-1 im oberen Drittel) · S02-B: wie A ohne Momentum-Filter | nächste Eröffnung | Tief 10 T. − 0,25 ATR, mind. 1 ATR | Tag 20 | höchstes 12-1-Momentum |
| **S03** | S03-P (**Proxy**, keine Fundamentaldaten): 12-1-Momentum oberes Drittel **und** 1-J.-Volatilität unteres Drittel, Rückgang ≥ 12 % vom 60-T.-Hoch, RSI(14) war < 35 und dreht hoch | nächste Eröffnung | Tief 10 T. − 0,25 ATR | Tag 20 | niedrigste Volatilität |
| **S04** | S04-M (**Marktbereinigt**, historische Branchen fehlen): 5-T.-Rendite minus Markt (SPY bzw. ^STOXX) im untersten Dezil des Tages, Kurs > EMA200 | nächste Eröffnung | 3 ATR | Tag 5 | stärkste Unterperformance |
| **S05** | S05-A: 12-1-Momentum Top 10, monatlich (letzter Handelstag) · S05-B: 6-1 Top 10 | nächste Eröffnung nach Monatsende | — | Monatsrebalance | Momentum |
| **S08** | S08-A: Schluss auf 55-T.-Hoch, Volumen > 1,5 × Ø50, Kurs > EMA200 · S08-B: 20-T.-Hoch, sonst gleich | nächste Eröffnung | 2 ATR | Schluss unter 20-T.-Tief (Signal), max. 60 T. | stärkster Volumenanstieg |
| **S11** | S11-A: RSI(2) < 10 und Kurs > EMA200 · S11-B: RSI(2) < 5 | nächste Eröffnung | 3 ATR | Schluss > SMA5 (Signal) oder Tag 10 | tiefster RSI(2) |
| **S13** | S13-ETF: ACWI (EUR) investiert, wenn Monatsschluss > SMA 10 Monate, sonst Cash · S13-Stock: Trendfolge je Aktie (Schluss > EMA200 und EMA50 > EMA200, Ausstieg Schluss < EMA200) gleichgewichtet, max. Positionen | Monatsende bzw. nächste Eröffnung | — | Signal | — / Momentum |
| **Bench** | ACWI Kaufen und Halten (EUR), einmal investiert | — | — | — | — |

Welle 2 (S06, S07, S09, S10-Proxy, S12-Proxy, S14, S16, S18-Insider) wird erst nach dem Zwischenbericht mit eigener Protokoll-Version registriert. S15 und S17: **NICHT VALIDE TESTBAR** (siehe 01).

## 6. Kennzahlen und Statistik

- Pro Variante und Abschnitt: Netto-CAGR (EUR), kumulierte Rendite, Max. Drawdown (täglich), Drawdown-Dauer, Sharpe/Sortino/Calmar (Cash = 0 %), Profit Factor, Ø Netto-R je Trade, Trefferquote, Anzahl Trades, Ø Haltedauer, Exposure, Turnover, Kostenanteil, Beta/Korrelation zu ACWI-EUR.
- Unsicherheit: Block-Bootstrap über Kalendermonate (1.000 Ziehungen, Seed 7) für CAGR und Ø-R.
- Mehrfachtests: **jeder** ausgeführte Lauf wird im Experiment-Register protokolliert (Konfiguration, Code-Commit, Daten-Hash, Abschnitt). In Phase D: Deflated Sharpe bzw. Anzahl-Korrektur auf Basis der registrierten Versuchszahl.
- Vergleich Kairo vs. Null: Anteil der 200 Zufalls-Seeds, die S01 übertreffen (empirischer p-Wert).

## 7. Auswahlregeln (Vorgabe für Phase D, endgültig in `04_SELECTION_RULES.md`)

1. Zulässig nur: echte Daten, geprüfte Engine (`03_ENGINE_AUDIT.md` = PASS/PASS WITH LIMITATIONS), ≥ 100 Trades bzw. ≥ 60 Monatsentscheidungen im Train-Abschnitt.
2. Primärziel: robuster Netto-CAGR (EUR) bei Max. Drawdown ≤ 20 % (Sensitivität 10/30 %), positiv in Train **und** Validierung, nach Kostenstress noch positiv.
3. Muss die passende Null-Strategie bzw. ACWI risikoadjustiert schlagen; sonst „kein belastbarer Vorteil“.
4. Bei ähnlichen Ergebnissen: einfachere, billigere Strategie.

## 8. Was dieses Protokoll ausdrücklich nicht erlaubt

Rasterweise Parametersuche; nachträgliches Hinzufügen von Filtern nach Einsicht in Train-Ergebnisse ohne neue Protokoll-Version und Registereintrag; jeder Blick auf 2022–2026 vor Phase E; synthetische 4H-/Earnings-Reihen als Ersatz für echte Daten.
