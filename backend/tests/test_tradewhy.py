"""Fehlschläge verstehen (backend/tradewhy.py): Ursachen je Trade, Lern-Bericht mit Zeit-Trennung, keine Regeländerung."""
import numpy as np
import pandas as pd

from backend import tradewhy as W

IDX = pd.bdate_range("2025-01-01", periods=400)
NORSS = lambda q: []


def _px(path):
    return pd.DataFrame({"Close": np.asarray(path, float)}, index=IDX)


def _sn(t, d, r, res="stop", days=5, stop_atr=1.5, tone="green", earn=None, region="us", sector="Technology", seen=None):
    return {"t": t, "k": "hit", "d": d, "late": 0, "ver": {"rule": "B60"},
            "sig": {"stop_atr": stop_atr, "mom": 0.0, "flags": {"atr_pct": 0.02}, "market": {"tone": tone},
                    "region": region, "sector": sector, "earn": earn},
            "exit": {"res": res, "r": r, "days": days, "seen": seen or str((pd.Timestamp(d) + pd.offsets.BDay(10)).date())}}


def test_explain_pre_and_post():
    up = np.linspace(100, 200, 400)
    down = up.copy(); down[300:] = down[299] * np.linspace(1, 0.5, 100)     # Markt fällt ab Tag 300
    d = str(IDX[340].date())
    ctx = {"^GSPC": _px(down), "XLK": _px(down)}
    stock = _px(down * 0.9)
    sn = _sn("A", d, -1.3, days=2, stop_atr=0.8, tone="red", earn=str(IDX[345].date()))
    w = W.explain(sn, stock, ctx)
    assert {"eng", "markt_rot", "zahlen_bald", "sektor_u50"} <= set(w["pre"])
    assert {"markt_fiel", "sektor_fiel", "luecke", "schnell", "zahlen"} <= set(w["post"])
    assert w["idx"] < -0.03


def test_explain_missing_market_data_is_unknown_not_false():
    w = W.explain(_sn("A", str(IDX[250].date()), 0.5, res="ema"), None, {})
    assert "index_u200" in w["unk"] and "sektor_u50" in w["unk"] and "markt_fiel" not in w["post"]


def test_analyze_only_closed_hits_and_once():
    snaps = {"A|hit|x": _sn("A", str(IDX[250].date()), -1.0), "B|trend|x": {**_sn("B", str(IDX[250].date()), -1.0), "k": "trend"},
             "C|hit|x": {k: v for k, v in _sn("C", str(IDX[250].date()), 0).items() if k != "exit"}}
    assert W.analyze(snaps, {}, {}, rss=NORSS) == 1 and "why" in snaps["A|hit|x"]
    snaps["A|hit|x"]["why"]["pre"] = ["sentinel"]
    assert W.analyze(snaps, {}, {}, rss=NORSS) == 0 and snaps["A|hit|x"]["why"]["pre"] == ["sentinel"]


def _book(n_eng_bad=12, n_ok=30, consistent=True):
    snaps = {}
    for i in range(n_eng_bad + n_ok):
        d = str(IDX[220 + i * 3].date())
        eng = i % 3 == 0 and i < 3 * n_eng_bad
        late_half = i >= (n_eng_bad + n_ok) // 2
        r = (-0.8 if (consistent or not late_half) else 1.2) if eng else 0.4 * (1 if i % 2 else -0.5)
        snaps[f"T{i}|hit|{d}"] = _sn(f"T{i}", d, r, stop_atr=3.0 if eng else 1.6)
    W.analyze(snaps, {}, {}, rss=NORSS)
    return snaps


def test_report_candidate_needs_size_effect_and_both_halves():
    rep = W.report(_book())
    eng = next(p for p in rep["pre"] if p["k"] == "weit")
    assert eng["status"] == "Kandidat – Backtest" and "weit" in rep["candidates"] and eng["diff"] <= -0.25
    assert all(h < 0 for h in eng["halves"])
    rep2 = W.report(_book(consistent=False))                    # in der späteren Hälfte umgekehrt → kein Kandidat
    assert "weit" not in rep2["candidates"]
    rep3 = W.report(_book(n_eng_bad=4))                         # zu wenig Fälle
    assert next(p for p in rep3["pre"] if p["k"] == "weit")["status"] == "zu wenig Fälle"


def test_already_tested_features_are_not_proposed_again():
    snaps = _book()
    for i, s in enumerate(snaps.values()):          # Merkmal ohne Zusammenhang mit dem Ergebnis → bleibt „schon getestet“
        s["why"]["pre"] = ["zahlen_bald"] if i % 2 else []
    rep = W.report(snaps)
    z = next(p for p in rep["pre"] if p["k"] == "zahlen_bald")
    assert z["status"] == "schon getestet" and "zahlen_bald" not in rep["candidates"] and z["note"]


def test_report_recent_losses_have_readable_reasons():
    rep = W.report(_book())
    assert rep["n"] == 42 and rep["recent"] and all(x["r"] <= 0 for x in rep["recent"])
    assert any("Stop weiter" in t for x in rep["recent"] for t in x["pre"])


def test_losers_get_headlines_and_a_lesson():
    seen = []
    def rss(q):
        seen.append(q)
        return [("Acme stock plunges after guidance cut - Reuters", "", ""), ("Acme shares fall as analysts downgrade", "", ""),
                ("Weather is nice today", "", "")]
    snaps = {"A|hit|x": _sn("A", str(IDX[250].date()), -1.0), "B|hit|x": _sn("B", str(IDX[250].date()), 1.5, res="ema")}
    W.analyze(snaps, {}, {}, names={"A": "Acme Corp", "B": "Beta"}, rss=rss)
    a, b = snaps["A|hit|x"]["why"], snaps["B|hit|x"]["why"]
    assert len(seen) == 1 and "Acme" in seen[0] and "after:" in seen[0]          # nur Verlierer werden gesucht
    assert "Ausblick" in a["news"] and "Analysten" in a["news"] and len(a["head"]) == 2 and "news" not in b
    W.analyze(snaps, {}, {}, rss=rss)
    assert len(seen) == 1                                                        # kein zweites Mal
    rep = W.report(snaps)
    x = rep["recent"][0]
    assert x["head"].startswith("Acme stock plunges") and "Vorher nicht erkennbar" in x["lesson"] and rep["news"][0][1] == 1


def test_tested_feature_is_flagged_again_if_live_contradicts_research():
    snaps = _book()
    for s in snaps.values():                       # „eng“ ist historisch geprüft – live aber beständig schlecht
        s["why"]["pre"] = ["eng"] if s["exit"]["r"] == -0.8 else []
    rep = W.report(snaps)
    e = next(p for p in rep["pre"] if p["k"] == "eng")
    assert e["status"] == "live auffällig – erneut prüfen" and "eng" in rep["candidates"]
    assert "wird als Filter geprüft" in rep["recent"][0]["lesson"] or any("Filter geprüft" in r["lesson"] for r in rep["recent"])
