# Ergebnis: Fundamentaldaten für Kairo-Treffer (25.10.2026)

Plan vorab: `docs/FUND_TEST_PLAN.md` · Skript: `tools/research/fund_kairo_test.py`.
9.373 US-Kairo-Trades 2008–03/2026; SEC-Zahlen zeitpunktgenau (nur am Signaltag veröffentlichte Berichte).
Qualität bestimmbar bei 4.868 Trades, KGV-Historie (≥ 36 Monate) bei 4.549.

## Test 1: Bessere Trades mit Merkmal? Nein.
| Merkmal | Train mit / ohne | Validierung mit / ohne | Holdout mit / ohne | p | Ergebnis |
|---|---|---|---|---|---|
| Q Qualität | +0,26 / +0,25 R | +0,41 / +0,36 R | +0,17 / +0,18 R | 0,37 | nicht bestanden |
| V günstig vs. eigenes KGV | +0,14 / +0,22 R | +0,29 / +0,37 R | +0,10 / +0,25 R | 0,96 | nicht bestanden |
| QV beides | +0,15 / +0,28 R | +0,38 / +0,42 R | +0,20 / +0,24 R | 0,66 | nicht bestanden |

Qualität ist praktisch neutral. „Günstig nach KGV“ ist sogar in allen drei Abschnitten schlechter:
Aktien, die nach KGV billig sind, sind oft aus gutem Grund billig (fallende Gewinne erwartet).

## Test 2: Fehlsignal bei guter Firma einfach 12 Monate halten? Nicht besser als der ETF.
| Abschnitt | Q-Treffer 12 M halten | S&P 500 gleicher Zeitraum | Mehrrendite (Median) | zufälliger Kaufzeitpunkt derselben Aktie |
|---|---|---|---|---|
| Train 2008–16 | +17,9 % | +14,2 % | +3,7 % (+1,5 %) | −0,6 % |
| Validierung 2017–21 | +17,2 % | +15,3 % | +1,9 % (−1,5 %) | −2,2 % |
| Holdout 2022–26 | +17,3 % | +17,8 % | −0,5 % (−3,6 %) | −5,9 % |

Nur die ausgestoppten Q-Trades: 12 Monate später lagen 58–68 % über dem Einstieg (die Idee stimmt also teilweise),
aber nur 43–49 % besser als der S&P 500 im selben Zeitraum.

Ergebnis: nicht bestanden (Holdout schlechter als SPY, Median in Validierung und Holdout negativ).
Interessant: Der Kairo-Kaufzeitpunkt ist 4–6 Prozentpunkte besser als ein zufälliger Kaufzeitpunkt in derselben Aktie.
Das Timing hat also einen Wert, er reicht nur nicht, um langes Halten besser als den Index zu machen.
Vorsicht: Die Kursdaten enthalten keine Pleitefirmen; „ohne Stop halten“ sieht dadurch eher zu gut aus.

## Test 3: Positionsgröße
Entfällt laut Plan, weil kein Merkmal Test 1 bestanden hat (mehr Risiko auf ein Merkmal ohne Vorteil bringt nur mehr Schwankung).

## Folge für die App
Keine Änderung an Kriterien, Score oder Ausstieg. Der Fundamental-Check in der App bleibt ein Hinweis.
