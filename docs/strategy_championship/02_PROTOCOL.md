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

---

## Nachtrag v1.1 (18.10.2026, nach Gate B — vom Nutzer freigegeben: „Ja ich schalte alles frei“)

Gilt für **alle** Strategien und ihre Null-Strategien gleich; festgelegt vor jedem Lauf von Welle 1.

1. **Mindest-Positionsgröße:** Ein Kauf entfällt, wenn das freie Cash weniger als 50 % der geplanten Stückzahl zulässt
   (`min_fill = 0.5`). Grund: Rest-Positionen von 1–2 Stück mit fixer Gebühr (B2, 03 §6). S01-A/B werden mit v1.1
   nachgerechnet; die v1-Zahlen bleiben im Register.
2. **Ø R** wird damit über volle Positionen gerechnet; Hauptkriterium bleibt Netto-CAGR/Drawdown in EUR.
3. **1.000-€-Sleeve** entfällt im Screening (nur Kosten-Warnfall aus B2).
4. **Umsetzungsdetails Welle 1** (vorab, für alle Varianten + Null gleich): Ereignis-Signale nur „frisch“ (5 Vortage ohne
   Bedingung); höchstens 20 Kandidaten je Tag und Strategie (nach Ranking); Stop „n ATR“ = Schluss am Signaltag − n·ATR14;
   Terzile/Dezile je Kalendertag über die zulässigen Titel; S04-Markt = SPY (US) bzw. STOXX 600 (EU); S05: Top 10,
   je 9,9 % Gewicht, Verkauf bei Ausscheiden aus den Top 10; S13-Stock: Gewicht 99 %/max. Positionen, täglich die bis zu
   20 momentumstärksten Trend-Titel als Kandidaten. Null je Variante: gleiche Kandidatenzahl je Tag, zufällige zulässige
   Titel desselben Tages, Stop/Ausstieg nach derselben Regel, zufällige Reihenfolge; 200 Seeds (5.000 €, 1 % bzw. Gewicht).
5. Kostenpflichtige Daten bleiben **ohne Einzelfreigabe** ausgeschlossen (Anbieter + Preis werden vorher vorgelegt).

---

## Nachtrag v1.2 — Welle 2 (18.10.2026, nach Zwischenbericht Welle 1; Nutzer: „Ja weiter mit A“)

Registriert **vor** dem ersten Lauf. Gleiche Daten, Kosten, Kapital, Mindestgröße, Kennzahlen und Null-Logik wie v1.1;
nur Train 2008–2016. Ziel danach: Validierung 2017–2021 **einmal gemeinsam** für alle Finalisten beider Wellen.

| ID | Variante(n) | Einstieg / Ausstieg | Ranking | Null |
|---|---|---|---|---|
| **S06-P** | Residual-Momentum (**Proxy**: nur Marktfaktor SPY bzw. STOXX 600, Regression über 36 Monate; Score = Σ Residuen Monat −11…−1 / Std der Residuen) | Top 10 je Monatsende, 9,9 % je Titel, Verkauf bei Ausscheiden | Score | 10 zufällige zulässige Titel monatlich |
| **S07** | A: 12-1-Momentum / Volatilität 1 J. · B: 6-1 / Volatilität 6 M. | wie S06-P | Score | wie S06-P |
| **S09** | A: 20-T.-Spanne (Hoch−Tief)/Schluss ≤ 10 % · B: ATR10/ATR50 < 0,6; jeweils Schluss > 20-T.-Hoch, Volumen > 1,5 × Ø50, Schluss > EMA200 | nächste Eröffnung; Stop = 20-T.-Tief − 0,25 ATR; Ausstieg Schluss < 20-T.-Tief (Signal) oder Tag 60 | Volumenanstieg | gleiche Anzahl je Tag, zufällige zulässige Titel, gleiche Stop-/Ausstiegsregel |
| **S14** | US-Sektor-ETFs (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY): A: Top 3 nach 6-M.-Rendite · B: Top 3 nach 12-1 | monatlich, je 33 %, Verkauf bei Ausscheiden | Rendite | 3 zufällige Sektoren monatlich |
| **S16** | A: Dual Momentum SPY vs. EFA (12 M.), absolut gegen BIL, sonst SHY · B: Top 1 aus SPY/EFA/QQQ, absolut gegen BIL, sonst SHY | monatlich, 99 % | Rendite | 1 zufälliger ETF der Auswahl monatlich |

ETF-Strategien handeln US-ETFs (USD, FX zum Tageskurs) als **Proxy** für UCITS-Gegenstücke (Kosten/Steuern dort anders).

