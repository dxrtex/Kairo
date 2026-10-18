# 00 — Repo- und Backtest-Audit (Phase A)

**Stand:** 18.10.2026 · **Branch der Prüfung:** `claude/aktienfinder-spec` = `origin/main` = Commit `9624040689d55beafa5ee49cc5e35280456e7f72` (15.10.2026), Arbeitsbaum sauber.
**Art der Prüfung:** Code gelesen, vorhandene Tests ausgeführt, GitHub-Actions-Läufe und Artefakte aufgelistet, Live-Zustand (Branch `kairo-data`) gelesen. **Kein** neuer Backtest, **kein** Datendownload, **keine** Änderung an App, Scanner oder Workflows.

Status-Labels: **GEPRÜFT** (Code/Artefakt selbst gelesen) · **BERICHTET** (Zahl steht nur in App-Konstanten, Docstrings oder Commit-Texten, nicht neu nachgerechnet) · **NICHT REPRODUZIERT** · **NICHT GEPRÜFT**.

---

## 1. Ist-Architektur (GEPRÜFT)

| Bereich | Dateien | Rolle |
|---|---|---|
| Daten | `backend/data_provider.py` | Yahoo Finance über `yfinance`, `auto_adjust=True` (dividenden-/splitbereinigte OHLC), SQLite-Cache. Stammdaten (`marketCap`, `sector`, nächster Earnings-Termin) nur **aktueller** Stand. |
| Universum | `backend/universe.py` | Yahoo-Screener je Land, Börsenwert ≥ 2 Mrd. USD (feste FX-Tabelle), ETFs/SPACs/Zweitlistings raus. Liste wird **bei jedem Lauf neu** erzeugt; aktuell 2.036 US + 917 EU + 2.917 Asien/Pazifik = **5.870** Aktien (`kairo-data:universe_*.csv`). |
| Indikatoren | `backend/indicators.py`, `backend/mbi.py` | EMA, RSI, MACD, ATR, Pivots (Pine-Script-Formeln), MBI-Port (AlgoAlpha). |
| Signal S01 | `backend/scanner.py`, `config.yaml` | 4 Grundfilter + 11 Setup-Kriterien (Abschnitt 2). |
| Score | `backend/scoring.py` | Bonuspunkte nur für volle Treffer (Ranking/Anzeige). |
| Trade-Plan | `backend/tradeplan.py`, `site/index.html` (`tp2Calc`) | Basis-Einstieg, Stop = Basistief − 0,25 ATR, Hebelwahl, Turbo-SL. |
| 4H-Setup | `backend/h4live.py`, `backend/push.py`, `.github/workflows/alerts.yml` | Live-Prüfung alle 30 Min. (Mo–Fr 6–21 UTC). |
| Live-Bilanz | `backend/live.py`, `backend/state.py`, Branch `kairo-data` | Signale seit 30.09.2026 gespeichert. |
| Backtest-Datenerzeugung | `backend/bilanz.py` (`scan_history`) | Tag-für-Tag-Neuberechnung von `scanner.evaluate()` je Aktie → Ereignisse mit Kurspfad (`px`). |
| Trade-Simulator | `backend/shortswing.py` (`simulate`, `_depot_real`, `_truth`) | Trade-Ebene auf relativen Kurspfaden, Depot-Simulation. |
| Weitere Studien | `h4study.py`, `exits.py`, `exitstudy10.py`, `nearstudy.py`, `capstudy.py`, `volstudy.py`, `grandtest.py`, `trend_study*.py`, `optimize.py`, `grade.py`, `etf*.py` | 37 Workflows, fast alle manuell (`workflow_dispatch`). |
| App | `site/index.html` (PWA, eine Datei) | Anzeige, Trade-Plan, Turbo-Rechner, Journal; Backtest-Ergebnisse als **hart codierte Konstanten** (`STRAT_BT`, `TP_EXP`, `GRPT`, Texte). |
| Tests | `backend/tests/` (63 Tests, alle grün am 18.10.2026), `tools/turbo_unit.mjs` (92 Prüfungen grün), `tools/app_smoke.py` (Browser) | — |
| Deploy | `scan.yml` (Abendscan + Pages + App-Test), `regression.yml` (Push auf `claude/**`) | Produktiv. |

## 2. Exakte S01-Regeln, wie sie heute im Code stehen (GEPRÜFT, `backend/scanner.py` + `config.yaml`)

