from backend import insider_eu as eu

FI_CSV = ("Publiceringsdatum;Emittent;LEI-kod;Person i ledande ställning;Befattning;Närstående;Korrigering;Beskrivning av korrigering;"
          "Är förstagångsrapportering;Är kopplad till aktieprogram;Karaktär;Instrumenttyp;Instrumentnamn;ISIN;Transaktionsdatum;"
          "Volym;Volymsenhet;Pris;Valuta;Handelsplats;Status\n"
          "2026-11-02 08:00:00;AB Volvo;X;Martin Lundstedt;Verkställande direktör (VD);Nej;Nej;;Nej;Nej;Förvärv;Aktie;Volvo B;SE0000115446;"
          "2026-10-31 00:00:00;10 000;Antal;250,5;SEK;XSTO;Aktuell\n"
          "2026-11-02 08:00:00;AB Volvo;X;Anna A;Styrelseledamot;Nej;Nej;;Nej;Ja;Tilldelning;Aktie;Volvo B;SE0000115446;"
          "2026-10-31 00:00:00;500;Antal;0;SEK;;Aktuell\n")


def test_parse_fi_buy_and_skip_programs():
    rows = eu.parse_fi(FI_CSV)
    assert len(rows) == 1 and rows[0]["kind"] == "buy" and rows[0]["d"] == "2026-10-31"
    assert rows[0]["val"] == round(10000 * 250.5 * eu.EUR["SEK"]) and rows[0]["who"] == "Martin Lundstedt"


def test_parse_six():
    rows = eu.parse_six([{"buySellIndicator": "1", "transactionDate": 20261102, "transactionAmountCHF": 100000.0, "ISIN": "CH0038863350",
                          "obligorFunctionCode": "1", "correcteeId": ""},
                         {"buySellIndicator": "2", "transactionDate": 20261101, "transactionAmountCHF": 5.0, "ISIN": "X", "correcteeId": "A1"}])
    assert len(rows) == 1 and rows[0]["kind"] == "buy" and rows[0]["d"] == "2026-11-02" and rows[0]["role"] == "Geschäftsleitung"


def test_match_figi_then_name():
    uni = {"VOLV-B.ST": "AB Volvo (publ)", "ERIC-B.ST": "Telefonaktiebolaget LM Ericsson (publ)"}
    by_key, by_name = eu._index(uni, ".ST")
    assert eu._match("SE1", "", uni, {"SE1": ["VOLVB"]}, by_key, by_name) == "VOLV-B.ST"
    assert eu._match("SE2", "Telefonaktiebolaget LM Ericsson", uni, {}, by_key, by_name) == "ERIC-B.ST"
    assert eu._match("SE3", "Okänd", uni, {}, by_key, by_name) is None


def test_net_rows_and_exact_name():
    rows = [{"t": "A.ST", "who": "P", "d": "2026-10-01", "kind": "buy", "val": 100_000},
            {"t": "A.ST", "who": "P", "d": "2026-10-01", "kind": "sell", "val": 90_000},
            {"t": "A.ST", "who": "Q", "d": "2026-10-01", "kind": "sell", "val": 50_000}]
    out = {x["who"]: x for x in eu.net_rows(rows)}
    assert out["P"]["kind"] == "buy" and out["P"]["val"] == 10_000 and out["Q"]["kind"] == "sell"
    uni = {"VOLV-B.ST": "AB Volvo (publ)"}
    by_key, by_name = eu._index(uni, ".ST")
    assert eu._match("X", "Volvo Car AB", uni, {}, by_key, by_name) is None


def test_parse_fi_skips_related_company():
    csv_ = FI_CSV.replace("X;Martin Lundstedt;", "X;Lundstedt Invest AB;Martin Lundstedt;", 1).replace("LEI-kod;Person", "LEI-kod;Anmälningsskyldig;Person", 1)
    assert eu.parse_fi(csv_) == []


def test_nnum_formats():
    assert eu._nnum("1,234,567.89") == 1234567.89 and eu._nnum("1.234.567,89") == 1234567.89 and eu._nnum("1 234") == 1234 and eu._nnum("12,5") == 12.5


def test_parse_mar():
    txt = ("a) Name Jane Doe Reason for the notification Position/status CEO b) Initial notification ... Nature of the transaction Acquisition "
           "c) Price(s) and volume(s) Price(s) 100.50 DKK Volume(s) 1,000 d) Aggregated information")
    m = eu.parse_mar(txt)
    assert m["kind"] == "buy" and m["who"] == "Jane Doe" and m["val"] == round(1000 * 100.5 * eu.EUR["DKK"])


UK_FORM = ("F&amp;C Investment Trust PLC &#160; a) &#160; Name &#160; Rain Newton-Smith 2 &#160; Reason for the notification &#160; a) Position/status "
           "&#160; PDMR (Non-Executive Director) b) Initial notification 4 a) Description Ordinary shares GB00BS88V647 b) &#160; Nature of the transaction "
           "&#160; {nat} c) &#160; Price(s) and volume(s) &#160; Price(s) &#160; Volume(s) &#160; {pv} d) Aggregated information")


