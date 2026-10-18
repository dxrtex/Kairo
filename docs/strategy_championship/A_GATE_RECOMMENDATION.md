# A — Gate-Empfehlung (Phase A)

**Stand:** 18.10.2026 · Grundlage: `00_REPO_AND_BACKTEST_AUDIT.md`, `01_DATA_FEASIBILITY.md`.

## Empfehlung: **GO WITH LIMITATIONS**

Ein überprüfbarer Forschungsprozess ist möglich, aber nur mit klar benannten Grenzen:

- Alle Aktien-Ergebnisse mit Gratisdaten tragen das Label **`DATENBESCHRÄNKT (Survivorship)`**. Vergleiche **zwischen** Strategien auf demselben Universum bleiben aussagekräftiger als die absoluten Renditen.
- Für S01 und alle 4H-Varianten gibt es **keinen sauberen historischen Holdout** mehr; 4H bleibt **EXPLORATIV**.
- S15 und S17 sind mit verfügbaren Daten/Produkten **NICHT VALIDE TESTBAR**; S03, S10, S12 nur als US-Proxy mit EDGAR-Aufbau oder mit Kaufdaten.
- Die bisherigen App-Zahlen (z. B. +15 % p. a.) gelten bis zur Nachprüfung als **BERICHTET / NICHT REPRODUZIERT**.

Kein NO-GO, weil Code, Indikatoren, Signale und ein Trade-Simulator mit Grundtests vorhanden sind, die Rechenressourcen kostenlos reichen und ein großer Teil der 18 Kandidaten mit Tageskerzen testbar ist. Kein uneingeschränktes GO, weil die drei kritischen Befunde (Survivorship, vorbelastete Prüfjahre, fehlende Rohdaten-Sicherung) jede künftige Siegeraussage gefährden.

## Dringend vor dem 26.10.2026 (eigene Freigabe nötig)

**D0 — Rohdaten sichern.** Die 80 Ereignis-Dateien (`kurz-*`) der beiden bisherigen Stichproben laufen am **26.10.2026** ab. Vorschlag: ein kleiner, manuell gestarteter Workflow lädt sie herunter und legt sie gepackt als Artefakt mit 90 Tagen Aufbewahrung bzw. als Release-Asset ab (≈ 0,8 GB unkomprimiert; kostenlos, keine Produktivänderung, App unberührt). Ohne diese Sicherung ist die bisherige S01-Baseline nur noch näherungsweise neu zu berechnen.

## Sinnvollster nächster Schritt (nach „GATE A FREIGEGEBEN“)

**Phase B in dieser Reihenfolge:**
1. **B0 Datengrundlage festlegen** (Ihre Entscheidung, siehe Fragen 2–3) und einen **eingefrorenen Datensatz** erzeugen: festes Universum als Datei mit Datum, feste Stichprobe, Kurse als versioniertes Artefakt, Manifest mit Hashes.
2. **B1 `02_PROTOCOL.md`**: Universum, Splits (Vorschlag unten), Kosten (0,99 €/Order, Spread, FX, Finanzierung), Risikoszenarien 10/20/30 %, Sleeve 1.000 / 5.000 / 20.000 €, vorregistrierte Varianten je Strategie, Experiment-Register.
3. **B3 Engine**: Ledger-basierter Depot-Simulator (Cash, Positionen, Gebühren, FX, Tageswert) mit synthetischen Tests und Zweitberechnung von 20–50 Stichproben-Trades → `03_ENGINE_AUDIT.md`. Vorher keine Siegervergleiche.
4. **B2 Baselines**: S01 unverändert (Commit 9624040), risiko-/exposure-gematchte Zufallsstrategie über viele Seeds, S13 einfache Trendfolge, Weltaktien-Total-Return-Proxy in EUR.

**Vorschlag Datenschnitt (zur Diskussion, wird erst in `02_PROTOCOL.md` eingefroren):**
- Entwicklung: 2008–2019 (enthält 2008, 2011, 2015/16, 2018).
- Validierung/Walk-Forward: 2020–2023.
- 2024–2026: für S01/4H **vorbelastet** → nicht als Holdout zählbar; für neue Strategiefamilien (S02–S18) bislang unberührt, aber durch Marktbeobachtung nicht völlig „blind“.
- **Echter finaler Holdout: vorwärts gerichtetes Paper-Trading ab Einfrieren der Regeln** (einzige wirklich unberührte Periode), optional ergänzt um eine heute nicht genutzte Region/Universumshälfte.

## Arbeitspakete (Schätzung, ohne Wartezeiten auf Ihre Freigaben)

| Paket | Inhalt | Aufwand | Datenkosten |
|---|---|---|---|
| D0 | Rohdaten sichern | < 0,5 Tag | 0 € |
| B0 | eingefrorener Datensatz + Manifest | 1–2 Tage (+ Rechenzeit) | 0 € (Yahoo) oder Kaufdaten |
| B1 | Protokoll | 1 Tag | 0 € |
| B3 | Ledger-Engine + Tests + Zweitberechnung | 2–4 Tage | 0 € |
| B2 | Baselines (S01, Zufall, S13, ETF) | 1–2 Tage | 0 € |
| C1 | Welle 1: S01, S02, S03*, S04, S05, S08, S11 (+S13) | 4–8 Tage | 0 € (S03 nur Proxy) bzw. Kaufdaten |
| C2 | Welle 2: S06, S07, S09, S10*, S12*, S14, S16, S18 | 5–10 Tage | 0 € / EDGAR-Aufbau / Kaufdaten |
| D–E | Vertiefung, Auswahlregeln, einmaliger Holdout | 3–6 Tage | — |

\* nur als Proxy, sofern keine PIT-Fundamentaldaten beschafft werden.

## Offene Entscheidungsfragen an Sie

1. **D0:** Darf ich die am 26.10. ablaufenden Rohdaten per Workflow sichern (kostenlos, ohne App-Änderung)?
2. **Datenbudget:** (a) nur Gratisdaten mit Survivorship-Label, oder (b) Kauf eines survivorship-freien US-Datensatzes (Größenordnung einige hundert USD/Jahr, Preis vorher prüfen) — dann wären US-Ergebnisse deutlich belastbarer.
3. **Universum für die Forschung:** weiter weltweit (US/EU/Asien, mehr Rauschen bei FX/Zeitzonen) oder zunächst **nur US + Deutschland/Europa** für sauberere Daten?
4. **Holdout:** Einverstanden, dass für S01/4H kein historischer Holdout mehr existiert und der finale Test als **Paper-Trading nach Einfrieren** läuft (Dauer je nach Handelsfrequenz Monate, nicht Wochen)?
5. **Broker/Kosten:** Bleibt Scalable (0,99 €/Order, Free-Broker) die Annahme? Welche Börsenplätze/Produkte (Aktie direkt, Turbos) sollen zulässig sein?
6. **Kapital-Szenarien:** Sind 1.000 / 5.000 / 20.000 € als Sleeve-Größen passend? (Ihr aktuelles Trading-Kapital laut App ≈ 900–3.000 €; bei < 1.500 € hat der eigene Kapital-Test bereits Verluste durch Gebühren gezeigt.)
7. **Persönliche Verlustgrenze:** wird erst vor einer realen Allokation abgefragt — hier nur zur Kenntnis.

**Ich stoppe hier und warte auf „GATE A FREIGEGEBEN“** (ggf. mit Einschränkungen und Antworten auf die Fragen).
