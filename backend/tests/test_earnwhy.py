import json

import numpy as np
import pandas as pd

from backend import earnfast, earnwhy
from tools import earn_review

RSS = "Fri, 30 Oct 2026 14:00:00 GMT"


def _px(tks, start, end):
    idx = pd.bdate_range("2026-09-01", "2026-11-06")
    out = {"SPY": pd.Series(np.linspace(600, 600, len(idx)), index=idx)}
    out["SPY"].loc["2026-10-30":] = 590.0                       # Markt am 30.10. −1,7 %
    for t in tks:
        if t != "SPY":
            out[t] = pd.Series(np.linspace(40, 50, len(idx)), index=idx)   # Vorlauf +
    return pd.DataFrame(out)


def test_ursachensuche_intel():
    arc = {"INTC|2026-10-30": {"s": 0.3, "p": 0.64, "r1": -0.28},          # Fehlprognose
           "AAPL|2026-10-30": {"s": 0.05, "p": 0.55, "r1": 0.02},          # getroffen (Vergleich)
           "MSFT|2026-10-30": {"s": 0.05}}                                 # noch keine Reaktion
    rss = lambda q: [("Intel stock plunges 21% as chipmaker blames PC slowdown for weak guidance - CNBC", "u", RSS),
                     ("Intel shares fall as margins disappoint - Reuters", "u", RSS),
                     ("Apple shares rise on iPhone sales - X", "u", RSS)]
    n = earnwhy.analyze(arc, {"INTC": "Intel Corporation", "AAPL": "Apple Inc."}, rss=rss, prices=_px)
    assert n == 2 and "why" not in arc["MSFT|2026-10-30"]
    w = arc["INTC|2026-10-30"]["why"]
    assert set(w["tags"]) >= {"Ausblick", "Marge"} and w["spy"] < -0.01 and w["run20"] > 0 and w["head"][0].startswith("Intel stock plunges")
    assert arc["AAPL|2026-10-30"]["why"]["tags"] == ["Umsatz"]
    assert earnwhy.is_miss(arc["INTC|2026-10-30"]) and not earnwhy.is_miss(arc["AAPL|2026-10-30"])
    assert earnwhy.analyze(arc, {}, rss=rss, prices=_px) == 0               # nichts doppelt


def test_kandidaten_und_nacheichung(tmp_path):
    rng = np.random.default_rng(1)
    arc = {}
    for i in range(300):
        d = (pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        down = i % 4 == 0                                              # jeder 4. Bericht: Ausblick gesenkt → fällt meist
        r1 = -0.06 if (down and rng.random() < .85) else (0.03 if rng.random() < .6 else -0.02)
        p = 0.61                                                       # alte Regel: kennt den Ausblick nicht
        miss = earnwhy.is_miss({"p": p, "r1": r1})
        arc[f"T{i}|{d}"] = {"s": 0.2, "g": -1 if down else None, "r1": r1, "p": p, "v": "alt",
                            "why": {"tags": ["Ausblick", "Marge"] if miss else ["Umsatz"], "head": ["T stock falls"], "spy": 0.0, "ex": r1, "run20": 0.1 if miss else 0.0}}
    (tmp_path / "a.json").write_text(json.dumps(arc))
    res = earn_review.review(str(tmp_path / "a.json"), "site/earn_stats.json", str(tmp_path / "o"))
    assert any(c.startswith("Ausblick") for c in res["candidates"]) and any(c.startswith("Vorlauf") for c in res["candidates"])
    cal = json.loads((tmp_path / "o" / "earn_calib.json").read_text())
    assert res["calib"] and cal["adopt"] and cal["p"]["4|gesenkt"] < 0.35 and cal["p"]["4|keine Meldung"] > 0.55
    # die Archiv-Prognose nutzt die übernommene Nacheichung
    (tmp_path / "earn_calib.json").write_text(json.dumps(cal))
    earnfast.archive({"X": {"last": {"date": "2026-11-01", "eps_s": 0.2, "guide": {"d": -1}}}}, tmp_path)
    a = json.loads((tmp_path / "earn_archive.json").read_text())["X|2026-11-01"]
    assert a["p"] == cal["p"]["4|gesenkt"] and a["v"].endswith("nachgeeicht")
