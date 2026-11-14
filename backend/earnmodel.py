"""Quartalszahlen-Prognose als kleines logistisches Modell – „steigt die Aktie am Tag nach den Zahlen?“

Warum (Analyse 14.11.2026, 669 eigene Meldungen mit Kursreaktion, 27.10.–13.11.2026): Die gezeigte Zahl lag mit Brier
0,252 kaum besser als ein Münzwurf (0,250). Drei Ursachen:
- Falsches Niveau: Die Quoten stammen aus 2019–2026 (nach Zahlen stiegen ~55 %); im fallenden Herbst 2026 nur 47 %.
- Sonderregeln ohne Beleg im Ganzen: Asien-Quoten, Schlagzeilen-„angehoben“ ignorieren, Tabellen-Wechsel je Ausblick.
- Die Umsatz-Überraschung zählte nicht, obwohl sie trennt (Umsatz unter Erwartung: nur 32 % gestiegen).
Rollierender Test (14.11.2026): Die Langzeit-Rangfolge Gewinn × Ausblick trennt gut (AUC 0,59), die gezeigte Zahl nach
allen Sonderregeln (Asien-Quoten, Schlagzeilen-Ausblick ignoriert) nur noch 0,53 – die Sonderregeln haben mehr verdorben als
genützt. Freie Modelle mit vielen Merkmalen waren kaum besser als der Münzwurf (zu wenige Fälle). Am besten: Langzeit-Quote
als Rangfolge + Umsatz-Überraschung, Niveau aus Kairos eigenen Meldungen geeicht (Platt-Eichung). Brier 0,249 gegen 0,252.
Das Modell wird jede Woche aus Kairos eigener Bilanz neu geschätzt (L2-geglättet, damit es mit wenigen hundert Fällen
nicht überreagiert) und nur übernommen, wenn es auf den jüngsten Meldungen – geschätzt nur
mit älteren – genauer war als die damals gezeigte Zahl (tools/earn_review.py). Die App rechnet dieselbe Formel (earnOddsM).
"""
from __future__ import annotations

import math

FEATURES = ["const", "prior", "rev"]
NAMES = {"const": "Grundwert (Marktlage)", "prior": "Langzeit-Quote Gewinn × Ausblick", "rev": "Umsatz-Überraschung"}
REV_SCALE = 0.03            # Umsatz-Überraschung über tanh(rs/3 %): ±3 % zählt schon viel, ±20 % kaum mehr
L2 = 2.0                    # Glättung (Pseudo-Beobachtungen Richtung „kein Effekt“)
GKEY = {-1: "gesenkt", 0: "bestätigt", 1: "angehoben"}


def prior(stats: dict, guide: dict | None, s: float | None, g: int | None) -> float | None:
    """Langzeit-Quote „steigt am Tag danach“: Gewinn-Stufe × Ausblick aus 8.518 Berichten 2023–26 (earn_guide.json),
    ohne Ausblick die Gewinn-Stufe aus den US-Berichten seit 2019 (earn_stats.json). Diese Rangfolge trägt (AUC 0,59 auf
    Kairos eigenen Meldungen) – nur ihr Niveau passt nicht zu jeder Marktphase; das eicht das Modell."""
    B = (stats or {}).get("buckets") or []
    if s is None or not B:
        return None
    i = next((k for k, b in enumerate(B) if b["lo"] <= s * 100 < b["hi"]), None)
    if i is None:
        return None
    if g in GKEY and guide and (guide.get("p") or {}).get(f"{i}|{GKEY[g]}") is not None:
        return guide["p"][f"{i}|{GKEY[g]}"]
    return B[i].get("up1")


def features(pr: float | None, rs: float | None) -> list[float] | None:
    if pr is None:
        return None
    pr = min(max(pr, 0.02), 0.98)
    return [1.0, math.log(pr / (1 - pr)), math.tanh(rs / REV_SCALE) if rs is not None else 0.0]


def predict(w: list[float], x: list[float]) -> float:
    z = sum(a * b for a, b in zip(w, x))
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))


def fit(X: list[list[float]], y: list[float], l2: float = L2, iters: int = 60) -> list[float]:
    """Logistische Regression mit L2-Strafe (ohne Strafe auf den Grundwert), Newton-Verfahren – ohne Zusatzpakete."""
    import numpy as np
    A, Y = np.asarray(X, float), np.asarray(y, float)
    k = A.shape[1]
    w = np.zeros(k)
    R = np.eye(k) * l2
    R[0, 0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w, -30, 30)))
        g = A.T @ (p - Y) + R @ w
        H = (A * (p * (1 - p))[:, None]).T @ A + R + np.eye(k) * 1e-9
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return [round(float(v), 4) for v in w]


def odds(model: dict | None, stats: dict, guide: dict | None, s: float | None, rs: float | None, g: int | None) -> float | None:
    """Wahrscheinlichkeit „steigt am Tag danach“ – nur wenn die Bilanz das Modell übernommen hat (adopt)."""
    if not model or not model.get("adopt") or model.get("f") != FEATURES:
        return None
    x = features(prior(stats, guide, s, g), rs)
    return round(predict(model["w"], x), 3) if x else None


def confidence(p: float | None) -> str | None:
    """Ehrliche Einordnung: Selbst die besten Signale liegen selten über 65 %. Nahe 50 % ist es ein Münzwurf."""
    if p is None:
        return None
    d = abs(p - 0.5)
    return "keine klare Richtung" if d < 0.04 else "leichte Tendenz" if d < 0.1 else "deutliche Tendenz"
