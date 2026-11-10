# Studie Fibonacci-Zonen (Lauf vom 10.11.2026)

**Frage:** Welche Rücksetzer-Tiefe bringt mit der Kairo-Regel am meisten – und stimmt die Zone der Scan-Regel?
**Daten:** 1.321 Aktien (heutiges Universum), Tageskerzen 14.11.2017 – 06.11.2026, 244.224 Ereignisse,
56.270 Trades. Workflow `fibstudy.yml`, Auswertung `backend/fibstudy.py`, Lauf 42709934343.
**Regel:** exakt wie live (B60, `backend/rule.py`): bis 10 Tage auf die Seitwärtsphase warten, Kauf zur Eröffnung,
Stop = Basis-Tief − 0,25 ATR, ab Tag 10 Ausstieg bei Schluss unter EMA 20, spätestens Tag 60.
Ergebnis netto in R je Trade (nach Spread/Gebühr, Aktie ohne Hebel). Lernjahre bis 2023, Prüfjahre ab 2024.
Nur was in **beiden** Zeiträumen hält, gilt als belastbar. Die Scan-Regel wurde **nicht** geändert.

## 1. Kairo-Treffer insgesamt

| | Trades | netto R | Gewinnquote | Profit-Faktor | 90-%-Bereich |
|---|---|---|---|---|---|
| alle | 4.985 | **+0,146** | 32,5 % | 1,22 | +0,09 … +0,21 |
| Lernjahre bis 2023 | 3.317 | +0,159 | 33,1 % | 1,24 | +0,08 … +0,23 |
| Prüfjahre ab 2024 | 1.668 | +0,119 | 31,4 % | 1,18 | +0,01 … +0,24 |

→ Die Regel verdient in beiden Zeiträumen Geld – wenig je Trade, aber stabil (wenige große Gewinner, viele kleine Stops).

## 2. Nach Rücksetzer-Tiefe (Retracement vom Hoch zum Tief)

| Tiefe | Trades | netto R | Lernen | Prüfen | Urteil |
|---|---|---|---|---|---|
| 0,382–0,5 | 407 | +0,05 | +0,06 | +0,03 | schwach |
| 0,5–0,618 | 746 | **+0,22** | +0,21 | +0,23 | **belastbar gut** (heute nur über die Unterstützung im Scan) |
| 0,618–0,706 | 524 | +0,15 | +0,26 | −0,01 | uneinheitlich |
| **0,706–0,79 (Golden Pocket)** | 577 | **+0,24** | +0,22 | +0,27 | **belastbar am besten** |
| 0,79–0,886 | 583 | +0,01 | +0,01 | +0,02 | **kein Vorteil** |
| 0,886–1 | 490 | 0,00 | −0,11 | +0,24 | uneinheitlich |

## 3. Nach Art der Zone

| Zone | Trades | netto R | Lernen | Prüfen |
|---|---|---|---|---|
| nur Fibonacci | 240 | +0,22 | +0,23 | +0,20 (kleine Zahl) |
| nur Unterstützung | 3.523 | +0,13 | +0,14 | +0,12 |
| beides | 1.222 | +0,17 | +0,21 | +0,10 |
| Golden Pocket (in der Zone) | 886 | +0,20 | +0,21 | +0,19 |

## 4. Nach Impulsgröße (Anstieg Tief → Hoch)

15–30 %: +0,24 (beide Zeiträume gut) · 30–60 %: +0,03 (Prüfen −0,07) · 60–120 %: +0,30 (beide gut) · über 120 %: +0,08.
Kein klares Muster (30–60 % fällt aus der Reihe) → als Zufall werten, nicht danach filtern.

## Folgerungen

1. **Golden Pocket (0,706–0,79) ist die stärkste Zone** – in beiden Zeiträumen gut 0,2 R je Trade, deutlich über dem Schnitt.
2. **Unter 0,79 (bis 0,886) bringt praktisch nichts** (+0,01 R). Diese Treffer kommen heute über die Unterstützung durch.
3. **0,5–0,618 ist überraschend stark und stabil** (+0,22 R), wird von der Fibonacci-Zone aber nicht erfasst.
4. Nicht prüfbar war, wie viele *zusätzliche* Signale eine Zone 0,5–0,79 bringen würde (Gruppe „nur die Zone fehlt“ war leer –
   solche Tage werden vom Scan nicht als Fast-Treffer geführt). Dafür ist ein eigener Vergleichslauf nötig.

**Empfehlung (Entscheidung bei Jonny, keine Änderung ohne Zustimmung):** Als Nächstes einen Vergleichslauf mit
Fibonacci-Zone 0,5–0,79 und einer Variante, die Treffer mit Rücksetzer 0,79–0,886 zurückstuft. Erst wenn beide Zeiträume
bestätigen, wird die Scan-Regel angepasst.

**Grenzen:** Heutiges Aktien-Universum (Survivorship-Bias → eher zu gut), keine Steuern, Aktie ohne Hebel.
