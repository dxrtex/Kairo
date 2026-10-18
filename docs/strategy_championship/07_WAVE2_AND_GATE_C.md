# 07 — Welle 2 (Train 2008–2016) und Vorschlag Gate C

**Status: EXPLORATIV · DATENBESCHRÄNKT · NUR ENTWICKLUNGSZEITRAUM.** Lauf `research_c2.yml` #39131612430 (Commit `79681bd`),
Protokoll v1.2. 42 neue Registereinträge (C2-…; Register jetzt 158 Einträge), Rohzahlen `c2_results_train.json`.
Bilanzprüfungen in allen Läufen bestanden.

## 1. Welle 2 (5.000 €, netto)

| Variante | CAGR | Max. DD | Sharpe | Kostenstress | p vs. Zufall | ohne Top 1 % | pos. Jahre |
|---|---|---|---|---|---|---|---|
| **S16-B** Dual Momentum SPY/EFA/QQQ → SHY | **+14,3 %** | **−20,6 %** | **0,75** | +13,4 % | **0,025** | +5.194 € | 5/6* |
| S16-A Dual Momentum SPY/EFA → SHY | +9,6 % | −21,6 % | 0,57 | +8,7 % | 0,105 | +2.443 € | 6/7* |
| **S07-B** Momentum 6-1 / Vol 6 M., Top 10 | **+16,9 %** | −37,6 % | 0,68 | +10,0 % | **0,015** | +7.491 € | 7/9 |
| S07-A Momentum 12-1 / Vol 1 J. | +5,9 % | −58,9 % | 0,34 | −0,9 % | 0,510 | −2.313 € | 5/9 |
| S06-P Residual-Momentum (Proxy) | +9,5 % | −57,7 % | 0,47 | +0,3 % | 0,265 | +3.034 € | 6/9 |
| S14-B Sektoren Top 3, 12-1 | +9,9 % | −34,6 % | 0,53 | +8,5 % | 0,495 | +4.578 € | 7/9 |
| S14-A Sektoren Top 3, 6 M. | +8,8 % | −38,4 % | 0,49 | +6,7 % | 0,665 | +3.816 € | 6/9 |
| S09-A enge Basis (Spanne) | +2,9 % | −16,6 % | 0,37 | +0,3 % | 0,610 | +386 € | 4/9 |
| S09-B enge Basis (ATR) | +0,8 % | −3,0 % | 0,55 | +0,7 % | 0,185 | — (nur 12 Trades) | 5/6 |

\* Jahre mit abgeschlossenen Trades (Wechsel selten). Zufall bei S14 = zufällige Sektoren (+9,9 % Median): Sektorwahl brachte
nichts. Zufall bei S16 = zufälliger ETF aus derselben Auswahl.

**Vorbehalt S16-B:** QQQ war 2008–2016 einer der stärksten Märkte; die Auswahl „SPY/EFA/QQQ“ ist aus heutiger Sicht
naheliegend (Rückschaufehler möglich). S16-A ist die klassische Fassung ohne diesen Vorbehalt.

## 2. Gesamtbild beider Wellen (23 Varianten + S01)

- **Kosten entscheiden:** Alles mit vielen kurzen Trades (S04, S11) ist bei 5–20 k€ und fixer Gebühr nicht tragfähig.
- **Was in Train trägt, ist fast nur Momentum/Trend auf mittlere Sicht:** S05-B, S07-B (beide 6-1-Momentum — **eine** Familie,
  hoch korreliert) und S16-B (ETF-Dual-Momentum).
- **Kairo (S01)** und die übrigen Swing-Setups zeigen keinen belastbaren Vorteil gegenüber Zufall.
- **Mehrfachtests:** ≈ 25 Varianten → Bonferroni-Schwelle ≈ 0,002. Keine Variante erreicht sie (beste p = 0,010–0,025).
  Die Validierung ist deshalb der eigentliche Test.

## 3. Vorschlag Gate C — Finalisten für die Validierung 2017–2021 (einmalig)

| # | Finalist | Rolle | Warum |
|---|---|---|---|
| 1 | **S13-ETF** (ACWI > SMA 10 M.) | Kern / Benchmark | robusteste Baseline (−22 % DD) |
| 2 | **S16-B** Dual Momentum SPY/EFA/QQQ | Kern-Alternative | bestes Risiko/Rendite-Verhältnis in Train |
| 3 | **S16-A** Dual Momentum SPY/EFA | Kontrolle zu #2 | prüft, ob #2 nur am QQQ-Rückschaufehler hängt |
| 4 | **S07-B** Momentum 6-1 / Vol, Top 10 | Satellit | schlägt Zufall, robust gegen Kosten und Ausreißer |
| 5 | **S05-B** Momentum 6-1, Top 10 | Satellit (Kontrolle zu #4) | gleiche Familie; zeigt, ob die Vol-Bereinigung hilft |
| 6 | **S01-B** Kairo, EMA20-Ausstieg | Referenz | amtierende Strategie |

Ablauf nach „GATE C FREIGEGEBEN“: Validierung 2017–2021 **einmal** für genau diese 6 Varianten mit unveränderten Regeln
(5.000 € und 20.000 €, Basis- und Stresskosten, Null je Variante), Ergebnis ins Register. Keine Parameteränderung danach.
Erst danach Phase D (Kombination Kern + Satellit, Drawdown-Regeln, Turbo-/Hebel-Szenarien nur als Modell) auf Train +
Validierung; der finale Holdout 2022–2026 bleibt versiegelt bis „FINALEN HOLDOUT FREIGEGEBEN“.

Aufwand: < 1 Stunde GitHub Actions (kostenlos), keine bezahlten Daten.
