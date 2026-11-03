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