**Nicht getestet in Welle 2** (Daten fehlen bzw. Aufbau außerhalb des Rahmens, ehrlich ausgewiesen statt Ersatzdaten):
S10 Earnings-Drift (keine historischen Termine/Überraschungen), S12 Multi-Faktor (keine zeitpunktgenauen Fundamentaldaten),
S18 Insider-Cluster-Käufe (EDGAR-Form-4-Historie müsste erst aufgebaut werden — möglich, eigener Schritt mit Freigabe).
S15/S17 bleiben **NICHT VALIDE TESTBAR**.

---

## Nachtrag v1.5 — Nutzer-Spezifikationen S19 und S20 (18.10.2026)

Vom Nutzer exakt vorgegeben (Chat 18.10.2026), **keine** Parametersuche. Da nichts an Train-Ergebnissen ausgewählt wird,
werden beide **im selben Lauf** auf Train (2008–2016) und — als ihre einmalige Validierung — auf 2017–2021 gerechnet.
Bestehensregeln wie `08_VALIDATION_PLAN.md` (Bezug 5.000 € und 20.000 €). Holdout bleibt versiegelt.

**S19 Hybride Mean Reversion** (nur US-Aktien, weil Fundamentaldaten nur aus EDGAR):
1. Regime: S&P 500 (^GSPC) Schluss > EMA200 → 1 % Risiko; sonst 0,5 % und höchstens 2 offene Positionen.
2. Qualität: Marktkapitalisierung ≥ 10 Mrd. USD **und** operative Marge > 0. *Ersatz:* EDGAR `EntityPublicFloat` ≥ 10 Mrd. USD
   (Streubesitz-Wert aus dem letzten 10-K, ≤ 18 Monate alt; konservativ, da ≤ Marktkapitalisierung) und operatives Ergebnis /
   Umsatz des letzten veröffentlichten Geschäftsjahrs > 0 (ohne operatives Ergebnis: Jahresüberschuss). Nur Werte mit
   Veröffentlichungsdatum ≤ Handelstag.
3. Branche: 3-Tage-Rendite der Aktie < 3-Tage-Rendite ihres Sektor-ETFs (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY;
   *Zuordnung über den SIC-Code*, Telekom/Medien → XLK, Rest → SPY).
4. Signal: Schluss ≤ EMA20 − 2,5 × Std20 (Schlusskurse, 20 Tage) **und** Volumen-Erschöpfung: die letzten 3 Tage schlossen
   jeweils tiefer (C_t < C_t−1 < C_t−2 < C_t−3) und V_t < V_t−1 < V_t−2.
5. Auslöser H4: *Ersatz Tageskerze* (keine historischen 4-Std.-Daten): an einem der 5 Folgetage schließt eine Kerze grün
   (Schluss > Eröffnung) **und** über dem Hoch der letzten roten Kerze → Kauf zur nächsten Eröffnung.
6. Stop = tiefstes Tief seit dem Signaltag („Panik-Tief“) − 0,5 × ATR14. Ziel = erste Berührung der EMA20 (EMA des Vortags).
   CRV ≥ 2 am Auslösetag (Ziel − Schluss ≥ 2 × (Schluss − Stop)). Kein Zeit-Ausstieg.
   Ranking: stärkste Überdehnung (C − EMA20)/Std20.
   Null: gleiche Anzahl je Tag, zufällige US-Titel aus demselben Qualitäts-Pool, die unter ihrer EMA20 liegen; Stop = Tagestief
   − 0,5 ATR, Ziel EMA20, gleiche CRV-Prüfung und gleiches Regime.

**S20 Prozyklische Trendfolge / VCP** (alle Titel des Universums):
1. Kein neuer Kauf, wenn ^GSPC < EMA200.
2. Schluss > EMA50 > EMA200.
3. Bollinger-Bandbreite (20, 2) = (oben − unten)/Mitte < SMA20 der Bandbreite **und** Schluss höchstens 1,5 % von der EMA50
   entfernt **oder** in der Zone 50–61,8 % Retracement zwischen 50-T.-Hoch und 50-T.-Tief (± 1,5 %).
4. Auslöser H4: *Ersatz Tageskerze*: an einem der 5 Folgetage Schluss > EMA20 × 1,01 („signifikant“ = 1 %) **und**
   Volumen > SMA20 des Volumens, Regime weiterhin positiv → Kauf zur nächsten Eröffnung.
5. Stop = Kaufkurs − 1,5 × ATR14. Ab Hoch ≥ Kaufkurs + 2 × ATR14: Stop auf Einstand, danach täglich unter das Vortagestief
   nachgezogen (*Ersatz* für „neue H4-Tiefs“). Kein festes Ziel, kein Zeit-Ausstieg. Risiko 1 % des Gesamtkapitals.
   Ranking: Volumen / SMA20 des Volumens. Null: zufällige zulässige Titel am selben Tag, gleiche Stop-/Trailing-Regel.

