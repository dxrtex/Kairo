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
