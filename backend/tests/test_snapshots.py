"""Momentaufnahmen neuer Signale (backend/snapshots.py): Point-in-Time, unveränderlich, Signaltag ≠ Kauftag."""
import numpy as np
import pandas as pd

from backend import live, snapshots, state


def _df(n=200, start="2026-01-01"):
    c = np.linspace(80, 100, n)
    d = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6}, index=pd.bdate_range(start, periods=n))
    return d


def _row(t="AAA", d=None, rsi=30.0, passed=True):
    crit = [{"key": f"c{i}", "label": f"K{i}", "ok": True, "value": str(i), "threshold": ">0"} for i in range(11)]
    return {"ticker": t, "name": t + " Corp", "date": d, "passed": passed, "fast_hit": False, "score": 7, "met": 11, "total": 11,
            "rsi": rsi, "macd_status": "grün", "mbi_status": "grün", "region": "us", "sector": "Tech", "close": 100.0,
            "criteria": crit, "flags": {"atr": 2.0, "atr_pct": 0.02, "volatility": 0.3},
            "plan": {"entry": 100.0, "stop": 96.0, "target1": 110, "target2": 120, "crv": 2.5}}


MARKET = {"regime": {"label": "Aufwärtstrend", "tone": "green"}, "fear": {"score": 55}}


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "DIR", tmp_path)
    monkeypatch.setattr(state, "READONLY", False)


def test_snapshot_fields_and_versions(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    df = _df()
    d = str(df.index[-1].date())
    live.update([_row(d=d)], {"AAA": df}, d, record=True, market=MARKET)
    snaps = state.load("snapshots.json", {})
    sn = snaps[f"AAA|hit|{d}"]
    g = sn["sig"]
    assert len(g["crit"]) == 11 and all(c["ok"] for c in g["crit"].values()) and g["crit"]["c3"]["v"] == "3"
    assert g["rsi"] == 30.0 and g["stop_pct"] == 0.04 and g["stop_atr"] == 2.0 and g["market"]["tone"] == "green"
    assert g["mom"] is not None and sn["ver"]["rule"] == "B60" and sn["ver"]["schema"] == snapshots.SCHEMA
    assert sn["d"] == d and sn["scan"] == d and sn["late"] == 0 and "buy" not in sn


def test_repeated_scan_does_not_overwrite(tmp_path, monkeypatch):
    """Zweiter Scan am selben Tag (oder später mit anderen Werten) ändert die Momentaufnahme nicht."""
    _setup(tmp_path, monkeypatch)
    df = _df()
    d = str(df.index[-1].date())
    live.update([_row(d=d, rsi=30.0)], {"AAA": df}, d, record=True, market=MARKET)
    first = state.load("snapshots.json", {})[f"AAA|hit|{d}"]
    live.update([_row(d=d, rsi=55.0)], {"AAA": df}, d, record=True, market={"regime": {"tone": "red"}})
    again = state.load("snapshots.json", {})
    assert len(again) == 1 and again[f"AAA|hit|{d}"]["sig"] == first["sig"] and again[f"AAA|hit|{d}"]["at"] == first["at"]


def test_daytime_run_records_nothing(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    df = _df()
    d = str(df.index[-1].date())
    live.update([_row(d=d)], {"AAA": df}, d, record=False, market=MARKET)
    assert state.load("snapshots.json", {}) == {}


def test_outage_marks_late_and_no_backfill(tmp_path, monkeypatch):
    """Scan fiel aus: Signaltag 3 Handelstage vor dem Scan → late = 3. Alte Signale ohne Aufnahme bleiben ohne."""
    _setup(tmp_path, monkeypatch)
    df = _df()
    d = str(df.index[-4].date())
    today = str(df.index[-1].date())
    state.save("signals.json", [{"t": "OLD", "n": "Old", "k": "hit", "d": "2026-03-02", "entry": 50, "stop": 48, "res": "running"}])
    live.update([_row(d=d)], {"AAA": df}, today, record=True, market=MARKET)
    snaps = state.load("snapshots.json", {})
    assert snaps[f"AAA|hit|{d}"]["late"] == 3
    assert not any(k.startswith("OLD|") for k in snaps)


def test_buy_and_exit_are_separate_from_signal_day():
    snaps = {"AAA|hit|2026-05-01": {"t": "AAA", "k": "hit", "d": "2026-05-01", "ver": {"rule": "B60"},
                                    "sig": {"rsi": 30, "mom": -0.1, "stop_pct": 0.04, "stop_atr": 2, "score": 7, "flags": {"atr": 2},
                                            "market": {"tone": "green"}, "region": "us"}}}
    frozen = dict(snaps["AAA|hit|2026-05-01"]["sig"])
    sig = [{"t": "AAA", "k": "hit", "d": "2026-05-01", "st60": {"res": "wait"}}]
    snapshots.track(snaps, sig, "2026-05-04")
    assert "buy" not in snaps["AAA|hit|2026-05-01"]                    # Basis noch offen: kein Kauf
    sig[0]["st60"] = {"res": "run", "r": 0.2, "days": 3, "e": 101.0, "sl": 97.0}
    snapshots.track(snaps, sig, "2026-05-12")
    assert snaps["AAA|hit|2026-05-01"]["buy"] == {"e": 101.0, "sl": 97.0, "seen": "2026-05-12"}
    sig[0]["st60"] = {"res": "ema", "r": 1.4, "days": 15, "e": 101.0, "sl": 97.0}
    snapshots.track(snaps, sig, "2026-05-30")
    snapshots.track(snaps, sig, "2026-06-02")                           # zweiter Lauf ändert nichts mehr
    sn = snaps["AAA|hit|2026-05-01"]
    assert sn["buy"]["seen"] == "2026-05-12" and sn["exit"] == {"res": "ema", "r": 1.4, "days": 15, "seen": "2026-05-30"}
    assert sn["sig"] == frozen
    t = snapshots.table(snaps)
    assert len(t) == 1 and bool(t.iloc[0]["win"]) and t.iloc[0]["f_atr"] == 2
    assert snapshots.compare(snaps) == {"n": 1, "need": 30}
