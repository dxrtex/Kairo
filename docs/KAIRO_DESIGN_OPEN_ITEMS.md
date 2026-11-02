# KAIRO Design – Offene Punkte (V4 02.11.2026, aktualisiert V5 03.11.2026)

Stand nach V5 zuerst; darunter die V4-Liste mit Status.


## V5 – Status der V4-Punkte

| # | Status nach V5 |
|---|---|
| O1 Premium als Standard | **Noch offen** – deine Entscheidung nach der Probe auf dem iPad |
| O2 Echtes Master-Detail | **Implementiert, getestet** (Scanner, ≥ 1024 px) |
| O3 „0 Stk.“ in jeder Zeile | **Implementiert** – einmal über der Liste, je Zeile nur bei Stückzahl > 0 |
| O4 „Nichts zu tun“ vs. „Kaufbereit“ | **Nachweisbar verbessert** – die Kachel erklärt jetzt „nur x Plätze frei“; die Logik selbst unverändert |
| O5/O6 Kontrast und 5 px in Klassisch | **Noch offen** – Klassisch bewusst unverändert |
| O9 Trefferflächen | **Noch offen** – keine neuen Verstöße (Kapital-Link 32 px), Bestand v. a. Fließtext-Links/Glossar |
| O10 Messfehler Reiter | **Erledigt** – Prüfstand erkennt den Indikator; dabei echten Fehler gefunden und behoben (Blau auf Blau, dunkel < 1024 px) |

## V5 – neue offene Punkte

| # | Punkt | Warum offen | Vorschlag |
|---|---|---|---|
| V1 | **Charts ohne Achsen** im Detail (Mini-Kerzen-SVG): keine Preis-/Datumsachse, keine Tooltips, kein Zoom | Chart wird von `paintChart` gezeichnet (gemeinsame Funktion); Achsen/Tooltips wären eine neue Chart-Funktion, nicht nur Gestaltung | eigenes Paket „Detail-Chart“: Preis-Skala rechts, Datum unten, Stop-/Einstiegslinie beschriftet; großer TradingView-Chart bleibt im Einstieg |
| V2 | Master-Detail nur im Scanner | „Heute“, „Einstieg“, „Depot“ öffnen Aktien weiter als Fenster | gleiches Muster für Einstieg/Depot prüfen |
| V3 | Warte-/Verfallen-Zeilen: Kriterienbalken in eigener Zeile | andere Zeilenart (`.bd-row`), nicht im Ziel­umfang | Balken rechts neben den Namen wie bei Kaufbereit |
| V4 | Tippfehler „Nur 5 Platze frei“ (gemeinsamer Text) | Korrektur würde Klassisch ändern | einzeilige Textkorrektur mit deiner Freigabe |
| V5 | Bilanz-Ansicht im Prüfstand ohne Daten | `bilanz.json` entsteht nur im echten Abendscan (Live-Signale) | Fixture um eine kleine Bilanz ergänzen |
| V6 | Messgrundlage synthetisch | github.io/Artefakte aus der Umgebung gesperrt | sobald erreichbar: zusätzlich mit echten Daten fotografieren (`app_smoke.py --fetch`) |
| V7 | Kein echtes Gerät / kein Safari (WebKit) | Umgebung | **bitte auf dem iPad in Safari ansehen** (Einstellungen → Design → Premium Workspace) |
| V8 | Ganzseiten-Screenshots zeigen das Filter-Blatt unterhalb des Bildschirms | Effekt der Aufnahme (Blatt liegt außerhalb), im Gerät unsichtbar | Prüfstand: Blatt vor Ganzseiten-Aufnahme ausblenden |

## V4-Liste (Stand 02.11.2026)

## Noch offen (machbar, bewusst nicht in diesem Schritt)

| # | Punkt | Warum offen | Vorschlag |
|---|---|---|---|
| O1 | **Premium zum Standard machen** | Prompt: zunächst optional | Nach deiner Probe auf dem iPad entscheiden |
| O2 | Echtes Master-Detail auf iPad quer (Liste dauerhaft links, Detail rechts statt Blatt) | bräuchte Änderung am Rendern der Detailansicht (JS), nicht nur CSS | eigenes kleines Paket |
| O3 | „0 Stk. · kein freies Kapital“ in jeder Kaufbereit-Zeile | Inhalt aus der Stückzahl-Logik; ändern hieße Text-/Logik-Anpassung | einmal als Hinweis über der Liste zeigen, Zellen „–“ |
| O4 | Scheinbarer Widerspruch „Heute: Nichts zu tun“ vs. „Scanner: Kaufbereit 9“ | Logik/Daten (verschiedene Regeln/Kapitalprüfung), kein Design | getrennt prüfen – Tradinglogik war hier tabu |
| O5 | Kontrast 3,65 : 1 (Weiß auf #0A84FF) im **klassischen** Design | Klassisch sollte unverändert bleiben | `--accent-fill` auch in Klassisch übernehmen (1 Zeile) |
| O6 | Telefon-Überbreite 5 px im **klassischen** Scanner | wie O5 | `.board>*{min-width:0}` auch in Klassisch |
| O7 | Eigene Dichte-Einstellung (kompakt/normal) | Dichte folgt derzeit der Breite | Schalter in Einstellungen, falls gewünscht |
| O8 | Postfach-Seitenleiste dreifach kopiert (CSS-Duplikat) | Aufräumen ohne Nutzen für das neue Design, Regressionsrisiko | bei nächster Postfach-Arbeit zusammenführen |
| O9 | Trefferflächen < 32 px (206 Stück, v. a. Inline-Links/„i“-Knöpfe/Glossar-Begriffe) | viele sind Fließtext-Links (WCAG 2.2 erlaubt Ausnahme für Inline-Links) | Info-Knöpfe auf 32 px vergrößern |
| O10 | Messfehler aktiver Reiter im Prüfstand (Geschwister-Hintergrund) | betrifft nur die Messung | Prüfstand um `.tab-ind`-Erkennung ergänzen |
| O11 | Onboarding/Rundgang, Splash, Lade-/Fehlerzustände im Premium-Look gezielt fotografiert | im Prüfstand ausgeblendet (`.splash`, `#tour`); funktional über App-Test abgedeckt | eigene Prüfstand-Ansichten ergänzen |

## Nicht möglich (in dieser Umgebung)

| Punkt | Grund |
|---|---|
| WebKit/Safari-Prüfung | WebKit-Browser für Playwright nicht installiert; Installation aus dem Netz nicht vorgesehen. **Bitte einmal auf dem iPad in Safari ansehen** (Einstellungen → Design → Premium Workspace). |
| Echtes Gerät (Touch, Safe-Area, Dynamic Type, VoiceOver) | kein physisches Gerät; Safe-Area-Abstände sind per `env()` gesetzt, aber nicht real geprüft |
| Lighthouse-Leistungswert | Seite ist eine einzelne HTML-Datei ohne Netz im Prüfstand; neue CSS-Menge ~9 KB, kein Blur, keine neuen Bibliotheken – messbarer Unterschied in Renderzeit: keiner (~1,9 s Prüfstand-Wartezeit) |

## Nicht verändert (Vorgabe)

Tradinglogik, B60, die elf Scanner-Kriterien, E2, W2, Strategieparameter, Nutzerdaten/Einstellungen, Echtgeld-Funktionen.
Kein PR und kein Merge ohne deine Zustimmung.
