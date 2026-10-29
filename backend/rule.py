"""Die Kairo-Regel an EINER Stelle (Version B60) – Live-Bilanz, Mitteilungen und Tests lesen von hier.

Getestet 2008–2026 (research/strategy_championship, S01-B-Basis, Forschung v2.5):
Treffer (11/11) → bis zu 10 Handelstage auf eine Seitwärtsphase warten (5 Kerzen, Spanne ≤ 1,5 ATR des Signaltags,
Tief der 10 Tage bis zum Signal hält) → Kauf zur nächsten Eröffnung innerhalb der Spanne → Stop = Basis-Tief − 0,25 ATR
(Risiko 0,5–3 ATR) → Ausstieg: Stop, ab Tag 10 Tagesschluss unter der EMA 20 zur nächsten Eröffnung, spätestens Tag 60.
1 % Risiko je Trade, höchstens 5 gleichzeitig; bei mehr Kandidaten zuerst schwächeres Vormomentum.
Die App (site/index.html, KMAX/H4X) und die Papier-Depots (paper/kairo.py) müssen dieselben Werte haben –
backend/tests/test_rule.py prüft das.
"""

KAIRO = dict(version="B60", wait=10, ck=5, cm=1.5, inv=10, buf=0.25, risk_atr=(0.5, 3.0),
             hold=60, ema=20, ema_from=10, risk=0.01, max_open=5)
