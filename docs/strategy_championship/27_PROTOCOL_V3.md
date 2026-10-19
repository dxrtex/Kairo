# 27 — Vorregistriertes Protokoll v3.0: Fundamental-, Ereignis- und Insider-Strategien + 4H-Einstieg

**Erstellt:** 19.10.2026, **vor** jedem Lauf und vor Einsicht in irgendein Ergebnis dieser Strategien. Festgeschrieben durch
den Git-Commit dieser Datei; jeder Lauf nennt den Commit. Änderungen nur als v3.x mit Begründung im Register
(`04_EXPERIMENT_LOG.jsonl`). Auftrag des Nutzers (Chat 19.10.2026): die bisher „mangels Daten nicht testbaren“ Strategien
mit kostenlosen Daten testen (S03/S12 Qualität/Multi-Faktor, S10 Earnings-Drift, S18 Insider, 4H-Einstieg).

## 1. Daten (alle kostenlos, eingefroren als Entwurfs-Releases)

| Datensatz | Quelle | Release | Zeitpunktgenau? |
|---|---|---|---|
| Tageskerzen Aktien/ETFs/FX | Yahoo, **Datensatz v1** (unverändert, SHA-256 im Manifest) | `research-data-v1`, `research-etf-*` | Kurse ja; Universum nein |
| Bilanzen/GuV/Cashflow (XBRL) | SEC `companyfacts.zip` (Abruf 19.10.2026 über den PC des Nutzers, User-Agent mit Kontakt) | `research-sec-v3` | **ja** – je Wert das Einreichungsdatum (`filed`) |
| Einreichungen, 8-K-Items, Ticker→CIK, SIC | SEC `submissions.zip` | `research-sec-v3` | ja – `acceptanceDateTime` je Einreichung |
| Insider-Transaktionen Form 3/4/5 | SEC „Insider Transactions Data Sets“, 2006 Q1 – 2026 Q1 (Q2/Q3 2026 noch nicht veröffentlicht) | `research-sec-v3` | ja – `FILING_DATE` |
| Stundenkerzen (BID) | Dukascopy-Datafeed, US- (`…USUSD`) und DE-Aktien (`…DEEUR`), **ab Jan. 2017** (für Aktien gibt es dort keine früheren Daten) | `research-duka-v3` | ja |
| Aktiensplits | Yahoo (`Ticker.splits`), nur zur Umrechnung der Aktienanzahl | `research-splits-v3` (Workflow) | ja (Split-Datum) |

**Zeitpunkt-Regel (PIT):** Ein XBRL-Wert darf ab dem **ersten Handelstag nach** seinem `filed`-Datum verwendet werden
(Entscheidung nach Schluss dieses Tages, Ausführung zur nächsten Eröffnung) – die Uhrzeit der Einreichung ist in
`companyfacts` nicht enthalten, daher ein Tag Sicherheitsabstand. Je (Kennzahl, Periode) gilt der **zuerst gemeldete** Wert
(spätere Korrekturen/Restatements werden erst ab ihrem eigenen `filed`-Datum sichtbar und ersetzen dann den alten Wert).
8-K- und Insider-Ereignisse: ab der nächsten Eröffnung nach Annahme bzw. Einreichung (8-K vor 16:00 ET → Tag 0 = derselbe
Handelstag, sonst nächster Handelstag).

**Universum:** US-Aktien der eingefrorenen Liste (`universe_frozen_2026-10-16.csv`, ohne Toronto) mit CIK-Zuordnung über
`submissions` (heutiger Ticker → CIK). Tägliche Grundfilter wie bisher (Kurs ≥ 1 EUR-Gegenwert, Ø-Dollarvolumen 20 T.
≥ 5 Mio. USD, ≥ 300 Kerzen). Fundamental-Strategien nur US (EDGAR gibt es nur für US-Emittenten).