Echte H4-Auslöser sind mit Gratisdaten nur für ≈ 2 Jahre verfügbar (liegt im versiegelten Holdout) → **nur vorwärts im
Papier-Handel** prüfbar. Max. offene Positionen 5 (5.000 €) bzw. 10 (20.000 €). Kosten und Mindestgröße wie v1.1.

### Nachtrag v1.6 — Datenrealität S19 (18.10.2026, vor dem ersten Lauf)

SEC EDGAR verweigert Abrufe aus GitHub Actions und aus dieser Umgebung (HTTP 403 für alle Header-Varianten, Diagnose im Release
`research-edgar-*`). Zeitpunktgenaue Fundamentaldaten sind damit **nicht verfügbar**. S19 wird deshalb in zwei offen
gekennzeichneten Varianten gerechnet:

- **S19-PIT:** Größe zeitpunktgenau über Ø-Dollarvolumen 20 T. ≥ 100 Mio. USD (Ersatz für ≥ 10 Mrd. Marktkapitalisierung).
- **S19-TODAY:** heutige Marktkapitalisierung ≥ 10 Mrd. USD (Stand 16.10.2026) — **Rückschaufehler**, nur zum Vergleich.
- Operative Marge > 0: **NICHT UMGESETZT** (keine historischen Daten).
- Branche: heutige Yahoo-Branche → Sektor-ETF (Real Estate → XLF, Communication Services → XLK, da XLRE/XLC 2008 nicht existierten).

Vorab-Befund aus dem Funktionstest (Train, ohne Branchen-Datei): von 2,08 Mio. Titel-Tagen erfüllen 64 alle Tagesfilter; 39 davon
lösen den Tageskerzen-Ersatz des H4-Triggers aus, **keiner** erfüllt danach CRV ≥ 2 (Kurs ist beim Auslösen schon nahe der EMA20).
Der Tageskerzen-Ersatz ist für S19 daher **nicht geeignet**; ein echter Test braucht 4-Std.-Daten (nur vorwärts im Papier-Handel).

---

## Nachtrag v1.7 — S19-Varianten (18.10.2026, vor dem Lauf; Nutzer: „Ja beides umsetzen!“)

Anlass: externe Kritik „S19 zu streng“. **Nur Train 2008–2016**, nur zur Orientierung (EXPLORATIV); Validierung/Holdout
werden dafür nicht angefasst. Entscheidung fällt im Papier-Test (echter H4-Auslöser), nicht in diesem Lauf.

| Variante | Überdehnung | Volumen | sonst |
|---|---|---|---|
| S19 (Original) | ≥ 2,5 Std unter EMA20 | V_t < V_t−1 < V_t−2 | wie v1.5 |
| S19-A | ≥ 2,0 | streng sinkend | wie v1.5 |
| S19-B | ≥ 2,5 | an mindestens 2 der letzten 3 Tage gesunken (V_t<V_t−1, V_t−1<V_t−2, V_t−2<V_t−3) | wie v1.5 |
| S19-C | ≥ 2,0 | mindestens 2 von 3 | wie v1.5 |

Je Variante zwei Einstiegsarten: (1) Tageskerzen-Ersatz des H4-Auslösers wie v1.5, (2) **ohne Auslöser**: Kauf zur nächsten
Eröffnung nach dem Signaltag, CRV ≥ 2 am Signaltag (Ziel EMA20, Stop Signaltag-Tief − 0,5 ATR) — misst, ob das Tages-Setup
selbst etwas taugt. Größe: S19-PIT (Ø-Dollarvolumen ≥ 100 Mio. USD) und S19-TODAY (heutige Marktkap. ≥ 10 Mrd., Rückschaufehler).
Kennzahlen: Signale/Jahr, davon CRV ≥ 2, Trades/Jahr, Ø R netto, Trefferquote, Depot 2.000 € und 20.000 € (Basis + Stress bei 2.000 €).
Papier-Test: S19-B und S19-C laufen zusätzlich zum Original als eigene Depots (je 2.000 €).


## Addendum v1.8 (18.10.2026) – Schattenbuch im Papier-Test

