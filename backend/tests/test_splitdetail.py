import json

from backend import splitdetail as sd


def test_bucket_ignores_separators_and_case():
    assert sd.bucket("BRK-B") == sd.bucket("BRK.B") == sd.bucket("brk.b") == sd.bucket("~BRK-B")
    assert 0 <= sd.bucket("MSFT") < sd.DET_N
    h = 0                                              # dieselbe Rechnung wie detB in site/index.html
    for c in "SAPDE":
        h = (h * 31 + ord(c)) % 2 ** 32
    assert sd.bucket("SAP.DE") == h % sd.DET_N


def test_split_moves_details_and_keeps_metrics():
    fund = {"generated": "2026-11-15", "med": {}, "by": {"MSFT": {"pe": 30, "eh": [[1, 2, 3]], "ud": [["d"]], "qh": [], "ih": [[1]]}, "SAP.DE": {"pe": 20}}}
    fin = {"generated": "2026-11-16", "by": {"MSFT": {"y": ["2025"], "rev": [1], "fl": [["2026-01-01", "10-K", "", "u"]]}}}
    slim, det = sd.split(fund, fin)
    assert slim["by"]["MSFT"] == {"pe": 30} and slim["by"]["SAP.DE"] == {"pe": 20} and slim["det"] == sd.DET_N
    m = det[sd.bucket("MSFT")]["MSFT"]
    assert m["eh"] == [[1, 2, 3]] and m["ud"] == [["d"]] and m["qh"] == [] and m["fin"]["rev"] == [1]
    assert "SAP.DE" not in det.get(sd.bucket("SAP.DE"), {})
    assert "eh" in fund["by"]["MSFT"]                  # Eingabe bleibt unverändert


def test_main_writes_files_and_is_idempotent(tmp_path):
    (tmp_path / "fund.json").write_text(json.dumps({"generated": "g", "by": {"NVDA": {"pe": 50, "eh": [[0]]}}}))
    (tmp_path / "fin.json").write_text(json.dumps({"generated": "f", "by": {"NVDA": {"y": ["2025"]}}}))
    assert sd.main([str(tmp_path)]) == 0
    assert not (tmp_path / "fin.json").exists() and len(list((tmp_path / "co").glob("*.json"))) == sd.DET_N
    b = json.loads((tmp_path / "co" / f"{sd.bucket('NVDA'):03d}.json").read_text())
    assert b["by"]["NVDA"] == {"eh": [[0]], "fin": {"y": ["2025"]}} and b["fin"] == "f"
    assert sd.main([str(tmp_path)]) == 0               # zweiter Lauf ändert nichts
    assert json.loads((tmp_path / "co" / f"{sd.bucket('NVDA'):03d}.json").read_text())["by"]["NVDA"]["fin"] == {"y": ["2025"]}


def test_detail_fields_never_collide_with_metrics():
    # 18.11.2026: „pm“ (Monatskurse) überschrieb die Nettomarge „pm“ – Detailfelder dürfen nie Kennzahl-Kürzel sein
    from backend.fundamentals import FIELDS as METRICS
    assert not set(sd.FIELDS) & set(METRICS) and not set(sd.FIELDS) & {"sec", "ind", "sf", "_d"}
    slim, det = sd.split({"by": {"X": {"pm": .2, "pxm": {"m0": "2020-01", "c": [1]}}}}, None)
    assert slim["by"]["X"] == {"pm": .2} and det[sd.bucket("X")]["X"] == {"pxm": {"m0": "2020-01", "c": [1]}}
