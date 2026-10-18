# Gate B — Zusammenfassung und Empfehlung

**Stand:** 18.10.2026 · Branch `research/strategy-championship-phase-a` · Produktiv-App unverändert · keine Orders,
keine kostenpflichtigen Daten oder Dienste genutzt.

## 1. Was in Phase B erledigt ist

| Schritt | Ergebnis | Dokument |
|---|---|---|
| D0 Datensicherung | Rohdaten beider alter 10-J.-Stichproben dauerhaft gesichert (Release `research-raw-2026-10`, 2 × tar.xz ≈ 610 MB, SHA-256). Stichprobe 1: 2.407 Titel, Stichprobe 2: 2.446 Titel, **997 in beiden** → die alten Läufe sind nicht unabhängig. | Release-Manifest |
| B0 Datensatz v1 | Eingefroren: Tageskerzen 2005–2026 (roh + AdjClose), 2.953 Titel US/EU, Benchmarks, FX (Release `research-data-v1`, SHA-256 im Manifest). | `01`, Manifest |
| B1 Protokoll | Zeitabschnitte, Kosten, Kapital, Kandidaten Welle 1, Kennzahlen, Auswahlregeln — vor jedem Screening festgelegt. Validierung/Holdout im Code gesperrt. | `02_PROTOCOL.md` |
| B3 Engine | Neue Ledger-Engine, 17 synthetische Tests, Gegenrechnung gegen Altsimulator: 98,3 % der Signale / 93,6 % der Trades identisch, geprüfte Abweichungen alle erklärt (Dividenden, Rundung an Schwellen, Periodenende). **PASS WITH LIMITATIONS.** | `03_ENGINE_AUDIT.md` |
| B2 Baselines | S01-A/B (12 Depots + Kostenstress), Null 2 × 200 Seeds, S13-ETF, ACWI — nur Train 2008–2016; 24 Einträge im Register. | `05_BASELINES_TRAIN.md`, `04_EXPERIMENT_LOG.jsonl` |

## 2. Kernergebnis (Train 2008–2016, EXPLORATIV · DATENBESCHRÄNKT)

- **S01 (Kairo 1D, unverändert) zeigt keinen belastbaren Vorteil gegenüber Zufall:** 5.000 € / 1 % Risiko +5,0 % p. a.
  (Max. DD −29 %); 15,5 % der Zufalls-Depots mit gleichen Regeln sind mindestens so gut. Bei 0,5 % Risiko +0,6 % p. a.,
  Zufall fast gleich (p = 0,47).
- **Nach Kosten bleibt pro Trade kaum etwas übrig** (−0,01 … +0,07 R netto; vor Kosten +0,15 … +0,22 R). Unter Kostenstress −13 % p. a.
- **1.000 € Startkapital ist mit fester Gebühr nicht tragfähig** (Totalverlust in allen S01-Läufen).
- **Stärkste Baseline: S13-ETF** (ACWI nur über dem 10-Monats-Durchschnitt): +9,6 % p. a., Max. DD −22 %, Sharpe 0,71 —
  vor ACWI-Halten (+7,8 %, −46 %) und vor jeder S01-Variante.
- Die **4H-Bestätigung** ist mangels historischer Daten **NICHT GETESTET** und kann nur vorwärts (Papier) geprüft werden.

Das ist **kein** Urteil über Validierung oder Holdout (noch verschlossen) und **keine** Handelsempfehlung.

## 3. Vorgeschlagene Protokoll-Nachträge (v1.1, gelten für alle Strategien gleich)

1. **Mindest-Positionsgröße:** Ein Kauf entfällt, wenn das freie Cash nur weniger als 50 % des geplanten Risikos zulässt
   (statt Rest-Positionen von 1–2 Stück). Begründung: Realismus, nicht Ergebnisverbesserung; der Effekt auf die Euro-
   Ergebnisse ist klein (siehe 03 §6). Beide Fassungen werden berichtet.
2. **Kennzahl Ø R** nur über volle Positionen; Hauptkriterium bleibt Netto-CAGR/Drawdown in EUR.
3. **1.000-€-Sleeve** nur noch als Kosten-Warnfall berichten, nicht als Kandidat.

## 4. Was nach „GATE B FREIGEGEBEN“ passiert (Phase C, Welle 1)

- Screening **nur auf Train 2008–2016**: S02-A/B, S03-P, S04-M, S05-A/B, S08-A/B, S11-A/B, S13-Stock — je mit 0,5 %/1 %
  Risiko, 5.000 €/20.000 €, Basis- und Stresskosten, jeweils gegen passende Null-Strategie, S13-ETF und ACWI.
  Höchstens 2–3 Varianten je Familie, alles im Register.
- Danach Zwischenbericht und **Gate C** (Freigabe der Validierung 2017–2021 für die besten wenigen Kandidaten).
- **Aufwand:** Signale dieser Strategien sind einfache Indikatoren (kein voller Scanner-Lauf) → geschätzt 1–3 Stunden
  GitHub-Actions-Rechenzeit, für das öffentliche Repo **kostenlos**. Keine kostenpflichtigen Daten, keine Cloud-Kosten.

## 5. Was ich von dir brauche

1. **„GATE B FREIGEGEBEN“**, wenn Phase C (Welle 1, nur Train) starten soll.
2. Ob die Nachträge 3.1–3.3 gelten sollen (Empfehlung: ja).
3. Optional, **nicht nötig für Phase C:** Survivorship-freie Daten (inkl. gestrichener Titel) gibt es nur kostenpflichtig.
   Ohne deine ausdrückliche Freigabe wird nichts bestellt; die Grenze bleibt dann ausgewiesen.

Deine persönliche Max.-Verlust-Grenze frage ich erst vor jeder echten Kapitalaufteilung (Phase E) ab.