**Bias-Label:** `DATENBESCHRÄNKT (Survivorship)` für jedes Ergebnis: Universum = heute existierende Firmen ≥ 2 Mrd. USD;
pleitegegangene/übernommene Firmen fehlen bei den Kursen (EDGAR selbst enthält sie, sie sind aber nicht handelbar im
Datensatz). Wirkung: Value/Reversal/Insider-Käufe in gefallenen Titeln eher **zu gut**. Zusätzlich: XBRL-Pflicht kam
gestaffelt (große Firmen ab Mitte 2009, alle ab Mitte 2011) → 2010–2011 kleinere Abdeckung, wird je Jahr berichtet.

## 2. Zeiträume

| Abschnitt | Zeitraum (Signaldatum) | Rolle |
|---|---|---|
| Aufwärmen | 2009-01-01 – 2009-12-31 | nur Kennzahlen/Indikatoren |
| **Train** | 2010-01-01 – 2016-12-31 | Prüfung 1 (keine Parameterwahl – alle Regeln stehen hier fest) |
| **Validierung** | 2017-01-01 – 2021-12-31 | Prüfung 2 |
| Holdout | 2022-01-01 – 2026-10-16 | **bereits geöffnet (v2.1)** → nur **Hinweis**, kein Beleg |

Für die Kandidaten K1–K4 sind alle Abschnitte unberührt (nie zuvor gerechnet). Für die 4H-Nebenanalyse: Dukascopy beginnt
2017 → Prüfung auf 2017–2021; der frühere 4H-Test (Yahoo, Okt. 2024 – Okt. 2026) liegt im Holdout und ist vorbelastet.

## 3. Ausführung, Kosten, Kapital

- Engine: `engine.py` (Ledger, geprüft in `03_ENGINE_AUDIT.md`), Entscheidung nach Schluss, Ausführung zur nächsten Eröffnung,
  Mindestfüllung 0,5, Dividenden als Cash, alles in EUR (historische FX).
- **Kosten Scalable PRIME+ (Basis):** 0 € je Order ab 250 € Orderwert, sonst 0,99 €; gemessener Spread je Titel (wie v1.9).
  **Stress:** 1,99 €, doppelter Spread, 0,05 % Slippage je Seite, 0,1 % FX-Aufschlag je Seite.
- Kapital: **5.000 € (Hauptfall)** und 20.000 €. Monatsportfolios: 10 Titel × 9,9 %. Ereignis-Strategien: höchstens 10
  Positionen × 9,9 %, nur freie Plätze.

## 4. Kandidaten (genau vier, je eine Variante, keine Parametersuche)

Ränge = Perzentil-Rang je Monatsende über alle zulässigen US-Titel mit vorhandenen Werten. TTM = letzte vier Quartale
(Jahreswert + laufendes Geschäftsjahr bis heute − Vorjahreszeitraum gleicher Länge). Fundamentaldaten gelten als veraltet,
wenn die letzte 10-Q/10-K älter als 200 Tage ist → Titel nicht zulässig.