- paper/shadow.py verfolgt ab 19.10.2026 jedes S19-Familien-Signal (gesammelt mit Variante C; Zugehörigkeit zu S19/B/C je Signal gespeichert) und jedes S20-Signal mit echten 4H-Kerzen, unabhängig von den Depots.
- S19: Einstieg „4h“ (Auslöser wie Depot, CRV gespeichert, nicht gefiltert) und „frueh“ (nächste Eröffnung, Stop Signaltag-Tief − 0,5 ATR). Ausstiege parallel: EMA20-Ziel, 5 Tage, 10 Tage (alle mit Stop; Notausstieg 40 Tage).
- S20: Ausstiege Nutzerregel (Einstand ab +2 ATR, dann nachziehen), 5 Tage, 10 Tage.
- Auswertung vorab festgelegt: Mindest-CRV {alle, 1, 1,5, 2} × Ausstieg; Kennzahl Ø R netto (Stückzahl 2.000-€-Depot, 1 % Risiko). Frühestens ab 30 Trades je Feld; Entscheidung zusammen mit dem Nutzer. Keine weiteren Parameter.
- Plan für Phase 2 (Hybrid Trend + Mean Reversion): 15_HYBRID_PLAN.md.


## Addendum v1.9 (18.10.2026, vor dem Lauf) – Welle 3 Position-Trading, Kosten Scalable PRIME+

Nutzer-Auftrag: beste Strategie für den Trading-Teil (10–30 % des Kapitals), Haltedauer Wochen–Monate. Kostenmodell PRIME+
(ab 250 € Orderwert gebührenfrei, sonst 0,99 €; Stress 1,99 € + doppelter Spread + Slippage + FX). Train 2008–2016.
- Referenz T1-top5 (S07-B mit 5 Titeln). Kandidaten (keine weiteren): P1 52-Wochen-Hoch-Nähe, P2 Rangmittel Momentum + 52W,
  P3 T1-top5 mit Marktvolatilitäts-Skalierung (15 % Ziel, S&P-Vol 6 M.), P4 T1-top5 nur Titel über EMA200.
- Zufall: 5 zufällige zulässige Titel monatlich, 100 Seeds (5.000 €, PRIME+).
- Finalist nur, wenn: Stress-CAGR (5.000 €) > T1-top5, p vs. Zufall ≤ 0,05, größter Rückgang höchstens 5 Prozentpunkte
  schlechter als T1-top5, Ergebnis ohne beste 1 % der Trades positiv. Sonst bleibt T1-top5 einziger Kandidat.
- Danach einmalige Validierung 2017–2021 für T1-top5 und ggf. einen Finalisten (zweiter Blick in die Validierung – wird
  als solcher gekennzeichnet). Holdout bleibt versiegelt.


## Addendum v2.0 (19.10.2026, vor dem Lauf) – Welle 4 Multi-Asset-Trendfolge (ETFs)

Grund: Endauswahl für den einmaligen Holdout soll alle gut belegten, mit Gratisdaten testbaren Familien enthalten.
Neue Daten: Zusatz-ETFs (etf_freeze.py, gleiche Spanne wie v1). Kandidaten (keine weiteren, Details c7_multiasset.py):
G1 Faber GTAA-5, G2 GTAA Aggressiv Top 3 aus 13 ETFs, G3 GEM (Antonacci), G4 Zeitreihen-Momentum 6 ETFs mit 1/Vol-Gewichten.
Kosten PRIME+ (Basis/Stress), Kapital 2.000/6.000/20.000 €, Zufall 100 Seeds (gleiche Anzahl zufälliger ETFs je Monat).
Finalist-Regel: auf Train p vs. Zufall ≤ 0,10 und Sharpe ≥ ACWI halten; höchstens zwei Finalisten (beste Sharpe) gehen
einmalig in die Validierung 2017–2021. Danach Endauswahl für den Holdout (max. 3 Strategien, inkl. S07-B Top 10, S16-B).


## Addendum v2.1 (19.10.2026) – Nutzer-Freigabe „FINALEN HOLDOUT FREIGEGEBEN“

Einmaliger Holdout 2022-01-01 … 2026-10-16, Plan unverändert aus 18/19 (keine Parameter-Änderung nach Öffnung):
- H1 S07-B Momentum 6-1/Vol Top 10 (monatlich) gegen 100 Zufalls-Depots (10 zufällige zulässige Titel) und gegen ACWI halten.
- H2 S16-B Dual Momentum SPY/EFA/QQQ → SHY gegen 100 Zufalls-Depots (zufälliger ETF derselben Auswahl) und ACWI halten.
- Kosten PRIME+ Basis und Stress; Kapital 2.000 / 5.000 / 10.000 € (Strategie allein), Gesamtsystem 20.000 € (ACWI + 20/30 %).
- Bestanden je Strategie: Stress-CAGR > ACWI halten (gleicher Zeitraum, gleiche Kosten) UND p vs. Zufall ≤ 0,05 (Bonferroni für 2).
- Ergebnis wird unabhängig vom Ausgang vollständig berichtet.
