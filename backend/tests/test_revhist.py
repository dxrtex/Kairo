import pandas as pd

from backend import revhist as R


def _q(vals):
    return {pd.Timestamp(d): v for d, v in vals.items()}


def test_verlangsamung_bloom_aehnlich():
    q = _q({"2025-06-30": 400e6, "2025-09-30": 500e6, "2026-06-30": 1050e6})   # Vorquartal +162 %
    r = R.accel(q, 1190e6, pd.Timestamp("2026-10-22"))                         # jetzt +138 % → −24 Pkt.
    assert r["revg"] == 1.38 and r["reva"] == -0.245


def test_beschleunigung_und_fehlende_daten():
    q = _q({"2025-06-30": 100.0, "2025-09-30": 100.0, "2026-06-30": 105.0, "2026-09-30": 115.0})
    r = R.accel(q, None, pd.Timestamp("2026-10-28"))
    assert r["revg"] == 0.15 and r["reva"] == 0.1
    assert R.accel({}, 1.0, pd.Timestamp("2026-10-28")) is None
