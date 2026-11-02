# Kairo Next Level – Roadmap (Stand 01.11.2026)

Grundsätze bleiben: B60 unverändert, 11 Pflichtkriterien nur mit Freigabe, E2 und Dual Momentum getrennt, keine
Echtgeld-Orders, keine Bezahldienste ohne Freigabe, kein Modell produktiv ohne zeitlich getrennten Nachweis.

## Jetzt – braucht nur deine Entscheidung

| # | Schritt | Was passiert | Risiko |
|---|---|---|---|
| 1 | Branch `claude/next-level` übernehmen (Pull Request → main) | App, Insider, Quartalszahlen-Status, Datenstatus, Momentaufnahmen gehen live | gering – Regel, Kriterien, Depots unverändert; alle Tests grün |
| 2 | E2-Schattentest starten | `paper/e2shadow.step` im täglichen Papier-Lauf aufrufen, Datei `e2_shadow.json` im Branch `paper-data`; zählt nur Treffer ab Starttag | gering – eigene Datei, kein Einfluss auf Depots |
| 3 | Asien-Treffer in der App zeigen? | `calmGate` blendet `region === "asia"` aus. Asien war in der Bestätigung je Trade positiv, ist live aber nicht getestet | mittel – Empfehlung: nur als „Beobachten“ zeigen, nicht kaufbereit |

## Nächste 4 Wochen – automatisch, ohne Eingriff

- **Momentaufnahmen sammeln:** ab dem ersten Abendscan nach dem Merge. Erste Gewinner/Verlierer-Auswertung
  (`snapshots.compare`) frühestens ab 30 abgeschlossenen Treffern – bei ~3–6 Treffern pro Woche und bis zu 60 Tagen
  Haltedauer realistisch **Februar/März 2027**.
- **Quartalszahlen-Lernschleife:** Archiv wächst je Berichtssaison; Kalibrierung (zeitlich getrennt) ab 200 Fällen.
  Latenz-Messung erscheint in der Bilanz ab 10 Fällen.
- **Insider-Abdeckung beobachten:** Wenn „Zeitlimit“ trotz 420 s regelmäßig auftaucht → Abruf auf zwei Läufe verteilen.

## 1–3 Monate – Ausbau (je mit Abnahmekriterium)

| Thema | Inhalt | Abnahme |
|---|---|---|
| Lern-Bericht | Wöchentliche Seite „Was unterscheidet Gewinner von Verlierern?“ aus `snapshots.compare` (Median je Merkmal, Anzahl, Konfidenz) | erst ab 30 Fällen sichtbar; jede Aussage mit n und Zeitraum; **keine** automatische Regeländerung |
| E2 vs. B60 live | Vergleichstabelle (Kaufquote, Ø R netto, nicht ausgelöste Orders) aus `e2shadow.summary` neben der B60-Live-Bilanz | ab 30 abgeschlossenen E2-Trades; Entscheidung über E2 frühestens nach 12 Monaten und nur mit Freigabe |
| Insider Großbritannien | FCA/RNS-Meldungen „PDMR“ (frei über die London-Stock-Exchange-Nachrichten) | Parser-Test mit echten Meldungen; Abdeckung zeigt „ok“ für .L |
| Insider Frankreich | AMF „Déclarations des dirigeants“ (frei, BDIF) | wie oben für .PA |
| Insider Schweiz/Italien/Dänemark | SIX-Management-Transaktionen (frei, ohne Namen), Consob/Borsa Italiana, Finanstilsynet | je Land prüfen, ob frei und stabil – sonst „keine Quelle“ lassen |
| WebKit-Test | Rundgang zusätzlich in WebKit (Safari-Engine, wie iPad) im Workflow „Tests & Regression“ | grün in WebKit und Chromium |

## 3–12 Monate – Forschung, nur mit Nachweis

- **Merkmals-Kandidaten aus den Momentaufnahmen** (z. B. Stop-Abstand in ATR, Vormomentum, Marktlage) erst als
  Forschungsfrage: vorab festgelegter Test auf **künftigen** Daten (nicht auf denselben Signalen, aus denen die Idee kam).
- **E2-Entscheidung:** nach ≥ 12 Monaten Schattentest und ≥ 30 Trades je Regel; Vergleich netto, inklusive nicht
  ausgelöster Orders. Übernahme nur mit Freigabe.
- **Kosten messen statt schätzen:** wenn genug Journal-Orders mit Uhrzeit vorliegen, die Abweichung zum Kurs zur
  Orderzeit (statt Tagesschnitt) messen. Kein erfundener Spread.

## Ausdrücklich nicht geplant

- Automatische Änderung der 11 Kriterien oder der Regel B60 durch die Lern-Engine.
- Kostenpflichtige Datenquellen (Norgate o. ä.) ohne Freigabe.
- Echtgeld-Orders.
