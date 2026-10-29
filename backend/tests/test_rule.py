"""Eine Kairo-Regel überall: Backend, Live-Bilanz, Papier-Depot und App müssen dieselben Werte haben (Review 29.10.2026)."""
import re
from pathlib import Path

from backend.live import RULE60
from backend.rule import KAIRO
from backend.shortswing import QRULE

ROOT = Path(__file__).resolve().parents[2]


def test_backend_einheitlich():
    assert RULE60 == {"hold": KAIRO["hold"], "ema_x": KAIRO["ema"], "ema_from": KAIRO["ema_from"]}
    for k in ("wait", "ck", "cm", "inv", "buf"):
        assert QRULE[k] == KAIRO[k], k
    assert QRULE["maxd"] == KAIRO["risk_atr"][1]


def test_papier_depot_gleiche_regel():
    src = (ROOT / "paper" / "kairo.py").read_text(encoding="utf-8")
    assert int(re.search(r"^HOLD = (\d+)", src, re.M).group(1)) == KAIRO["hold"]
    wait, ck, cm, buf = re.search(r"^WAIT, CK, CM, BUF, RISK_ATR = (\d+), (\d+), ([\d.]+), ([\d.]+)", src, re.M).groups()
    assert (int(wait), int(ck), float(cm), float(buf)) == (KAIRO["wait"], KAIRO["ck"], KAIRO["cm"], KAIRO["buf"])
    assert re.search(r"^MAX_OPEN, RISK = (\d+), ([\d.]+)", src, re.M).groups() == (str(KAIRO["max_open"]), str(KAIRO["risk"]))


def test_app_gleiche_regel():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    kmax = re.search(r"const KMAX = \{ hold: (\d+), hold2: (\d+),[^}]*maxOpen: (\d+)", html)
    assert kmax and {int(kmax.group(1)), int(kmax.group(2))} == {KAIRO["hold"]} and int(kmax.group(3)) == KAIRO["max_open"]
    h4x = re.search(r"const H4X = \{ hold: (\d+), from: (\d+) \}", html)
    assert h4x and (int(h4x.group(1)), int(h4x.group(2))) == (KAIRO["hold"], KAIRO["ema_from"])
    # keine abweichende Haltedauer in Handlungsanweisungen der Kairo-Regel
    assert "spätestens Tag 40" not in html and "spätestens Tag 20" not in html


def test_fertiger_tagesschluss():
    """Review 2, K3: tagsüber zählt die laufende Kerze nicht für den EMA-Ausstieg."""
    from datetime import datetime, timezone
    import pandas as pd
    from backend.run_scan import closed_bar
    idx = pd.bdate_range("2026-09-01", "2026-10-29")
    df = pd.DataFrame({"Close": [100.0] * (len(idx) - 1) + [90.0]}, index=idx)
    day = closed_bar(df, datetime(2026, 10, 29, 13, tzinfo=timezone.utc))
    eve = closed_bar(df, datetime(2026, 10, 29, 22, tzinfo=timezone.utc))
    assert day["cd"] == "2026-10-28" and day["cc"] == 100.0
    assert eve["cd"] == "2026-10-29" and eve["cc"] == 90.0 and eve["ce"] > 90
