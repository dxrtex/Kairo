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
    xs = s["x"]                                   # Einzelkäufe für die Detailansicht (nur 90 Tage, neueste zuerst)
    assert len(xs) == 2 and {x["who"] for x in xs} == {"Plan", "Boss"}
    boss = next(x for x in xs if x["who"] == "Boss")
    assert boss["opp"] is True and boss["own"] == 12 and boss["role"] == "CEO" and boss["val"] == 2_000_000


def test_openinsider_delta_own():
    from backend.insider import parse_openinsider
    page = ('<table class="tinytable"><tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Insider Name</th><th>Title</th>'
            '<th>Trade Type</th><th>Price</th><th>Qty</th><th>Owned</th><th>&Delta;Own</th><th>Value</th></tr>'
            '<tr><td></td><td>2026-10-20</td><td>2026-10-18</td><td>PLTR</td><td>Karp</td><td>CEO</td><td>P - Purchase</td>'
            '<td>$100.00</td><td>+1,000</td><td>11,000</td><td>+10%</td><td>+$100,000</td></tr></table>')
    r = parse_openinsider(page)[0]
    assert r["own"] == 10 and r["kind"] == "buy" and r["val"] == 100000


def test_filing_date_unknown_routine_and_cover():
    """Meldedatum wird gelesen; Käufe ohne Kaufhistorie (BaFin) zählen nicht als gezielt; Abdeckung je Aktie."""
    from backend import insider as I
    page = ('<table class="tinytable"><tr><th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Insider Name</th><th>Title</th>'
            '<th>Trade Type</th><th>Price</th><th>Qty</th><th>Owned</th><th>&Delta;Own</th><th>Value</th></tr>'
            '<tr><td></td><td>2026-10-20 18:01:02</td><td>2026-10-18</td><td>PLTR</td><td>Karp</td><td>CEO</td><td>P - Purchase</td>'
            '<td>$100.00</td><td>+1,000</td><td>11,000</td><td>+10%</td><td>+$100,000</td></tr></table>')
    assert I.parse_openinsider(page)[0]["fd"] == "2026-10-20"
    d0 = I._days_ago(3)
    de = [{"t": "SAP.DE", "who": "A", "kind": "buy", "d": d0, "val": 2_000_000, "role": "Dir", "cur": "EUR", "own": 50}]
    assert I.signal(de)["SAP.DE"]["score"] == 0 and I.signal(de)["SAP.DE"]["unk"] == 1
    I.COVER.clear(); I.COVER.update({"AAPL": "ok", "MSFT": "zeitlimit"})
    c = I.cover({"AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "SAP.DE": "SAP", "NOVO-B.CO": "Novo", "ASML.AS": "ASML"},
                {"watch": de}, {"AS"})
    assert c["AAPL"]["st"] == "ok" and c["MSFT"]["st"] == "zeitlimit" and c["NVDA"]["st"] == "nicht geprüft"
    assert c["SAP.DE"] == {"st": "ok", "src": "BaFin", "hit": True}
    assert c["NOVO-B.CO"]["st"] == "ok" and c["ASML.AS"]["st"] == "fehler"


XML_PLAN = XML.replace("<nonDerivativeTable>", "<aff10b5One>1</aff10b5One><nonDerivativeTable>", 1).replace(
    "<transactionPricePerShare><value>400.5</value></transactionPricePerShare></transactionAmounts>",
    "<transactionPricePerShare><value>400.5</value></transactionPricePerShare></transactionAmounts>"
    "<postTransactionAmounts><sharesOwnedFollowingTransaction><value>11000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>", 1)


def test_plan_flag_and_ownership_change():
    r = parse_form4(XML_PLAN)[0]
    assert r["plan"] is True and r["after"] == 11000 and r["own"] == 10          # 10.000 → 11.000 Aktien = +10 %
    assert "plan" not in parse_form4(XML)[0] and "own" not in parse_form4(XML)[0]


def test_merge_ownership_over_partial_fills():
    a = {"t": "X", "who": "A", "kind": "buy", "d": "2026-10-08", "sh": 100, "px": 10.0, "val": 1000, "after": 1100, "own": 10}
    m = _merge([a, dict(a, sh=100, val=1000, after=1200, own=9)])[0]
    assert m["after"] == 1200 and m["own"] == 20                                    # 1.000 vorher → 1.200 nachher
    n = _merge([dict(a, after=100, own="neu"), dict(a, after=200, own=100)])[0]
    assert n["own"] == "neu"


def test_combine_sources_enriches_openinsider():
    from backend.insider import combine_sources
    oi = [{"t": "X", "who": "Smith Patrick W", "kind": "sell", "d": "2026-10-08", "val": 5e6}]
    sec = [{"t": "X", "who": "Smith Patrick W", "kind": "sell", "d": "2026-10-08", "val": 5e6, "plan": True, "after": 900, "own": -10},
           {"t": "Y", "who": "Doe Jane", "kind": "buy", "d": "2026-10-09", "val": 1e5}]
    rows, src = combine_sources(sec, oi)
    assert len(rows) == 2 and rows[0]["plan"] is True and rows[0]["own"] == -10 and "SEC" in src
    assert combine_sources([], oi)[0] == oi and combine_sources(sec, [])[0] == sec
