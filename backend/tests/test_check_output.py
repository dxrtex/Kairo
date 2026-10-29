"""Pflichtprüfung vor dem Veröffentlichen (Review W13)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_output  # noqa: E402


def _write(d, results, search, h4):
    for n, o in (("results.json", results), ("search.json", search), ("h4.json", h4)):
        (d / n).write_text(json.dumps(o) if not isinstance(o, str) else o, encoding="utf-8")


def test_vollstaendig_besteht(tmp_path):
    _write(tmp_path, {"generated": "x", "stats": {"universe": 100, "loaded": 95}, "results": []},
           {"rows": [{}] * 1200}, {"items": []})
    assert check_output.check(tmp_path) == []


def test_unvollstaendig_oder_kaputt_faellt_durch(tmp_path):
    _write(tmp_path, {"generated": "x", "stats": {"universe": 100, "loaded": 40}, "results": []}, "{kaputt", {"items": []})
    e = check_output.check(tmp_path)
    assert any("40 von 100" in x for x in e) and any("search.json" in x for x in e)
