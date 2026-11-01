# Kairo Next Level – Bestandsaufnahme und Umsetzung (01.11.2026)

Branch `claude/next-level` (Basis: `main` 69d6707). Kein Pull Request, kein Merge – beides nur mit ausdrücklicher Freigabe.

**Unverändert geblieben:** die Regel B60 (`backend/rule.py`), die 11 Scanner-Pflichtkriterien (`backend/scanner.py`,
`config.yaml`), die Papier-Depots (`paper/kairo.py`, `paper/run.py`, `paper/core.py`), Dual Momentum, Journal- und
Depotdaten im Browser (nur Anzeige geändert, kein Speicherformat). E2 bleibt ein getrennter Forschungskandidat.
`git diff origin/main -- backend/scanner.py backend/rule.py config.yaml paper/kairo.py paper/run.py paper/core.py
backend/shortswing.py` ist leer.

---

## A. Bestandsaufnahme (priorisiert)

| # | Thema | Nutzen | Aufwand | Risiko | Dateien | Abnahmekriterium | Stand |
|---|---|---|---|---|---|---|---|
| 1 | Veraltete Forschungsaussagen (+0,14 R, ≈ +7 % p. a., −25 %) in App, KI-Seite, Live-Bilanz, Forschungsseite | hoch – die App versprach mehr als die korrigierte Engine zeigt | klein | gering | `site/index.html`, `backend/aipage.py`, `backend/trackpage.py`, `site/research/index.html` | alle Zahlen aus einer Quelle (`RESEARCH`) bzw. gleichlautend: 13.241 Trades, +0,12 R normal / −0,03 R Stress, Depot +6 % / −1,2 %, ETF +9 % | **erledigt** |
| 2 | Quartalszahlen: Status (vorläufig/bestätigt/korrigiert), „in Kairo seit“, Latenz | mittel – man sieht, ob eine Zahl frisch und verlässlich ist | klein | gering | `backend/earnings.py`, `backend/earnfast.py`, `tools/earn_review.py`, `site/index.html` | Status in der Ansicht; Latenz (Median/90 %) in der Wochenbilanz | **erledigt** |
| 3 | Insider: Abdeckung je Aktie, Meldedatum, Signalqualität | hoch – „nur 5–10 Aktien“ war unklar; unbekannte Historie zählte als gezielt | mittel | gering | `backend/insider.py`, `site/index.html` | Abdeckung geprüft/Zeitlimit/Fehler/keine Quelle sichtbar; „Routine unbekannt“ zählt nicht als gezielt | **erledigt** |
| 4 | Datenstatus mit Zeitstempel je Quelle | mittel – Ausfälle sofort sichtbar | klein | gering | `site/index.html` | Einstellungen → Datenstatus listet Scan, Live-Kurse, 4H, Quartalszahlen, Insider, ETF mit Stand und Ampel | **erledigt** |
| 5 | Journal-Kosten richtig benennen | mittel – Abweichung zum Tagesschnitt wurde als „Kosten“/Spread gelesen | klein | gering | `site/index.html` | „Abweichung zum Tagesschnitt“, „kein Spread“, Gebühren getrennt aus dem Export, Backtest-Annahme als Schätzung markiert | **erledigt** |
| 6 | Lern-Grundlage: Point-in-Time-Momentaufnahme neuer Signale | sehr hoch – Voraussetzung für jede ehrliche Gewinner/Verlierer-Analyse | mittel | gering (eigene Datei, Fehler stoppen den Scan nicht) | `backend/snapshots.py`, `backend/live.py`, `backend/run_scan.py` | unveränderlicher Block „sig“, Kauf/Ergebnis getrennt, „late“ bei Ausfall, keine Rückfüllung | **erledigt** (läuft ab dem ersten Abendscan nach Merge) |
| 7 | E2-Schattentest | hoch – E2 war je Trade in zwei unabhängigen Datensätzen besser | mittel | gering (nicht aktiv) | `paper/e2shadow.py` | gleiche Signale, eigene Einstiegsregel, nicht ausgelöste Orders protokolliert, nur künftige Signale | **Grundlage fertig, nicht aktiviert** |
| 8 | Insider-Quellen UK/FR/IT/DK/CH/HK | mittel | groß (je Land eigener Parser, teils kostenpflichtig) | mittel | `backend/insider.py` | je Land frei, stabil, mit Betrag | offen → Roadmap |
| 9 | Asien-Treffer in der App wieder zeigen (`calmGate` blendet `region === "asia"` aus) | mittel | klein | mittel (Asien nicht live getestet) | `site/index.html` | Entscheidung Jonny | offen – Entscheidung nötig |
| 10 | Quartalszahlen-Kalibrierung | hoch | – (läuft automatisch) | gering | `tools/earn_review.py` | ab 200 archivierten Fällen zeitlich getrennt prüfen | wartet auf Daten (< 200 Fälle) |
| 11 | WebKit-Browsertest (Safari/iPad-Engine) | mittel | klein, wenn verfügbar | gering | `tools/app_smoke.py` | Rundgang in WebKit ohne Fehler | in dieser Umgebung nicht verfügbar |

