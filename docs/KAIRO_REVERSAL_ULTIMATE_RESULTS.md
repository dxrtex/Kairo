# Kairo Reversal Ultimate – Ergebnisse (30.10.2026)

**Kurzfassung:** Keine der vier vorregistrierten Varianten (R1–R4) hat die vorher festgelegten Regeln erfüllt.
**Empfehlung: B60 unverändert behalten.** Die Korrektur der Engine-Fehler aus dem Code-Review verschiebt die Zahlen meist um
unter 1–2 Prozentpunkte. Die Entscheidung ändert sich dadurch nicht, ebenso wenig die Spitze der Rangfolge. Weiter unten in der
Rangfolge wechseln Plätze unter Varianten, die ohnehin Geld verlieren.

Grundlage: Plan `docs/KAIRO_REVERSAL_ULTIMATE_PLAN.md` (eingefroren bei Commit `26934ac`). Nur Forschung: App, Scanner und
`backend/rule.py` sind unverändert. Es gab keine Orders, keine kostenpflichtigen Daten und keinen Pull Request.

---

## 1. Code-Review: die 7 Punkte

| # | Punkt | Urteil | Was getan wurde |
|---|---|---|---|
| 1 | P0 – Depotwert zur Positionsgröße nutzt Schlusskurse des Kauftags (Look-ahead) | **BESTÄTIGT** | Neu `equity_open(d)`: Bestände zum letzten Schluss **vor** dem Kauftag, heute gekaufte zum Kaufkurs. Test `test_sizing_ignores_same_day_close_of_held_positions` |
| 2 | P0 – Wechselkurs des Kauftags (erst am Abend bekannt) | **BESTÄTIGT** | Neu `FX.known(cur, d)`: letzter Kurs **vor** dem Tag, auch für Gebühren und Spreads. Test `test_fx_at_open_uses_previous_known_rate` (USD, GBp) |
| 3 | P1 – R3: Mindestorder-Prüfung vor der Kapitalgrenze | **BESTÄTIGT** | Prüfung zusätzlich **nach** der Kapitalgrenze: Wird die Order unter 250 € gedrückt, entfällt sie (`fee_small`). Tests für 249/250/251 €, 200 € Kasse, zu hohes Risiko |
| 4 | P1 – R2 sortiert nach Stop-Abstand, nicht nach echten Kosten je R | **TEILWEISE** | Umsetzung entspricht der Vorregistrierung (Rangfolge nach Stop-Abstand in %), also kein Fehler. Ergänzende Messung: Spearman-ρ (Stop-Abstand, Kosten/R) = **−0,80**; 67 % des Fünftels mit dem weitesten Stop liegen auch im Fünftel mit den kleinsten Kosten je R. Gute, aber keine exakte Annäherung. Eine Rangfolge nach echten Kosten/R wäre eine neue Hypothese |
| 5 | P1 – R3: Vorteil durch weniger Gebühren oder durch mehr Risiko? | **BESTÄTIGT** | Risiko-Kennzahlen je Depot ergänzt (Tabelle 4). Bei 1.000 € kommt die R3-Verbesserung überwiegend aus **mehr Risiko**: 1,28 % statt 0,82 % je Trade, offenes Risiko 5,2 % statt 1,3 %, investiert 62 % statt 12 % |
| 6 | P1 – R4 ohne Zerlegung in Bausteine | **BESTÄTIGT** | Ablation X1–X3 nachgeholt, **ausdrücklich explorativ** (Tabelle 5) |
| 7 | P1 – Statistik: Trennung von Beleg und Hinweis | **BESTÄTIGT** | Train zählt nicht (Diagnose). Holdout 2022–26 ist nicht unabhängig (oft gesehen). Vorzeit 1999–2007 nur Hinweis, weil das Kerzen-Gate der Datenprüfung gescheitert ist. Holm über alle Tests |

Regressionstests: 34 Tests in `research/strategy_championship/tests/test_engine.py`. Die alte Engine fällt in genau den drei
neuen Fehlertests durch, die korrigierte besteht alle 34.

