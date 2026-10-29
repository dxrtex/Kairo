# Schwellen-Prüfung aller Kairo-Kriterien (28./29.10.2026)

Frage (Jonny): Sind die festgelegten Werte der 11 Kriterien die renditestärksten?
Lauf research_sweep #40778404648 (Branch claude/sweep, Skript research/strategy_championship/sweep.py), Datensatz v1,
2.954 Aktien 2008–2026, Einstieg/Ausstieg wie in allen Tests (S01-B-Basis, EMA20-Ausstieg), R netto bei 5.000 € PRIME+.
78 Varianten: je Kriterium andere Werte bzw. Kriterium weglassen, immer nur eine Änderung. Gegenprobe vor dem Lauf: mit
den heutigen Werten exakt dieselben Treffer wie der echte Scanner (AMD, NVIDIA, D-Wave).
Vorab-Regel: bester Wert nur aus Train (2008–16), dann besser in Validierung (2017–21) UND Holdout (2022–26) und p ≤ 0,05/11.

| Kriterium | heute | Train-Bester | Train | Validierung | Holdout | p | bestanden |
|---|---|---|---|---|---|---|---|
| (heute) | | | +0,127 (2.202) | +0,265 (2.001) | +0,106 (2.671) | | |
| Rückgang vom Hoch | ≥ 12 % | weglassen | +0,156 | +0,267 | +0,086 | 0,54 | nein |
| Kein Crash | > −25 % | −15 % | +0,128 | +0,266 | +0,105 | 0,51 | nein |
| Abflachung | 1,5 ATR | 1,0 ATR | +0,146 | +0,299 | +0,063 | 0,57 | nein |
| Zone | Fib 0,618–0,79 | 0,618–0,706 | +0,134 | +0,272 | +0,095 | 0,52 | nein |
| RSI-Divergenz | ≥ 3 Punkte | ≥ 5 Punkte | +0,153 | +0,296 | +0,133 | 0,28 | nein (überall besser, nicht signifikant) |
| RSI-Bereich | 28–48 | 28–44 | +0,149 | +0,223 | +0,042 | 0,86 | nein |
| MACD dreht | Kreuz ≤ 7 T. | ≤ 15 T. | +0,160 | +0,247 | +0,104 | 0,58 | nein |
| MBI | rot ≤ 70 % | ≤ 50 % | +0,196 | +0,226 | +0,005 | 0,93 | nein |
| Chance-Risiko | ≥ 2,0 | heute am besten | | | | | – |
| Struktur (EMA) | Pflicht | weglassen | +0,127 | +0,265 | +0,092 | 0,57 | nein |
| MACD unter 0 | Pflicht | heute am besten | | | | | – |

Weitere Befunde:
- Divergenz „tiefster RSI ± 2 Tage“ (D-Wave-Vorschlag): deutlich schlechter (+0,062 / +0,255 / +0,087) – nicht übernehmen.
- Kein Kriterium ist überflüssig: Weglassen senkt das Ø R je Trade fast immer (stärkste Wirkung: MBI, MACD dreht, RSI-Bereich).
- Weglassen bringt teils mehr Trades und mehr Summe R (z. B. ohne MBI), aber schlechtere Trades – bei begrenztem Kapital ungünstig.
- Kandidat für Beobachtung: Divergenz ≥ 5 Punkte war in allen drei Zeiträumen besser (+0,03 R), aber nicht signifikant.

Ergebnis: Keine Änderung besteht die Vorab-Regel → kein Kombi-Test nötig, der Scanner bleibt unverändert.
Hinweis: Die Zahl der Trades (6.874) ist kleiner als im Lauf vom 19.10. (13.241), weil hier der heutige Scanner-Stand
verwendet wurde; Vergleiche innerhalb dieses Laufs sind gleichwertig.
