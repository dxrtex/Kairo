# Insider-Käufe als Merkmal für Kairo-Treffer – Test vom 25.10.2026

Regeln vorab festgelegt. Daten: 9.373 Kairo-Trades in US-Aktien (heutige Regel, R netto bei 5.000 € und PRIME+-Kosten, 2008 – 03/2026)
und 187.686 Insider-Käufe aus den SEC-Insider-Datensätzen 2006–2026. Zeitpunkt-genau: nur Meldungen, die am Signaltag schon
veröffentlicht waren; Kauf in den 90 Tagen vor dem Signal, Wert ≥ 10.000 $. Skript: `tools/research/insider_kairo_test.py`.

| Merkmal | 2008–16 mit / ohne | 2017–21 mit / ohne | 2022–26 mit / ohne | p (2017–26) | Ergebnis |
|---|---|---|---|---|---|
| A gezielter Kauf (keine Routine) | +0,14 (418) / +0,15 | +0,28 (352) / +0,24 | +0,20 (479) / +0,11 | 0,23 | nicht bestanden |
| B irgendein Insider-Kauf | +0,13 (421) / +0,15 | +0,28 (356) / +0,24 | +0,19 (485) / +0,11 | 0,26 | nicht bestanden |
| C mindestens 2 Käufer | +0,29 (146) / +0,14 | +0,02 (128) / +0,26 | −0,11 (165) / +0,14 | 0,96 | nicht bestanden |

Ø R je Trade, in Klammern Anzahl Trades mit Merkmal.

**Ergebnis:** Kein Merkmal ist in allen drei Zeiträumen besser. Gezielte Käufe liegen seit 2017 leicht vorn, aber nicht
statistisch gesichert und 2008–16 sogar knapp hinten. Mehrere Käufer (Cluster) waren bei Kairo-Treffern seit 2017 deutlich
**schlechter**. Insider-Käufe kommen deshalb **nicht** in die Kairo-Regel oder Rangfolge. Die Insider-Liste und das
Insider-Signal bleiben als Information in der App (Markt → Insider), klar als „kein Kaufsignal“ gekennzeichnet.
Hinweis: Für Aktien allgemein (ohne Kairo-Setup) ist der Insider-Effekt in der Forschung belegt – getestet ist hier nur die
Frage, ob er Kairo-Treffer verbessert.
