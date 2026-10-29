"""Datenprüfung erkennt die typischen Fehler (künstliche Kurse)."""
import numpy as np
import pandas as pd

from research.ultimate.data_audit import per_ticker, signal_impact, stooq_symbol


def frame(c, a=None, v=1e5):
    d = pd.bdate_range("2010-01-01", periods=len(c))
    c = np.asarray(c, float)
    return pd.DataFrame({"date": d, "Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
                         "AdjClose": c if a is None else np.asarray(a, float), "Volume": v})


def test_sauber():
    r = per_ticker("X", frame(np.linspace(10, 20, 300)))
    assert not r["spikes"] and not r["split_rest"] and r["ohlc_bad"] == 0 and r["gaps"] == 0


def test_fehlkurs_und_split_rest():
    c = np.full(300, 50.0); c[100] = 90.0            # Ausreißer, am Folgetag zurück
    c[200:] = 25.0                                     # unbereinigter 2:1-Split (AdjClose springt mit)
    r = per_ticker("X", frame(c))
    assert r["spikes"] == [str(pd.bdate_range("2010-01-01", periods=300)[100].date())]
    assert len(r["split_rest"]) == 1


def test_bereinigter_split_zaehlt_nicht():
    c = np.full(300, 50.0); c[200:] = 25.0
    r = per_ticker("X", frame(c, a=np.full(300, 25.0)))
    assert not r["split_rest"]


def test_luecke_und_kerze():
    f = frame(np.linspace(10, 20, 300)).drop(index=range(50, 60))
    f.loc[5, "High"] = 1.0
    r = per_ticker("X", f)
    assert r["gaps"] == 1 and r["ohlc_bad"] == 1


def test_wirkung_und_symbole():
    sig = pd.DataFrame({"ticker": ["X", "X", "Y"], "date": pd.to_datetime(["2015-01-10", "2018-01-01", "2015-01-10"])})
    w = signal_impact(sig, {"X": ["2015-03-01"], "Y": []})
    assert w["affected"] == 1 and w["signals"] == 3
    assert stooq_symbol("AAPL") == "aapl.us" and stooq_symbol("SAP.DE") == "sap.de" and stooq_symbol("7203.T") is None
