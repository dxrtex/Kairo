# KAIRO Design V4 – Offene Punkte (02.11.2026)

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
