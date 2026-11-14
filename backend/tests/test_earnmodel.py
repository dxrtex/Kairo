"""Quartalszahlen-Prognosemodell: Merkmale, Schätzung, Freigabe nur bei besserem rollierendem Test, Einbau in app_odds."""
import numpy as np
import pandas as pd

from backend import earnfast, earnmodel
from tools.earn_review import model_fit

STATS = {"buckets": [{"lo": -1e9, "hi": -2, "up1": .40, "name": "unter Erwartung"}, {"lo": -2, "hi": 2, "up1": .50, "name": "wie erwartet"},
                     {"lo": 2, "hi": 1e9, "up1": .60, "name": "über Erwartung"}]}
GUIDE = {"p": {"2|gesenkt": .35, "2|angehoben": .66}}


def test_prior_uses_guide_cell_then_bucket():
    assert earnmodel.prior(STATS, GUIDE, .1, -1) == .35
    assert earnmodel.prior(STATS, GUIDE, .1, None) == .60
    assert earnmodel.prior(STATS, GUIDE, -.1, 1) == .40          # keine Zelle → Gewinn-Stufe
    assert earnmodel.prior(STATS, GUIDE, None, 1) is None


def test_fit_recovers_direction_and_odds_need_adopt():
    rng = np.random.default_rng(1)
    X, y = [], []
    for _ in range(3000):
        pr, rs = rng.choice([.4, .5, .6]), rng.normal(0, .03)
        x = earnmodel.features(pr, rs)
        y.append(float(rng.random() < earnmodel.predict([-.2, 1.0, .5], x)))
        X.append(x)
    w = earnmodel.fit(X, y)
    assert abs(w[1] - 1.0) < .35 and abs(w[2] - .5) < .2 and w[0] < 0
    m = {"adopt": True, "f": earnmodel.FEATURES, "w": w}
    assert earnmodel.odds(m, STATS, GUIDE, .1, .05, 1) > earnmodel.odds(m, STATS, GUIDE, .1, -.05, -1)
    assert earnmodel.odds({**m, "adopt": False}, STATS, GUIDE, .1, None, None) is None
    assert earnmodel.odds({**m, "f": ["alt"]}, STATS, GUIDE, .1, None, None) is None      # alte Merkmalsliste nie anwenden


def test_confidence_labels():
    assert earnmodel.confidence(.52) == "keine klare Richtung"
    assert earnmodel.confidence(.43) == "leichte Tendenz"
    assert earnmodel.confidence(.65) == "deutliche Tendenz"


def _frame(n, shown_good: bool, seed=2):
    rng = np.random.default_rng(seed)
    rows = []
    days = pd.bdate_range("2026-10-01", periods=40).strftime("%Y-%m-%d")
    for i in range(n):
        s = rng.normal(0, .1)
        rs = rng.normal(0, .03)
        z = -.1 + 3 * s + 15 * rs
        yv = float(rng.random() < 1 / (1 + np.exp(-z)))
        p = 1 / (1 + np.exp(-z)) if shown_good else .5 + rng.normal(0, .15)
        rows.append({"t": f"T{i}", "d": days[i % 40], "s": s, "rs": rs, "gi": None, "y": yv, "p": min(max(p, .01), .99)})
    return pd.DataFrame(rows)


def test_model_fit_adopts_only_when_better_than_shown():
    good = model_fit(_frame(800, shown_good=False), STATS, GUIDE)
    assert good["adopt"] and good["f"] == earnmodel.FEATURES and len(good["folds"]) == 3
    assert good["brier_model"] < good["brier_shown"]
    bad = model_fit(_frame(800, shown_good=True), STATS, GUIDE)     # gezeigte Zahl kennt die wahre Formel → nicht schlagbar
    assert not bad["adopt"]
    assert not model_fit(_frame(50, False), STATS, GUIDE)["adopt"]


def test_app_odds_prefers_adopted_model(monkeypatch):
    monkeypatch.setattr(earnfast, "_site", lambda n: STATS if n == "earn_stats.json" else GUIDE)
    m = {"adopt": True, "f": earnmodel.FEATURES, "w": [0.0, 1.0, 0.0]}
    L = {"eps_s": .1, "guide": {"d": 1, "src": "Schlagzeilen"}}
    assert earnfast.app_odds(L, {}, None, "NVDA", m) == .66        # Schlagzeilen-„angehoben“ zählt im Modell mit
    assert earnfast.app_odds(L, {}, None, "NVDA", {**m, "adopt": False}) != .66
    txt = earnfast.result_text("NVDA", "NVIDIA", L, {}, None, m)["body"]
    assert "Kairo-Prognose" in txt and "66 %" in txt and "deutliche Tendenz" in txt