**Grundfilter (zählen nicht zu den 11):** Börsenwert ≥ 2 Mrd. USD (aus aktuellem `marketCap`; *unbekannt = bestanden*), Ø-Dollarvolumen 20 T. ≥ 5 Mio. USD (feste FX-Tabelle), Kurs ≥ 1, ≥ 300 Kerzen.

**11 Setup-Kriterien (Tageskerzen, Stand Schlusskurs):**
1. `drawdown` — Rückgang vom höchsten Pivot-High (Länge 5) der letzten 20–180 Tage ≥ 12 %.
2. `no_crash` — kein Tagesverlust > 25 % in den letzten 10 Tagen.
3. `structure` — Schluss < EMA20 und < EMA50, EMA20 heute < EMA20 vor 5 Tagen.
4. `zone` — Fib-Variante: tiefstes Pivot-Low ≤ 120 T. vor H, Impuls ≥ 15 %, Schluss oder Tief der letzten 3 Kerzen in 0,618–0,79, nicht unter 0,886 · **oder** Support-Variante: ≥ 2 Pivots (± 3 %) der letzten 250 T. (ohne jüngste 5), ältester ≥ 15 T., Kurs −5 %/+3 % um Zonenmitte, kein Schluss > 7 % darunter in 5 T.
5. `flattening` — Spanne der letzten 10 Kerzen < 1,5 × ATR14 × √10 **oder** ≥ 2 lange untere Lunten (≥ 50 % der Spanne) in der Zone.
6. `rsi_div` — bullische RSI(14)-Divergenz klassisch (Tief T2 ≤ T1 × 1,01, RSI ≥ +3) oder versteckt; T2 ≤ 10 T. alt, T1 2–60 T. davor, Pivot-Länge 2.
7. `rsi_range` — RSI aktuell 28–48.
8. `macd_below0` — MACD-Linie und Signal < 0.
9. `macd_turn` — Kreuz ≤ 7 T. **oder** Histogramm < 0, ≥ 4 T. steigend und ≤ 25 % des 30-T.-Tiefs; Ausschluss bei Fehlsignal.
10. `mbi` — grünes MBI-X ≤ 15 Kerzen, rote Spitze über der Impulslinie, Rot jetzt ≤ 70 % der Spitze oder Histogramm grün, keine höhere Spitze seitdem.
11. `crv` — (Swing-High − Schluss) / (Schluss − Stop) ≥ 2,0, Stop aus Zone (0,886 bzw. L −1 % / Zonenunterkante −2 %, mind. 1 ATR).

**Treffer** = alle 11 + Grundfilter. Fast-Treffer = genau 1 fehlt; „MBI gelockert“ (10s) = nur MBI-Abklingen fehlt (`Result.mbi_soft`); 9/11 = Auswahl.
**Score** (`scoring.py`): Basis 40 + Boni; ändert die Signalmenge nicht.
**Ranking im Depot:** „ruhigste zuerst“ (niedrigste ATR %), max. 5 Positionen, max. 2 je Sektor (App).

**Ein-/Ausstieg (zwei Varianten produktiv):**
- *Tages-Strategie* (`tradeplan.py`, `shortswing.QRULE`): innerhalb von 10 Tagen nach Signal 5 Tage mit Spanne ≤ 1,5 ATR (Basis), Invalidierung (Tief der 10 Tage bis Signaltag) hält, Kauf zur nächsten Eröffnung **in** der Basis; Stop = Basistief − 0,25 ATR; Verkauf am Stop oder an Tag 20; kein Take-Profit; Risiko 1 %, kleinster passender Hebel.
- *4H-Top-Setup* (`h4live.py`): zusätzlich in **derselben abgeschlossenen 4H-Kerze** RSI zuletzt ≤ 40 und steigend, MACD-Kreuz ≤ 6 Kerzen, grünes MBI-X ≤ 6 Kerzen, Schluss über Hoch der 6 Vorkerzen; Fenster bis Tag s+10; Kauf zur nächsten 4H-Eröffnung; Ausstieg ab Tag 10 bei Tagesschluss < EMA20 (nächste Eröffnung), spätestens Tag 40; Stop wie oben.

## 3. 1D / 4H — Status (GEPRÜFT)

