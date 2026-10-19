# 29 — Vorregistriertes Protokoll v3.1: S19 und S20 mit echten 4H-Kerzen und SEC-Fundamentaldaten

**Erstellt:** 19.10.2026, 22:30 Uhr – **vor** jedem Lauf. Festgeschrieben durch den Git-Commit dieser Datei. Anlass (Nutzer,
Chat 19.10.2026): S19 (Hybride Mean Reversion) und S20 (Trendfolge/VCP) wurden bisher nur mit einem Tageskerzen-Ersatz für
den 4H-Auslöser und ohne Margen-/Börsenwert-Daten gerechnet (v1.5/v1.6) – also nicht so, wie der Nutzer sie definiert hat.
Mit den neuen Daten (SEC EDGAR, Dukascopy-Stundenkerzen ab 2017) sind sie erstmals in ihrer Originalform testbar.

## 1. Regeln (unverändert vom Nutzer, Umsetzung = Papier-Handel `paper/core.py` + `paper/run.py`)

Die historische Simulation verwendet **denselben Code wie der laufende Papier-Handel** (Tagessignale `s19_signal`,
`s20_setup`, 4H-Auslöser `s19_trigger`/`s20_trigger`, Positionsführung `step_position`, Tagesablauf `process_day`). Damit
sind Backtest und Live-Test dieselbe Regel.

| ID | Tagessignal | 4H-Auslöser (≤ 5 Handelstage) | Stop / Ziel / Ausstieg | Risiko |
|---|---|---|---|---|
| **S19** | ≥ 2,5 Std unter EMA20, 3 Tage fallend, Volumen streng sinkend, 3-T.-Rendite < Branchen-ETF; Börsenwert ≥ 10 Mrd. USD und operative Marge > 0 | grüne 4H-Kerze schließt über dem Hoch der letzten roten Kerze; CRV ≥ 2 zum Ziel | Stop = Panik-Tief − 0,5 ATR; Ziel = EMA20 (Tag); kein Zeit-Ausstieg | S&P > EMA200: 1 %, sonst 0,5 % und max. 2 Positionen |
| **S19-B** | wie S19, Volumen „2 von 3 Tagen gesunken“ | wie S19 | wie S19 | wie S19 |
| **S19-C** | wie S19-B, Überdehnung ≥ 2,0 Std | wie S19 | wie S19 | wie S19 |
| **S20** | S&P > EMA200; Schluss > EMA50 > EMA200; Bandbreite < 20-T.-Schnitt; ≤ 1,5 % an der EMA50 oder in 50–61,8-%-Zone | 4H-Schluss ≥ 1 % über 4H-EMA20, Volumen > 4H-Schnitt 20 | Stop = Kauf − 1,5 ATR; ab +2 ATR Einstand, danach unter das Tief der letzten 4H-Kerze | 1 % |

Kauf jeweils zur Eröffnung der **nächsten** 4H-Kerze nach dem Auslöser. Max. offene Positionen 5 (2.000/5.000 €) bzw. 10
(20.000 €). Ranking bei mehreren Auslösern zur selben Zeit: S19 stärkste Überdehnung, S20 höchster Volumenanstieg.

## 2. Daten (zeitpunktgenau)

- **Universum:** Titel der eingefrorenen Liste, für die Dukascopy Stundenkerzen hat (527, davon 25 DE). S19 nur US
  (Fundamentaldaten aus EDGAR). Tageskerzen: Datensatz v1 (Yahoo). **Survivorship-Label** wie immer.
- **4H-Kerzen:** Dukascopy-Stunden (BID) in Börsenzeit (US 9–15 Uhr ET, DE 9–17 Uhr MEZ, Beginn der Stundenkerze), je Tag in
  4er-Gruppen (`to_h4`), Preisniveau je Tag auf Yahoo skaliert (wie Protokoll v3.0 §8). Volumen = Dukascopy-Tick-Volumen
  (nur relativ verwendet: 4H-Volumen gegen eigenen 20-Kerzen-Schnitt).
- **Börsenwert:** XBRL-Aktienanzahl (zuletzt gemeldet, ab Folgetag der Einreichung) × Kurs, Split-Basis wie v3.0.
- **Operative Marge:** `OperatingIncomeLoss` ÷ Umsatz des **letzten veröffentlichten Geschäftsjahres** (10-K), ab Folgetag der
  Einreichung; ohne operatives Ergebnis: Jahresüberschuss (wie v1.5).
- **Branche:** SIC-Code (SEC) → Sektor-ETF (Zuordnung im Code, fest vor dem Lauf); Immobilien → XLF, Telekom/Medien → XLK
  (XLRE/XLC gab es nicht durchgehend), Rest/unbekannt → SPY.
- **Regime:** S&P 500 (^GSPC) Schluss > EMA200, Wert des Vortags (wie Papier-Handel).

## 3. Zeitraum

**Test 2017-01-01 – 2021-12-31** (Dukascopy-Aktien beginnen 2017). **Vorbelastung offen:** Die Tagesersatz-Varianten von S19/S20
wurden 2017–2021 bereits gerechnet (v1.5/v1.7); die 4H-Originalversionen nie. 2022–2026: nur Hinweis (Holdout seit v2.1
offen). Eine Train-Periode gibt es nicht – es werden keine Parameter gewählt.

## 4. Kosten, Kapital, Steuern

PRIME+ Basis und Stress wie v3.0; 2.000 € (Papier-Depot-Größe), **5.000 € (Hauptfall)**, 20.000 €. Steuern wie v3.0 §6.

## 5. Zufall (Null) und Statistik

Je Strategie 100 Seeds: an jedem Tag mit neuen Tagessignalen gleich viele **zufällige zulässige Titel** desselben Pools
(S19: Qualitäts-Pool mit Börsenwert/Marge, unter der EMA20; S20: alle zulässigen Titel bei positivem Regime), danach
**identische** 4H-Auslöser-, Stop-, Ziel- und Ausstiegsregeln. p = (Seeds mit CAGR ≥ Strategie + 1) ÷ 101 (5.000 €, Basis).
Familie = 4 Strategien → **Bonferroni p ≤ 0,0125**.

## 6. Bestehensregeln (je Strategie, 5.000 €)

1. Stress-CAGR 2017–2021 > 0; 2. Stress-CAGR > ACWI (gleiche Kosten); 3. p vs. Zufall ≤ 0,0125; 4. nach Steuern > ACWI nach
Steuern; 5. ≥ 30 Trades. Besteht eine Strategie, wird sie Kandidat für den laufenden Papier-Handel (kein echtes Geld vorher);
zusätzlich beschreibend: Vergleich mit Dual Momentum S16-B und 70/30.

## 7. Nicht erlaubt

Weitere Varianten, andere Schwellen, Wechsel des Zeitraums nach Einsicht; Abweichungen vom Papier-Handel-Code außer
nachgewiesenen Fehlern (jede Korrektur im Register, alle Läufe bleiben sichtbar).
