import json

from backend import fundamentals as F


def test_score_axes_range_and_logic():
    good = {"pe": 12, "fpe": 10, "pb": 1.2, "ev": 8, "tm": 150, "cp": 100, "rg": .2, "eg": .25, "pm": .2, "roe": .25, "om": .2, "gm": .5,
            "de": 30, "cr": 2, "fcf": 1e9, "cash": 5e9, "debt": 1e9, "dr": 4, "pr": .4, "sec": "Tech"}
    bad = {"pe": -5, "rg": -.1, "eg": -.3, "pm": -.2, "de": 300, "cr": .6, "fcf": -1e8, "cash": 1e8, "debt": 5e9, "sec": "Tech"}
    med = {"pe": 20, "pb": 3, "ev": 15, "rg": .05, "pm": .1}
    sg, sb = F.score(good, med, med), F.score(bad, med, med)
    assert all(0 <= x <= 6 for x in sg + sb)
    assert sum(sg) >= 25 and sum(sb) <= 3


def test_combine_keeps_previous(tmp_path):
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps({"by": {"OLD": {"pe": 10, "sec": "X", "sf": [1, 1, 1, 1, 1]}}}))
    p = tmp_path / "fund_part_0.json"
    p.write_text(json.dumps({"NEW": {"pe": 30, "pm": .1, "rg": .1, "sec": "X"}}))
    res = F.combine([p], prev)
    assert set(res["by"]) == {"OLD", "NEW"} and len(res["by"]["NEW"]["sf"]) == 5