| ID | Name | Regel | Handel |
|---|---|---|---|
| **K1** | Quality + Earnings Momentum | Qualität = Mittel der Ränge von **GP/A** (TTM-Bruttogewinn ÷ Bilanzsumme; ohne Bruttogewinn: Umsatz − Herstellkosten) und **ROA** (TTM-Jahresüberschuss ÷ Bilanzsumme). Earnings Momentum **EM** = (Quartalsergebnis − Vorjahresquartal) ÷ Bilanzsumme (zuerst gemeldete Werte, Q4 = Geschäftsjahr − 9 Monate). Score = ½ Qualität + ½ Rang(EM). | Top 10 am letzten Handelstag des Monats, Kauf zur nächsten Eröffnung, Verkauf bei Ausscheiden |
| **K2** | Multi-Faktor Value/Quality/Momentum | Value = Mittel der Ränge von **E/P** (TTM-Jahresüberschuss ÷ Börsenwert), **B/P** (Eigenkapital ÷ Börsenwert; EK ≤ 0 → schlechtester Rang), **CF/P** (TTM operativer Cashflow ÷ Börsenwert). Quality wie K1. Momentum = Rang 12-1. Score = Mittel der drei Bausteine. Börsenwert = zuletzt gemeldete Aktienanzahl (`dei:EntityCommonStockSharesOutstanding`, sonst `us-gaap` Aktien im Umlauf) × Kurs, beide auf dieselbe Split-Basis umgerechnet (Yahoo-Splits). | wie K1 |
| **K3** | PEAD (Earnings-Drift) | Ereignis = 8-K mit **Item 2.02** (Quartalszahlen). Überraschung = Kursreaktion **EAR** = Rendite Schluss Tag −1 → Schluss Tag +1 minus SPY im selben Fenster (Tag 0 nach §1). Signal, wenn EAR ≥ **+5 %** und Titel zulässig; je Firma höchstens ein Signal je 30 Tage. Ranking: höchste EAR. | Entscheidung Schluss Tag +1, Kauf zur Eröffnung Tag +2, Verkauf zum Schluss von Handelstag 60, kein Stop |
| **K4** | Insider-Cluster-Käufe | Form 4, nicht-derivative Transaktion Code **P** (Kauf am Markt), Meldender ist Director oder Officer; Kaufwert = Stück × Preis. Cluster = **≥ 3 verschiedene** Insider kaufen mit Einreichung innerhalb von **30 Kalendertagen**, Summe **≥ 100.000 USD**. Signal am Einreichungstag des Kaufs, der das Cluster vollständig macht; je Firma höchstens ein Signal je 90 Tage. Ranking: höchste Kaufsumme. | Kauf zur nächsten Eröffnung, Verkauf zum Schluss von Handelstag 60, kein Stop |

**Zufall (Null) je Kandidat, 200 Seeds, 5.000 €, Basis-Kosten:** K1/K2: jeden Monat 10 zufällige Titel aus demselben zulässigen
Pool (mit Fundamentaldaten). K3/K4: an jedem Signaltag gleich viele zufällige zulässige US-Titel (mit CIK) mit derselben
Halteregel. p = (Anzahl Seeds mit CAGR ≥ Kandidat + 1) ÷ 201.

## 5. Benchmarks (gleiche Engine, gleiche Kosten, gleicher Zeitraum, 5.000 €)

1. **ACWI** kaufen und halten (EUR). 2. **Dual Momentum S16-B** (SPY/EFA/QQQ → SHY, monatlich, unverändert).
3. **70 % ACWI / 30 % Nasdaq-100 (QQQ)**, jährliches Rebalancing am ersten Handelstag (Umschichtung 0,1 % Basis / 0,2 % Stress).
US-ETFs dienen als Proxy für UCITS-Gegenstücke.

## 6. Deutsche Steuern (Szenario, deutlich gekennzeichnet)

Abgeltungsteuer 25 % + Soli 5,5 % = **26,375 %**, keine Kirchensteuer, **kein** Sparerpauschbetrag (vorsichtig; er steht meist
für andere Anlagen zur Verfügung). Einzelaktien: Kursgewinne bei Verkauf, Verluste nur mit Aktiengewinnen verrechenbar
(Aktientopf, Vortrag); Dividenden voll steuerpflichtig. Aktien-ETFs (ACWI, QQQ, SPY, EFA): **Teilfreistellung 30 %** auf
Gewinne, Ausschüttungen und Vorabpauschale (Basiszins 2018: 0,87 %, 2019: 0,52 %, 2020: 0,07 %, 2021–2022: 0, 2023: 2,55 %,
2024: 2,29 %, 2025: 2,53 %, 2026: 3,20 %; vor 2018 altes Recht → vereinfacht keine Vorabpauschale); Anleihe-ETF SHY: keine
Teilfreistellung. ETF-Verluste in den allgemeinen Topf. Steuer wird jährlich am Jahresende aus dem Depot bezahlt (als
anteilige Entnahme gerechnet); am Ende des Zeitraums Verkauf aller Positionen mit Steuer (Vergleich „nach Liquidation“).
Quellensteuer: vereinfacht voll anrechenbar (keine Zusatzlast).

## 7. Statistik und Bestehensregeln (je Kandidat, Hauptfall 5.000 €)

