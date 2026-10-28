# Fib-Tiefe der Konsolidierung (28.10.2026)

Frage (Jonny): Macht es einen Unterschied, ob sich die Konsolidierung an der 0,618, 0,706 oder 0,79 bildet?
Daten: 13.241 Kairo-Trades 2008–2026 (R netto bei 5.000 € PRIME+), Fib-Anker des echten Scanners (Daten bis Tag vor Kauf),
Tiefe = (H − Tief der letzten 5 Kerzen) / (H − L). Skript `tools/research/fib_level_test.py`.
Vorab-Regel: Eimer in Train, Validierung UND Holdout besser als der Rest und gepoolt p ≤ 0,01.

| Tiefe | Train | Validierung | Holdout |
|---|---|---|---|
| < 0,618 | +0,20 (1.207) | +0,20 (1.102) | +0,01 (1.327) |
| 0,618–0,706 | +0,12 (411) | +0,33 (411) | +0,18 (573) |
| 0,706–0,79 | +0,09 (450) | +0,28 (370) | +0,08 (577) |
| 0,79–0,886 | +0,05 (415) | +0,39 (361) | +0,32 (593) |
| ≥ 0,886 | +0,06 (1.731) | +0,22 (1.521) | +0,05 (2.192) |
| alle | +0,11 | +0,25 | +0,09 |

Ergebnis: keine Level-Regel besteht. 0,618–0,706 überall leicht besser, aber nicht signifikant (p 0,11);
0,79–0,886 in Train am schlechtesten, danach am besten – kein stabiles Muster. Frühere Prüfung 19.10.2026
(„an der 0,79“, docs/strategy_championship/21_FIB079_HYPOTHESIS.md im Forschungszweig): ebenfalls nicht bestätigt.
Folge: keine Änderung am Scanner.
