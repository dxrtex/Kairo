"""„MBI gelockert“: nur Fast-Treffer, denen allein das Abklingen beim MBI fehlt (frisches X, Spitze über der Linie)."""

from backend.h4live import candidates
from backend.scanner import Criterion, Result


def _res(missing, **flags):
    crit = [Criterion(k, k, False, "", "") for k in missing] + [Criterion("rsi_range", "RSI", True, "", "")]
    return Result("T", "2026-10-14", 1.0, criteria=crit, flags=flags)


def test_mbi_soft_rules():
    ok = dict(raw_mbi_age=1, raw_mbi_ref=1.4, raw_mbi_fade=0.79)
    assert _res(["mbi"], **ok).mbi_soft                                           # BYD-Fall: Rot 79 % der Spitze
    assert not _res(["mbi"], **{**ok, "raw_mbi_age": 17}).mbi_soft                # X zu alt
    assert not _res(["mbi"], **{**ok, "raw_mbi_ref": 0.9}).mbi_soft               # Spitze nicht über der Linie
    assert not _res(["mbi"], **{**ok, "raw_mbi_fade": 1.2}).mbi_soft              # neue, höhere rote Spitze
    assert not _res(["macd_turn"], **ok).mbi_soft                                 # anderes Kriterium fehlt
    assert not _res(["mbi", "crv"], **ok).mbi_soft                                # 9/11


def test_candidates_take_soft_signals():
    sig = [{"t": "1211.HK", "k": "soft", "d": "2026-10-14"}, {"t": "X", "k": "fast", "d": "2026-10-14"},
           {"t": "Y", "k": "hit", "d": "2026-10-13"}]
    c = {x["t"]: x for x in candidates(sig, "2026-10-14")}
    assert c["1211.HK"]["soft"] and c["1211.HK"]["grp"] == "10s" and not c["Y"].get("soft")
    assert c["X"]["grp"] == "10" and c["Y"]["grp"] == "11"                         # 10/11 zur Auswahl mit dabei


def test_candidates_prefer_real_hit_over_newer_near():
    sig = [{"t": "A", "k": "hit", "d": "2026-10-08"}, {"t": "A", "k": "near", "d": "2026-10-14"},
           {"t": "B", "k": "near", "d": "2026-10-10"}, {"t": "B", "k": "near", "d": "2026-10-14"},
           {"t": "C", "k": "near", "d": "2026-06-01"}]
    c = {x["t"]: x for x in candidates(sig, "2026-10-14")}
    assert c["A"]["grp"] == "11" and c["A"]["d"] == "2026-10-08"                   # laufender Treffer bleibt
    assert c["B"]["d"] == "2026-10-14" and c["B"]["grp"] == "9" and "C" not in c