Betroffen von der Korrektur sind **nur Depot-Läufe**. Je-Trade-Ergebnisse in R hängen weder von der Depotgröße noch vom
Wechselkurs ab. Geprüft: Die E0-Trades sind alt und neu identisch (13.241 Trades).

## 2. Alt gegen neu – ändern sich Ergebnisse oder Rangfolge?

10.000 €, 20 × 0,25 %, Stress-Kosten, CAGR (Validierung 2017–21 / Holdout 2022–26 / gesamt 2008–26):

| Variante | alte Engine | korrigierte Engine |
|---|---|---|
| E0 = B60 | −0,8 % / −3,7 % / −0,1 % | −1,9 % / −5,7 % / −1,3 % |
| E2 Ausbruch | +1,8 % / −4,1 % / +1,3 % | +1,8 % / −4,2 % / +0,9 % |
| R1 | −2,9 % / −7,7 % / −0,7 % | −3,5 % / −8,9 % / −1,4 % |
| R2 | −3,6 % / −7,4 % / −2,1 % | −3,2 % / −8,2 % / −2,6 % |
| R3 | −1,6 % / −5,0 % / −0,6 % | −2,3 % / −4,7 % / −1,2 % |
| R4 | +1,6 % / −5,6 % / +0,4 % | +1,5 % / −6,7 % / −0,3 % |

- **Entscheidung:** In beiden Fassungen besteht keine Variante. R3 scheiterte schon mit der alten Engine (1.000 €). Mit der
  korrigierten Engine scheitert R3 zusätzlich bei 3.000 € (Validierung −10,5 % statt −10,2 % bei B60).
- **Rangfolge:** Die Spitze bleibt: bei 10.000 € / 20 Plätzen E2 vor allen anderen, bei 5 × 1 % R2 vor R4, bei 10 × 0,5 % R4
  vorn. Geändert haben sich Plätze im hinteren Feld. Dort liegen Varianten mit negativer Rendite, deren Abstände kleiner als
  das Rauschen sind.
- **Ultimate Runde 1 und Wettbewerb B:** Abweichungen ≤ ±2 Pp. Die Reihenfolge in Wettbewerb B ist unverändert: S16-B
  (+14,4 % / −30,6 %) > SP2F > S07-B > ACWI > S13-ETF > SP1F > K1 > B60. Die Empfehlungen in `KAIRO_ULTIMATE_RESULTS.md`
  bleiben gültig, die Zahlen dort stammen aber von der alten Engine.
- **Kleine Konten (1.000–3.000 €)** schwanken zwischen alt und neu teils extrem (z. B. von −100 % auf 0 %). Ursache sind
  keine Programmfehler: Feste Gebühren von 0,99–1,99 € je Order bei Einsätzen um 100 € leeren diese Konten. Kleine
  Unterschiede entscheiden dann nur, **wann** das Konto leer ist. Diese Zellen sind nicht aussagekräftig.

Vollständige Tabellen: Branch `claude/reversal-out`, Ordner `41031835455/` (`vergleich_reversal.md`, `vergleich_runde1.md`,
`wettbewerb_b_alt.md` / `_neu.md`).

## 3. Ergebnisse (korrigierte Engine)

### Je Trade (Ø R nach Stress-Kosten; Basis-Kosten in Klammern)

| Variante | Train (nur Info) | Validierung | Holdout | Vorzeit 1999–2007 (Hinweis) | Asien 2008–26 |
|---|---|---|---|---|---|
| E0 B60 | −0,071 | +0,069 (+0,229) | −0,068 (+0,073) | −0,065 (n 2.744) | +0,010 (n 14.204) |
| R1 | −0,030 | +0,073 (+0,213) | −0,043 (+0,085) | −0,057 (n 3.160) | +0,008 (n 16.843) |
| R4 | +0,014 | +0,101 (+0,202) | −0,079 (+0,005) | +0,002 (n 1.666) | +0,076 (n 8.622) |
| E2 | +0,015 | +0,101 (+0,202) | −0,079 (+0,005) | – | – |

Asien vollständig (30 von 30 Teilen; 20 Teile im Nachlauf 41031968365 wiederholt, weil sie im ersten Versuch am API-Limit
scheiterten, Code identisch).

