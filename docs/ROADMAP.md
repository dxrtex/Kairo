# Kairo – Roadmap

Stand 19.10.2026 · Ziel: Kairo zuerst zum besten Werkzeug für den eigenen Gebrauch machen. Erst wenn das System
nachweislich Geld bringt, wird über ein Produkt für andere aktive Trader nachgedacht.

## Leitlinien

1. **Ehrlichkeit vor Hoffnung:** Jede Strategie in der App zeigt ihren belegten Stand (getestet / im Papier-Test / nicht bestanden).
2. **Kosten zählen:** Alles wird mit echten Kosten gerechnet (Scalable PRIME+: ab 250 € Orderwert gebührenfrei).
3. **Erst Papier, dann Geld:** Neue Regeln laufen erst im Papier-Test; Regeln werden vorab festgelegt, nicht nachträglich angepasst.
4. **Keine Broker-Anbindung, keine automatischen Orders.**

## Stand der Forschung (Kurzfassung)

| Baustein | Status |
|---|---|
| Welt-ETF per Sparplan | belegt – Kern des Depots |
| Dual Momentum (SPY/EFA/QQQ → SHY) | bester Kandidat: in allen drei Zeiträumen besser als ETF, im Holdout knapp nicht signifikant (p 0,07) → Papier-Test |
| Momentum Top 5/10 | Holdout 2022–26 nicht bestanden → nur Vergleich |
| Kairo-Setup (Scanner) | bleibt; Neubewertung mit PRIME+-Kosten gegen Zufall läuft (Protokoll v2.3) |
| S19/S20, Hybrid, Mean Reversion, Multi-Asset, Fib-0,79-Hypothese | nicht bestätigt; S19/S20 laufen im Papier-Test |

Details: Branch `research/strategy-championship-phase-a`, Ordner `docs/strategy_championship/` (Berichte 05–21).

## Phase 1 – Eigengebrauch maximieren (jetzt bis ca. April 2027)

| # | Baustein | Nutzen |
|---|---|---|
| 1 | **Track-Record-Seite**: alle Strategien live seit Start vs. ETF (Rendite, Rückgang, Trades, Status-Label) | ein Blick: was funktioniert wirklich |
| 2 | **Persönliche Journal-Auswertung**: eigene Trades nach Setup, Fib-Tiefe, Haltedauer, Wochentag, Hebel; R und Trefferquote | eigene Stärken und Schwächen mit eigenen Zahlen prüfen |
| 3 | **Startseite neu**: ETF-Status, Dual-Momentum-Signal (Papier), Kairo-Treffer, offene Positionen; Labor-Bereich für Tests | weniger Ablenkung, Fokus auf Belegtes |
| 4 | **Kostenrechner im Einstieg** (PRIME+, Spread, Positionsgröße) | jede Order kennt ihre echten Kosten |
| 5 | **Monatliche Auswertung** der Papier-Depots (eingerichtet, ab 02.11.2026) | Entscheidungen nach Live-Daten |
| 6 | **Technik-Hygiene**: Ausfall-Warnung bei fehlgeschlagenen Läufen, mehr Tests, aufgeräumter Code | Verlässlichkeit |

Entscheidung nach 12 Monaten Papier-Test: Dual Momentum für 10–30 % Trading-Teil ja/nein (Kriterien vorab: nach Kosten ≥ ETF,
Rückgang höchstens ~5 Prozentpunkte schlechter, Wechsel exakt nach Regel).

## Phase 2 – Prüfen, ob andere es wollen (frühestens nach Phase 1)

- 10–20 aktive Trader befragen, kleine kostenlose Beta
- Rechtliche Erstberatung (Finanzaufsichtsrecht: Anlageempfehlungen/MAR, ggf. Erlaubnispflicht; Werkzeuge statt Signale)
- Kosten durchrechnen: lizenzierte Kursdaten (Yahoo-Daten sind für kommerzielle Nutzung nicht freigegeben), Hosting, Zahlungsanbieter

## Phase 3 – Produkt (nur wenn Phase 2 klar „ja“ sagt)

- Nutzerkonten, Datenbank, Bezahl-Abo, DSGVO, Impressum/AGB, Support
- Fokus: Werkzeuge, Transparenz, Track-Record – keine „Kauf jetzt“-Versprechen