---

## B. Sofort-Verbesserungen (umgesetzt)

### B1 Forschungsaussagen aktualisiert
- `site/index.html`: neue Konstante `RESEARCH` (Stand „Forschung 31.10.2026“) und `resR()`; alle Stellen (Bilanz-Vorschau,
  Bilanz-Kopf, „Hält der Vorteil live?“, Live-Kachel, Papier-Depot-Regel, KAIROS-Text, Scanner-Hinweis, Trade-Plan-Statistik)
  lesen daraus. Gebühren-Kommentar (feeDrag) korrigiert.
- `backend/aipage.py`, `backend/trackpage.py`, `site/research/index.html`: gleichlautender Text.
- Tests: `backend/tests` (alle), `tools/dupe_check.py`.

### B2 Quartalszahlen: Aktualität, Status, Latenz
- `backend/earnings.py` `stamp_status(fresh, prev, now)`: „seen“ (erstmals gesehen, bleibt), „push_at“ übernommen,
  „eps0“ = erster EPS-Wert, Stufe „korrigiert“ bei > 2 % Abweichung, sonst „vorläufig“ (Pressemitteilung) oder „bestätigt“.
- `backend/earnfast.py`: Push-Zeit, Archiv mit ts/seen/push/stage.
- `tools/earn_review.py` `latency(arc)`: Minuten Veröffentlichung → erkannt → Mitteilung (Median, 90 %).
- App: `earnStage()` zeigt Stufe und „in Kairo seit“; Latenz im Bilanz-Fuß ab 10 Fällen.
- Test: `backend/tests/test_earn_review.py::test_latenz_und_status`.

### B3 Insider: Abdeckung und Signalqualität
- `backend/insider.py`: `COVER` je Aktie (ok/zeitlimit/fehler), `cover()` mit Quelle je Land (SEC, BaFin, AFM, ASX)
  und Ausfall-Markierung je Quelle; Zeitbudget 240 → 420 s; Meldedatum `fd` aus OpenInsider.
- **Signal-Korrektur:** Stärke-Punkt „gezielt“ nur noch für belegt gezielte Käufe (`opp`), nicht mehr für Käufe ohne
  Kaufhistorie (BaFin) – „Unvollständige Historien dürfen nicht als Beweis für einen gezielten Kauf behandelt werden“.
- App: ausklappbare Abdeckung („x von y deiner Aktien geprüft“, Zeitlimit, Quelle nicht erreichbar, keine freie Quelle),
  „gemeldet am“, „Routine unbekannt“, Erklärtext.
- Test: `backend/tests/test_insider.py::test_filing_date_unknown_routine_and_cover`.

### B4 Datenstatus
- App: `sourcesStatus()` – Stand je Quelle mit Ampel (grün im Takt, gelb älter als üblich, grau nicht geladen).
  Wochenende/Montag mit längerem Takt. Reine Anzeige.

### B5 Journal-Kosten
- Kachel „Ø Abweichung zum Tagesschnitt“ statt „Ø Kosten je Order“; Hinweis „kein Spread“ (enthält Tageszeitpunkt und
  Kursbewegung); „Ordergebühren (Export)“ als eigene Kachel aus der Spalte Gebühr (Summe, Anzahl, Anteil vom Umsatz);
  „Annahme im Backtest … geschätzt, nicht gemessen“. Kein erfundener Spread.

---

## C. Lern-Engine: Signal-Momentaufnahmen

`backend/snapshots.py` (neu), aufgerufen aus `backend/live.py::update` direkt nach dem Speichern der Signale.

- **Wann:** nur Abendscans (`record=True`). Läufe tagsüber schreiben nichts.
- **Was (Block `sig`, unveränderlich):** alle Pflichtkriterien (ok, Wert, Schwelle), erfüllt/gesamt, Score, Schluss, RSI,
  MACD-, MBI-Status, Divergenz, Flags (ATR, ATR %, Volatilität, MACD-Histogramm/Kreuz-Alter, MBI-Rohwerte, Börsenwert,
  Quartalszahlen-Risiko), Einstieg, Stop, Stop-Abstand in % und in ATR, Vormomentum (Monat −6…−1 wie
  `paper/kairo.py::momentum`), Marktlage (Regime, Farbe, Angst-Gier), Region, Sektor, Note.
