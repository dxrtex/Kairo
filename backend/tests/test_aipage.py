import json
from pathlib import Path

from backend import aipage


def test_render_without_js(tmp_path: Path, monkeypatch):
    d = tmp_path / "site" / "data"
    d.mkdir(parents=True)
    (d / "results.json").write_text(json.dumps({"generated": "2026-10-25T16:00:00+00:00", "results": [
        {"ticker": "SQN.SW", "name": "Swiss<quote>", "region": "europe", "close": 34.8, "currency": "CHF", "passed": True, "plan": {"stop": 34.1}}]}))
    (d / "h4.json").write_text(json.dumps({"items": [{"t": "SQN.SW", "st": "4h", "base": {"lo": 34, "hi": 36, "sl": 33.8, "pending": True}}]}))
    monkeypatch.setattr(aipage, "ROOT", tmp_path)
    monkeypatch.setattr(aipage, "paper_summary", lambda: None)
    t = aipage.write(tmp_path, "2026-10-25").read_text()
    assert "<script" not in t and "Swiss&lt;quote&gt;" in t and "kaufbereit" in t and "Aufbau der App" in t
