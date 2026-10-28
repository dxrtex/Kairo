from backend.fedlive import headline, parse


def test_hold():
    html = "<p>In support of its goals, the Committee decided to maintain the target range for the federal funds rate at 3-3/4 to 4 percent.</p><p>Voting against this action was Stephen I. Miran, who preferred to lower the target range.</p>"
    r = parse(html)
    assert r["decision"] == "hold" and r["lo"] == 3.75 and r["hi"] == 4.0 and "Miran" in r["dissent"]
    assert headline(r) == "Fed lässt den Leitzins unverändert bei 3,75–4,00 %"


def test_cut():
    r = parse("the Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 3-1/2 to 3-3/4 percent.")
    assert r["decision"] == "cut" and r["bp"] == 25 and r["lo"] == 3.5 and r["hi"] == 3.75
    assert headline(r) == "Fed senkt den Leitzins um 25 Basispunkte auf 3,50–3,75 %"
