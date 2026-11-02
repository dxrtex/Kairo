# KAIRO Design V4 – Audit des Ist-Zustands (02.11.2026)

Branch `claude/design-v4` (Basis: main 3a3379d). Messgrundlage: `tools/design_shots.py` – feste Uhrzeit (29.10.2026 21:30),
Daten aus `site/data`, synthetische Charts (`tools/design_fixtures/charts.json`), Test-Depot mit Stop-Warnung, sehr langem
Namen und vier Währungen, alle externen Anfragen blockiert. Chromium 1194. **WebKit war in der Umgebung nicht installiert**
(siehe Offene Punkte).

Legende: **Implementiert** · **Getestet** · **Nachweisbar verbessert** · **Noch offen** · **Nicht möglich**

## 1. Sicherung und Vorgehen

| | Status |
|---|---|
| Eigener Branch, keine Änderung an main, kein PR/Merge | Implementiert |
| Neues Design **optional** (Einstellungen → Design → „Premium Workspace · Dunkel/Hell (neu)“), Klassisch bleibt Standard | Implementiert, Getestet |
| Keine Änderung an Tradinglogik, B60, 11 Kriterien, E2, Strategieparametern, Nutzerdaten | Eingehalten – Diff in `site/index.html` besteht aus zwei neuen `<style>`-Blöcken + 3 Zeilen JS (Designliste, `isLight`, `applyDesign`) |
| Reproduzierbare Screenshots + Messwerte (7 Größen, 3 Designs, 13 Ansichten) | Implementiert |

## 2. Die sechs Nutzerwege (Ist-Zustand, iPad quer 1194 × 834, Klassisch)

| Weg | Befund vorher | Schwere |
|---|---|---|
| 1. „Muss ich heute etwas tun?“ (Heute) | Antwort steht oben – gut. Darunter nimmt „Erste Schritte“ (Einrichtung) die zweitbeste Fläche ein. Untere Tab-Leiste 74 px, Kopf + Begrüßung ~150 px. | mittel |
| 2. „Welche Aktien sind kaufbereit?“ (Scanner) | Erste Aktie erst bei **527 px**; Werkzeugleiste fünfzeilig; Kaufbereit-Zeile **179 px** hoch → nur **1** Zeile ganz sichtbar. | hoch |
| 3. „Wie sieht die Aktie aus?“ (Detail) | Seitenblatt 560 px; Chart (150 px hoch) beginnt bei **757 px**, also **unter dem sichtbaren Bereich**. | hoch |
| 4. „Trade planen“ (Einstieg) | Klar und kurz; kaum Handlungsbedarf. | gering |
| 5. „Wie steht mein Depot?“ (Depot) | Vier gleich große Aktionsknöpfe in einer breiten Zeile; Verteilungs-Analyse **vor** den Positionen. | mittel |
| 6. Einstellungen/Design wechseln | Funktioniert; Designs sind als getrennte `<style>`-Blöcke sauber umschaltbar. | gering |

Weitere Befunde:
- **Telefon 390 px, Scanner: 5 px horizontale Überbreite** im klassischen Design (Messung `overflow`), d. h. die Seite wackelt seitlich.
- Weißer Text auf `#0A84FF` = **3,65 : 1** (unter WCAG AA 4,5 : 1) – aktive Segmente, „+ Position“, Zählerplaketten. 63 Kontrastbefunde über die 35 Kern-Kombinationen.
- „Heute: Nichts zu tun“ vs. „Scanner: Kaufbereit 9“ widerspricht sich scheinbar – **Logik/Daten, nicht Design**; nur dokumentiert (Offene Punkte).
- Die Seitenleiste der Postfach-Designs ist dreimal kopiert (CSS-Duplikat) – nicht angefasst.
- „0 Stk. · kein freies Kapital“ wiederholt sich in jeder Kaufbereit-Zeile (Inhalt, nicht Layout).

## 3. Richtungsentscheidung A vs. B

| | A – Focused Premium | B – Professional Workspace |
|---|---|---|
| Idee | eine Spalte, viel Luft, wenige Elemente | Seitenleiste, dichte Raster, Master-Detail |
| Stärke | Telefon, Einsteiger | iPad quer/Desktop: mehr Information pro Blick |
| Schwäche | verschenkt auf iPad quer die Breite | auf dem Telefon zu dicht |

**Entscheidung: B ab 1024 px, A-Prinzipien darunter** (eine Spalte, große Trefferflächen). Begründung: Der Hauptnutzer arbeitet
auf dem iPad quer; dort lagen die gemessenen Hauptprobleme (Weg 2 und 3). Auf dem Telefon bleibt der Aufbau weitgehend wie
gehabt, nur sauberer (keine Überbreite, deckende Tab-Leiste, kontrastreiche Flächen).

## 4. Informationsarchitektur

- Navigation: ab 1280 px Seitenleiste 224 px mit Text; **1024–1279 px (iPad quer) schmale Symbolleiste 84 px** – gewinnt
  ~140 px Breite für Listen und Chart. Unter 1024 px bleibt die untere Tab-Leiste.
- Master-Detail iPad quer: Liste bleibt links sichtbar, Detail als breites Seitenblatt (`min(820px, 68vw)`) statt 560 px.
  Ein echtes geteiltes Layout mit dauerhaft sichtbarer Liste wurde **nicht** gebaut (würde das Rendering der Detailansicht
  ändern, nicht nur CSS) → Offene Punkte.
- Detail: Reihenfolge **Kopf → Kurs → Chart → Plan → Rest** (vorher Plan vor Chart). Nur CSS-`order`, keine Inhalte entfernt.
- Heute: „Erste Schritte“ unter die Tagesaufgaben verschoben (bleibt vollständig da).
- Depot: Positionen vor der Verteilungs-Analyse; Hauptaktion blau, Nebenaktionen kompakt.
