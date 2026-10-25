"""Formular 4: Käufe/Verkäufe über die Börse erkennen, Teil-Geschäfte zusammenfassen."""

from backend.insider import _merge, parse_form4

XML = """<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerCik>1</issuerCik><issuerName>Axon Enterprise, Inc.</issuerName><issuerTradingSymbol>axon</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>SMITH PATRICK W</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-10-08</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>1000</value></transactionShares><transactionPricePerShare><value>400.5</value></transactionPricePerShare></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-10-08</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>5000</value></transactionShares><transactionPricePerShare><value>10</value></transactionPricePerShare></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_purchase_only_open_market():
    rows = parse_form4(XML)
    assert len(rows) == 1
    r = rows[0]
    assert r["t"] == "AXON" and r["kind"] == "buy" and r["role"] == "CEO" and r["val"] == 400500 and r["who"] == "Smith Patrick W"


def test_bad_xml_and_merge():
    assert parse_form4("<nope") == []
    a = {"t": "X", "who": "A", "kind": "buy", "d": "2026-10-08", "sh": 100, "px": 10.0, "val": 1000}
    m = _merge([a, dict(a, sh=100, px=12.0, val=1200)])
    assert len(m) == 1 and m[0]["val"] == 2200 and m[0]["px"] == 11.0


OI_HTML = """<table width="100%" cellpadding="0" cellspacing="0" border="0" class="tinytable">
<thead><tr><th>X</th><th>Filing&nbsp;Date</th><th>Trade&nbsp;Date</th><th>Ticker</th><th>Company&nbsp;Name</th><th>Insider&nbsp;Name</th>
<th>Title</th><th>Trade&nbsp;Type</th><th>Price</th><th>Qty</th><th>Owned</th><th>&Delta;Own</th><th>Value</th></tr></thead>
<tbody><tr><td>M</td><td><div><a href="x">2026-10-09 16:05:11</a></div></td><td><div>2026-10-08</div></td><td><b><a href="/AXON" onmouseover="Tip('<img src=\'x.png\'>', DELAY, 1)" ONMOUSEOUT="UnTip()">AXON</a></b></td>
<td><a href="/AXON">Axon Enterprise, Inc.</a></td><td><a href="/insider/x">Smith Patrick W</a></td><td>CEO, Dir</td><td>P - Purchase</td>
<td>$400.50</td><td>+1,000</td><td>10,000</td><td>+11%</td><td>+$400,500</td></tr>
<tr><td></td><td>2026-10-09</td><td>2026-10-07</td><td>NVDA</td><td>Nvidia</td><td>Huang Jen</td><td>CEO</td><td>S - Sale+OE</td>
<td>$180.00</td><td>-100,000</td><td>1</td><td>-1%</td><td>-$18,000,000</td></tr></tbody></table>"""


def test_openinsider_table():
    from backend.insider import parse_openinsider
    rows = parse_openinsider(OI_HTML)
    assert [r["kind"] for r in rows] == ["buy", "sell"]
    a = rows[0]
    assert a["t"] == "AXON" and a["who"] == "Smith Patrick W" and a["role"] == "CEO, Dir" and a["val"] == 400500 and a["px"] == 400.5 and a["sh"] == 1000 and a["d"] == "2026-10-08"
    assert rows[1]["val"] == 18000000 and parse_openinsider("<html></html>") == []


def test_routine_vs_opportunistic_and_signal():
    from backend.insider import routine, signal, _days_ago
    d0 = _days_ago(5)
    y, m = int(d0[:4]), d0[5:7]
    rows = [{"t": "X", "who": "Plan", "kind": "buy", "d": f"{y - k}-{m}-10", "val": 50_000, "role": "Dir"} for k in (1, 2)]
    rows += [{"t": "X", "who": "Plan", "kind": "buy", "d": d0, "val": 60_000, "role": "Dir"},
             {"t": "X", "who": "Boss", "kind": "buy", "d": d0, "val": 2_000_000, "role": "CEO", "own": 12}]
    routine(rows)
    assert rows[2]["opp"] is False and rows[3]["opp"] is True
    s = signal(rows)["X"]
    assert s["buyers"] == 2 and s["top"] and s["opp"] == 1 and s["score"] == 3


def test_openinsider_delta_own():
    from backend.insider import parse_openinsider
    page = ('<table class="tinytable"><tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Insider Name</th><th>Title</th>'
            '<th>Trade Type</th><th>Price</th><th>Qty</th><th>Owned</th><th>&Delta;Own</th><th>Value</th></tr>'
            '<tr><td></td><td>2026-10-20</td><td>2026-10-18</td><td>PLTR</td><td>Karp</td><td>CEO</td><td>P - Purchase</td>'
            '<td>$100.00</td><td>+1,000</td><td>11,000</td><td>+10%</td><td>+$100,000</td></tr></table>')
    r = parse_openinsider(page)[0]
    assert r["own"] == 10 and r["kind"] == "buy" and r["val"] == 100000
