import json

from backend import sighist as S


def test_summary_counts_only_finished_trades():
    sig = [{"d": "2025-01-02", "res": "ema", "r": 2.0}, {"d": "2025-03-02", "res": "stop", "r": -1.0},
           {"d": "2025-05-02", "res": "nobase"}, {"d": "2025-07-02", "res": "run", "r": 0.4}]
    s = S.summary(sig)
    assert s == {"n": 4, "trades": 2, "avg": 0.5, "win": 1, "best": 2.0, "worst": -1.0}
    assert S.summary([{"d": "x", "res": "wait"}]) == {"n": 1, "trades": 0}


def test_combine_keeps_previous_and_overwrites(tmp_path):
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps({"by": {"OLD": [{"d": "2025-01-01", "res": "stop", "r": -1}], "UPD": []}}))
    p = tmp_path / "sig_part_0.json"
    p.write_text(json.dumps({"UPD": [{"d": "2026-01-01", "res": "ema", "r": 1.5}]}))
    res = S.combine([p], prev)
    assert set(res["by"]) == {"OLD", "UPD"} and res["by"]["UPD"][0]["r"] == 1.5
    assert res["sum"]["UPD"]["avg"] == 1.5 and res["rule"] == "B60"


def test_signals_short_history_is_empty():
    import pandas as pd
    df = pd.DataFrame({"Open": [1.0] * 50, "High": [1.0] * 50, "Low": [1.0] * 50, "Close": [1.0] * 50, "Volume": [1] * 50},
                      index=pd.date_range("2024-01-01", periods=50))
    assert S.signals(df) == []
