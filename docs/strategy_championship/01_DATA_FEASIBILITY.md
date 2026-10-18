# 01 — Daten- und Machbarkeitsinventar (Phase A)

**Stand:** 18.10.2026 · Keine Daten gekauft oder heruntergeladen. Preise externer Anbieter sind **grobe, unverifizierte Größenordnungen** aus allgemeinem Wissen — vor jeder Entscheidung beim Anbieter prüfen.

## 1. Was heute tatsächlich vorhanden ist

| Datenart | Quelle im Code | Tiefe / Auflösung | Point-in-Time? | Bemerkung |
|---|---|---|---|---|
| Tageskerzen Aktien | Yahoo (`yfinance`, `auto_adjust=True`) | je nach Wert 10–30+ J., täglich | nein (bereinigt, Historie wird nachträglich korrigiert) | kostenlos, inoffizielle Schnittstelle, Nutzungsbedingungen von Yahoo erlauben keine kommerzielle Nutzung; Rate-Limits. |
| Universum | Yahoo-Screener (heute) | nur aktueller Stand | **nein** → Survivorship-Bias | 5.870 Aktien ≥ 2 Mrd. USD (US/EU/Asien). |
| Delistings | — | — | — | **nicht vorhanden**. |
| Stundenkerzen | Yahoo 60 Min. | ~730 Tage | ja (abgeschlossene Kerzen) | daraus 4H gebaut (4er-Gruppen je Tag). 1-Min.-Daten nur ~7–30 Tage. |
| Börsenwert, Sektor | Yahoo `info` | nur heute | nein | Sektor bei vielen US-Werten leer. |
| Earnings | Yahoo `info` | nur nächster Termin | nein | keine Historie, keine Überraschungen. |
| Fundamentaldaten | — | — | — | nicht vorhanden. |
| ETFs (US) | Yahoo | SPY ab 1993, ACWI ab 2008, Sektor-SPDR ab 1998 | bereinigt ≈ Total Return in USD | in `grandtest.py`, `etf*.py` genutzt. |
| UCITS-ETF | Yahoo (`SPYI.DE`) | ab 2011, Datenreihe teils unzuverlässig (`etfextra.py`) | — | — |
| FX | Yahoo (`EURUSD=X` u. a.) | ab ~2003 | ja | in Backtests bisher **nicht** genutzt (statische Tabelle). |
| VIX, Zinsen | Yahoo `^VIX`, `^IRX` | lang | ja | — |
| Insider US | SEC EDGAR Form 4 (`insider.py`), OpenInsider (`grandtest.py`) | EDGAR ab 2003, mit Meldezeitpunkt | **ja** | kostenlos, offiziell. |
| Insider DE | BaFin-CSV (`bafin.py`) | aktuell | teils | — |
| Makrotermine | Fed/EZB/BLS, Forex Factory (`macro.py`) | aktuell + 14 Tage | — | keine Historie. |
| Turbo-Produktdaten | onvista API (`site/index.html`, `tools/turbo_live.mjs`) | nur aktuell | — | **keine** historischen Turbo-Kurse. |
| Brokerkosten | Annahmen im Code | — | — | 0,99 €/Order (Scalable Free), Spread 0,05–0,15 %, Finanzierung 5 % p. a. — nicht mit echten Abrechnungen verifiziert. |
| Short-Leihe | — | — | — | nicht vorhanden; für Privatanleger bei Scalable Aktien-Leerverkauf nicht verfügbar. |

## 2. Realistische zusätzliche Quellen (nicht beauftragt)

| Quelle | Inhalt | Kosten (grob, unverifiziert) | Nutzen |
|---|---|---|---|
| SEC EDGAR (XBRL „companyfacts“, Filing-Index) | US-Fundamentaldaten ab ~2009 **mit Einreichungsdatum**, 8-K-Termine | kostenlos | Point-in-Time-Quality und Earnings-Proxy (SUE aus EPS-Reihe) für US — mit erheblichem Aufbereitungsaufwand. |
| Kenneth-French-Datenbibliothek | Faktor-Renditen (Markt, Size, Value, Momentum, Branchen) US und Developed | kostenlos | Residual-Momentum, Benchmarks. |
| Norgate Data | US/AU-Aktien **inkl. Delistings**, historische Index-Mitgliedschaften | einige hundert USD/Jahr | survivorship-freie US-Tagesdaten — größter Qualitätsgewinn pro Euro. |
| Sharadar (Nasdaq Data Link) | US-Kurse inkl. Delistings + PIT-Fundamentaldaten | einige hundert USD/Jahr aufwärts | Survivorship + Quality in einem. |
| EODHD / FMP / Polygon / Tiingo | weltweit bzw. US, teils mit Delistings, Earnings, Intraday | ca. 20–200 USD/Monat je Paket | breitere Abdeckung; Delisting-Qualität je Anbieter prüfen. |
| Emittenten-/Börsendaten zu Turbos | historische Turbo-Preise | meist nicht frei verfügbar | ohne sie nur Modell-Turbos. |