- **Versionen:** Regel (`B60`), `SCHEMA`, Hash von `config.yaml`, Commit (`GITHUB_SHA`), Scan-Datum und UTC-Zeit.
- **Signaltag ≠ Kauftag:** `d` = Signaltag; `buy` (Kaufkurs, Stop, wann erkannt) und `exit` (Ergebnis, R, Tage) werden
  getrennt aus `st60` nachgetragen, ohne `sig` zu berühren.
- **Ausfälle:** `late` = Handelstage zwischen Signaltag und Scan. Alte Signale ohne Aufnahme bleiben ohne – keine
  Rückfüllung mit heutigen Werten.
- **Auswertung:** `table()` (eine Zeile je abgeschlossenem Treffer), `compare()` (Median je Merkmal Gewinner/Verlierer,
  erst ab 30 Fällen).
- Speicher: `state/snapshots.json` im Zustands-Branch `kairo-data` (der Workflow übernimmt neue Dateien mit `git add -A`).
- Tests `backend/tests/test_snapshots.py`: Felder/Versionen; wiederholter Scan überschreibt nicht; Lauf tagsüber
  schreibt nichts; Ausfall → `late = 3`, keine Rückfüllung; Kauf und Ergebnis getrennt, zweiter Lauf ändert nichts.

## D. E2-Schattentest – Grundlage (nicht aktiv)

`paper/e2shadow.py` (neu). Gleiche Signale wie B60 (Treffer 11/11, USA/Europa), eigene Einstiegsregel (Buy-Stop
Basishoch + 0,05 ATR, Kurslücke > 0,5 ATR verfällt, 10 Tage gültig), Stop und Ausstieg wie B60. Protokolliert auch
nicht ausgelöste Orders mit Grund. Zählt nur Signale ab dem Starttag. Abgeschlossene Einträge eingefroren. Eigene Datei
`e2_shadow.json`, kein Zugriff auf Depots.

**Noch nicht eingebunden** (bewusst): Zum Start fehlt nur ein Schritt in `.github/workflows/paper.yml` bzw.
`paper/run.py`, der `e2shadow.step(book, signals, prices, heute)` mit den Tageskerzen aufruft und `e2_shadow.json` im
Branch `paper-data` speichert. Das ist eine Änderung am Papier-Test-Lauf → **erst nach Freigabe**.

Tests `paper/tests/test_e2shadow.py`: Auslösen + Zeit-Ausstieg; nicht ausgelöst / Kurslücke / Basis gebrochen;
Wartezustände; Stop am Kauftag; nur künftige Signale + Einfrieren; Parameter gleich B60.

---

## E. Qualitätssicherung

| Prüfung | Ergebnis |
|---|---|
| `pytest backend/tests paper/tests` | 194 bestanden |
| `pytest research/strategy_championship/tests` | 24 bestanden |
| `node tools/turbo_unit.mjs` | 94/94 |
| `node tools/kursdienst_wake_test.mjs` | bestanden |
| `python tools/dupe_check.py` | keine doppelten Funktionen |
| B60-Gleichheit | `test_rule.py` (App, Papier-Depots, Regel identisch) bestanden; Diff an Regel/Scanner/Config/Depots leer |
| Browser `tools/app_smoke.py` (Chromium, iPad 820×1180, Handy 390×844, alle Reiter, Import, Backup, Größe) | lokal mit Daten vom 07.10.: alles grün bis auf „Regel-Test: h4.json fehlt“ – die Datei gab es in diesen alten Daten noch nicht (kein Fehler des Codes); mit aktuellen veröffentlichten Daten im Workflow „Tests & Regression“ (Lauf 41309736857): **bestanden** |
| Gezielte Browserprüfung (iPad + Handy): Insider-Abdeckung, Meldedatum, „Routine unbekannt“, Datenstatus je Quelle, Kosten-Check-Beschriftung, keine horizontale Verbreiterung | bestanden |
| API-Ausfälle: insider/earnings/h4/etf/bilanz/alerts/changes/calendar/briefing/analysis liefern 500 bzw. brechen ab | keine JS-Fehler, alle Reiter gefüllt, Datenstatus zeigt „nicht geladen“ |

**Nicht ausgeführt:** WebKit/Safari (in dieser Umgebung nicht installiert); `tools/kursdienst_test.mjs` (braucht Netz zu
Kursquellen); Browsertest mit aktuellen veröffentlichten Daten (github.io hier gesperrt – lokal mit Daten vom 07.10.2026;
der Workflow „Tests & Regression“ läuft mit aktuellen Daten bei jedem Push auf `claude/**`).
