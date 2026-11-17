import pandas as pd

from backend import indices

UNI = {"AAPL": "Apple Inc.", "BRK-B": "Berkshire Hathaway Inc.", "MSFT": "Microsoft Corp", "SAP.DE": "SAP SE", "ADS.DE": "adidas AG",
       "MC.PA": "LVMH Moët Hennessy Louis Vuitton SE", "ASML.AS": "ASML Holding N.V.", "7203.T": "Toyota Motor Corporation"}


def test_candidates():
    assert indices.candidates("BRK.B", "")[0] == "BRK-B"
    assert indices.candidates("ADS", ".DE")[0] == "ADS.DE"
    assert indices.candidates("XETRA: SAP", ".DE")[0] == "SAP.DE"
    assert indices.candidates("7203", ".T")[0] == "7203.T"
    assert indices.candidates("MC.PA", None)[0] == "MC.PA"
    assert indices.candidates(float("nan"), "") == []
    assert indices.candidates(9983.0, ".T")[0] == "9983.T"


def test_name_col_variants():
    t = pd.DataFrame({"Symbol": ["XX1"], "Name (A–Z)": ["Apple"]})
    got, _ = indices.resolve(t, "", UNI)
    assert got == ["AAPL"]


def test_pick_and_resolve():
    other = pd.DataFrame({"Year": [2020, 2021], "Note": ["a", "b"]})
    t = pd.DataFrame({"Symbol": ["AAPL", "BRK.B", "MSFT", "XYZ"], "Security": ["Apple", "Berkshire", "Microsoft", "Unknown Co"]})
    tab = indices.pick_table([other, t], 3, 10)
    assert tab is not None and "Symbol" in tab.columns
    got, total = indices.resolve(tab, "", UNI)
    assert got == ["AAPL", "BRK-B", "MSFT"] and total == 4


def test_name_fallback():
    t = pd.DataFrame({"Ticker": ["XX1", "ASML"], "Company": ["LVMH Moët Hennessy Louis Vuitton", "ASML Holding"]})
    got, _ = indices.resolve(t, None, UNI)
    assert "MC.PA" in got and "ASML.AS" in got


def test_build_with_fallback():
    uni = {**UNI, **{f"Q{i}": f"Firma {i}" for i in range(498)}}
    sp = pd.DataFrame({"Symbol": ["AAPL", "MSFT"] + [f"Q{i}" for i in range(498)], "Security": ["Apple", "Microsoft"] + [f"Firma {i}" for i in range(498)]})
    def fetch(url):
        if "S%26P" in url:
            return [sp]
        raise OSError("blocked")
    prev = {"dax": {"n": "DAX 40", "t": ["SAP.DE"], "total": 40}}
    out = indices.build(uni, fetch=fetch, previous=lambda: prev)
    assert len(out["idx"]["sp500"]["t"]) == 500 and out["idx"]["sp500"]["total"] == 500 and "AAPL" in out["idx"]["sp500"]["t"]
    assert out["idx"]["dax"] == prev["dax"] and "ndx" not in out["idx"]


def test_too_few_matches_rejected():
    sp = pd.DataFrame({"Symbol": [f"Q{i}" for i in range(500)], "Security": [f"Firma {i}" for i in range(500)]})
    out = indices.build(UNI, fetch=lambda u: [sp] if "S%26P" in u else [], previous=lambda: {})
    assert "sp500" not in out["idx"]
