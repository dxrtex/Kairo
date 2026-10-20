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
             ("Microsoft raises outlook - X", "u", RSS_DATE)]
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
