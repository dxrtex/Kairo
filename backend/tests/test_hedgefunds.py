from backend.hedgefunds import compare, parse_infotable

XML = """<?xml version="1.0"?><informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>1000000</value>
<shrsOrPrnAmt><sshPrnamt>5000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><investmentDiscretion>SOLE</investmentDiscretion></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>200000</value>
<shrsOrPrnAmt><sshPrnamt>1000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><investmentDiscretion>DFND</investmentDiscretion></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>CALL</titleOfClass><cusip>037833100</cusip><value>99</value>
<shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><putCall>Call</putCall></infoTable>
<infoTable><nameOfIssuer>NVIDIA CORP</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>67066G104</cusip><value>800000</value>
<shrsOrPrnAmt><sshPrnamt>4000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
</informationTable>"""


def test_parse_sums_lots_and_skips_options():
    h = parse_infotable(XML)
    assert h["037833100"]["sh"] == 6000 and h["037833100"]["val"] == 1_200_000
    assert h["67066G104"]["sh"] == 4000


def test_compare_actions():
    new = {"A": {"name": "A", "sh": 110, "val": 110}, "B": {"name": "B", "sh": 50, "val": 50}, "N": {"name": "N", "sh": 10, "val": 10}}
    old = {"A": {"name": "A", "sh": 100, "val": 100}, "B": {"name": "B", "sh": 100, "val": 100}, "X": {"name": "X", "sh": 5, "val": 5}}
    m = {x["cusip"]: x for x in compare(new, old)}
    assert m["A"]["a"] == "auf" and m["B"]["a"] == "ab" and m["N"]["a"] == "neu" and m["X"]["a"] == "raus"
    assert abs(m["A"]["chg"] - .1) < 1e-9 and m["X"]["val"] == 0


def test_norm_matches_sec_titles():
    from backend.hedgefunds import norm
    assert norm("APPLE INC") == norm("Apple Inc.")
    assert norm("NVIDIA CORPORATION") == norm("NVIDIA CORP")
    assert norm("ALPHABET INC CL A") == norm("Alphabet Inc.")


def test_parse_with_prefixes_and_xsi():
    x = """<?xml version="1.0" encoding="UTF-8"?>
<ns1:informationTable xmlns:ns1="http://www.sec.gov/edgar/document/thirteenf/informationtable" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://x y">
<ns1:infoTable><ns1:nameOfIssuer>APPLE INC</ns1:nameOfIssuer><ns1:cusip>037833100</ns1:cusip><ns1:value>100</ns1:value>
<ns1:shrsOrPrnAmt><ns1:sshPrnamt>10</ns1:sshPrnamt><ns1:sshPrnamtType>SH</ns1:sshPrnamtType></ns1:shrsOrPrnAmt></ns1:infoTable></ns1:informationTable>"""
    h = parse_infotable(x)
    assert h["037833100"]["sh"] == 10


def test_quarter_start():
    from backend.hedgefunds import quarter_start
    assert quarter_start("2026-09-30") == "2026-07-01" and quarter_start("2026-03-31") == "2026-01-01" and quarter_start("2026-12-31") == "2026-10-01"


def test_entry_zone_vwap_and_band():
    from backend.hedgefunds import entry_zone
    rows = [("2026-06-30", 50, 50, 50, 1e6)]                          # vor dem Quartal: zählt nicht
    rows += [(f"2026-07-{d:02d}", 10, 10, 10, 100) for d in range(1, 21)]   # 20 Tage bei 10 mit wenig Volumen
    rows += [(f"2026-08-{d:02d}", 20, 20, 20, 400) for d in range(1, 21)]   # 20 Tage bei 20 mit vierfachem Volumen
    rows += [("2026-11-13", 25, 24, 24.5, 1000)]                      # nach dem Quartal: nur aktueller Kurs
    ez = entry_zone(rows, "2026-07-01", "2026-09-30")
    assert abs(ez["vw"] - 18) < 1e-9                                # (10·100 + 20·400) / 500 je Tag
    assert ez["lo"] == 20 and ez["hi"] == 20                        # mittlere Hälfte des Volumens liegt komplett bei 20
    assert ez["ql"] == 10 and ez["qh"] == 20 and ez["px"] == 24.5 and ez["pxd"] == "2026-11-13"


def test_entry_zone_needs_enough_days():
    from backend.hedgefunds import entry_zone
    assert entry_zone([(f"2026-07-{d:02d}", 1, 1, 1, 1) for d in range(1, 10)], "2026-07-01", "2026-09-30") is None
