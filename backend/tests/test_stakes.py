"""13D/13G: Atom-Feed lesen, Subject/Filer paaren, passive Großanleger bei 13G ausblenden, Verlauf sammeln."""
from backend.stakes import accumulate, pair, parse_feed

FEED = """<?xml version="1.0" encoding="ISO-8859-1" ?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>SCHEDULE 13D - Example Corp (0000000123) (Subject)</title>
 <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/123/000095017026000001/0000950170-26-000001-index.htm"/>
 <updated>2026-11-13T16:30:00-04:00</updated></entry>
<entry><title>SCHEDULE 13D - ELLIOTT INVESTMENT MANAGEMENT L.P. (0001791786) (Filed by)</title>
 <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1791786/000095017026000001/0000950170-26-000001-index.htm"/>
 <updated>2026-11-13T16:30:00-04:00</updated></entry>
<entry><title>SCHEDULE 13G/A - Example Corp (0000000123) (Subject)</title>
 <link href="/Archives/edgar/data/123/000110465926000002/0001104659-26-000002-index.htm"/><updated>2026-11-12T10:00:00-04:00</updated></entry>
<entry><title>SCHEDULE 13G/A - VANGUARD GROUP INC (0000102909) (Filed by)</title>
 <link href="/Archives/edgar/data/102909/000110465926000002/0001104659-26-000002-index.htm"/><updated>2026-11-12T10:00:00-04:00</updated></entry>
<entry><title>SC 13G - Other Inc (0000000456) (Subject)</title>
 <link href="/Archives/edgar/data/456/000110465926000003/0001104659-26-000003-index.htm"/><updated>2026-11-11T10:00:00-04:00</updated></entry>
<entry><title>SC 13G - Situational Awareness LP (0002011111) (Filed by)</title>
 <link href="/Archives/edgar/data/2011111/000110465926000003/0001104659-26-000003-index.htm"/><updated>2026-11-11T10:00:00-04:00</updated></entry>
</feed>"""


def test_parse_and_pair():
    e = parse_feed(FEED)
    assert len(e) == 6 and e[0]["role"] == "subject" and e[1]["role"] == "filer" and e[0]["d"] == "2026-11-13"
    out = pair(e, {123: "EXMP", 456: "OTHR"})
    assert [x["t"] for x in out] == ["EXMP", "OTHR"]                        # Vanguard-13G/A ausgeblendet
    a = out[0]
    assert a["act"] and a["form"] == "13D" and a["f"] == "Elliott Investment Management L.P." and a["url"].startswith("https://")
    assert out[1]["form"] == "13G" and not out[1]["act"]


def test_pair_needs_ticker_and_accumulate():
    assert pair(parse_feed(FEED), {}) == []
    old = [{"acc": "a", "d": "2026-06-01"}, {"acc": "b", "d": "2026-11-01"}]
    got = accumulate(old, [{"acc": "b", "d": "2026-11-01"}, {"acc": "c", "d": "2026-11-10"}], days=120, today="2026-11-14")
    assert [x["acc"] for x in got] == ["c", "b"]