## 3. Querschnittsrisiken (für alle Strategien)

| Risiko | Lage heute | Folge |
|---|---|---|
| Survivorship / Delistings | nicht abgedeckt | absolute Renditen zu hoch; Reversal-/Value-artige Strategien stärker betroffen als Trendfolge. |
| Splits/Dividenden | bereinigt (Yahoo) | Renditen ok, exakte Orderlevels leicht verzerrt; Dividenden als Total Return enthalten. |
| Adjusted vs. handelbar | nur bereinigt | für Stops/Limits kleine Abweichungen. |
| Währung | ignoriert (statisch) | EUR-Anleger-Rendite falsch, v. a. US/Asien. |
| Zeitzonen | Tageskerzen je Heimatbörse | Kombination US/EU/Asien am selben Kalendertag ungenau. |
| Sektor historisch | nicht vorhanden | Branchen-Neutralisierung nur mit heutiger Zuordnung bzw. ETF-Proxys. |
| Earnings-Zeitpunkte | nicht vorhanden | kein Earnings-Filter, kein PEAD. |
| Kosten | Annahmen | Sensitivität nötig; Kleinkapital-Effekt (Gebühr je Order) dominant. |
| Short-Borrow | nicht vorhanden / nicht handelbar | Pairs nur theoretisch. |
| Vorbelastete Zeiträume | 2024–26 mehrfach genutzt | kein sauberer historischer Holdout für S01 und alles, was auf denselben Stichproben gesucht wurde. |

## 4. Machbarkeitsmatrix der 18 Kandidaten

Legende Machbarkeit: **A** = mit vorhandenen Gratisdaten testbar (Survivorship-Label `DATENBESCHRÄNKT`) · **B** = testbar mit Proxy oder größerem Aufbau aus Gratisquellen · **C** = valide nur mit Kaufdaten · **X** = mit verfügbaren Daten/Produkten **NICHT VALIDE TESTBAR**.
Aufwand: S < 1 Tag, M 1–3 Tage, L > 3 Tage (Implementierung + Tests, ohne Rechenzeit).

