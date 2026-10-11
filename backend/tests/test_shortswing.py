"""Kurzfrist-Studie: Kurslücken, Stop vor Ziel, K.-o., Wochenende, Zeit-Stop – vorsichtige Abrechnung."""

from backend.shortswing import simulate


def px(o, h, l, c, wd=None, pl=(1.0, 0.97, 0.95), atr=0.02, e20=1.05, tp=None):
    n = len(o)
    return {"o": o, "h": h, "l": l, "c": c, "wd": wd or [0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0][: n + 1], "pl": list(pl),
            "atr": atr, "e20": e20, "tp": tp or [], "s": 0.94, "h0": 1.01, "h3": 1.02}


BASE = dict(entry="open", late=0.5, inv=3, buf=0.0, maxd=4.0, hold=5, tgt=None, wkend=False, levs=[1])


def test_gap_below_stop_sells_at_open_not_stop():
    p = px(o=[1.0, 0.90, 0.9], h=[1.01, 0.91, 0.9], l=[0.99, 0.88, 0.88], c=[1.0, 0.9, 0.9])
    s = simulate(p, BASE)
    assert s["x"] == "stop" and abs(s["r"] - (0.90 - 1.0) / 0.05) < 1e-9     # −2 R, nicht −1 R


def test_stop_and_target_same_day_counts_as_stop():
    p = px(o=[1.0, 1.0], h=[1.2, 1.0], l=[0.94, 1.0], c=[1.0, 1.0])
    s = simulate(p, {**BASE, "tgt": ("R", 1.0)})
    assert s["x"] == "stop" and abs(s["r"] + 1) < 1e-9


def test_knockout_on_gap_loses_stake():
    p = px(o=[1.0, 0.89], h=[1.0, 0.9], l=[0.99, 0.85], c=[1.0, 0.86])
    s = simulate(p, {**BASE, "levs": [1, 3, 5, 10], "kob": 1.0})
    assert s["lev"] == 10 and s["x"] == "ko" and abs(s["r"] - (-(0.1) / 0.05)) < 1e-9


def test_leverage_reduced_when_ko_too_close_to_stop():
    p = px(o=[1.0, 1.0], h=[1.0, 1.0], l=[1.0, 1.0], c=[1.0, 1.0], pl=(0.93,), atr=0.03)
    s = simulate(p, {**BASE, "hold": 2, "levs": [1, 3, 5, 10], "kob": 1.2})
    assert s["lev"] == 5                                                      # 10er-K.-o. 0,90 läge über Stop 0,93 − 1,2 ATR


def test_weekend_exit_on_last_trading_day():
    p = px(o=[1.0, 1.01, 1.02], h=[1.01, 1.02, 1.03], l=[0.99, 1.0, 1.01], c=[1.0, 1.01, 1.02], wd=[3, 4, 0, 1])
    s = simulate(p, {**BASE, "wkend": True})
    assert s["x"] == "wochenende" and s["d"] == 1                           # Signal Do → Kauf Fr, Verkauf Fr-Schluss


def test_time_stop_and_trailing_only_up():
    o = [1.0, 1.05, 1.10, 1.08, 1.07]
    p = px(o=o, h=[x + 0.01 for x in o], l=[x - 0.01 for x in o], c=o)
    s = simulate(p, {**BASE, "hold": 5, "trail": 3.0, "trail_from": 1.0})
    assert s["x"] == "zeit" and s["d"] == 5 and s["r"] > 0


def test_late_entry_is_skipped():
    p = px(o=[1.02, 1.03], h=[1.03, 1.04], l=[1.01, 1.02], c=[1.02, 1.03])
    assert simulate(p, BASE) == {"skip": "late"}


def test_trailing_stop_exits_when_touched():
    o = [1.0, 1.05, 1.10, 1.08, 1.07]
    p = px(o=o, h=[x + 0.01 for x in o], l=[x - 0.01 for x in o], c=o)
    s = simulate(p, {**BASE, "hold": 5, "trail": 2.0, "trail_from": 1.0})
    assert s["x"] == "be/trail" and abs(s["r"] - (1.07 - 1.0) / 0.05) < 1e-9   # 1,11 − 2 × 0,02