| Element | Status |
|---|---|
| 1D-Scanner S01 | **produktiv** (Abendscan, Signale gespeichert seit 30.09.2026). |
| 1D-Basis-Einstieg + Tag-20-Ausstieg | **produktiv** in App/Trade-Plan; historisch getestet (siehe 4). |
| 4H-Bestätigung + EMA20-Ausstieg | **produktiv seit 13./14.10.2026** (Push alle 30 Min.). Live: **2 Trades, beide offen** (`kairo-data:h4trades.json`). |
| 4H-Historie | Yahoo liefert 60-Min.-Kerzen nur ~730 Tage (`h4study.py` Z. 68). 4H-Kerzen werden **je Handelstag aus 4er-Gruppen von Stundenkerzen** gebaut (keine börsenoffizielle 4H-Session). Backtest-Fenster daher nur **≈ Okt. 2024 – Okt. 2026**. |
| Konsequenz | Jede 4H-Aussage ist **EXPLORATIV**: kurzer Zeitraum, eine Marktphase, Zeitraum identisch mit den mehrfach genutzten „Prüfjahren“. |

## 4. Frühere große Backtests (Rekonstruktion)

| Studie | Code | Daten | Zeitraum/Umfang (BERICHTET) | Ergebnisse (BERICHTET, Fundstelle) |
|---|---|---|---|---|
| Wahrheits-Test / „10-Jahres-Test“ | `shortswing._truth`, Workflow `shortswing.yml` | 2 Läufe à 40 Shards (`kurz-*`): Runs **38183381057** (11./12.10., Commit 9676f18) und **38263294012** (12.10., Commit 64614b4) | „2 Stichproben à ~3.200 Aktien, 2017 – Okt. 2026“ (App-Text `bilanzHtml`) | Depot +14,8 % / +15,0 % p. a., Prüfjahre 2024–26 +3,9 % / +18 %, max. Rückgang 35 % / 50 % (`STRAT_BT`, `site/index.html` Z. ~3610) · **Treffer ≈ Zufallstage mit gleichen Regeln** (App-Abschnitt „Was wir noch nicht wissen“) · zufällige statt „ruhigste zuerst“ Auswahl −1,4 % / −2,2 % p. a. |
| 4H-Test | `h4study.py`, Run **38442418788** u. a. (`h4variants`, `h4fine`, `h4robust`, `h4near`, `h4miss`, `h4exits*`) | Kairo-Treffer der beiden `kurz-*`-Läufe + Yahoo-Stundenkerzen | ~Okt. 2024 – Okt. 2026 | +0,39 / +0,54 R je Trade (4H) vs. +0,10 / +0,11 R ohne 4H; EMA20-Ausstieg +0,73 / +0,63 R (Docstring `h4live.py`). |
| Ausstiegs-Test 10 J. | `exitstudy10.py`, Run 38492967325 | `kurz-*` | Lern ≤ 2023 / Prüf 2024–26 | in App-Texten zusammengefasst. |
| Fast-Treffer-Test | `nearstudy.py`, Run 38476803913 | `kurz-*` | dto. | 10/11: −0,01 / +0,24 R; 9/11: −0,37 / −0,12 R (`GRPT`). |
| Kapital-Test | `capstudy.py`, Run 38422562916 | `kurz-*` | dto. | 900 €: −12 % bis Totalverlust; 3.000 €: +12 / +13 % p. a. (App-Tabelle). |
| Großer Strategie-Vergleich | `grandtest.py`, Runs 38404029058/38401711259 | Yahoo ETFs/Aktien, OpenInsider | lange ETF-Historie | im Code-Docstring: heutiges Universum (Survivorship), USD ohne FX. |
| Ältere Bilanz-Läufe (3/6 J.) | `bilanz.py`, `exits.py`, `optimize.py`, `grade.py` | Artefakte `bilanz-*` | 3–6 J. | `data/bilanz_backtest.json` (nur Zusammenfassung, im Repo). |

**Hinweis:** Run 38183381057 endete mit Status *failure* (Auswertungs-Job), die 40 Daten-Shards wurden aber hochgeladen und später von anderen Studien wiederverwendet.

## 5. Reproduzierbarkeit (GEPRÜFT)

