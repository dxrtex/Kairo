"""E2-Schattentest: Buy-Stop über dem Basishoch, nicht ausgelöste Orders, nur künftige Signale, Einfrieren."""
import pandas as pd

from paper import e2shadow as E


def _df(after, n0=40):
    rows = [(100, 101, 99, 100)] * n0 + list(after)            # ruhig um 100, ATR ≈ 2, Signaltag = Index n0-1
    d = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], dtype=float, index=pd.bdate_range("2026-01-01", periods=len(rows)))
    d["Volume"] = 1e6
    return d, str(d.index[n0 - 1].date())


BASE = [(100, 100.6, 99.6, 100.2)] * 5                           # Basis: Spanne 1,0 ≤ 1,5 ATR, Tief 99,6 > 99


def test_buy_stop_triggers_and_exits_at_time():
    df, d = _df(BASE + [(100.3, 101.0, 100.2, 100.9)] + [(101, 102, 100.9, 101.5 + 0.1 * k) for k in range(70)])
    r = E.simulate(df, d)
    assert r["res"] in ("zeit", "ema") and r["buy_day"] == str(df.index[45].date())
    assert abs(r["e"] - r["trig"]) < 1e-9 and r["trig"] > 100.6 and r["sl"] < 99.6 and r["r"] > 0 and r["r_net"] < r["r"]


def test_not_triggered_and_gap_and_broken_base_are_logged():
    df, d = _df(BASE + [(100.2, 100.5, 99.9, 100.1)] * 10)
    assert E.simulate(df, d)["res"] == "nicht_ausgelöst"
    df, d = _df(BASE + [(110, 111, 109, 110)])
    assert E.simulate(df, d)["res"] == "kurslücke"
    df, d = _df(BASE + [(100, 100.2, 99.0, 99.2)])
    assert E.simulate(df, d)["res"] == "basis_gebrochen"
    df, d = _df([(100, 104, 96, 100)] * 10)
    assert E.simulate(df, d)["res"] in ("nobase", "basis_gebrochen")


def test_waiting_states_without_future_bars():
    df, d = _df(BASE[:3])
    assert E.simulate(df, d)["res"] == "wait"
    df, d = _df(BASE)
    assert E.simulate(df, d)["res"] == "armed"


def test_stop_on_buy_day_counts_as_stopped():
    df, d = _df(BASE + [(100.3, 101.0, 98.0, 98.5)])
    r = E.simulate(df, d)
    assert r["res"] == "stop" and r["r"] == -1.0 and r["days"] == 1


def test_step_only_future_signals_and_freezes():
    df, d = _df(BASE + [(100.2, 100.5, 99.9, 100.1)] * 10)
    sig = [{"t": "A", "k": "hit", "d": d, "region": "us", "st60": {"res": "run"}},
           {"t": "B", "k": "hit", "d": "2025-01-02", "region": "us"},          # vor dem Start → nie aufgenommen
           {"t": "C", "k": "trend", "d": d, "region": "us"},                   # anderes Setup → nicht aufgenommen
           {"t": "D", "k": "hit", "d": d, "region": "asia"}]                    # Asien wie die Depots ausgeschlossen
    book = E.step({"items": {}}, sig, {"A": df, "B": df}, d)
    assert book["start"] == d and set(book["items"]) == {f"A|{d}"} and book["items"][f"A|{d}"]["res"] == "nicht_ausgelöst"
    frozen = dict(book["items"][f"A|{d}"])
    df2, _ = _df(BASE + [(100.3, 101.0, 100.2, 100.9)] * 20)                   # andere Kerzen später: Eintrag bleibt
    E.step(book, sig, {"A": df2}, "2026-04-01")
    assert book["items"][f"A|{d}"] == frozen and book["start"] == d
    s = E.summary(book)
    assert s["n"] == 1 and s["status"] == {"nicht_ausgelöst": 1} and s["closed"] == 0


def test_rule_matches_b60_parameters():
    from backend.rule import KAIRO
    assert (E.RULE["wait"], E.RULE["ck"], E.RULE["cm"], E.RULE["buf"], E.RULE["hold"], E.RULE["ema"], E.RULE["ema_from"]) == \
        (KAIRO["wait"], KAIRO["ck"], KAIRO["cm"], KAIRO["buf"], KAIRO["hold"], KAIRO["ema"], KAIRO["ema_from"])


def test_same_day_trigger_and_base_break_is_conservative():
    """Tageskerze löst aus UND bricht die Basis: Reihenfolge unbekannt → Kauf zählt, Stop am Kauftag (−1 R brutto)."""
    df, d = _df(BASE + [(100.4, 101.2, 98.0, 99.0)])
    r = E.simulate(df, d)
    assert r["res"] == "stop" and r["days"] == 1 and r["r"] == -1.0 and r["r_stress"] < r["r_net"] < r["r"]


def test_open_gap_into_trigger_fills_at_open():
    df, d = _df(BASE + [(101.0, 101.5, 100.9, 101.2)] + [(101, 101.5, 100.8, 101.2)] * 70)
    r = E.simulate(df, d)
    assert r["e"] == 101.0 and r["e"] > r["trig"]                   # Eröffnung über dem Buy-Stop, unter der Lücken-Grenze
