# Kairo Reversal Ultimate – Bestandsaufnahme, Diagnose und vorregistriertes Protokoll (30.10.2026)

Ziel: die beste belastbare Version der Kairo-Rücksetzer-Idee (B60) – B60 bleibt die unveränderte Referenz, Dual Momentum und
Welt-ETF sind nur Vergleichsmaßstäbe. Produktive App, Scanner und `backend/rule.py` bleiben unverändert; neue Varianten nur
unter `research/`. Kostenpflichtige Daten nur mit Freigabe.

Code-Stand: Branch `claude/ultimate-research`. Datensatz `prices_v1` (SHA-256 `e405016e…`). Engine
`research/strategy_championship/engine.py`. Diagnose-Lauf: Workflow-Run 41013256065 (Commit `0c7c66c`).

---

## Phase 1 – Warum B60 trotz plausibler Signale kein überzeugendes Depot ergibt

Grundlage: 13.241 B60-Trades 2008–2026 (je Trade, unbegrenztes Kapital) und Depot-Läufe aus Kairo Ultimate Runde 1.

1. **Der Gewinn kommt aus sehr wenigen Trades.** Im Train (2008–16) liegt die Summe aller 4.214 Trades bei −220 R (Stress).
   Die besten 1 % bringen +496 R, die besten 10 % +2.086 R – **ohne die besten 10 % wäre B60 mit −2.306 R tief im Minus.**
   Median-Trade −0,86 R, Trefferquote 31 %. Validierung und Holdout zeigen dasselbe Bild.
2. **Ausstiege:** 49 % enden am Stop (Ø −1,09 R), 7 % mit Kurslücke unter den Stop (Ø **−1,52 R**), 43 % mit dem EMA20-Signal
   (Ø +1,15 R), 1 % am Tag 60 (Ø **+10,1 R**). Die großen Gewinner laufen bis zum Zeitende; nach Tag 60 kommt im Schnitt nur
   noch +0,9 % in 60 Tagen → längeres Halten bringt nichts.
3. **Kosten sind der Hauptgegner – und sie hängen am Stop-Abstand.** Stress-Kosten in R je Trade nach Stop-Abstand (alle Jahre):

   | Stop-Abstand vom Kauf | Trades | Ø R Basis | Ø R Stress | Kosten in R |
   |---|---|---|---|---|
   | < 2 % | 1.307 | +0,035 | −0,219 | 0,35 |
   | 2–3 % | 3.741 | +0,089 | −0,098 | 0,25 |
   | 3–5 % | 5.619 | +0,148 | +0,018 | 0,17 |
   | 5–8 % | 2.113 | +0,170 | +0,084 | 0,11 |
   | > 8 % | 461 | +0,301 | +0,245 | 0,07 |

   38 % aller Trades haben einen Stop unter 3 % und verlieren nach Stress-Kosten Geld – auch vor Kosten sind sie schwächer
   (enge Stops liegen im normalen Tagesrauschen; Trefferquote 25 % im untersten Fünftel).
4. **Kleine Konten scheitern an den Gebühren.** 5.000 €, 20 × 0,25 %: Ø Einsatz 203 € → unter der PRIME+-Grenze von 250 €,
   Ø 2,76 € Gebühr je Trade bei 12,50 € Risiko (≈ 0,2 R allein Gebühr). 10.000 €: Ø Einsatz 762 €, Gebühren fast null.
5. **Kapitalbindung und Auswahl:** Bei 10.000 € / 20 Plätzen sind die Plätze oft voll (3.336 Signale ohne Platz), Ø 72 %
   investiert. Welche Signale den Platz bekommen, entscheidet die Rangfolge – bisher „schwächeres Vormomentum zuerst“.
6. **Auswahl-Vorteil klein, Survivorship groß:** B60 ist je Trade nur ≈ +0,03 R besser als Zufall mit derselben Mechanik;
   das heutige Universum hat +7,6 Pp. p. a. Rückenwind gegenüber einem Index mit allen damaligen Firmen.

