from backend import secguide as S


def test_spanne_quartal_gegen_erwartung():
    t = S.text_of("<p>Fourth Quarter 2026 Outlook</p><p>Amazon expects net sales to be between $206.0 billion and $213.0 billion in the fourth quarter.</p>")
    g = S.parse(t)
    assert g["q"] and g["lo"] == 206e9 and g["hi"] == 213e9
    assert S.judge(g, 205e9, None)["d"] == 1          # Mitte 209,5 vs. 205 → über Erwartung
    assert S.judge(g, 212e9, None)["d"] == -1
    assert S.judge(g, 209e9, None)["d"] == 0


def test_ausgaben_zaehlen_nicht():
    t = "We expect capital expenditures of $70 billion to $72 billion in 2026. Revenue grew 26%."
    assert S.parse(t) is None


def test_verb_ohne_zahlen():
    g = S.parse("The company raised its full-year outlook for revenue and earnings.")
    assert S.judge(g, None, None)["d"] == 1


def test_ohne_secret_aus(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT", raising=False)
    assert S.fetch(320193, "2026-01-01") is None


def test_ergebnis_aus_pressemitteilung():
    t = S.text_of("<p>Apple reported quarterly revenue of $102.5 billion, up 8 percent year over year, and quarterly diluted earnings per share of $1.85.</p>")
    r = S.results(t)
    assert r["rev"] == 102.5e9 and r["eps"] == 1.85 and r["eps_kind"] == "GAAP"
    t2 = "GAAP diluted EPS was $0.25. Non-GAAP diluted EPS was $0.62. Revenue was $13.7 billion. Fourth-quarter revenue is expected to be between $13.0 billion and $14.0 billion."
    r2 = S.results(t2)
    assert r2["eps"] == 0.62 and r2["eps_kind"] == "bereinigt" and r2["rev"] == 13.7e9
    assert S.parse(t2)["mid"] == 13.5e9
