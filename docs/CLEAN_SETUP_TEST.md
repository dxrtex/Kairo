# Saubere Setups (28.10.2026)

Frage (Jonny): Bringen nur „saubere“ Setups – ruhige Konsolidierung nach dem Abverkauf, wenig Hin und Her – bessere Trades?
Daten: 13.241 Kairo-Trades (heutige Regel, R netto bei 5.000 € PRIME+), Merkmale am Tag vor dem Kauf.
Skript: `tools/research/clean_setup_test.py`. Regel vorab: sauberstes Fünftel in allen drei Abschnitten besser und p ≤ 0,05/7.

| Merkmal | Train | Validierung | Holdout | p | vorab bestanden |
|---|---|---|---|---|---|
| tight: Spanne 5 Tage / ATR (klein) | +0,10 / +0,11 | +0,34 / +0,22 | +0,24 / +0,05 | 0,005 | knapp nein (Train) |
| chop: Hin und Her 10 Tage (klein) | +0,18 / +0,09 | +0,23 / +0,25 | +0,30 / +0,03 | 0,007 | knapp nein (Validierung) |
| hug, wicks, vdry | gemischt | | | > 0,4 | nein |
| selloff / speed: starker Abverkauf | schlechter | schlechter | schlechter | > 0,99 | nein – eher Nachteil |

Nachträglich (nicht vorab festgelegt): Spanne ≤ 1,5 ATR **und** Hin und Her ≤ 1,65 (je Median), etwa ein Viertel der Trades:

| | Train | Validierung | Holdout |
|---|---|---|---|
| sauber | +0,12 R | +0,34 R | +0,26 R |
| Rest | +0,11 R | +0,22 R | +0,03 R |

Gegenprobe: Am Tag des Treffers selbst bringt „ruhig“ nichts (+0,44 / −0,03 / +0,10 R gegenüber +0,07 / +0,28 / +0,09 R) –
die Wirkung kommt erst mit der ruhigen Seitwärtsphase danach.

Folge (auf Wunsch von Jonny): Eine Aktie gilt erst als Treffer, wenn die 11 Kriterien erfüllt sind UND die Konsolidierung
am Scan-Tag ruhig ist (Spanne 5 Tage ≤ 1,5 ATR, Hin und Her 10 Tage ≤ 1,65). Unruhige erscheinen nicht als Treffer, auch
nicht in Mitteilungen und Live-Bilanz (backend/run_scan.py, „calm_wait“). Weil die Schwellen nachträglich gewählt sind,
zeigt die Live-Bilanz, ob der Vorteil hält.
Überraschung: Ein besonders starker oder schneller Abverkauf davor macht Trades nicht besser, eher schlechter.

# Kauf kurz vor Quartalszahlen (28.10.2026)
Skript `tools/research/earnings_entry_test.py`, 8.498 US-Trades, Zahlen = SEC-8-K Punkt 2.02. Kauf ≤ 10 Tage vor den Zahlen:
+0,22 / +0,32 / +0,53 R gegenüber +0,18 / +0,27 / +0,04 R (Train / Validierung / Holdout). Vorab-Regel („schlechter in allen
drei“) nicht erfüllt – im Gegenteil. Folge: Der Trade-Plan zieht den Ausstieg nicht mehr vor die Zahlen vor, kein Score-Abzug
mehr (config earnings_penalty 0); nur noch Hinweis auf das Kurslücken-Risiko (v. a. bei Turbos).
