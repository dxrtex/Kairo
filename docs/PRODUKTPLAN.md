# Kairo – Produkt- und Technikplan (Entwurf für ein späteres Abo)

Stand 20.10.2026 · Status: **Planung, nichts davon ist umgesetzt.** Grundlage: Roadmap Phase 2/3. Alle Kosten sind
**Schätzungen**, die vor jeder Entscheidung mit echten Angeboten geprüft werden müssen. Keine Rechtsberatung – die
rechtlichen Punkte sind eine Fragenliste für einen Anwalt.

## 1. Was Kairo als Produkt sein soll

- **Ein Werkzeug, kein Börsenbrief:** täglicher Scan von rund 6.000 Aktien nach festen, offengelegten Regeln, dazu
  Trade-Plan-Rechner (Stop, Positionsgröße, echte Kosten), Journal mit Kosten-Check und Papier-Depots.
- **Ehrlichkeit als Alleinstellungsmerkmal:** öffentliche, nicht nachträglich änderbare Live-Bilanz aller Treffer
  (`/track/`), vollständige Forschung inkl. aller gescheiterten Strategien (`/research/`). Die meisten Angebote am Markt
  zeigen geschönte Backtests – Kairo zeigt auch die Verlierer.
- **Zielgruppe:** aktive Privatanleger mit Swing-Trading-Interesse, die regelbasiert arbeiten wollen (z. B. Scalable/
  Trade-Republic-Nutzer, 18–35 Jahre).

## 2. Voraussetzungen, bevor jemand zahlt (Gates)

| # | Voraussetzung | Stand 10/2026 |
|---|---|---|
| G1 | ≥ 12 Monate öffentliche Live-Bilanz, Ergebnis im Rahmen der Forschung | läuft seit 30.09.2026 |
| G2 | Papier-Depots bestätigen den Vorteil nach Kosten (Kairo-S, Dual Momentum) | läuft seit 16.10.2026 |
| G3 | 10–20 Testnutzer sagen „ja, dafür zahle ich“ (kostenlose Beta) | offen |
| G4 | Rechtliche Erstberatung abgeschlossen, Pflichten umgesetzt | offen |
| G5 | Lizenzierte Kursdaten statt Yahoo | offen |

Frühester realistischer Start eines Bezahl-Abos: **Herbst 2027.**

## 3. Recht – Fragenliste für die Erstberatung

1. **Anlageberatung (KWG/WpIG):** Kairo gibt keine persönliche, auf den Nutzer zugeschnittene Empfehlung, sondern zeigt
   allen dieselben regelbasierten Treffer. Reicht das, um nicht erlaubnispflichtig zu sein? Was ist mit dem
   Positionsgrößen-Rechner (nutzt eigene Eingaben des Nutzers)? Nach dem BaFin-Merkblatt zu Finfluencern gelten
   öffentliche Empfehlungen in der Regel nicht als Anlageberatung – genau prüfen lassen.
2. **Anlageempfehlungen nach MAR (Art. 20):** Gilt die Liste „Top-Setups“ als Anlageempfehlung? Wenn ja: Anzeige bei der
   BaFin, Darstellungs- und Offenlegungspflichten (Interessenkonflikte, eigene Positionen), Kennzeichnung.
3. **Werbung und Renditeangaben:** Wie dürfen Backtest- und Live-Ergebnisse gezeigt werden (Hinweise, Zeiträume, Kosten)?
4. **Pflichten jeder Bezahl-App:** Impressum, Datenschutzerklärung (DSGVO; Daten bleiben heute nur auf dem Gerät),
   AGB, Widerrufsbelehrung für digitale Abos, Gewerbeanmeldung, Umsatzsteuer (Kleinunternehmerregelung?).
5. **Haftung:** Haftungsausschluss für Fehler im Scan, Ausfälle, falsche Kurse.

Geschätzte Kosten Erstberatung (Fachanwalt Bank-/Kapitalmarktrecht): **ca. 500–2.000 € einmalig** (Schätzung).

## 4. Daten – größter Kostenpunkt

- **Heute:** Yahoo Finance (kostenlos, für kommerzielle Nutzung **nicht** erlaubt), SEC-Daten (frei), Dukascopy.
- **Für ein Produkt:** Anbieter mit Lizenz zur Anzeige an zahlende Endnutzer. Standardtarife (z. B. EODHD ≈ 20–100 €/Monat,
  Massive/früher Polygon ab ≈ 29 $/Monat) gelten meist nur für den Eigengebrauch; Weitergabe/Anzeige an Kunden läuft über
  Business-Verträge mit individuellem Angebot, ggf. plus Börsengebühren für die Anzeige.
- **Planwert:** 200–800 €/Monat für Tagesdaten von ~6.000 Aktien inkl. Anzeige-Lizenz (Schätzung, Angebote einholen).
- **Sparweg:** Nur Signale und eigene Kennzahlen anzeigen, keine Rohkurse/Charts – senkt Lizenzkosten oft deutlich
  (mit Anbieter klären).

## 5. Technik – Zielbild

| Baustein | Heute | Für das Produkt |
|---|---|---|
| App | eine Datei `site/index.html` (~5.300 Zeilen) | Module mit Build (z. B. Vite + TypeScript), Tests je Bereich |
| Scan | GitHub Actions, Ergebnisse als JSON auf GitHub Pages | bleibt als Batch-Job (z. B. GitHub Actions oder kleiner Server), Ergebnisse in Datenbank/Objektspeicher |
| Nutzerdaten | nur im Browser (localStorage) | Konto + Datenbank (z. B. Supabase/Postgres), Export/Löschen nach DSGVO |
| Mitteilungen | Web Push mit von Hand kopiertem Secret | Push-Abos je Nutzer in der Datenbank, automatisch |
| Bezahlung | – | Zahlungsanbieter (z. B. Stripe: Abo, Rechnungen, Steuer) |
| Betrieb | Ausfall-Warnung per Push | zusätzlich Fehlerprotokoll, Statusseite |

**Umbau in Schritten (jeweils lauffähig):** 1) App in Module zerlegen, gleiches Verhalten (Smoke-Test als Schutz) →
2) Login + Datenbank, eigene Daten optional synchronisieren → 3) Push je Nutzer → 4) Bezahlung + Zugangsprüfung →
5) Datenanbieter wechseln. Aufwand grob 4–8 Wochen konzentrierte Arbeit.

## 6. Kosten und Preis (Schätzung)

| Posten | pro Monat |
|---|---|
| Kursdaten mit Lizenz | 200–800 € |
| Server, Datenbank, Speicher | 20–60 € |
| Zahlungsanbieter | ≈ 1,5 % + 0,25 € je Zahlung (EU-Karten, Stripe-Standard) |
| Domain, E-Mail, Sonstiges | 10–20 € |
| **Summe fix** | **≈ 250–900 €** |

Bei 9,99 €/Monat (nach Zahlungsgebühr ≈ 9,60 €, vor Steuern) braucht es **≈ 25–95 zahlende Nutzer**, um die laufenden
Kosten zu decken – ohne Lohn für die eigene Arbeit. Bei 19,99 € halbiert sich das.

## 7. Nächste Schritte (ohne Kosten)

1. Live-Bilanz und Papier-Depots laufen lassen (G1, G2) – monatliche Auswertung ab 02.11.2026.
2. App weiter für den Eigengebrauch verbessern; dabei neue Funktionen schon modular denken.
3. Ab etwa April 2027: kleine kostenlose Beta mit Freunden/Bekannten, Feedback sammeln (G3).
4. Erst danach Geld ausgeben: Rechtsberatung (G4), Datenangebote (G5).