**Welche Komponenten tragen?** Belegt: Basis-Einstieg + Stop unter der Basis + Gewinner bis Tag 60 laufen lassen (Mechanik,
auch mit Zufallstiteln positiv vor Kosten); schwaches Vormomentum je Trade (Bericht 22). Nicht belegt: Fib-Tiefe,
strengere Divergenz, Ruhe, Volumen-Austrocknung, Marktfilter, Fundamentalfilter, 4H, Nachrichten-Filter (N1), Gültigkeits-
Prüfung (V1). Offen und wirtschaftlich relevant: **Kosten je R, Kapitalverteilung, kleine Konten** – also nicht „welches
Signal“, sondern „welcher Trade lohnt sich nach Kosten und wie wird das Kapital verteilt“.

## Phase 2 – Diagnose (EXPLORATIV, nur Train 2008–2016)

Merkmale am Abend vor dem Kauf, Ø R Stress je Fünftel (Spearman-ρ). Vollständige Tabelle: Lauf 41013256065, Datei
`diag_report.md`.

| Merkmal | Befund im Train | ρ |
|---|---|---|
| Stop-Abstand in % | unterstes Fünftel (< 2,3 %) −0,17 R, Trefferquote 25 % | **+0,18** |
| Kosten in R | oberstes Fünftel (> 0,26 R) −0,20 R | **−0,17** |
| Stärke des Anstiegs vor der Korrektur | nur das oberste Fünftel (≥ +88 %) positiv (+0,21 R) | +0,05 |
| Markt-/Sektoranteil am Rückgang (A2) | marktweite Rückgänge eher schlechter, kein klares Muster | ≈ 0 |
| Abstand zu Quartalszahlen, Nachrichten-Rückgang | kein stabiles Muster (N1 schon gescheitert) | ≈ 0 |
| Volumen-Austrocknung, Auf-/Ab-Volumen, kleinere Abwärtstage, ATR-Kontraktion, höhere Tiefs, relative Stärke in der Basis | kein monotones Muster, teils gegen die Erwartung | |ρ| < 0,04 |
| Stand an Tag 10 | R ≤ −0,5 an Tag 10: Ø Ende −0,92 R, 0 von 180 werden große Gewinner – wird vom EMA20-Ausstieg ab Tag 10 schon weitgehend erfasst | – |

**Lesart:** Die technischen Erschöpfungs-Merkmale (Forschungsfeld B) und die Ursache des Rückgangs (Feld A) trennen Gewinner
und Verlierer in diesen Daten nicht – das bestätigt frühere Studien. Der einzige starke, wirtschaftlich erklärbare
Unterschied ist **der Stop-Abstand relativ zu Kosten und Rauschen** (Feld E/C). Fundamentale Erwartungsänderungen (A3)
brauchen zeitpunktgenaue Analystenschätzungen; die gibt es nicht kostenlos → offen, nicht testbar.

---

## Phase 3 – Vorregistrierte Hypothesen (eingefroren vor dem ersten Test; Code `research/reversal/run.py`)

Gemeinsam: Treffer = unveränderter Scanner 11/11, B60-Basis (5 Kerzen ≤ 1,5 ATR, max. 10 Tage, Invalidierung), Ausstieg
B60 (Stop, EMA20 ab Tag 10, spätestens Tag 60). Alle Varianten in derselben Engine. **Prüfdaten: Validierung 2017–21,
Holdout 2022–26 (nur Hinweis, schon oft gesehen), Vorzeit 1999–2007 und Asien 2008–26** – der Train ist durch die Diagnose
verbraucht und zählt nicht als Beleg.

### R1 – Stop-Mindestabstand 1 ATR (Kosten und Rauschen)
- Begründung: Stops innerhalb des normalen Tagesrauschens werden zufällig ausgelöst; feste Kosten wiegen bei engem Stop
  schwer. Ein weiterer Stop mit kleinerer Stückzahl hält das Euro-Risiko gleich, senkt Kosten je R und Fehl-Stopps.
- Regel: Stop = min(B60-Stop, Schluss am Entscheidungstag − 1,0 × ATR14). Sonst alles wie B60 (Risiko 0,5–3 ATR ab Kauf).
- Kein Trade fällt weg; nur breitere Stops. Schwelle 1,0 ATR ist eine runde, nicht aus den Daten gesuchte Zahl.

