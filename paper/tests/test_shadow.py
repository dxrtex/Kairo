"""Schattenbuch: Signale werden ohne CRV-Filter verfolgt, Ausstiegsregeln laufen parallel, Zeit-Ausstieg, Auswertung."""
import pandas as pd

from paper import shadow
from paper.tests.test_run import market


def empty():
    return {"start": None, "last_day": None, "pending": [], "open": [], "closed": []}


def test_s19_trigger_recorded_despite_low_crv():
    mk, days, D_prev, D = market()
    mk.h4["AAA"].iloc[0, mk.h4["AAA"].columns.get_loc("Close")] = 98.0       # rote Kerze vor dem Auslöser
    sb = empty()
    sb["pending"] = [{"fam": "S19", "t": "AAA", "day": str(D_prev.date()), "expiry": str(D.date()), "panic": 90.0, "atr": 2.0,
                      "z": -2.2, "var": ["S19C"], "regime": "bull"}]
    shadow.step_day(sb, mk, D, D_prev, days, True)
    tr = sb["open"] + sb["closed"]
    assert len(tr) == 1 and tr[0]["mode"] == "4h" and tr[0]["crv"] < 2          # Depot lehnt ab, Schattenbuch verfolgt weiter
    assert tr[0]["entry"] is not None and pd.Timestamp(tr[0]["entry_ts"]) > pd.Timestamp(tr[0]["after_ts"])
    assert not sb["pending"]


def test_time_exit_and_summary():
    mk, days, D_prev, D = market()
    sb = empty()
    x = shadow._trade({"fam": "S19", "t": "AAA", "day": str(days[-9].date()), "var": ["S19", "S19B", "S19C"], "z": -3, "atr": 2.0},
                      "frueh", 80.0, 1.6, after_day=str(days[-9].date()))
    x.update(entry=90.0, entry_ts=str(days[-8] + pd.Timedelta(hours=13)), qty=2, sp=0.001, rate=1.0,
             pos={r: {"sid": "S19", "entry": 90.0, "stop": 80.0, "atr": 2.0, "be": False} for r in shadow.EXITS["S19"]})
    sb["open"].append(x)
    shadow.step_day(sb, mk, D, D_prev, days, True)
    ex = (sb["open"] + sb["closed"])[0]["exits"]
    assert ex["t5"]["why"] == "zeit" and ex["t5"]["R"] > 0 and ex["t5"]["R_net"] < ex["t5"]["R"]
    assert "t10" not in ex                                                      # erst 7 Handelstage gehalten
    ex["t10"] = ex["ema20"] = ex["t5"]
    shadow.step_day(sb, mk, D, D_prev, days, True)                              # alle Regeln fertig → abgeschlossen
    assert len(sb["closed"]) == 1
    m = {(r["var"], r["mode"], r["crv_min"], r["exit"]): r for r in shadow.summary(sb)["matrix"]}
    assert m[("S19", "frueh", None, "t5")]["n"] == 1 and m[("S19", "frueh", 1.5, "t5")]["n"] == 1
    assert m[("S19", "frueh", 2.0, "t5")]["n"] == 0