| Punkt | Befund |
|---|---|
| Rohdaten | Die Ereignis-Dateien beider Stichproben (`kurz-0…39`, je 8–12 MB, gesamt ≈ 0,8 GB) liegen nur als Actions-Artefakte mit **14 Tagen Aufbewahrung**: **Ablauf 26.10.2026**. Danach sind die Grundlagen aller 10-Jahres- und 4H-Zahlen **unwiederbringlich weg**. Aus dieser Sandbox ist der Download gesperrt (HTTP 403); ein Workflow im Repo könnte sie sichern. |
| Ergebnis-JSONs | `kurzfrist-ergebnis`, `h4-test` u. a. (wenige KB) verfügbar bis Jan. 2027; nur Zusammenfassungen. |
| Code-Version | Je Lauf über `head_sha` eindeutig (z. B. 9676f18, 64614b4, a278328). |
| Neu-Berechnung | **Nicht bit-genau möglich:** Universum wird bei jedem Lauf frisch vom Yahoo-Screener gezogen (Zusammensetzung und Reihenfolge ändern sich täglich), Stichprobe = `random.Random(11).shuffle(...)` auf dieser Liste (`bilanz.py` Z. 304), Yahoo korrigiert/ändert Historien. Bestenfalls **näherungsweise** reproduzierbar. |
| Seeds | Depot-Simulation mit festen Seeds (11), Bootstrap Seed 3 — innerhalb eines Datensatzes deterministisch. |
| Fazit | Alle in der App genannten Backtest-Zahlen: **NICHT REPRODUZIERT** (in Phase A bewusst nicht neu gerechnet) und **nach dem 26.10.2026 ohne die Rohdaten nicht mehr reproduzierbar**. |

## 6. Inhaltliche Befunde zu den bisherigen Backtests

Priorität: 🔴 kritisch für Aussagekraft · 🟠 wesentlich · 🟡 begrenzt

1. 🔴 **Survivorship-Bias.** Universum = heute existierende Aktien ≥ 2 Mrd. USD. Pleiten, Übernahmen, abgestiegene Werte fehlen. Für ein Reversal-System („Kauf nach Rückgang“) besonders gefährlich: gerade die Rückgänge, die nie zurückkamen, fehlen. Im Code selbst eingeräumt (`grandtest.py` Docstring, App-Text „Pleite-Aktien fehlen“).
2. 🔴 **Börsenwert-Filter nicht zeitpunktgenau.** `scan_history` ruft `evaluate(df)` **ohne** `info` auf → `cap` gilt als „unbekannt = bestanden“; die Auswahl ≥ 2 Mrd. USD stammt aus dem heutigen Börsenwert (Look-ahead in der Universumsbildung).
3. 🔴 **Mehrfachtests auf denselben Daten.** Dieselben zwei Stichproben und dieselben „Prüfjahre“ 2024–26 wurden für Dutzende Varianten genutzt (Einstieg, Ausstieg, Ranking, Risiko, Hebel, 4H-Auslöser, Fenster, Feinregeln, MBI-Lockerung). Die Prüfjahre sind damit **vorbelastet**; es gibt **keinen unberührten Holdout**. Das 4H-Fenster (Okt. 2024 – Okt. 2026) liegt vollständig in diesem vorbelasteten Bereich.
4. 🔴 **„Zwei Stichproben“ sind nicht unabhängig.** 2 × ~3.200 aus ~5.900 Aktien desselben Universums überschneiden sich rechnerisch zu rund der Hälfte (Erwartungswert, nicht aus den Daten verifiziert) und teilen denselben Zeitraum und dieselben Marktschocks.
5. 🟠 **Signal vs. Regeln.** Der eigene Wahrheits-Test fand, dass Zufallstage mit denselben Ein-/Ausstiegsregeln etwa gleich viel brachten. Ein eigenständiger Vorteil der 11 S01-Kriterien ist damit **nicht belegt**; der Effekt liegt eher in Basis-Einstieg/Stop/Ausverkaufs-Timing.
6. 🟠 **Auswahlregel nach Ergebnis gewählt.** „Ruhigste zuerst“ wurde gewählt, nachdem die zufällige Auswahl Geld verlor (−1,4 / −2,2 % p. a.) — das zeigt starke Abhängigkeit von einer nachträglich gefundenen Regel.
7. 🟠 **Trefferquote ≠ Nettogewinn.** Ältere Bilanz (`bilanz.py`) zählte „Ziel 1 zuerst“; spätere Studien rechnen korrekt netto in R mit Kosten. Die alte Rechnung ohne Turbo-Kosten war deutlich geschönt (+32 % / +20 % p. a., App-Tabelle „geschönt“).
8. 🟠 **Turbo-Modell vereinfacht.** K.-o. = Einstieg × (1 − 1/Hebel), Finanzierung 5 % p. a., Spread 0,15 % — keine echten Produktpreise, kein Emittenten-Aufgeld, keine Handelspausen. Kein naives „× 10“, aber auch kein validiertes Produktmodell.
9. 🟠 **Depot-Simulation vereinfacht** (`_depot_real`): Haltedauer in Kalendertage umgerechnet (`n × 7/5`), Gewinn/Verlust erst beim Verkauf gebucht (Tageswert nur für Drawdown), keine Cash-Verzinsung, kein FX (alles in Aktienwährung ≈ EUR gerechnet), kein Orderbuch-Ledger.
10. 🟡 **Bereinigte Kurse** (`auto_adjust=True`): Stop-/Einstiegsniveaus in dividendenbereinigtem Kursraum; für Renditen korrekt, für exakte Ausführungslevels leicht verzerrt.
11. 🟡 **Statische FX-Tabelle** (2026er Kurse) für Liquidität/Börsenwert in allen Jahren.
12. 🟡 **Earnings:** nur der nächste künftige Termin bekannt → historisch kein Earnings-Filter, PEAD nicht testbar.
13. 🟡 **Sektor:** nur aktuelle Zuordnung (bei vielen US-Werten leer, z. B. NVDA in `universe_us.csv`).
14. 🟡 **Live-Bilanz ohne Aussagekraft:** Signale seit 30.09.2026 (inkl. Nachträgen; 987 Treffer-Signale bis 16.10.), 2 offene 4H-Trades.

