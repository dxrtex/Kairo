import pandas as pd

from backend import earnings as E

RSS_DATE = "Tue, 20 Oct 2026 20:13:00 GMT"
REPORT = pd.Timestamp("2026-10-20 16:00:00-04:00")


def test_guidance_lowered_from_real_headlines():
    items = [("Here's what to expect when Netflix reports earnings after the bell - CNBC", "u0", "Tue, 20 Oct 2026 16:00:01 GMT"),
             ("Netflix Stock Falls Despite Solid Q3 Results On Lowered Q4 Revenue And Advertising Guidance - Deadline", "u1", RSS_DATE),
             ("Netflix Q3 Highlights: Shares Slide As Earnings Beat Overshadowed by Weak Q4 Guidance - Benzinga", "u2", RSS_DATE),
             ("Netflix earnings outlook: tone and guidance matter more than the beat - Investing.com", "u3", "Mon, 19 Oct 2026 19:36:13 GMT")]
    g = E.guidance(items, ["Netflix", "NFLX"], REPORT)
    assert g["d"] == -1 and g["n"] == 2 and g["u"] == "u1"


def test_guidance_raised_and_confirmed():
    up = [("JPMorgan Chase Raises Full-Year Net Interest Income Outlook Despite Missing Q3 Revenue Expectations - TIKR.com", "u", RSS_DATE)]
    assert E.guidance(up, ["JPMorgan", "JPM"])["d"] == 1
    keep = [("SAP bestätigt Prognose für 2026 - Handelsblatt", "u", RSS_DATE)]
    assert E.guidance(keep, ["SAP"])["d"] == 0


def test_guidance_ignores_other_companies_and_previews():
    other = [("Applied Materials slides as Q3 results, guidance top/miss estimates - Seeking Alpha", "u", RSS_DATE),
             ("Microsoft raises outlook - X", "u", RSS_DATE),
             ("Martin Gamble on US markets: ASML slips, TSMC’s weak outlook - AJ Bell", "u", RSS_DATE)]
    assert E.guidance(other, ["ASML"]) is None
    preview = [("Netflix expected to raise guidance - X", "u", "Mon, 19 Oct 2026 10:00:00 GMT")]
    assert E.guidance(preview, ["Netflix"], REPORT) is None


def test_assess_guidance_counts_double():
    v = E.assess(0.02, None, -1)                   # Gewinn im Rahmen, Ausblick gesenkt
    assert v["lbl"] == "eher negativ" and v["tone"] == "red"
    v = E.assess(0.10, 0.02, None)                  # Gewinn und Umsatz klar darüber
    assert v["lbl"] == "eher positiv"
    v = E.assess(0.10, -0.02, None)
    assert v["lbl"] == "gemischt"
    assert E.assess(None, None, None) is None


def _closes(tz="America/New_York"):
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"])).tz_localize(tz)
    return pd.Series([100.0, 101.0, 100.0, 92.0, 94.0], index=idx)


def test_reaction_after_close_counts_next_day():
    r = E.reaction(_closes(), REPORT)               # 16:00 Uhr → Reaktion am 21.10., Basis Schluss 20.10.
    assert r["day"] == "2026-10-21" and r["d1"] == -0.08 and r["since"] == -0.06


def test_reaction_before_open_counts_same_day():
    r = E.reaction(_closes(), pd.Timestamp("2026-10-20 06:00:00-04:00"))
    assert r["day"] == "2026-10-20" and r["d1"] == round(100 / 101 - 1, 4)


def test_reaction_european_listing_converts_timezone():
    # ASML meldet um 01:00 New York = 07:00 Amsterdam, also vor Börsenstart am selben Tag
    c = _closes("Europe/Amsterdam")
    r = E.reaction(c, pd.Timestamp("2026-10-20 01:00:00-04:00"))
    assert r["day"] == "2026-10-20"


def test_reaction_not_yet_traded():
    c = _closes()
    assert E.reaction(c, pd.Timestamp("2026-10-22 16:30:00-04:00")) is None


def test_typical_move_needs_three_reports():
    c = _closes()
    assert E.typical_move(c, [REPORT]) is None


def test_guidance_company_after_phrase():
    items = [("Upbeat outlook sends GM shares higher - Reuters", "u", RSS_DATE),
             ("General Motors Profit Outlook Disappoints, Stock Sinks - Benzinga", "u2", RSS_DATE)]
    assert E.guidance(items[:1], ["GM"])["d"] == 1
    assert E.guidance(items[1:], ["General", "GM"])["d"] == -1


def test_guidance_ignores_analyst_targets():
    items = [("JPMorgan trims target for General Motors stock from USD 120 to USD 110 - ad-hoc-news.de", "u", RSS_DATE),
             ("Goldman raises Netflix price target, sees stronger outlook - X", "u", RSS_DATE)]
    assert E.guidance(items[:1], ["JPMorgan", "JPM"]) is None
    assert E.guidance(items[1:], ["Netflix"]) is None


def test_guidance_ignores_stock_forecast_articles():
    items = [("General Motors Stock Forecast: GM Coils Below $85.23 as Q3 Earnings Test a Third Guidance - FXEmpire", "u", RSS_DATE)]
    assert E.guidance(items, ["General", "GM"]) is None


class _TK:
    def __init__(self, eh): self._eh = eh
    def get_earnings_history(self): return self._eh


def test_history_fallback_fills_missing_fresh_report():
    # Netflix: Termin 20.10. fehlt in get_earnings_dates, Historie hat das Quartal 30.09. schon
    idx = pd.DatetimeIndex([pd.Timestamp("2026-07-16 16:00", tz="America/New_York"), pd.Timestamp("2026-04-16 16:00", tz="America/New_York")])
    rep = pd.DataFrame({"EPS Estimate": [0.79, 1.25], "Reported EPS": [0.80, 1.23]}, index=idx)
    eh = pd.DataFrame({"epsActual": [0.80, 0.87], "epsEstimate": [0.78858, 0.82268]}, index=pd.to_datetime(["2026-06-30", "2026-09-30"]))
    syn = E._from_history(_TK(eh), {"date": "2026-10-20"}, rep, pd.Timestamp("2026-10-21"))
    assert syn is not None and syn.index[0].hour == 16 and str(syn.index[0].date()) == "2026-10-20"
    assert syn.iloc[0]["Reported EPS"] == 0.87
    # Terminliste schon aktuell → kein Ersatz
    rep2 = pd.concat([pd.DataFrame({"EPS Estimate": [0.82], "Reported EPS": [0.87]}, index=pd.DatetimeIndex([pd.Timestamp("2026-10-20 16:00", tz="America/New_York")])), rep])
    assert E._from_history(_TK(eh), {"date": "2026-10-20"}, rep2, pd.Timestamp("2026-10-21")) is None
    # Termin in der Zukunft → kein Ersatz
    assert E._from_history(_TK(eh), {"date": "2026-10-28"}, rep, pd.Timestamp("2026-10-21")) is None
