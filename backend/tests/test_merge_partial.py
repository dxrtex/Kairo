"""Watchlist-Scan: nur die neu gescannten Aktien ersetzen, alles andere bleibt."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("merge_partial", Path(__file__).resolve().parents[2] / "tools" / "merge_partial.py")
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)


def _w(d, name, obj):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(obj), encoding="utf-8")


def test_merge(tmp_path):
    live, part = tmp_path / "live", tmp_path / "part"
    _w(live, "results.json", {"generated": "2026-10-26T21:00:00+00:00", "stats": {"hits": 1},
                              "results": [{"ticker": "AAA", "passed": True, "score": 90, "senti": {"fu": {"pe": 10, "pe_sec": 15}}},
                                          {"ticker": "BBB", "passed": False, "score": 50}]})
    _w(part, "results.json", {"generated": "2026-10-27T14:00:00+00:00",
                              "results": [{"ticker": "AAA", "passed": False, "score": 70, "senti": {"fu": {"pe": 11}}}]})
    _w(live, "search.json", {"rows": [{"t": "AAA", "s": "hit"}, {"t": "BBB", "s": ""}]})
    _w(part, "search.json", {"rows": [{"t": "AAA", "s": ""}]})
    _w(live, "analysis.json", {"market": {"x": 1}, "tickers": {"AAA": {"v": 1}, "BBB": {"v": 1}}})
    _w(part, "analysis.json", {"market": {"x": 2}, "tickers": {"AAA": {"v": 2}}})
    _w(part / "charts", "AAA.json", {"c": [1]})
    out = mp.merge(live, part)
    R = json.loads((live / "results.json").read_text())
    assert out["n"] == 1 and R["stats"]["hits"] == 0 and R["full_at"].startswith("2026-10-26")
    a = next(r for r in R["results"] if r["ticker"] == "AAA")
    assert a["score"] == 70 and a["senti"]["fu"]["pe_sec"] == 15 and len(R["results"]) == 2
    S = json.loads((live / "search.json").read_text())
    assert [r["s"] for r in S["rows"]] == ["", ""]
    A = json.loads((live / "analysis.json").read_text())
    assert A["tickers"]["AAA"]["v"] == 2 and A["tickers"]["BBB"]["v"] == 1 and A["market"]["x"] == 1
    assert (live / "charts" / "AAA.json").exists()