**Auffällig:** Der Ausbruchs-Einstieg (R4 ≈ E2) ist je Trade in **beiden** unabhängigeren Datensätzen besser als B60: in der
Vorzeit um +0,068 R, in Asien um +0,067 R. In der Validierung beträgt der Vorsprung +0,032 R, im Holdout −0,011 R. Das ist
kein Beleg nach den Regeln (Holm 1,0; Depot-Kriterium verfehlt), aber der beständigste Hinweis der ganzen Untersuchung.
Er stützt die Empfehlung, E2 als Schattentest laufen zu lassen. R1 ist überall praktisch gleich wie B60.

Block-Bootstrap (Monatsblöcke) über Validierung + Holdout gegen B60: R1 p = 0,17, R4 p = 0,39. Nach Holm ist beides nicht
signifikant. Gegen Zufallstitel mit derselben Mechanik (20 Seeds) liegen R1 und R4 im Train+Val bei p = 0,05: Die Auswahl hat
einen kleinen echten Vorteil, nach Kosten bleibt davon kaum etwas.

**R4 ist je Trade praktisch identisch mit E2.** Der Mindestabstand von 1 ATR (R1) greift beim Ausbruchs-Einstieg fast nie, weil
der Buy-Stop über dem Entscheidungskurs liegt und der Stop dadurch schon weiter weg ist.

### Depot – CAGR nach Stress-Kosten, gesamt 2008–26 (max. Rückgang)

| Variante | 5.000 € 5 × 1 % | 10.000 € 5 × 1 % | 10.000 € 10 × 0,5 % | 10.000 € 20 × 0,25 % | 20.000 € 20 × 0,25 % |
|---|---|---|---|---|---|
| E0 B60 | −1,4 % (−77 %) | +0,8 % (−71 %) | −0,8 % (−63 %) | −1,3 % (−52 %) | −1,2 % (−52 %) |
| E2 | −1,3 % (−51 %) | −0,6 % (−48 %) | +1,3 % (−33 %) | +0,9 % (−29 %) | +0,9 % (−30 %) |
| R1 | −3,3 % (−86 %) | −4,9 % (−83 %) | −2,1 % (−69 %) | −1,4 % (−53 %) | −0,3 % (−46 %) |
| R2 | +2,1 % (−71 %) | +2,4 % (−73 %) | −2,6 % (−71 %) | −2,6 % (−48 %) | −1,7 % (−41 %) |
| R3 | −0,7 % (−69 %) | −2,2 % (−73 %) | −2,6 % (−68 %) | −1,2 % (−55 %) | −1,0 % (−50 %) |
| R4 | +2,1 % (−46 %) | +2,0 % (−44 %) | +1,7 % (−32 %) | −0,3 % (−36 %) | −0,1 % (−35 %) |
| *Welt-ETF (ACWI)* | | | | *+9,0 % (−46 %)* | |
| *Dual Momentum S16-B* | | | | *+14,4 % (−31 %)* | |

Zum Vergleich mit Basis-Kosten: B60 (10.000 €, 20 × 0,25 %) liegt bei **+5,9 %** statt −1,3 %. **Spreads und Schlupf kosten
rund 7 Prozentpunkte pro Jahr.** Ob die Strategie Geld verdient, hängt also fast vollständig an der Ausführungsqualität.

### Entscheidung nach Plan

| Variante | Bedingung | Ergebnis | Urteil |
|---|---|---|---|
| R1 | je Trade besser in Val, Vorzeit, Asien; Holm; Depot 10k besser in Val & Hold | ΔR Val +0,003, Vorzeit +0,009, Asien −0,002; Holm 1,0; Depot Val −3,5 % vs. −1,9 % | **nicht bestanden** |
| R2 | Depot 10k (20 × 0,25 %) besser in Val & Hold; Holm | Val −3,2 % vs. −1,9 %, Hold −8,2 % vs. −5,7 % | **nicht bestanden** |
| R3 | Depot 5 × 1 % bei 1k, 3k, 5k besser in Val & Hold; Holm | 3k Val −10,5 % vs. −10,2 %; Holm p 0,39–1,0 | **nicht bestanden** |
| R4 | wie R1 + Depot 10k besser als B60 **und** E2 in Val & Hold | je Trade ΔR Val +0,032, Vorzeit +0,068, Asien +0,067, Holm 1,0; Depot Val +1,5 % (B60 −1,9 %, E2 +1,8 %), Hold −6,7 % (B60 −5,7 %) | **nicht bestanden** |