### R2 – Rangfolge nach Kosten je R (Kapital an die günstigsten Trades)
- Begründung: Bei vollen Plätzen soll das knappe Kapital an Trades gehen, deren Kosten im Verhältnis zum Risiko am kleinsten
  sind. (Die frühere Rangfolge „ruhigere zuerst“ ist das Gegenteil und war schlecht – das passt dazu.)
- Regel: bei mehreren kaufbereiten Signalen am selben Tag zuerst der größte Stop-Abstand in % (statt schwächeres
  Vormomentum). Nur Depot-Wirkung.

### R3 – Gebührenbewusste Mindestorder für kleine Konten
- Begründung: Unter 250 € Orderwert kostet jede Order 0,99 € (Stress 1,99 €); bei 1.000–5.000 € ist das ein Großteil des
  Risikos je Trade.
- Regel: ergibt die 1-%-Rechnung (bzw. 0,5 % / 0,25 %) einen Orderwert unter 250 €, wird auf 250 € aufgestockt, **wenn**
  das Risiko dadurch höchstens doppelt so groß wird wie geplant; sonst wird der Trade ausgelassen. Nur Depot-Wirkung, Fokus
  1.000 / 3.000 / 5.000 €.

### R4 – „Kairo Reversal Ultimate“: die Kombination
- Ausbruchs-Einstieg E2 (bester Einstieg aus Runde 1) + R1 + R2 + R3. Keine neuen Parameter. Bei E2 bezieht sich der
  Mindestabstand auf den Buy-Stop-Kurs (Stop = min(E2-Stop, Buy-Stop-Kurs − 1 ATR)), die Rangfolge ebenso.
- Frage: Verstärken sich die Bausteine, oder ist die Summe nicht besser als die Teile?

### Bestehensregeln (vor dem Lauf festgelegt)
- **R1 (je Trade):** Ø R Stress besser als B60 in Validierung, Vorzeit **und** Asien; Holdout wird berichtet. Block-Bootstrap
  (Monate) über Validierung + Holdout gepoolt p ≤ 0,05 nach Holm (4 Tests). Zusätzlich Depot 10.000 € (20 × 0,25 %) Stress-CAGR
  besser als B60 in Validierung und Holdout.
- **R2 / R3 (Depot):** Stress-CAGR besser als B60 in Validierung **und** Holdout bei 10.000 € (R2) bzw. bei 1.000, 3.000 und
  5.000 € (R3, je mit 5 × 1 %); Block-Bootstrap (3-Monats-Blöcke) der Tagesrenditen gegen B60, p ≤ 0,05 nach Holm.
- **R4:** wie R1 je Trade (gegen B60) und zusätzlich Depot-CAGR (Stress) bei 10.000 € in Validierung und Holdout über B60 **und**
  über E2.
- Alle: Ergebnis auch ohne die 223 unsicheren Titel und ohne die besten 1 % der Trades berichten; Vergleich mit ACWI,
  Dual Momentum (S16-B) und Zufall (gleiche Mechanik).
- Erfüllt keine Variante die Regeln: **„Keine Verbesserung nachgewiesen – B60 unverändert behalten.“**

### Nicht getestet (begründet)
- Weitere technische Bestätigungen (Volumen, Kerzen, relative Stärke): in der Diagnose kein Signal, früher gescheitert.
- Adaptive Wahl früh/Ausbruch: kein beobachtbares Merkmal unterscheidet die Fälle (Schlusslage, höhere Tiefs neutral).
- Früher Ausstieg bei Scheitern: wird vom EMA20-Ausstieg ab Tag 10 schon weitgehend erfasst; längeres Halten nach Tag 60
  bringt nichts.
- Analysten-Erwartungsänderungen: keine kostenlosen Point-in-Time-Daten.
- Survivorship beheben: nur mit kostenpflichtigen Daten möglich (Norgate US Platinum, ca. 630 USD/Jahr) – nicht freigegeben;
  bis dahin wird jedes Ergebnis mit dem gemessenen Bias von +7,6 Pp. p. a. eingeordnet.
