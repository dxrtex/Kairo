# Kairo Maximum – Review (01.11.2026)

Branch `claude/maximum`, aufgebaut auf `claude/next-level` (65df929), der wiederum auf `main` (69d6707) aufsetzt.
**Kein Pull Request, kein Merge, keine Änderung an `main`.** B60 (11 Kriterien, Einstieg, Stop, Ausstieg), Dual Momentum und
die Papier-Depots sind unverändert. `git diff origin/main -- backend/scanner.py backend/rule.py config.yaml paper/kairo.py
paper/run.py paper/core.py backend/shortswing.py` ist leer.

## Paket 0 – Ist-Zustand

| Stand | Commit | Inhalt |
|---|---|---|
| `main` | 69d6707 | Quartalszahlen Gewinn × Ausblick, Lernschleife, Asien-Universum, Insider neueste zuerst |
| `claude/next-level` | 65df929 | +7 Commits: Forschungszahlen, Quartalszahlen-Status/Latenz, Insider-Abdeckung, Datenstatus, Kosten-Check, Momentaufnahmen, Ursachensuche, Lern-Test, E2-Grundlage |
| `claude/ultimate-research` | 83ade7a | Forschung B60/E2/R1–R4, Ruhe-Test, Lern-Test |

Keine parallele Session hat seitdem auf diese Branches geschrieben. Vor dem Start: 226 Tests grün. `claude/maximum` übernimmt
`claude/next-level` vollständig (Fast-Forward, keine Konflikte) – nichts davon wurde doppelt gebaut.

## Paket 1 – Sofortiger Mehrwert

### 1.1 Einheitliches Portfolio-Profil (P0)
- **Problem:** Drei Aufteilungen an verschiedenen Stellen (automatisch 100/80/70 nach Kapital im ETF-Reiter, Übungsdepot fest
  70/30, Trading-Budget separat). Ziel: 90/10.
- **Änderung (`site/index.html`):** `pfCfg()` + `state.pf` als einzige Quelle: Standard **90 % ETF / 10 % Trading**, Szenario-Knöpfe
  100/0, 90/10, 80/20, 70/30, frei eingebbar, **Notgroschen außerhalb** der Aufteilung (`pfReserve`). ETF-Ziel, Trading-Kapital,
  „Trading-Kapital im Einstieg setzen“, neue Übungsdepots und „Kapital & Risiko“ lesen daraus.
- **Datenschutz:** ein früher fest eingestellter ETF-Anteil (`state.etf.share` + `shareManual`) wird weiter übernommen; laufende
  Übungsdepots behalten ihre Aufteilung (`g.share`); Depot, Journal, Watchlist, Backups unberührt.
- Die alte Kapital-Staffel bleibt als **Hinweis** (Gebühren-Forschung unter 10.000 €), nicht als Vorgabe.
- **Test:** Browser (iPad/Handy): 90 % Standard, Notgroschen 10.000 € von 30.000 € → ETF-Ziel 18.000 €, Szenario 70/30 greift,
  Spiel-Start zeigt 90/10.

### 1.2 Kapital & Risiko (P0/P1)
- `riskModel()` / `riskHtml()` auf „Heute“ (auch im Postfach-Design): Trading frei/gebunden, freie Plätze, **Verlust bis zu den
  Stops** (ab heutigem Kurs, in % vom Trading und vom Ganzen), Sektor- und Markt-Konzentration, Warnungen (> 50 % in einem
  Sektor, Risiko über dem Rahmen Risiko × max. Positionen, Hebelprodukte offen, Einstieg-Budget ≠ Profil).
- Nur der aktive Modus (echt oder Übung). Korrelationen werden **nicht** behauptet (bräuchten Kursreihen) – nur Konzentration.

### 1.3 Ehrliche, versionierte Forschungsangaben (P0)
- `EVIDENCE` (zentrale Quelle): je Stand Strategie, Regelversion, Zeitraum, Universum, Datenquelle, Kosten, Positionsgröße,
  Kapital, Stichprobe, Belastbarkeit, Prüfdatum, Status *aktuell / Forschung / überholt*. Bilanz → „Forschungsstände“.
- Korrigiert: Live-Urteil der Bilanz verglich mit **0,14 R** (alt) → jetzt B60 +0,12 R; „Deine Trades“ verglichen mit
  `STRAT_BT.perTrade` (Turbo-Studie) → jetzt B60; die Trade-Plan-Erwartung kam aus `TP_EXP` (überholte Kurzfrist-Studie, Tag 20)
  → für Kairo jetzt B60.
- Ältere Stufen (`grade`) als „ältere Ziel-/Stop-Regel, nicht B60“ gekennzeichnet; der Score ausdrücklich **keine validierte
  Qualitätsrangfolge**.

### 1.4 Signal ≠ Empfehlung
- Treffer-Karte: „Einordnung“ in fünf Ebenen – **Regelstatus**, **Handelbarkeit** (Seitwärtsphase/Region getestet),
  **Risiko & Kosten** (Stop-Abstand in % und ATR, Spread in R, 0,99 € unter 250 €), **historische Evidenz** (B60 mit Stress und
  gegen Zufall), **Live-Evidenz** (Live-Bilanz, „noch zu wenige“ unter 30).

