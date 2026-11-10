import numpy as np
import pandas as pd

from backend.run_scan import chart_frame, chart_payload


def _df(start, n, base=100.0):
    idx = pd.bdate_range(start, periods=n)
    c = base + np.arange(n, dtype=float)
    return pd.DataFrame({"Open": c, "High": c + 1, "Low": c - 1, "Close": c, "Volume": np.full(n, 1000)}, index=idx)


def test_lange_historie_wird_vorne_angesetzt_scan_daten_bleiben_gleich():
    scan = _df("2024-11-18", 500, 500.0)
    long = _df("2021-11-18", 1300, 10.0)          # andere Werte im Überlappungsbereich → dürfen NICHT übernommen werden
    out = chart_frame(scan, long)
    assert out.index[0] < scan.index[0]
    tail = out.loc[out.index >= scan.index[0]]
    pd.testing.assert_frame_equal(tail, scan)
    assert out.index.is_monotonic_increasing and not out.index.duplicated().any()


def test_ohne_lange_historie_bleibt_es_beim_scan():
    scan = _df("2024-11-18", 300)
    assert chart_frame(scan, None) is scan
    assert chart_frame(scan, pd.DataFrame()) is scan


def test_chart_payload_hat_bis_zu_1000_kerzen():
    out = chart_payload(chart_frame(_df("2024-11-18", 500, 500.0), _df("2020-11-18", 1600, 10.0)))
    assert len(out["t"]) == 1000 and len(out["c"]) == 1000 and len(out["rsi"]) == 1000