### 4. R3 – Gebühren oder Risiko? (5 × 1 %, Stress, gesamt)

| Kapital | Variante | CAGR | max. Rückgang | Ø Risiko je Trade | Ø offenes Risiko | Ø investiert | Ø Gebühr je Trade | Ø Einsatz |
|---|---|---|---|---|---|---|---|---|
| 1.000 € | B60 | −29,5 % | −100 % | 0,82 % | 1,3 % | 12 % | 3,58 € | 103 € |
| 1.000 € | R3 | −3,7 % | −64 % | 1,28 % | 5,2 % | 62 % | 0,48 € | 282 € |
| 3.000 € | B60 | −2,1 % | −71 % | 0,83 % | 7,6 % | 82 % | 0,25 € | 801 € |
| 3.000 € | R3 | +0,6 % | −68 % | 0,85 % | 7,8 % | 82 % | 0,03 € | 1.005 € |
| 5.000 € | B60 | −1,4 % | −77 % | 0,84 % | 7,8 % | 82 % | 0,05 € | 1.436 € |
| 5.000 € | R3 | −0,7 % | −69 % | 0,85 % | 7,7 % | 82 % | 0,01 € | 1.391 € |

Bei 1.000 € spart R3 Gebühren, nimmt aber deutlich mehr Risiko. Ab 3.000 € sind Risiko und Gebühren fast gleich, und der
Unterschied ist Rauschen.

### 5. Ablation R4 (EXPLORATIV – nicht Teil der Entscheidung), 10.000 €, 20 × 0,25 %, Stress

| Variante | Inhalt | Validierung | Holdout | gesamt | max. Rückgang |
|---|---|---|---|---|---|
| E2 | Ausbruch allein | +1,8 % | −4,2 % | +0,9 % | −29 % |
| X1 | E2 + R1 | +1,8 % | −4,1 % | +0,9 % | −29 % |
| X2 | E2 + R1 + R2 | +1,2 % | −6,9 % | −0,6 % | −38 % |
| X3 | E2 + R1 + R3 | +2,1 % | −4,9 % | +1,0 % | −28 % |
| R4 | alles | +1,5 % | −6,7 % | −0,3 % | −36 % |

Lesart: R1 bringt beim Ausbruch nichts, **R2 schadet** (Rangfolge nach Stop-Abstand verschlechtert Rendite und Rückgang),
R3 ist neutral. Die Summe ist schlechter als E2 allein.

## 6. Die 8 Entscheidungsfragen

**1. Beste bisher getestete Mean-Reversion-Version?**
Nach den Regeln gilt: **B60 bleibt die Referenz.** Keine Variante hat eine Verbesserung belegt. Am robustesten unter den
getesteten Versionen ist der **Ausbruchs-Einstieg E2** (Kauf erst über dem Hoch der Basis). Bei 10.000 € und mehr hat er in
Validierung und Holdout eine höhere Depotrendite als B60 und deutlich kleinere Rückgänge (−29 % statt −52 %). Er hat aber in
Runde 1 die Je-Trade-Regeln nicht bestanden und ist damit ebenfalls nicht belegt.

**2. Welche Verbesserung gegenüber B60 ist nachgewiesen?**
**Keine.** Alle Unterschiede liegen innerhalb des Zufalls (Holm-p ≥ 0,39).

**3. Höchste langfristige Nettorendite?**
Unter den Rücksetzer-Varianten R2 / R4 mit 5 × 1 % bei 5.000–10.000 €: **+2,0 bis +2,4 % p. a.** nach Stress-Kosten, bei
Rückgängen von −44 % bis −73 %. Das ist weit unter dem Welt-ETF (+9,0 %) und Dual Momentum S16-B (+14,4 %).

