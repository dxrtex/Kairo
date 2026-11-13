import numpy as np
import pandas as pd

from backend.run_scan import bench_payload


def test_bench_aligned_and_filled():
    i = pd.bdate_range("2025-01-01", periods=400)
    h = {"^GSPC": pd.DataFrame({"Close": np.linspace(100, 200, 400)}, index=i),
         "^GDAXI": pd.DataFrame({"Close": np.linspace(10, 20, 380)}, index=i.delete(range(100, 120)))}
    b = bench_payload(h)
    assert len(b["t"]) == 300 and set(b["c"]) == {"^GSPC", "^GDAXI"}
    assert all(len(v) == 300 for v in b["c"].values()) and None not in b["c"]["^GDAXI"]


def test_bench_needs_sp500():
    assert bench_payload({"^GDAXI": pd.DataFrame({"Close": np.ones(100)}, index=pd.bdate_range("2025-01-01", periods=100))}) is None
