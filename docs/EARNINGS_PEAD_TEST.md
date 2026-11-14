# Quartalszahlen 2: Läuft die Aktie nach der Eröffnung weiter? (14.11.2026)

Skript `tools/research/earn_pead.py`, Workflow `earnpead.yml`. Ziele, Merkmale, Prüfverfahren und Übernahmeregel wurden
vor dem ersten Lauf im Kopf des Skripts festgelegt. Der Nachtrag (Tag 0 und kleinere Werte) wurde nach Lauf 1 und vor
Lauf 2 ergänzt. Anlass war eine Empfehlung von Gemini: Ensemble, LightGBM, marktbereinigtes Ziel, Purged Walk-Forward.

## Daten und Prüfung
- Große Werte: 27.142 Meldungen von 863 US-Aktien (Rang 1–900 nach Börsenwert), 02/2018 bis 11/2026.
- Kleinere Werte: 28.486 Meldungen von 980 US-Aktien (Rang 901–2400).
- Einstieg zur Eröffnung des ersten Handelstags nach den Zahlen. Gewinn-Überraschung und Kurslücke sind zu diesem
  Zeitpunkt bekannt. Ziel ist eine marktbereinigte Rendite über 0 (minus SPY im selben Zeitfenster).
- Purged Walk-Forward: jedes Prüfjahr 2021–2026 einzeln. Gelernt wird nur mit Meldungen, die mindestens 10 Handelstage
  vor dem Prüfjahr liegen.
- Modelle:
  - M0: Basisrate
  - M1: Quote je Gewinn-Stufe
  - M2: logistisch
  - M3: Gradient Boosting, geeicht

## Ergebnis (AUC; 0,50 = Münzwurf)

| Ziel | Große Werte M1 / M2 / M3 | Kleinere Werte M1 / M2 / M3 |
|---|---|---|
| Tag 0, Eröffnung → Schluss | 0,507 / 0,510 / 0,513 | 0,504 / 0,518 / 0,525 |
| 2 Tage ab Eröffnung | 0,503 / 0,514 / 0,514 | 0,494 / 0,506 / 0,516 |
| 5 Tage ab Eröffnung | 0,502 / 0,505 / 0,513 | 0,498 / 0,506 / 0,498 |
| zum Vergleich: Tag 1 inkl. Lücke (heutiges App-Ziel), M1 | 0,597 | 0,616 |

- **Nach der Eröffnung ist bei großen Werten nichts mehr vorhersagbar.** Weder die Überraschung noch die Größe der
  Kurslücke, der Lauf davor, die Schwankung, die Marktlage oder das Volumen am Vortag helfen. Das gilt für das logistische
  Modell genauso wie für Gradient Boosting. Die Information steckt vollständig in der Kurslücke.
- Die Lücke zeigt in 61 % (groß) bzw. 64 % (klein) der Fälle in Richtung der Gewinn-Überraschung.
- **Kleinere Werte, Tag 0:** Gradient Boosting erfüllt formal alle vier Übernahmebedingungen.
  - Brier 0,2495 statt 0,2501, besser in 6 von 6 Jahren.
  - 745 „Rückenwind“-Fälle, im Mittel +0,40 % netto (95 %: +0,05 … +0,85).
  - Trotzdem **nicht übernommen.** Getestet wurden 16 Kombinationen (4 Ziele × 2 Gruppen × 2 Modelle). Bei 95 % Sicherheit
    ist etwa ein Zufallstreffer zu erwarten. Der Effekt ist winzig (AUC 0,525), betrifft 3,6 % der Fälle und liegt bei
    kleinen Werten in der Größenordnung des echten Spreads. Er kommt auf die Beobachtungsliste und wird mit den Meldungen
    ab 2027 erneut geprüft.
- Das Ziel „Tag 1 inkl. Lücke“ erreicht zur Eröffnung bis zu 77 % Treffer. Das ist trivial, denn die Lücke ist dann schon
  passiert und lässt sich nicht mehr handeln.

## Folgen für Kairo
1. Die Prognose vor der Reaktion bleibt wie seit #511, also Langzeit-Quote plus Umsatz, wöchentlich geeicht. Mehr gibt die
   Richtung am ersten Tag nicht her. Die Langzeit-Quote trennt mit AUC 0,60–0,62.
2. **Nach der Reaktion sagt die App jetzt deutlich: kein Nachlauf.** Gute Zahlen und eine Kurslücke nach oben sind kein
   Grund, am nächsten Tag hinterherzukaufen. Ein Einstieg nur nach Kairo-Setup.
3. Der Implied Move (Optionsmarkt) wird ab jetzt vor jeder US-Meldung gespeichert. Historisch ist er nicht kostenlos
   verfügbar. Geprüft wird er, sobald einige hundert Meldungen vorliegen.
4. Nicht weiterverfolgt: ein LLM-Stimmungswert (kostenpflichtig) und Minutendaten zur Eröffnung (nicht verlässlich
   kostenlos verfügbar).