Positiv (GEPRÜFT): Einstieg erst zur nächsten Eröffnung, Gap unter Stop → Verkauf zur Eröffnung, Stop und Ziel am selben Tag = Stop, Bootstrap über Handelstage, Kosten in Euro je Order, Lern-/Prüfjahre getrennt (wenn auch mehrfach genutzt), 4H nur abgeschlossene Kerzen live, Code für Live und Studie über Tests abgeglichen (`test_h4live.py::test_same_trades_as_study`).

## 7. Backtest-Engine (A4)

| Aspekt | Befund |
|---|---|
| Typ | Ereignis- bzw. pfadbasiert je Trade (`simulate`), dann Depot-Overlay (`_depot_real`). Kein voll ereignisgetriebener Portfolio-Simulator. |
| Fill-Regeln | Einstieg Folgetag-Eröffnung bzw. erste Eröffnung in der Basis; Stop untertags zum Stop, bei Gap zur Eröffnung; Ziel/Stop gleicher Tag = Stop. |
| Kapital | Risiko = Depotwert × Risikoanteil; Hebelwahl „kleinster passender“; max. offene Positionen; Einsatzprüfung gegen freies Kapital nur in der Hebel-Variante. |
| Ledger | Kein Order-/Fill-Ledger, keine Cash-Bilanz je Tag, Equity-Kurve nur Näherung. |
| Zeitrichtigkeit | Signale auf Schlusskurs, Handel ab Folgetag; 4H nur abgeschlossene Kerzen (live); Indikatoren ohne Zukunftsdaten (Tag-für-Tag-`evaluate` auf `df.iloc[:i+1]`). |
| Vorhandene Tests | 11 synthetische Tests für `simulate` (Gap, gleicher Tag, K.-o., Wochenende, Trailing, Basis …), 4 für `h4live`, 2 Live-Strategie. **Keine** Tests für Depot/Equity/Cash, Splits/Delistings, Zeitzonen, Teil-/Nichtausführung, unabhängige Zweitimplementierung. |
| Aufwand für fehlende Prüfungen | Ledger-basierter Depot-Simulator + synthetische Tests + Zweitimplementierung für Stichproben-Trades: ca. 2–4 Arbeitstage (Phase B3). |

## 8. Was in Phase A **nicht** geprüft wurde

- Kein Neu-Lauf irgendeines Backtests, keine Nachrechnung der App-Zahlen.
- Inhalt der `kurz-*`-Rohdaten (Download aus der Sandbox gesperrt), tatsächliche Stichprobengröße und -überschneidung.
- Exakte Eingabeparameter (`--n`, `--period`) der beiden Stichproben-Läufe (nur aus App-Text: ~3.200 Aktien, 2017–2026).
- Steuerliche Annahmen, Brokerkonditionen im Detail, Lizenzbedingungen der Datenquellen (nur grob, siehe 01).
