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

**Kern von Kairo ist der Scanner:** einmal täglich alle ~6.000 Aktien nach klaren Regeln prüfen und die besten Einstiegs-Setups
nennen – eine regelbasierte Auswahl, keine Anlageberatung. Ziel: die renditestärkste Strategie, die nach echten Kosten,
auf unbekannten Zeiträumen, gegen Zufall und live besteht.

| # | Baustein | Nutzen |
|---|---|---|
| 1 | **Kairo mit PRIME+-Kosten gegen Zufall** (Protokoll v2.3, 49.134 Treffer 2008–2026) | hat das Setup einen echten Vorteil? |
| 2 | **Merkmale besserer Treffer** (v2.4: Score, Zone, Markt, Momentum, Volatilität, Region, Tiefe) | Rangfolge „beste Setups zuerst“ nach Belegen |
| 3 | **Gezielte Erweiterungen** (z. B. Marktfilter, relative Stärke) – nur vorab festgelegt, Train → Validierung → Holdout → Papier | Scanner wird besser, ohne Zufallstreffer |
| 4 | **Tagesliste „Top-Setups“**: Einstiegszone, Stop, Ziel, Positionsgröße, echte Kosten (PRIME+, Spread) | klare Entscheidungsgrundlage |
| 5 | **Live-Bilanz des Scanners**: jeder genannte Treffer wird automatisch verfolgt | ehrliche Erfolgsquote der Empfehlungen |
| 6 | **Persönliche Journal-Auswertung** eigener Trades (Setup, Fib-Tiefe, Haltedauer, Hebel) | eigene Hypothesen mit eigenen Zahlen prüfen |
| 7 | **Technik-Hygiene**: Ausfall-Warnung (✅ seit 19.10.: Push bei Fehler in Scan, Mitteilungen, Papier-Handel), Tests, aufgeräumter Code | Verlässlichkeit |

Im Hintergrund: Papier-Depots (Dual Momentum u. a.) und monatliche Auswertung (ab 02.11.2026). Entscheidung nach 12 Monaten:
Dual Momentum für 10–30 % Trading-Teil ja/nein (nach Kosten ≥ ETF, Rückgang höchstens ~5 Prozentpunkte schlechter).

## Phase 2 – Prüfen, ob andere es wollen (frühestens nach Phase 1)

- 10–20 aktive Trader befragen, kleine kostenlose Beta
- Rechtliche Erstberatung (Finanzaufsichtsrecht: Anlageempfehlungen/MAR, ggf. Erlaubnispflicht; Werkzeuge statt Signale)
- Kosten durchrechnen: lizenzierte Kursdaten (Yahoo-Daten sind für kommerzielle Nutzung nicht freigegeben), Hosting, Zahlungsanbieter

## Phase 3 – Produkt (nur wenn Phase 2 klar „ja“ sagt)

- Nutzerkonten, Datenbank, Bezahl-Abo, DSGVO, Impressum/AGB, Support
- Fokus: Werkzeuge, Transparenz, Track-Record – keine „Kauf jetzt“-Versprechen
