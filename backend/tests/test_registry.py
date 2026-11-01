"""Champion-Challenger-Register: nur der Champion bestimmt Trades, keine automatische Beförderung einer Handelsregel."""
from backend import registry as G


def test_single_rule_champion_is_b60():
    champs = [x for x in G.REGISTRY if x["kind"] == "regel" and x["stage"] == "champion"]
    assert [x["id"] for x in champs] == ["B60"] and all(x["stage"] in G.STAGES for x in G.REGISTRY)
    assert G.may_change_trades(champs[0]) and not G.may_change_trades(next(x for x in G.REGISTRY if x["id"] == "E2"))


def test_rule_never_auto_promoted():
    e2 = next(x for x in G.REGISTRY if x["id"] == "E2")
    ok, miss = G.promote_allowed(e2, {"hist_periods": True, "hist_depot": True, "independent": True, "shadow_n": 99, "shadow_months": 24})
    assert ok is False and miss == [G.GATES_RULE["approval"]]
    ok, miss = G.promote_allowed(e2, {"shadow_n": 3})
    assert len(miss) >= 5


def test_forecast_gate():
    m1 = next(x for x in G.REGISTRY if x["id"] == "EARN-M1")
    assert G.promote_allowed(m1, {"cases": 250, "brier_better": True}) == (True, [])
    assert G.promote_allowed(m1, {"cases": 120, "brier_better": True})[0] is False