### 1.5 Abend-Cockpit
- „Heute“: neben „Heute zu tun“ (Verkaufs-/Kaufaufgaben) jetzt **Kapital & Risiko**; die Bilanz-Kachel zeigt die
  **Lern-Erkenntnis** (Anzahl analysierter Trades, auffällige Merkmale, Lehre des letzten Verlusts). Bestehende Komponenten
  wiederverwendet, keine neue Seite.

## Paket 2 – Learning Engine

| Baustein | Stand |
|---|---|
| Point-in-Time-Signal (`snapshots.take`) | unveränderlicher Block `sig`: 11 Kriterien, RSI/MACD/MBI, ATR, Stop-Abstand, Vormomentum, **Rückgang vom Hoch** (neu), Marktlage, Region/Sektor, Quartalszahlen-Termin, Versionen |
| Lebenslauf (`stage`, neu) | signal → gekauft → beendet bzw. kein_einstieg |
| Kauf-Kontext (`buy`, erweitert) | Kaufkurs, Stop, erkannt am, **Handelstage nach dem Signal**, **Marktlage beim Kauf** |
| Verlauf (`exit`, erweitert) | Ergebnis, R, Tage, **Kauftag aus Tageskerzen**, **MFE/MAE in R** (größter zwischenzeitlicher Gewinn/Verlust) |
| Ursachen (`tradewhy`) | vorher erkennbar vs. hinterher, Schlagzeilen, Lehre, historisch geprüfte Merkmale bleiben beobachtet |
| **Kontrollgruppen (neu)** | 9/11 (bis 15/Abend) und 5 Zufallsaktien USA/Europa je Abend (fester Zufall je Datum), 10/11 + 4H-Vorstufen schon in `signals.json` |
| **Folgerenditen (neu)** | 20/60 Handelstage + Tiefpunkt für Treffer, 10/11, 9/11, Zufall – gleiche Messlatte; Anzeige in der Lern-Karte |
| **Register (neu)** | `backend/registry.py`: Champion B60, Challenger/verworfene Ideen mit Grund, feste Hürden; Handelsregeln werden nie automatisch befördert (Freigabe immer nötig); Prognose-Anzeigen nach Brier-Regel |

Noch nicht: „Geplante Kauforder“ und „abgelehnte Order“ als eigene Ereignisse (fehlen im Live-Signal-Fluss; im E2-Schattentest
vorhanden), lernende Wahrscheinlichkeitsmodelle (bewusst erst ab genug Live-Fällen – Baseline zuerst).

## Paket 3 – Produktqualität

- **App-Update sichtbar:** Die Seite kommt offline-fähig zuerst aus dem Speicher; ein Update wurde bisher erst beim
  übernächsten Öffnen sichtbar. Jetzt Versions-Abgleich beim Start und alle 30 Min. → Leiste „Neue Kairo-Version verfügbar –
  Neu laden“.
- **Insider:** Umschalter „Neueste zuerst / Nach Betrag“ (zusätzlich zu Abdeckung, Meldedatum, Signal-Korrektur aus next-level).
- **E2-Schattentest:** Parität zur Forschungsregel geprüft und dokumentiert, Kosten jetzt wie in der Engine (Basis 0,05 %,
  Stress 0,15 % je Seite), Zusammenfassung mit Kaufquote, Haltedauer, Stress-R und B60-Vergleich derselben Signale.
- Journal: Dubletten-Erkennung über die Referenz war bereits vorhanden (kein Umbau nötig).

## Paket 4 – Tests

| Prüfung | Ergebnis |
|---|---|
| `pytest backend/tests paper/tests research/strategy_championship/tests` | **233 bestanden** (neu: Registry 3, Momentaufnahmen 2, E2 2) |
| `node tools/turbo_unit.mjs` / `kursdienst_wake_test.mjs` / `tools/dupe_check.py` | bestanden |
| B60-Parität | `test_rule.py` (App = Papier-Depots = Regel) bestanden; Diff an Regel/Scanner/Config/Depots leer |
| E2-Parität | Punkt-für-Punkt gegen `research/ultimate/round1.py` + Engine (siehe `paper/e2shadow.py`), neue Tests für unklare Tagesreihenfolge und Lücke in den Buy-Stop |
| Browser Chromium, iPad 820×1180 + Handy 390×844 | Portfolio-Profil, Kapital & Risiko, Forschungsstände, Einordnung, Insider-Abdeckung/Sortierung, Datenstatus, Kosten-Check, Lern-Karte, API-Ausfälle (500/Abbruch): bestanden |
| `tools/app_smoke.py` (alle Reiter, Import, Backup) | lokal mit Daten vom 07.10.: nur „h4.json fehlt“ (Datei gab es damals nicht); mit aktuellen Daten im Workflow „Tests & Regression“ |

**Nicht ausgeführt:** WebKit/Safari (hier nicht installiert), `kursdienst_test.mjs` (braucht Netz), Browsertest mit aktuellen
Daten lokal (github.io gesperrt – übernimmt der Regressions-Workflow beim Push).
