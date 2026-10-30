import json

from backend import earnfast
from tools import earn_review


def test_bilanz_und_vorschlag(tmp_path):
    arc = {}
    for i in range(40):                       # 40× Gewinn deutlich darüber + Ausblick gesenkt: Kairo sagte 25 %, 10 % stiegen
        arc[f"T{i}|2026-11-{1 + i % 28:02d}"] = {"s": 0.3, "g": -1, "r1": 0.03 if i < 4 else -0.05, "p": 0.25, "v": "A", "gt": "X cuts outlook"}
    for i in range(10):
        arc[f"U{i}|2026-11-02"] = {"s": 0.05, "r1": 0.02, "p": 0.55, "v": "A"}
    arc["V|2026-11-03"] = {"s": 0.05}                                  # noch keine Reaktion → zählt nicht
    (tmp_path / "a.json").write_text(json.dumps(arc))
    res = earn_review.review(str(tmp_path / "a.json"), "site/earn_stats.json", str(tmp_path / "o"))
    assert res["n"] == 50 and abs(res["hit"] - 46 / 50) < 1e-9
    assert any("Ausblick gesenkt" in x and "tatsächlich 10%" in x for x in res["suggest"])
    md = (tmp_path / "o" / "earn_review.md").read_text()
    assert "Eichung" in md and "X cuts outlook" in md


def test_archiv_friert_prognose_mit_kursreaktion_ein(tmp_path):
    rec = {"INTC": {"last": {"date": "2026-10-29", "eps_s": 0.30, "reva": -0.04, "guide": {"d": 1, "t": "Intel lifts outlook"}}}}
    earnfast.archive(rec, tmp_path)
    a = json.loads((tmp_path / "earn_archive.json").read_text())["INTC|2026-10-29"]
    assert a["p"] == 0.636 and a["v"] == earnfast.MODEL and a["gt"] == "Intel lifts outlook"
    rec["INTC"]["last"]["rx"] = {"d1": -0.28}
    earnfast.archive(rec, tmp_path)                                    # Reaktion da: p wird letztmals geschrieben
    rec["INTC"]["last"]["guide"] = {"d": -1, "t": "Intel cuts outlook"}
    earnfast.archive(rec, tmp_path)                                    # danach eingefroren
    a = json.loads((tmp_path / "earn_archive.json").read_text())["INTC|2026-10-29"]
    assert a["p"] == 0.636 and a["r1"] == -0.28 and a["g"] == -1
