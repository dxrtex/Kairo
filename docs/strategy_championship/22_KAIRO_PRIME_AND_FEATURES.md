# 22 · Kairo mit PRIME+-Kosten gegen Zufall (v2.3) und Merkmale besserer Treffer (v2.4)

Lauf research_kn #39239034595. 13.241 Kairo-Trades (S01-B-Basis) 2008–2026, je Trade ohne Kapitalgrenze; Zufall = an jedem
Treffer-Tag gleich viele zufällige zulässige Titel mit derselben Basis-/Ausstiegsregel, 20 Seeds. Survivorship-Bias im Datensatz.

## v2.3 – Kairo gegen Zufall (Ø R je Trade nach Spread; PRIME+-Gebühr bei 5.000 € Depot praktisch 0, da Orders ≥ 250 €)

| Abschnitt | Kairo | Zufall (Median) | p |
|---|---|---|---|
| Train 2008–16 | +0,108 R (n 4.214) | +0,086 R | 0,15 |
| Validierung 2017–21 | +0,248 R (n 3.765) | +0,177 R | 0,10 |
| Holdout 2022–26 | +0,087 R (n 5.262) | +0,064 R | 0,25 |
| gesamt | +0,140 R | +0,107 R | < 0,05 (0 von 20) |

Kriterien v2.3 (netto > 0 in allen Abschnitten, über Zufalls-Median in allen, gepoolt p ≤ 0,05): **erfüllt.**
Einordnung: Der Vorteil der Kairo-Auswahl ist **klein** (+0,03 R je Trade gegenüber Zufall); ein großer Teil des Ergebnisses
kommt aus der Einstiegs-/Ausstiegsmechanik (Basis, Stop, EMA20), die auch mit Zufallstiteln positiv ist – das kann am
Survivorship-Bias liegen. Trefferquote ≈ 33 %, typischer Trade verliert ≈ ¾ R.

## v2.4 – Merkmale (beste/schlechteste Gruppe aus Train; R netto)

| Merkmal | Train | Validierung | Holdout | Ergebnis |
|---|---|---|---|---|
| **eigenes Momentum 6-1** niedrig vs. hoch | +0,18 / +0,07 | +0,30 / +0,22 | +0,17 / −0,03 | **bestätigt** (p 0,004 ≤ 0,007) |
| Region US vs. EU | +0,14 / +0,02 | +0,25 / +0,25 | +0,09 / +0,07 | Richtung hält, nicht signifikant |
| Zone Fib vs. nur Support | +0,12 / +0,10 | +0,25 / +0,25 | +0,23 / +0,03 | nicht bestätigt |
| Markt (S&P > EMA200) | gut besser | schlecht besser | schlecht besser | nicht bestätigt (kehrt sich um) |
| Score, Volatilität, Tiefe | – | – | – | nicht bestätigt |

**Befund:** Kairo-Treffer von Aktien mit **schwachem** Vormomentum (stärker gefallen in Monat −6…−1) liefern in allen drei
Zeiträumen bessere Trades. Vorbehalt: Genau dieses Muster wird vom Survivorship-Bias begünstigt (gefallene Aktien, die sich
erholt haben, sind im Datensatz; die, die pleitegingen, fehlen). Daher: Kandidat für die Rangfolge, aber erst nach Live-Prüfung.
Ein Marktfilter (S&P über EMA200) hilft Kairo **nicht** – in 2017–26 waren Treffer in schwachen Märkten sogar besser.
