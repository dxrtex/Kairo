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