**4. Beste risikobereinigte Rendite?**
**R4 bzw. E2 mit 10 × 0,5 %** (+1,3 bis +1,7 % bei −32 % Rückgang). Sie liegen aber immer noch unter jedem ETF-Vergleich.

**5. Was ist bei kleinem Tradingkapital sinnvoll?**
Unter 5.000 € ist **keine** Rücksetzer-Variante sinnvoll. Feste Gebühren und Stress-Spreads fressen den Vorteil auf, mehrere
Konten laufen im Test leer. R3 mildert das nur, indem es mehr Risiko nimmt. Für kleine Konten ist ein ETF bzw. S16-B klar
überlegen (siehe `KAIRO_ULTIMATE_RESULTS.md`).

**6. Verbleibende wissenschaftliche Unsicherheiten**
- **Survivorship-Bias:** Das Universum enthält nur heute existierende Firmen (+7,6 Pp. p. a. Rückenwind gegenüber RSP).
  Die wahren Werte liegen also eher **noch niedriger**. Beheben lässt sich das nur mit kostenpflichtigen Daten (Norgate, nicht
  freigegeben).
- **Kosten:** Zwischen Basis- und Stress-Kosten liegen rund 7 Pp. p. a. Die echten Spreads beim Broker zur Handelszeit sind
  nicht gemessen.
- **Fette Ränder:** Die besten 10 % der Trades tragen den gesamten Gewinn. Welche davon ein Depot mit begrenzten Plätzen
  erwischt, ist weitgehend Zufall. Darum weichen Depot-R (z. B. B60 5 × 1 % Val −0,21 R) und Je-Trade-R (+0,07 R) stark
  voneinander ab.
- Der Holdout ist nicht unabhängig. Die Vorzeit (1999–2007) ist nur ein Hinweis (Datenqualitäts-Gate gescheitert). Asien ist
  vollständig ausgewertet, enthält aber ebenfalls nur heute existierende Firmen.

**7. Neuer unabhängiger Paper-Test?**
**B60 unverändert weiterlaufen lassen** als Referenz. Daneben als reiner Schattentest ohne Geld **E2 (Ausbruchs-Einstieg),
20 × 0,25 %**, weil er die kleineren Rückgänge über alle Zeiträume zeigt. Bewertet wird frühestens nach 12 Monaten bzw.
150 Trades, unverändert und mit dem echten Broker-Spread.

**8. Was wäre für eine produktive Umsetzung nötig?**
Derzeit nichts, weil nichts belegt ist. Falls E2 den Paper-Test besteht: Buy-Stop-Order statt Kauf zur Eröffnung, eine
Ausbruchs-Anzeige im Scanner („Kauf über X €“), Kontogröße ab 10.000 €, sowie Messung der tatsächlichen Spreads im Journal.
Die Umstellung erfolgt erst nach ausdrücklicher Freigabe.

---

## Reproduktion

| Was | Wert |
|---|---|
| Plan eingefroren | Commit `26934ac` |
| Engine-Korrektur | Commit `a084e2f` (+ `12cc911` Workflow), Tests 34/34 |
| Daten | `prices_v1` SHA-256 `e405016e2348755bb9eef3fe5e70e7f6ff405755b15487fd15fd310a5e823c3c` |
| Testlauf (Je-Trade, Zufall, Bestätigung; alte Engine) | Workflow-Run 41014032183 (Commit `c44cbfe`) |
| Depot-Läufe korrigierte Engine | Workflow-Run 41023535500 |
| Alt-Neu-Vergleich, Wettbewerb B neu | Workflow-Run 41031835455 (Commit `00ced6a`) |
| Asien-Nachlauf | Workflow-Run 41031968365 |
| Endbericht (alle Bestätigungsdaten) | Workflow-Run 41062843542, Branch `claude/reversal-out`, Ordner `final-41062843542/` |
| Code | `research/reversal/run.py`, `research/reversal/compare.py`, `research/strategy_championship/engine.py` |
| Kosten | Basis: 0,99 €/Order unter 250 €, Titel-Spread; Stress: 1,99 €/Order unter 250 €, doppelter Spread, Schlupf, FX-Gebühr |