| ID | Strategie | Mindestdaten | Vorhanden | PIT / Delistings | Hauptrisiken | Machbarkeit | Aufwand | Bemerkung |
|---|---|---|---|---|---|---|---|---|
| S01 | Kairo Deep Reversal (1D) | Tageskerzen 10 J., Universum | ja | nein / nein | Survivorship (stark für Reversal), vorbelastete Prüfjahre | **A** | S (Code existiert) | Baseline einfrieren = heutiger Code-Stand 9624040. |
| S01-4H | Kairo 1D + 4H | Stundenkerzen ≥ 5 J. | nur ~2 J. | ja / nein | sehr kurze Historie, eine Marktphase, vorbelastet | **B, nur EXPLORATIV** | S | Längere 4H-Historie nur mit Kaufdaten (Intraday-Anbieter) → dann C. |
| S02 | Momentum + Trend-Pullback | Tageskerzen | ja | nein / nein | Survivorship (mäßig) | **A** | S–M | `trend.py` als Ausgangspunkt (Trend-Rücksetzer). |
| S03 | Quality Momentum Reversal | Kurse + PIT-Fundamentaldaten | nein | — | Look-ahead bei Quality | **B** (US via EDGAR) / **C** | L | Ohne PIT-Daten nur Preis-Quality-Proxy (Volatilität, Drawdown-Historie) → als Proxy kennzeichnen. |
| S04 | Industry-Adjusted Reversal | Kurse + historische Branchenzuordnung | teils (heutiger Sektor, Sektor-ETFs) | nein | Branchenwechsel, leere Sektoren | **B** | M | US: Sektor-SPDR als Branchen-Benchmark; EU/Asien grob. |
| S05 | Cross-Sectional Momentum | Tageskerzen, Monats-Rebalance | ja | nein / nein | Survivorship, Momentum-Crashs | **A** | S–M | Literaturbaseline; teils in `grandtest.py` (Top-10-Aktien). |
| S06 | Residual Momentum | Kurse + Faktorrenditen | Kurse ja, Faktoren frei (French) | Faktoren ja | Schätzfehler, Region-Mismatch | **B** | M | US sauberer als EU/Asien. |
| S07 | Risk-Adjusted Momentum | Tageskerzen | ja | nein / nein | wie S05 | **A** | S | Variante von S05 — nicht als unabhängiger Beweis zählen. |
| S08 | Breakout + Volatility Expansion | Tageskerzen + Volumen | ja | nein / nein | Survivorship gering–mäßig, Gap-Fills | **A** | S–M | — |
| S09 | Volatility Contraction Breakout | Tageskerzen | ja | nein / nein | Familie S08 | **A** | S | als Unterfamilie von S08 führen. |
| S10 | Earnings Momentum / PEAD | historische Earnings-Termine + Überraschung (+ Uhrzeit) | **nein** | — | Look-ahead, falsche Termine | **B** (US: SUE aus EDGAR, Proxy) / **C** (Konsensdaten) | L | Ohne Termin-Historie **nicht valide**; keine Pseudo-Earnings. |
| S11 | Short-Term Mean Reversion | Tageskerzen (RSI2 etc.) | ja | nein / nein | Kosten-/Spread-Sensitivität, Survivorship stark | **A** | S | Kostenstress Pflicht (viele Trades, kleine Gewinne). |
| S12 | Multi-Factor Momentum | Kurse + PIT-Fundamentaldaten | nein | — | Look-ahead | **B** (US) / **C** | L | nur Momentum-Teil mit A-Daten. |
| S13 | Time-Series Momentum / Trend | Tageskerzen Aktien/ETFs | ja (ETFs lange Historie) | ETFs weitgehend unkritisch | Trendphasen-Abhängigkeit | **A** | S | Schon Phase B als Referenz; auf ETFs fast survivorship-frei. |
| S14 | Relative Strength + Sektorrotation | Sektor-ETFs, Branchenzuordnung | US-Sektor-ETFs ja | ETFs ja | nur US sauber | **A** (US-ETF-Ebene) / **B** (Aktien darin) | M | — |
| S15 | Gap-/Intraday-Reversal | Intraday-Kurse mit Zeitstempel, Spreads | 60-Min. 2 J., keine Spreads | — | Fills unrealistisch | **X** (mit Gratisdaten) / **C** | L | Für Privatanleger mit 0,99-€-Orders zusätzlich kostenkritisch. |
| S16 | Dual Momentum / ETF-Rotation | ETF-Total-Return | ja (US-ETFs, lange) | weitgehend | UCITS-Verfügbarkeit/Steuern | **A** | S | taktischer Vergleich zum ETF-Kern; teils in `grandtest.py`/`etftest.py`. |
| S17 | Pairs Trading | Kurse + Leihe/Borrow-Kosten + Short-Möglichkeit | Kurse ja, Borrow nein | — | Short für Privatkunde nicht handelbar | **X** (realistisch) | L | Nur theoretische Variante ohne Borrow möglich → nicht entscheidungsfähig. |
| S18 | Event-Driven (ein Ereignistyp) | zeitgestempelte Ereignisse | US-Insiderkäufe (EDGAR Form 4) ja | **ja** | Meldeverzug, Kleinwerte | **B** | M–L | Vorschlag: Insiderkäufe (Cluster-Käufe) als einziger Ereignistyp; Survivorship wie oben. |

**Zusammenfassung:** Mit Gratisdaten valide (mit Survivorship-Label): S01, S02, S05, S07, S08, S09, S11, S13, S14 (ETF-Ebene), S16. Mit Gratisquellen und Aufbau: S03/S12 (nur US, EDGAR), S04, S06, S10 (Proxy), S18. Nicht valide: S15, S17. 4H nur explorativ.

## 5. Rechenressourcen

- Bisherige Läufe: 40 parallele GitHub-Actions-Jobs × bis 5 Std. (öffentliches Repo → Standard-Runner ohne Minutenkosten). Ein voller 10-Jahres-Datensatz (Tag-für-Tag-`evaluate` für ~3.200 Aktien) ≈ 4–5 Std. Wandzeit.
- Engpass ist Yahoo (Rate-Limits/Sperren), nicht CPU/RAM.
- Für Phase C (Welle 1, 7–8 Strategien, wenige Varianten) realistisch: 1–3 Tage Rechenzeit verteilt, plus Implementierung.
- Speicher: Rohdaten müssen dauerhaft gesichert werden (Artefakte mit 90 Tagen Aufbewahrung oder Release-Assets bzw. ein Daten-Branch), sonst ist nichts reproduzierbar.

## 6. Engpässe in Reihenfolge

1. **Rohdaten der bisherigen Studien laufen am 26.10.2026 ab.**
2. **Kein survivorship-freies Aktienuniversum** (größter Einzelfehler für Reversal-/Mean-Reversion-Strategien).
3. **Kein unberührter Holdout** für S01/4H (2024–26 vorbelastet); 4H-Historie nur 2 Jahre.
4. **Keine PIT-Fundamental-/Earnings-Daten** (S03, S10, S12).
5. **Keine Ledger-basierte Portfolio-Engine** mit FX und Cash.
