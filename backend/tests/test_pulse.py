import json

import pandas as pd

from backend.pulse import market, poly, social, worldbank


def test_social():
    s = social([{"ticker": "nvda", "name": "NVIDIA &amp; Co", "mentions": "50", "mentions_24h_ago": 20, "rank": 1, "rank_24h_ago": 3}, {"ticker": "X", "mentions": 0}, {"bad": 1}])
    assert s == [{"t": "NVDA", "n": "NVIDIA & Co", "m": 50, "m0": 20, "r": 1, "r0": 3}]


def test_poly_filters_and_parses():
    ev = [{"title": "Fed decision in December?", "slug": "fed-dec", "volume": 1e6, "volume24hr": 5e4, "endDate": "2026-12-10T00:00:00Z",
           "markets": [{"groupItemTitle": "25 bps cut", "outcomes": json.dumps(["Yes", "No"]), "outcomePrices": json.dumps(["0.7", "0.3"])},
                       {"groupItemTitle": "No change", "outcomes": json.dumps(["Yes", "No"]), "outcomePrices": json.dumps(["0.25", "0.75"])}]},
          {"title": "Who wins the football final?", "markets": [{"outcomes": "[\"A\",\"B\"]", "outcomePrices": "[\"0.5\",\"0.5\"]"}]},
          {"title": "Recession in 2026?", "slug": "rec", "volume24hr": 9e4, "markets": [{"outcomes": "[\"Yes\",\"No\"]", "outcomePrices": "[\"0.2\",\"0.8\"]"}]}]
    p = poly(ev)
    assert [x["q"] for x in p] == ["Recession in 2026?", "Fed decision in December?"]
    assert p[1]["o"][0] == ["25 bps cut", 0.7] and p[0]["o"][0] == ["No", 0.8]


def test_market_and_worldbank():
    idx = pd.bdate_range("2025-01-01", periods=300)
    df = pd.DataFrame({"Close": [100.0 + i for i in range(300)]}, index=idx)
    m = market({"GC=F": df})
    assert m["GC=F"]["n"] == "Gold" and m["GC=F"]["c"] == 399.0 and len(m["GC=F"]["s"]) == 260 and m["GC=F"]["d1"] > 0
    wb = worldbank({"g": [{"country": {"id": "DE", "value": "Germany"}, "countryiso3code": "DEU", "value": 0.31, "date": "2025"},
                          {"country": {"id": "1W", "value": "World"}, "countryiso3code": "WLD", "value": 2.7, "date": "2025"},
                          {"country": {"id": "XX", "value": "Agg"}, "countryiso3code": "", "value": 1, "date": "2025"}],
                    "i": [{"country": {"id": "DE", "value": "Germany"}, "countryiso3code": "DEU", "value": 2.25, "date": "2025"}]})
    assert set(wb) == {"DE"} and wb["DE"]["g"] == 0.31 and wb["DE"]["i"] == 2.25


def test_worldbank_valid_filter():
    wb = worldbank({"g": [{"country": {"id": "EU", "value": "European Union"}, "countryiso3code": "EUU", "value": 1, "date": "2025"},
                          {"country": {"id": "FR", "value": "France"}, "countryiso3code": "FRA", "value": 0.8, "date": "2025"}]}, {"FR": "Europe & Central Asia"})
    assert list(wb) == ["FR"] and wb["FR"]["r"] == "Europe & Central Asia"


def test_poly_skips_placeholders_and_old_worldbank():
    ev = [{"title": "Next CEO of NVIDIA?", "slug": "c", "volume24hr": 1, "markets": [{"groupItemTitle": "Candidate T", "outcomes": "[\"Yes\",\"No\"]", "outcomePrices": "[\"0.5\",\"0.5\"]"}]},
          {"title": "Fed cut?", "slug": "f", "volume24hr": 1, "markets": [{"groupItemTitle": "A", "outcomes": "[\"Yes\",\"No\"]", "outcomePrices": "[\"0.5\",\"0.5\"]"}, {"groupItemTitle": "B", "outcomes": "[\"Yes\",\"No\"]", "outcomePrices": "[\"0.4\",\"0.6\"]"}]}]
    p = poly(ev)
    assert [x["q"] for x in p] == ["Fed cut?"] and p[0]["o"] == [["B", 0.4]]
    wb = worldbank({"d": [{"country": {"id": "DE", "value": "Germany"}, "countryiso3code": "DEU", "value": 20.8, "date": "1990"}],
                    "g": [{"country": {"id": "DE", "value": "Germany"}, "countryiso3code": "DEU", "value": 0.2, "date": "2025"}]})
    assert "d" not in wb["DE"] and wb["DE"]["g"] == 0.2


def test_eonet_parses_latest_point_and_kind():
    from backend.pulse import eonet
    ev = [{"title": "Fire A", "categories": [{"id": "wildfires"}], "sources": [{"url": "https://x"}],
           "geometry": [{"type": "Point", "date": "2026-11-10T00:00:00Z", "coordinates": [10.0, 50.0]},
                        {"type": "Point", "date": "2026-11-12T00:00:00Z", "coordinates": [10.5, 50.5]}]},
          {"title": "Storm", "categories": [{"id": "severeStorms"}], "geometry": [{"type": "Point", "date": "2026-11-15", "coordinates": [-80, 25]}]},
          {"title": "Iceberg", "categories": [{"id": "unknown"}], "geometry": [{"type": "Point", "date": "2026-11-15", "coordinates": [0, 0]}]},
          {"title": "Polygon", "categories": [{"id": "floods"}], "geometry": [{"type": "Polygon", "coordinates": [[[0, 0]]]}]}]
    out = eonet(ev)
    assert [x[0] for x in out] == ["storm", "fire"] and out[1][2:5] == [10.5, 50.5, "2026-11-12"] and out[1][5] == "https://x"


def test_weekly_skips_factors():
    import pandas as pd
    from backend.pulse import weekly
    idx = pd.date_range("2022-01-07", periods=30, freq="W-FRI")
    df = pd.DataFrame({"Close": range(1, 31)}, index=idx)
    w = weekly({"GC=F": df, "SPY": df})
    assert "GC=F" in w and "SPY" not in w and w["GC=F"][-1] == [idx[-1].strftime("%Y-%m-%d"), 30.0]
