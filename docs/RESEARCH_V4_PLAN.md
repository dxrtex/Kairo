# Forschung v4 – Index-Trendfolge mit und ohne Hebel (Plan, vorab festgelegt 25.10.2026)

Warum: Alle Einzelaktien-Tests (v1–v3) leiden unter dem Survivorship-Bias (nur heute gelistete Firmen). Indizes haben dieses
Problem nicht und reichen bis 1988 zurück (Dotcom-Crash, Finanzkrise, Corona). Literatur: Faber 2007 (200-Tage-Linie),
Gayed & Bilello 2016 („Leverage for the Long Run“: Hebel nur über der 200-Tage-Linie).

Daten (Yahoo): S&P 500 Total Return (^SP500TR, ab 1988), Nasdaq-100 (^NDX, Kurs + 1 % Dividende p. a. als Näherung),
3-Monats-T-Bill (^IRX) für Cash-Zins und Finanzierung.
Mechanik: Signal am Tagesschluss, Umsetzung erst einen Tag später (konservativ). Hebel L täglich neu (wie ein gehebelter ETF):
Tagesrendite = L × r − (L − 1) × (T-Bill + 0,5 %)/252 − Kosten des ETF (0,6 % p. a. bei L > 1, 0,1 % bei L = 1).
Jeder Wechsel kostet 0,25 % (Spanne + Ausführung). Außerhalb des Marktes: T-Bill-Zins. Keine Steuern (Hinweis im Bericht).

Varianten (fest, keine weiteren):
| Name | Index | Hebel | Filter |
|---|---|---|---|
| SP1 (Vergleich) | S&P 500 | 1× | immer investiert |
| SP1F | S&P 500 | 1× | über SMA200 |
| SP2 | S&P 500 | 2× | immer investiert |
| SP2F | S&P 500 | 2× | über SMA200 |
| SP3F | S&P 500 | 3× | über SMA200 |
| NQ1 | Nasdaq-100 | 1× | immer investiert |
| NQ2F | Nasdaq-100 | 2× | über SMA200 |
| NQ3F | Nasdaq-100 | 3× | über SMA200 |

Zeiträume: Train 1989–2007 · Validierung 2008–2016 · Holdout 2017–10/2026.
Kandidat nur, wenn: (1) CAGR höher als SP1 in allen drei Zeiträumen, (2) größter Rückgang über alles höchstens 15 Prozentpunkte
schlechter als SP1, (3) robust: dieselbe Variante mit SMA 100/150/250 schlägt SP1 über den Gesamtzeitraum ebenfalls.
Sonst: nicht bestanden. Ein Kandidat ginge zuerst in den Papier-Test (kein echtes Geld ohne 12 Monate Vorwärtstest).
