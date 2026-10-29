"""Review K4: Kurslücke unter den Stop wird zur Eröffnung verkauft, nicht zum Stop."""
import numpy as np

from backend.bilanz import outcome


def test_luecke_unter_stop():
    o = np.array([100, 100, 80.0, 80])
    h = np.array([101, 101, 82.0, 82])
    l = np.array([99, 99, 79.0, 79])
    c = np.array([100, 100, 81.0, 81])
    r = outcome(o, h, l, c, 0, 100.0, 90.0, 120.0, None)
    assert r["res"] == "stop" and abs(r["r"] - (-2.0)) < 1e-9          # Eröffnung 80 statt Stop 90 → −2 R


def test_ohne_luecke_wie_bisher():
    o = np.array([100, 100, 95.0])
    h = np.array([101, 101, 96.0])
    l = np.array([99, 99, 89.0])
    c = np.array([100, 100, 90.5])
    r = outcome(o, h, l, c, 0, 100.0, 90.0, 120.0, None)
    assert r["res"] == "stop" and abs(r["r"] + 1.0) < 1e-9
