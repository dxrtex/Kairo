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


def test_echte_formulierungen_29_10():
    pbf = ("PBF Energy Announces Third Quarter 2026 Results, Declares Dividend of $0.325 per Share. The company reported third quarter 2026 "
           "net income of $1,543.3 million and net income attributable to PBF Energy Inc. of $1,529.3 million or $12.54 per share. "
           "Adjusted fully-converted net income for the third quarter 2026, excluding special items, was $1,568.6 million, or $12.78 per share on a fully-exchanged, fully-diluted basis.")
    r = S.results(pbf)
    assert r["eps"] == 12.78 and r["eps_kind"] == "bereinigt"
    drs = "Net Earnings: $115 million, up 60% year-over-year • Diluted EPS: $0.43, up 65% • Adjusted Diluted EPS: $0.46, up 59% year-over-year"
    assert S.results(drs)["eps"] == 0.46


def test_sonderbelastung_ist_kein_gewinn():
    # Lilly 29.10.: „non-GAAP EPS included $4.57 of acquired IPR&D charges“ stand vor dem echten Wert 7.48
    lly = ("Q3 2026 EPS increased by 16% to $7.22 on a reported basis and increased by 7% to $7.48 on a non-GAAP basis. "
           "Q3 2026 reported and non-GAAP EPS included $4.57 of acquired IPR&#38;D charges compared to $0.71 in Q3 2025. "
           "Financial Results $ in millions, except per share data Third-Quarter 2026 2025 % Change Revenue $ 24,397 $ 17,601 39% "
           "Net income – Reported 6,451 5,583 16% Earnings per share – Reported (1) 7.22 6.21 16% Net income – Non-GAAP 6,679 6,312 6% "
           "Earnings per share – Non-GAAP (1) 7.48 7.02 7%")
    r = S.results(lly)
    assert r["eps"] == 7.48 and r["eps_kind"] == "bereinigt"
    spec = ("Non-cash special items decreased net income by a net, after-tax charge of $28.9 million, or $0.24 per share. "
            "Net income attributable to the company was $1,529.3 million or $12.54 per share.")
    assert S.results(spec)["eps"] == 12.54


def test_verlust_und_klammerformat():
    insm = ("For the third quarter of 2026, Insmed reported a net loss of $100.3 million, or $0.46 per share, compared to a net loss "
            "of $370.0 million, or $1.75 per share, for the third quarter of 2025.")
    assert S.results(insm)["eps"] == -0.46
    indv = ("GAAP net income for the 2026 quarter was $137 million ($1.12 diluted earnings per share), compared to GAAP net income for the 2025 "
            "quarter of $42 million ($0.33 diluted earnings per share). Non-GAAP net income for the 2026 quarter was $161 million "
            "($1.32 diluted earnings per share), compared to non-GAAP net income for the 2025 quarter of $93 million ($0.72 diluted earnings per share).")
    r = S.results(indv)
    assert r["eps"] == 1.32 and r["eps_kind"] == "bereinigt"


def test_ausblick_segment_wird_nicht_verglichen():
    g = S.parse("Company Raises 2026 BRINSUPRI Revenue Guidance to $1.35 Billion to $1.4 Billion.")
    j = S.judge(g, None, 2.2e9)                            # Firmenumsatz-Erwartung 2,2 Mrd. – Spanne ist ein Produkt
    assert j["d"] == 1 and "vs" not in j                   # nur „angehoben“ aus dem Verb, kein Zahlenvergleich


def test_jahresausblick_ist_kein_quartal():
    g = S.parse("Increased the midpoint of our 2026 full-year revenue guidance by $5.5 billion to be in the range of $91.0 to $92.0 billion in the third quarter update.")
    assert g["q"] is False and g["mid"] == 91.5e9


def test_6k_nur_mit_ergebniszahlen():
    """Review W8: Ein 6-K ist nicht immer eine Ergebnis-Meldung."""
    agm = "Notice of Annual General Meeting. The board of directors resolved to convene the meeting on June 5. Voting instructions follow."
    res = ("Third Quarter 2026 Results. Revenues of US$ 24.1 billion, net income of US$ 9.8 billion, "
           "earnings per share of US$ 1.85 for the quarter.")
    assert not S.is_results(agm) and S.is_results(res)