def test_parse_uk_buy_sell_pence_and_skip():
    b = eu.parse_uk(UK_FORM.format(nat="Purchase of shares", pv="£33.50 &#160; 10,000"))
    assert b["kind"] == "buy" and b["val"] == round(33.5 * 10000 * eu.EUR["GBP"]) and b["who"] == "Rain Newton-Smith"
    s = eu.parse_uk(UK_FORM.format(nat="Sale of shares", pv="1,250.5p 40,000 1,251p 10,000"))
    assert s["kind"] == "sell" and s["val"] == round((12.505 * 40000 + 12.51 * 10000) * eu.EUR["GBP"])
    assert eu.parse_uk(UK_FORM.format(nat="Dividend re-investment", pv="335.66p 12 shares")) is None
    assert eu.parse_uk(UK_FORM.format(nat="Purchase of partnership shares under the SIP", pv="300p 50")) is None
    assert eu.parse_uk(UK_FORM.format(nat="Exercise of options", pv="0p 5000")) is None


def test_parse_text_trade_oslo():
    r = eu.parse_text_trade("Edorf Invest AS, a company owned by Frode Haugli, Board Member and primary insider in Goodtech ASA, has on 3 November 2026 "
                            "purchased 7,000 shares in Goodtech ASA at an average price of NOK 14,09. Following the transaction")
    assert r == {"kind": "buy", "val": round(7000 * 14.09 * eu.EUR["NOK"]), "who": "Frode Haugli", "role": "Board Member", "px": 14.09, "pcur": "NOK"}
    assert eu.parse_text_trade("John Smith, CEO of X ASA, has today sold 1 250 000 shares at a price of NOK 102.5")["kind"] == "sell"
    assert eu.parse_text_trade("allocated 500,000 shares in the rights issue") is None


def test_uk_tidm():
    assert eu._uk_tidm("BT-A.L") == "BT.A" and eu._uk_tidm("LSEG.L") == "LSEG"


def test_parse_uk_real_layouts():
    azn = ("a) Name Michel Demaré 2 Reason for the notification a) Position/status Non-Executive Chair of the Board b) Initial notification /Amendment "
           "Initial notification 4 a) Description Ordinary Shares of US$0.25 each in AstraZeneca PLC GB0009895292 b) Nature of the transaction Purchase of "
           "AstraZeneca PLC Ordinary Shares of US$0.25 c) Price(s) and volume(s) Price(s) Volume(s) £121.213296 2,500 d) Aggregated information")
    r = eu.parse_uk(azn)
    assert r["kind"] == "buy" and r["val"] == round(121.213296 * 2500 * eu.EUR["GBP"]) and r["who"] == "Michel Demaré"
    shel = ("Name Sinead Gorman Position/status Chief Financial Officer Initial notification Description of the financial instrument Ordinary shares of "
            "€0.07 each Identification Code GB00BP6MXD84 Nature of the transaction Disposal of ordinary shares Currency GBP Price £33.686565 Volume 30,000 "
            "Total £1,010,596.95 Aggregated information: Price £33.686565 Volume 30,000")
    s = eu.parse_uk(shel)
    assert s["kind"] == "sell" and s["val"] == round(33.686565 * 30000 * eu.EUR["GBP"]) and s["who"] == "Sinead Gorman"


def test_num_prices_with_many_decimals_and_programs():
    r = eu.parse_text_trade("Jostein Sørvoll, primary insider and Chair of the Board in Protector Forsikring ASA, has today 13 August 2026 acquired "
                            "10,000 shares in Protector Forsikring ASA at a price of NOK 490.4066 per share.")
    assert r["val"] == round(10000 * 490.4066 * eu.EUR["NOK"]) and r["px"] == 490.4066 and r["pcur"] == "NOK"
    o = eu.parse_text_trade("Syno Invest AS, a related party to Øyvind Torpp, EVP & Investment Executive, has on 22 September 2026 bought "
                            "10,000 shares in Orkla ASA at a price of NOK 92.6898 per share.")
    assert o["val"] == round(10000 * 92.6898 * eu.EUR["NOK"])
    assert eu.parse_text_trade("Today, Yara has purchased 71,592 shares in the market at an average price of NOK 454.7355 per share. "
                               "The shares are purchased on behalf of and transferred to Yara Group Executive Board members taking part in "
                               "Yara's Share Based Remuneration (SBR) programs.") is None


def test_price_check_drops_implausible_rows():
    rows = [{"t": "RMV.L", "px": 5416.0, "pcur": "GBP", "val": 1}, {"t": "RMV.L", "px": 5.416, "pcur": "GBP", "val": 2},
            {"t": "PROT.OL", "px": 490.4, "pcur": "NOK", "val": 3}, {"t": "SAP.DE", "val": 4}, {"t": "X.L", "px": 9.9, "pcur": "GBP", "val": 5}]
    out = eu.price_check(rows, {"RMV.L": "GBp", "PROT.OL": "NOK", "X.L": "USD"}, closes=lambda ts: {"RMV.L": 541.6, "PROT.OL": 480.0, "X.L": 1.0})
    assert [x["val"] for x in out] == [2, 3, 4, 5]          # 5416 £ statt 5,416 £ fliegt raus; fremde Währung bleibt


def test_parse_uk_returns_price():
    r = eu.parse_uk(UK_FORM.format(nat="Purchase of shares", pv="1,250.5p 40,000 1,251p 10,000"))
    assert abs(r["px"] - (12.505 * 40000 + 12.51 * 10000) / 50000) < 1e-9 and r["pcur"] == "GBP"
