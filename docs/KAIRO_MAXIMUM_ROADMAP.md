# Kairo Maximum – Roadmap (Stand 01.11.2026)

Leitlinie: Jede Funktion muss einen messbaren Mehrwert haben. B60 bleibt Champion, bis ein Challenger die festen Hürden in
`backend/registry.py` erfüllt **und** freigegeben wird.

## Entscheidungen, die bei dir liegen

| # | Entscheidung | Empfehlung |
|---|---|---|
| 1 | `claude/maximum` (enthält `claude/next-level`) per Pull Request nach `main` | ja – alle Tests grün, Regel/Depots unverändert, Nutzerdaten unberührt |
| 2 | E2-Schattentest dauerhaft starten (Aufruf im Papier-Lauf, Datei `e2_shadow.json` in `paper-data`) | ja – kein Einfluss auf Depots, nur künftige Signale |
| 3 | Asien-Treffer zeigen (heute ausgeblendet) | nur als „Beobachten“, nicht kaufbereit |
| 4 | Trading-Budget im Einstieg einmalig auf das 90/10-Profil setzen | Knopf im ETF-Reiter („Trading-Kapital im Einstieg setzen“) – bewusst nicht automatisch |

## Als Nächstes (je Paket mit Abnahmekriterium)

| Thema | Inhalt | Messgröße / Abnahme |
|---|---|---|
| Kosten zeitgenau messen | Export enthält die Uhrzeit → Ausführungskurs gegen den Kurs zur Orderzeit (Stundenkerzen, nur liquide Aktien) statt Tagesschnitt | Abweichung je Order mit Streuung; Spread nur, wo Geld/Brief-Daten vorliegen |
| Kauforder-Ereignisse | „geplant“ (Basis fertig) und „nicht ausgeführt/abgelehnt“ (Kapital, Plätze, Lücke) als eigene Snapshot-Ereignisse aus `h4live`/Papier-Depot | jeder Treffer hat einen vollständigen Lebenslauf |
| Börsenkalender | Handelstage je Börse (USA, Xetra, LSE, Euronext, SIX, HK, Tokio) aus einer gepflegten Bibliothek statt fester Feiertage | `bdBetween`/Exit-Tage identisch zu den Börsen 2026/27 |
| WebKit-Test | Rundgang in WebKit im Regressions-Workflow (Playwright WebKit) | grün in Chromium und WebKit |
| Nachrichten | gleiche Meldung verschiedener Medien bündeln (Titel-Ähnlichkeit), Originalquelle bevorzugen, persönlicher Verlauf | weniger Doppel, jede Meldung mit Quelle/Zeit |
| Quartalszahlen-Latenz | offizielle Uhrzeit (SEC-Annahmezeit) neben „erkannt/Push“, Umsatz getrennt vom Gewinn bewerten | Median Veröffentlichung → Push in Minuten, wöchentlich |
| index.html modularisieren | Schritt für Schritt: Forschungs-/Portfolio-/Risiko-Bausteine in eigene Dateien (ohne Build-Schritt) | keine Regression im App-Test |

## Forschung (automatisch ja, Strategieänderung nein)

- **Kontrollgruppen auswerten:** ab einigen hundert Fällen je Gruppe: Treffer vs. 9/11 vs. Zufall (20/60 Tage). Erste belastbare
  Aussage frühestens Mitte 2027.
- **Lernende Prognosen:** zuerst Baselines (Basisrate, logistische Regression auf Signal-Merkmalen), Ziel Netto-R und
  Stop-Wahrscheinlichkeit, zeitlich getrennt geprüft. Komplexere Modelle nur, wenn sie die Baseline schlagen.
- **E2:** Entscheidung frühestens nach 12 Monaten und 30 abgeschlossenen Schatten-Trades (Hürden im Register).
- **Dual Momentum:** handelbare UCITS-Alternativen dokumentieren (Tracking-Differenz, Kosten) – ohne Gleichwertigkeit zu behaupten.

## Ausdrücklich nicht geplant
Echtgeld-Orders, kostenpflichtige Daten ohne Freigabe, automatische Änderung von Kriterien/Einstieg/Stop/Ausstieg, Hebel zur
künstlichen Vergrößerung des Trading-Kapitals.