Familie = 4 Kandidaten → **Bonferroni: p ≤ 0,05 / 4 = 0,0125**.

Ein Kandidat **besteht** (→ Kandidat für den Papier-Test, kein echtes Geld vorher) nur, wenn **alle** gelten:
1. Stress-CAGR > 0 in **Train und Validierung**;
2. Stress-CAGR > ACWI (gleiche Kosten) in **Train und Validierung**;
3. p vs. Zufall ≤ 0,0125 (Basis-Kosten, durchgehender Lauf 2010–2021);
4. nach deutschen Steuern (Stress, 2010–2021, nach Liquidation) CAGR > ACWI nach Steuern;
5. Mindestumfang: ≥ 60 Monatsentscheidungen (K1/K2) bzw. ≥ 100 Trades (K3/K4) in Train.

Beschreibend (keine Bestehensregel): Vergleich mit S16-B und 70/30; Sharpe, Sortino, max. Rückgang, Rückgangsdauer,
Trefferquote, Ø Haltedauer, Umschlag, Kostenanteil, Beta zu ACWI; 20.000 €; Holdout 2022–2026 (Hinweis); Abdeckung der
Fundamentaldaten je Jahr. Ergebnisse werden **unabhängig vom Ausgang vollständig** berichtet.

## 8. Nebenanalyse N1 — 4H-Einstieg für Kairo-Signale (nicht Teil der Bonferroni-Familie)

- Signale: unveränderte Kairo-Treffer (S01, Release `research-fib-*`, 49.134 Treffer) für Titel mit Dukascopy-Stundenkerzen.
- 4H-Kerzen: Dukascopy-Stunden (BID) in die Börsenzeit des Titels (US 9:30–16:00 ET, DE 9:00–17:30 MEZ) gelegt, je Handelstag
  in 4er-Gruppen wie `h4study.to4h`; Preisniveau je Tag auf die Yahoo-Tageskerzen skaliert (Median-Verhältnis 5 Tage).
  Titel mit unplausiblem Verhältnis (Median-Abweichung > 2 %) werden ausgeschlossen und gezählt.
- **A (Referenz) Tages-Einstieg:** heutige Basis-Regel (5 Tage ≤ 1,5 ATR, Kauf zur nächsten Eröffnung in der Basis,
  Stop = Basistief − 0,25 ATR). **B (4H):** exakt die Live-Regel `h4live` „HB|RMBS“ (RSI zuletzt ≤ 40 und steigend, MACD-Kreuz,
  grünes MBI-X, Strukturbruch in derselben 4H-Kerze, Fenster 10 Handelstage, Kauf zur Eröffnung der nächsten 4H-Kerze,
  gleicher Stop). Ausstieg für **beide gleich**: Stop; ab Tag 10 Schluss < EMA20 → nächste Eröffnung; spätestens Tag 40.
- Kosten in R: voller Spread (US 0,10 %, DE 0,15 %) × Einstieg ÷ Risiko; Stress ×2 + 0,1 % Slippage.
- **4H gilt als besser**, wenn Ø R netto (Stress) von B > A **und** einseitiger Permutationstest der Mittelwertdifferenz
  (10.000 Permutationen, Seed 7) p ≤ 0,05 auf 2017–2021. Zusätzlich berichtet: Summe R je Jahr (Häufigkeit!), Trefferquote,
  Anteil der Signale mit 4H-Auslöser, 2022–2026 als Hinweis. Abschnitte mit < 30 B-Trades entscheiden nicht.

## 9. Was dieses Protokoll ausdrücklich nicht erlaubt

Weitere Varianten oder Schwellen nach Einsicht in Ergebnisse; Austausch von Kennzahlen; nachträgliche Universums- oder
Zeitraumänderungen; Ersatzdaten (z. B. heutige Fundamentaldaten) ohne Kennzeichnung. Fehler im Code dürfen behoben werden;
jede Behebung nach dem ersten Lauf wird im Register mit Grund und Auswirkung vermerkt, alle Läufe bleiben sichtbar.
