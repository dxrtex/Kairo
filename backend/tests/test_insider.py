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
