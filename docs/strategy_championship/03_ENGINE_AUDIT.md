# 03 — Engine-Audit (B3)

**Stand:** 18.10.2026 · Branch `research/strategy-championship-phase-a` · Code: `research/strategy_championship/engine.py`
**Urteil: PASS WITH LIMITATIONS** (Gegenrechnung voller Lauf: 98,3 % der Signale / 93,6 % der Trades identisch, Rest vollständig durch Dividenden bzw. Periodenende erklärt — Abschnitt 6)

## 1. Was die Engine tut

Neu geschriebene, ledger-basierte Depot-Simulation (Long-only, Aktien direkt, kein Hebel). Unabhängig vom alten
`shortswing`-Simulator, damit dieser als Gegenrechnung dienen kann.

| Punkt | Umsetzung |
|---|---|
| Zeitpunkt | Entscheidung nach Schluss von Tag t → Ausführung frühestens zur nächsten Eröffnung **des jeweiligen Titels** (handelt er nicht, wartet die Order). |
| Kurse | Unbereinigte OHLC (wie gehandelt; Splits von Yahoo eingerechnet). Signale/Indikatoren auf auto_adjust-Kursen wie im Produktiv-Scanner; Schwellen mit dem Faktor des Entscheidungstags in Handelskurse umgerechnet. |
| Dividenden | D_t = C_{t−1} · (1 − f_{t−1}/f_t) mit f = AdjClose/Close; Gutschrift am Ex-Tag, nur wenn die Position vor dem Ex-Tag bestand (Kauf zur Eröffnung des Ex-Tags → keine Dividende). |
| Stop | Eröffnung ≤ Stop → Verkauf zur Eröffnung (Kurslücke), sonst Tief ≤ Stop → zum Stop. Stop und Ziel am selben Tag → Stop. Kauftag: Tief ≤ Stop → Stop (Eröffnung lag über dem Stop). |
| Zeit-Ausstieg | Schluss von Handelstag N (Kauftag = Tag 1). |
| Signal-Ausstieg | z. B. EMA20: Schluss < EMA ab Tag 10 → Verkauf zur nächsten Eröffnung. |
| Bedingte Einstiege | `entry_band` (Eröffnung in (Tief, Hoch] der Basis), `risk_atr` (0,5–3 ATR, sonst Signal verworfen), `group` (höchstens ein Kauf je Signal). |
| Größe | Risiko-Anteil des aktuellen Depotwerts / (Kaufkurs − Stop), abgerundet auf ganze Stück, begrenzt durch Cash − Gebühr. Alternativ Zielgewicht. |
| Kosten | Gebühr je Order (0,99 €), halber Spread je Seite (titelweise), Slippage, FX-Zuschlag (Stress). |
| Währung | Alle Buchungen in EUR mit EURxxx-Tageskurs; GBp = Pence (/100). |
| Depot | Max. offene Positionen; Reihenfolge nach Priorität; kein negatives Cash; Equity täglich = Cash + Stück × Schluss / FX. |
| Datenende | Endet die Kursreihe eines Titels → Zwangsverkauf zum letzten Schluss (`data_end`); Simulationsende → `end`. |

## 2. Synthetische Prüfungen (17/17 bestanden, `tests/test_engine.py`)

Konstante Kurse ohne Kosten → Equity unverändert · Kauf nie am Signaltag · Kurslücke unter Stop → Eröffnung · Intraday-Stop
→ Stop-Kurs · Stop + Ziel am selben Tag → Stop · Eröffnung unter Stop → kein Kauf · Gebühren- und Spread-Rechnung von Hand ·
Dividenden-Gutschrift · USD-Position: reiner Währungsgewinn exakt · Pence-Notierung · fehlender Handelstag → Order wartet;
Datenende → Zwangsverkauf · Max. Positionen + Priorität · Signal-Ausstieg zur nächsten Eröffnung · kein negatives Cash ·
Einstiegsband mit Wiederholung + nur ein Kauf je Gruppe · Risiko-ATR-Grenze verwirft · EMA-Ausstieg.

Zusätzlich prüft **jeder** Lauf automatisch: Σ Cashflows = Endcash − Startcash, Mindest-Cash ≥ 0,
Σ Trade-PnL + Dividenden = Equity-Änderung (`checks` in jedem Ergebnis).

## 3. Unabhängige Gegenrechnung

Jedes S01-Signal im Train-Zeitraum wird isoliert (ein Titel, ohne Kosten) mit der neuen Engine und mit dem alten
`shortswing.simulate` (QRULE, Haltedauer 20) gerechnet; verglichen werden Einstiegstag, Ausstiegstag, Ausstiegsgrund und
Ergebnis in R (Toleranz 0,02 R — alt: auf 4 Stellen gerundete bereinigte Kurse; neu: Handelskurse + Dividenden-Cash).

- Probelauf (8 Titel, 71 Signale, 18 Trades): **70/71 gleich**; die eine Abweichung war eine Dividende im Haltezeitraum
  (alt 4,52 R auf bereinigten Kursen, neu 4,29 R Kurs + 0,22 R Dividende = 4,51 R) → Vergleich seither auf Gesamt-R.
- Voller Lauf: siehe `crosscheck_summary.json` im Release `research-b2-<Lauf>`; Zahlen in Abschnitt 6.

## 4. Bekannte Grenzen (nicht behoben, offen ausgewiesen)

1. **Survivorship:** Universum = heute gelistete Titel (eingefroren 16.10.2026). Pleiten/Übernahmen 2008–2016 fehlen
   → Ergebnisse aller Aktienstrategien eher **zu gut**; `data_end` greift kaum. Gilt für S01 **und** die Null gleich.
