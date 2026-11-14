"""ARK-Bestandslisten: lesen, Tag-zu-Tag-Vergleich, Sammeln über 30 Tage."""
from backend.ark import FUNDS, diff, parse, update

CSV1 = """date,fund,company,ticker,cusip,shares,"market value ($)","weight (%)"
11/12/2026,ARKK,TESLA INC,TSLA,88160R101,"1,000,000","$400,000,000.00",10.50%
11/12/2026,ARKK,ROKU INC,ROKU,77543R102,"500,000","$50,000,000.00",3.10%
11/12/2026,ARKK,COINBASE GLOBAL INC -CLASS A,COIN,19260Q107,"200,000","$60,000,000.00",4.00%
11/12/2026,ARKK,MORGAN STANLEY GOVT INSTL 8035,MSGXX,X9USDMORS,"1","$1.00",0.10%
"""
CSV2 = CSV1.replace("11/12/2026", "11/13/2026").replace('"1,000,000"', '"1,005,000"').replace('"500,000"', '"420,000"').replace(
    "11/13/2026,ARKK,COINBASE GLOBAL INC -CLASS A,COIN,19260Q107,\"200,000\",\"$60,000,000.00\",4.00%\n", "") + \
    '11/13/2026,ARKK,CIRCLE INTERNET GROUP INC,CRCL,172573107,"300,000","$30,000,000.00",2.00%\n'


def test_parse():
    d, h = parse(CSV1)
    assert d == "2026-11-12" and h["TSLA"]["sh"] == 1_000_000 and h["TSLA"]["w"] == 10.5 and "MSGXX" in h


def test_diff_moves():
    _, a = parse(CSV1); d, b = parse(CSV2)
    m = {x["t"]: x for x in diff("ARKK", d, b, a)}
    assert "TSLA" not in m                                  # +0,5 % = Fondszufluss, kein Kauf
    assert m["ROKU"]["a"] == "ab" and m["ROKU"]["chg"] == -0.16 and m["COIN"]["a"] == "raus" and m["CRCL"]["a"] == "neu"


def test_update_collects_and_keeps_state():
    pages = {"ARKK": CSV1}
    st, h = update({}, [], fetch=lambda f: pages.get(f, ""), today="2026-11-14")
    assert st["ARKK"]["d"] == "2026-11-12" and h == []
    pages["ARKK"] = CSV2
    st, h = update(st, h, fetch=lambda f: pages.get(f, ""), today="2026-11-14")
    assert st["ARKK"]["d"] == "2026-11-13" and {x["t"] for x in h} == {"ROKU", "COIN", "CRCL"}
    st2, h2 = update(st, h, fetch=lambda f: pages.get(f, ""), today="2026-11-14")   # gleicher Tag nochmal: nichts doppelt
    assert len(h2) == 3 and set(FUNDS) >= {"ARKK"}
