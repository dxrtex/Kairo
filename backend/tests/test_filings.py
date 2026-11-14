"""8-K: Feed lesen, auf eigene Aktien filtern, Items übersetzen."""
from backend.filings import accumulate, parse_feed

FEED = """<feed>
<entry><title>8-K - APPLE INC (0000320193) (Filer)</title>
 <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/320193/000032019326000100/0000320193-26-000100-index.htm"/>
 <summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-11-13 &lt;b&gt;AccNo:&lt;/b&gt; 0000320193-26-000100 &lt;b&gt;Size:&lt;/b&gt; 2 MB
 &lt;br&gt;Item 2.02: Results of Operations and Financial Condition
 &lt;br&gt;Item 9.01: Financial Statements and Exhibits</summary>
 <updated>2026-11-13T16:05:00-04:00</updated></entry>
<entry><title>8-K - OTHER CORP (0000000999) (Filer)</title>
 <link href="/Archives/edgar/data/999/000000099926000001/0000000999-26-000001-index.htm"/>
 <summary type="html">Item 5.02: Departure of Directors</summary><updated>2026-11-13T10:00:00-04:00</updated></entry>
<entry><title>8-K - NVIDIA CORP (0001045810) (Filer)</title>
 <link href="/Archives/edgar/data/1045810/000104581026000009/0001045810-26-000009-index.htm"/>
 <summary type="html">Item 9.01: Financial Statements and Exhibits</summary><updated>2026-11-12T10:00:00-04:00</updated></entry>
</feed>"""
CIK = {320193: "AAPL", 999: "OTHR", 1045810: "NVDA"}


def test_parse_filters_and_translates():
    out = parse_feed(FEED, CIK, {"AAPL", "NVDA"})
    assert len(out) == 1                                     # OTHR nicht gesucht, NVDA nur Anlagen (9.01)
    x = out[0]
    assert x["t"] == "AAPL" and x["d"] == "2026-11-13" and x["items"] == [["2.02", "Quartalszahlen", 1]] and x["w"] == 1
    assert x["n"] == "Apple Inc" and x["url"].startswith("https://www.sec.gov/")


def test_accumulate():
    got = accumulate([{"acc": "a", "d": "2026-08-01"}], [{"acc": "b", "d": "2026-11-13"}], days=60, today="2026-11-14")
    assert [x["acc"] for x in got] == ["b"]