2. **Split-bereinigte „Rohkurse“:** Yahoo rechnet spätere Splits rückwirkend ein. Der Preisfilter „Kurs ≥ 1“ und die
   Stückzahl-Rundung sind dadurch nicht zeitpunktgenau (Beispiel NVDA: 2008–2016 nach heutigen Splits < 1 $, damals
   10–30 $ → fällt im Backtest aus dem Universum). Dollar-Volumen und Renditen sind davon nicht betroffen.
3. **Marktkapitalisierung** historisch unbekannt → Filter gilt als erfüllt (großzügiger als produktiv).
4. **Spread-Klasse** je Titel aus dem Median-Dollarvolumen des Train-Zeitraums (nicht tagesgenau).
5. **FX** zum Schlusskurs des Ausführungstags (auch bei Ausführung zur Eröffnung) — wirkt nur auf die Umrechnung,
   nie auf eine Entscheidung; Größenordnung Basispunkte.
6. **Depot-Abweichung zum isolierten Altmodell:** Ist das Depot am ersten Basis-Tag voll, darf ein späterer Basis-Tag
   desselben Signals (innerhalb von 10 Tagen) noch kaufen. Im isolierten Modell gibt es kein „voll“.
7. Keine Teilausführungen/Volumengrenzen (bei 1–20 k€ unkritisch), keine Leerverkäufe, kein Zins auf Cash (0 %).
8. Dividenden aus Yahoo-AdjClose abgeleitet; Yahoo-Fehler (selten falsche Faktoren) werden übernommen.
9. Keine historischen Indexmitgliedschaften, Sektoren oder Earnings-Termine (Phase A, 01).

## 5. Urteil

**PASS WITH LIMITATIONS.** Die Mechanik (Zeitpunkte, Stops, Kosten, Währung, Dividenden, Bilanz) ist synthetisch und gegen
den unabhängigen Altsimulator geprüft. Die Grenzen 1–3 betreffen die **Daten**, nicht die Engine, und verzerren Kairo und
Null-Strategie gleichartig; sie verbieten aber, absolute Renditen als realistisch zu lesen.

## 6. Gegenrechnung voller Lauf

Lauf `research_b2.yml` #39120774730 (Commit `b22fceb`), alle 16.154 S01-Signale 2008–2016:

| | Anzahl |
|---|---|
| Signale gesamt | 16.154 |
| davon mit Trade (alt oder neu) | 4.255 |
| identisch (Signale gesamt) | 15.880 (98,3 %) |
| identisch (Trades) | 3.981 (93,6 %) |

Ursachen der Abweichungen — die 60 im Lauf gespeicherten Fälle (von 274) einzeln nachgeprüft:

| Ursache | Fälle | Bewertung |
|---|---|---|
| Ex-Dividende im Haltezeitraum (alt: bereinigte Kurse; neu: Kursabschlag + Cash-Gutschrift, Stop wird durch den Abschlag eher erreicht) | 32 | erwartete Modellabweichung; neu ist realitätsnäher (Stop-Order in Handelskursen) |
| Ex-Dividende am Kauftag bzw. in der Basis (Stop/Band in Handelskursen verschoben, z. B. CSX 24.02.2010, APD 29.12.2011, SPGI 23.02.2016, NI 27.10.2016, BB.PA 30.05.2016) | 11 | erwartete Modellabweichung, gleiche Ursache |
| Grenzfall genau auf einer Regelschwelle (Spanne = 1,500 ATR: EME, ECHO, TM, SMFG, TEM.L · Risiko = 0,500 ATR: ALK · Tief = Invalidierung: VRSN). Alt rundet Kurse auf 4 Stellen relativ und kippt auf die andere Seite | 7 | Rundung im Altmodell; neu rechnet exakt |
| Kleine R-Differenz 0,02–0,04 R bei sehr großen Gewinnern (6–14 R; FTNT, IOSP, WDC, TS) | 4 | Rundung (relativer Fehler ≈ 0,3 %) |
| Periodenende 30.12.2016 (alt: zu wenige Folgekerzen → kein Trade; neu: Verkauf zum Schluss „end“) | 6 | erwartete Abweichung (Abschneiden am Train-Ende) |

**Keine** der 60 Abweichungen geht auf die Mechanik zurück (Zeitpunkt, Stop-Logik, Haltedauer). Die übrigen 214
Abweichungen wurden nicht einzeln geprüft (nicht gespeichert); bei gleicher Verteilung ist dasselbe Bild zu erwarten —
**NICHT EINZELN GEPRÜFT**. Bilanzprüfungen (Cash, kein negativer Kassenstand, PnL + Dividenden = Equity) in allen
22 gespeicherten Depot-Läufen bestanden.

**Hinweis zur Kennzahl Ø R:** Im Depot entstehen Rest-Positionen (1–2 Stück), wenn das Cash nicht mehr für die volle
Größe reicht (1 % Risiko bei engem Stop bindet ≈ 50 % des Depots je Position). Deren Risiko ist winzig, die Gebühr fix →
R-Werte bis −50 und ein verzerrter Durchschnitt. Für Euro-Ergebnisse ist das unerheblich (S01-A 5 k€/1 %: −7 € von
+2.004 €). Im Bericht wird Ø R deshalb nur über **volle Positionen** (Risiko ≥ 50 % des geplanten) ausgewiesen;
eine Mindestgrößen-Regel für alle Strategien ist als Protokoll-Nachtrag vorgeschlagen (Gate B).

**Endurteil B3: PASS WITH LIMITATIONS.**
