# Wellenstudie: Wo beginnt die kleine Fibonacci-Welle? (10.11.2026)

Frage (TSMC 11/2026): Soll die Welle schon an einem Tief beginnen, vor dem ein flacherer Rücksetzer lag (z. B. 61,8 %)?
Getestet mit der echten Chart-Logik (`tools/wave_js.mjs` → `chartModel` aus `site/index.html`), ohne Blick in die Zukunft,
1.197 Aktien, 2018–2026, 308.636 Stichtage. Lauf: Actions-Run 42919919396. Code: `backend/wavestudy.py`.

Gemessen: wo der Kurs nach dem Hoch tatsächlich dreht (Rückprall ≥ ¼ der Welle oder neues Hoch), ausgedrückt als Tiefe der Welle.
Dichte-Faktor = Wenden im Golden Pocket je 0,01 Tiefe ÷ Nachbarbereiche (1,0 = Zufall).

## Direktvergleich (nur Fälle, in denen die Grenze eine andere Welle liefert als heute 0,786)

| Grenze | Fälle | GP-Treffer heute / neu | Dichte heute / neu | Hält im GP heute / neu | Lernjahre Dichte | Prüfjahre Dichte |
|---|---|---|---|---|---|---|
| 0,5   | 17.306 | 5,3 % / 4,4 % | 1,22 / 1,04 | 37 % / 27 % | 1,24 / 1,11 | 1,20 / 0,92 |
| 0,618 | 12.817 | 5,6 % / 4,1 % | 1,29 / 1,00 | 38 % / 27 % | 1,32 / 1,07 | 1,23 / 0,90 |
| 0,706 |  7.568 | 6,9 % / 3,8 % | 1,79 / 0,97 | 43 % / 27 % | 1,76 / 1,03 | 1,85 / 0,88 |
| 0,886 | 13.011 | 3,7 % / 5,1 % | 0,93 / 0,90 | 26 % / 31 % | 0,94 / 0,93 | 0,93 / 0,86 |

Ergebnis: Die heutige Grenze 0,786 ist die beste. Gegen 0,5 / 0,618 / 0,706 gewinnt sie in beiden Zeiträumen deutlich;
die strengere 0,886 bringt keine echte Verbesserung (Dichte beider ≈ Zufall, der höhere GP-Anteil kommt nur von größeren Wellen).
Über ALLE Wellen liegt der Dichte-Faktor bei ≈ 1,0 – der Golden Pocket allein ist kein Wendepunkt; seinen Wert hat er
zusammen mit den übrigen Kairo-Kriterien (research/fibstudy: 0,706–0,79 → +0,24 R je Trade).
Entscheidung: keine Änderung (Jonny entscheidet).
