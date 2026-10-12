"""BaFin-CSV (Directors' Dealings): Käufe/Verkäufe erkennen, deutsche Zahlen lesen, andere Geschäftsarten auslassen."""

from backend.bafin import parse_csv

CSV = ("﻿Emittent;Bafin-ID;ISIN;Meldepflichtiger;Position / Status;Art des Instruments;Art des Geschäfts;Durchschnittspreis;"
       "Aggregiertes Volumen;Mitteilungsdatum;Datum des Geschäfts;Ort des Geschäfts;Datum der Aktivierung\n"
       "Rheinmetall Aktiengesellschaft;40002496;DE0007030009;Papperger, Armin Theodor;Vorstand;Aktie;Kauf;950,38 EUR;498.947,80 EUR;"
       "29.09.2026;29.09.2026;XETRA;29.09.2026 15:24:14\n"
       "Rheinmetall Aktiengesellschaft;40002496;DE0007030009;Muster, Max;Aufsichtsrat;Aktie;Verkauf;1.000,00 EUR;2.000.000,00 EUR;"
       "02.10.2026;01.10.2026;Xetra;02.10.2026 10:00:00\n"
       "Rheinmetall Aktiengesellschaft;40002496;DE0007030009;A, B;Vorstand;Aktie;Zuteilung;0,00 EUR;5.000,00 EUR;01.01.2026;01.01.2026;;\n")


def test_parse_bafin_csv():
    rows = parse_csv(CSV, "RHM.DE")
    assert [r["kind"] for r in rows] == ["buy", "sell"]
    a = rows[0]
    assert a["t"] == "RHM.DE" and a["val"] == 498948 and a["px"] == 950.38 and a["d"] == "2026-09-29" and a["role"] == "Vorstand"
    assert rows[1]["d"] == "2026-10-01" and rows[1]["val"] == 2_000_000
    assert parse_csv("") == []
