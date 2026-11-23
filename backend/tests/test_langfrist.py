import numpy as np
import pandas as pd

from backend import langfrist as LF


def _df(drift, n=600, seed=0, vol=1e6):
    idx = pd.bdate_range("2024-01-01", periods=n)
    r = np.random.default_rng(seed)
    c = 50 * np.exp(np.cumsum(r.normal(drift, 0.01, n)))
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": np.full(n, vol)}, index=idx)


def test_rebalance_dates_quarterly():
    idx = pd.bdate_range("2025-01-01", "2025-12-31")
    d = LF.rebalance_dates(idx, 3)
    assert [x.month for x in d] == [1, 4, 7, 10]
    assert all(x == idx[(idx.year == x.year) & (idx.month == x.month)][0] for x in d)


def test_build_picks_strongest_and_skips_non_us_and_illiquid():
    data = {f"S{i}": _df(0.0005 * i, seed=i) for i in range(30)}
    data["EU.DE"] = _df(0.01, seed=99)                 # stärkste, aber nicht USA
    data["TINY"] = _df(0.01, seed=98, vol=10)          # stärkste, aber illiquide
    meta = {t: {"name": t} for t in data}
    out = LF.build(data, meta, bench=_df(0.0003, seed=5), rule={"n": 5}, fund={})
    held = [x["t"] for x in out["hold"]]
    assert len(held) == 5 and "EU.DE" not in held and "TINY" not in held
    assert set(held) <= {f"S{i}" for i in range(20, 30)}
    assert out["next"] > out["since"] and out["ret"] is not None and out["bench"] is not None


def test_no_lookahead_rank_uses_only_past():
    a = _df(0.002, seed=1)
    cut = a.index[400]
    b = a.copy()
    b.loc[b.index >= cut, "Close"] *= 10                # Zukunft verändern
    r1 = LF.rank({"A": a, "B": _df(0.001, seed=2)}, {}, cut)
    r2 = LF.rank({"A": b, "B": _df(0.001, seed=2)}, {}, cut)
    assert r1 == r2


def test_push_langfrist_message_once_per_date():
    from backend import push
    lf = {"since": "2027-01-04", "next": "2027-04-01", "hold": [{"t": "A", "n": "Alpha Inc."}], "top": [],
          "out": ["A"], "inn": ["B"], "chg": {"out": ["X"], "inn": ["A"]}}
    sent = {}
    m = push.langfrist_message("2027-01-05", sent, lf)
    assert len(m) == 1 and "Verkaufen: X" in m[0]["body"] and "Kaufen: Alpha" in m[0]["body"]
    assert push.langfrist_message("2027-01-06", sent, lf) == []
    pre = push.langfrist_message("2027-03-30", sent, lf)
    assert len(pre) == 1 and "in 2 Tagen" in pre[0]["title"]


def test_watchlist_eight_checks():
    data = {f"S{i}": _df(0.0005 * i, seed=i, vol=1e6) for i in range(30)}
    meta = {t: {"name": t, "market_cap_usd": 5e9, "sector": f"Sek{i % 3}"} for i, t in enumerate(data)}
    last = data["S0"].index[-1]
    meta["S27"]["earnings_date"] = (last + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    fund = {"S26": {"roe": 0.4, "peg": 0.8}, "S25": {"roe": -0.2, "peg": -1}}
    out = LF.build(data, meta, bench=_df(0.0003, seed=5), rule={"n": 5}, fund=fund)
    assert out["checks"] == ["liq", "trend", "stab", "mom", "qual", "val", "sector", "earn"]
    for x in out["top"]:                                         # Rang-Tabelle für alle: Bits = Häkchen in fester Reihenfolge
        rk, m, nc, bits = out["ranks"][x["t"]]
        assert rk == x["rk"] and nc == x["nchk"] and [(bits >> i) & 1 for i in range(8)] == x["chk"]
    for x in out["hold"] + out["top"]:
        assert len(x["chk"]) == 8 and x["nchk"] == sum(x["chk"])
    held = {x["t"] for x in out["hold"]}
    for w in out["watch"]:
        assert w["nchk"] >= 6 and w["t"] not in held and w["rk"] > 5 and len(w["miss"]) == 8 - w["nchk"]
    ck = {x["t"]: x for x in out["top"]}
    if "S27" in ck:
        assert ck["S27"]["chk"][7] == 0                          # Quartalszahlen morgen
    assert ck["S25"]["chk"][5] == 0 and ck["S26"]["chk"][5] == 1  # PEG ≤ 0 = schlechtester Value, PEG 0,8 = bester
    sec_cnt = {}
    for t in held:
        sec_cnt[meta[t]["sector"]] = sec_cnt.get(meta[t]["sector"], 0) + 1
    for t, x in ck.items():
        if t not in held and sec_cnt.get(meta[t]["sector"], 0) >= 3:
            assert x["chk"][6] == 0                              # Sektor voll


def test_watchlist_illiquid_and_small_fail_liquidity():
    data = {f"S{i}": _df(0.0005 * i, seed=i) for i in range(12)}
    meta = {t: {"name": t, "market_cap_usd": 5e9} for t in data}
    meta["S11"]["market_cap_usd"] = 1e9                          # unter 2 Mrd. $
    out = LF.build(data, meta, bench=_df(0.0003, seed=5), rule={"n": 3}, fund={})
    x = {r["t"]: r for r in out["top"]}["S11"]
    assert x["chk"][0] == 0


def test_pe_5y_avg():
    f = {"pe": 20, "fa": {"y": ["2022", "2023", "2024", "2025"], "fye": "12-31", "eps": [5, 5, 5, 5]}, "pxm": {"m0": "2021-01", "c": [100.0] * 60}}
    assert abs(LF.pe_5y_avg(f) - 20.0) < 1e-9
    f["pe"] = 200
    assert LF.pe_5y_avg(f) is None
