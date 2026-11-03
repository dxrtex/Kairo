# Quartalszahlen: Regionen und Absturz-Risiko (03.11.2026)

33.967 Quartalsberichte (USA 16.430, Europa 6.655, Asien 10.882) seit 2019, Ziel = erster Handelstag nach der Meldung.
Lernen bis 30.06.2024, Prüfen danach (10.761). Skript `tools/research/earn_region.py`, Workflow `earnregion.yml` (Branch claude/earn-region).

| Frage | Ergebnis | Folge |
|---|---|---|
| Europa: eigene Quoten statt US-Quoten? | US-Quoten 59,9 % Treffer, eigene nicht besser (Brier 0,2392 → 0,2415) | Europa nutzt die US-Quoten voll (Halbierung vom Mittag zurückgenommen) |
| Asien: eigene Quoten? | Brier 0,2506 → 0,2478 (95 % −0,0047…−0,0011), Treffer 54,3 % | Asien: eigene, flachere Quoten je Gewinn-Stufe |
| „Steigt“ + Schwankung / frühere Reaktion / Marktlage | Verbesserungen im Rauschen (Intervalle enthalten 0) | nicht übernommen |
| Absturz ≤ −5 % nach den Zahlen (mit Überraschung) | AUC 0,685 → 0,736, Brier 0,1046 → 0,1008 | übernommen (`site/earn_crash.json`, post) |
| Absturz ≤ −5 % VOR den Zahlen (ohne Überraschung) | AUC 0,646 → 0,716, Brier 0,1059 → 0,1027; Eichung je Fünftel 2,3 / 6,7 / 10,7 / 17,4 / 24,8 % | übernommen (pre) |

Stärkstes Merkmal fürs Absturz-Risiko: wie stark die Aktie früher auf Zahlen reagiert hat (Absturz-Quote je Fünftel 2 % → 25 %),
danach die Schwankung der letzten 20 Tage. Vorlauf und Marktlage spielen kaum eine Rolle.
Live: Wochenbilanz (tools/earn_review.py) prüft weiter je Stand der Regel (MODEL in backend/earnfast.py).
