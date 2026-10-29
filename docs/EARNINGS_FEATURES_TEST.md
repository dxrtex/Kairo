# Quartalszahlen-Prognose: zusätzliche Merkmale (29.10.2026)

16.435 Meldungen von 600 großen US-Aktien seit 2019, Ziel = Kurs am ersten Handelstag danach höher.
Lernen bis 30.06.2024 (11.231), Prüfen danach (5.204). Skript `tools/research/earn_features.py`.

| Modell | LogLoss | AUC | Treffer gesamt | „sicher“ (≥ 58 % / ≤ 42 %) | davon richtig |
|---|---|---|---|---|---|
| Basis: Gewinn-Überraschung (heute in der App) | 0,6760 | 0,601 | 58,5 % | 46 % der Fälle | 62,3 % |
| + Lauf 20 Tage davor | 0,6772 | 0,599 | 58,4 % | 46 % | 62,2 % |
| + Lauf 60 Tage davor | 0,6761 | 0,604 | 58,5 % | 45 % | 62,5 % |
| + eigenes Muster (alle Meldungen) | 0,6760 | 0,600 | 58,5 % | 46 % | 62,4 % |
| + eigenes Muster (nach guten Zahlen) | 0,6757 | 0,604 | 58,5 % | 46 % | 62,3 % |
| + Umsatzwachstum (SEC) | 0,6753 | 0,607 | 58,5 % | 46 % | 62,3 % |
| + Umsatz-Beschleunigung | 0,6759 | 0,604 | 58,5 % | 46 % | 62,3 % |
| Kombination (eigenes Muster, Wachstum, Beschleunigung) | 0,6751 | 0,607 | 58,7 % | 44 % | 62,1 % |

Ergebnis: Formal verbessern drei Merkmale LogLoss und AUC minimal, die Trefferquote ändert sich praktisch nicht
(58,5 → 58,7 %, bei den „sicheren“ Fällen sogar 62,3 → 62,1 %). Der Lauf vor den Zahlen hilft nicht.
Folge: Das App-Modell bleibt (Gewinn-Überraschung). Der fehlende große Faktor ist der Ausblick – historisch nicht frei
testbar, live jetzt aus der Pressemitteilung (SEC) bzw. deutschen Ad-hoc-Meldungen.
Die Basis selbst ist im Prüfzeitraum stabil: 58,5 % richtig insgesamt, 62 % in den Fällen mit klarer Tendenz.
