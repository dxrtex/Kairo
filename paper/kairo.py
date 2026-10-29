"""Papier-Depots KAIRO / KAIROS: handeln die echten Scanner-Treffer (signals.json im Branch kairo-data, k = "hit") nach der
Kairo-Basisregel aus der Forschung (S01-B, Protokoll v2.3 bestanden) – nur US und Europa (wie getestet).

Nach dem Treffer-Tag bis zu 10 Handelstage: Treffer verworfen, sobald ein Tief unter das tiefste Tief der 10 Tage bis zum
Treffer fällt. Ab dem 5. Tag: bilden die letzten 5 Kerzen eine Seitwärtsphase (Hoch − Tief ≤ 1,5 ATR), Kauf zur nächsten
Eröffnung, wenn sie in der Spanne liegt (Tief < Eröffnung ≤ Hoch) und der Abstand zum Stop 0,5–3 ATR beträgt.
Stop = Basis-Tief − 0,25 ATR, Risiko 1 % des Depots, max. 5 Positionen. Ausstieg: Stop; ab Tag 10 Schluss unter EMA20 →
Verkauf zur nächsten Eröffnung; spätestens Schluss von Tag 60 (v2.5).
KAIRO und KAIROS: Vorrang schwächeres Vormomentum (Rendite Monat −6…−1) – KAIRO bis 28.10.2026 „ruhigere Titel zuerst“,
umgestellt nach dem Depot-Test der Regel B60 (research/strategy_championship/v2_test.py). Die Depots laufen einen Handelstag hinter dem Scan (Scan muss fertig sein).

Langfrist-Idee des Nutzers (20.10.2026, ungetestet – nur Vorwärtstest): gleicher Basis-Einstieg, dann halten bis zum Ziel.
KAIROZ (Kairo-Ziel): nur Treffer mit attraktivem Analysten-Kursziel am Signaltag – Abstand zum Ziel ≥ 1 × Jahresschwankung,
mindestens 3 Analysten. Verkauf, sobald 80 % des Wegs zum Kursziel geschafft sind. KAIROL (Vergleich, „Kairo lang“): dieselben
Treffer ohne Kursziel-Filter, Ziel = Einstieg + 80 % einer Jahresschwankung. Beide: Sicherheitsnetz −30 %, spätestens nach
24 Monaten, 20 Plätze à 5 % des Depots (20.000 € virtuell). Kursziele stammen aus dem Scan des Signaltags (kein Rückblick).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WAIT, CK, CM, BUF, RISK_ATR = 10, 5, 1.5, 0.25, (0.5, 3.0)
MAX_OPEN, RISK = 5, 0.01
# Depot-Aufbau je Variante: KAIRO = Backtest-Original (5 × 1 %), KAIROS = bester Aufbau aus v2.7 (20 × 0,25 %, 20.000 € virtuell)
DESIGN = {"KAIRO": (5, 0.01), "KAIROS": (20, 0.0025)}
HOLD = 60                        # spätestens Tag 60 (Forschung v2.5: in allen drei Zeiträumen besser als Tag 40, p 0,0002)
LONG = {"KAIROZ", "KAIROL"}      # Langfrist-Varianten (halten bis zum Ziel)
DESIGN.update({"KAIROZ": (20, 0.015), "KAIROL": (20, 0.015)})   # −30 % Netz × 1,5 % Risiko = 5 % je Position
CAT, GOAL_SHARE, LONG_HOLD = 0.30, 0.80, 504                    # Sicherheitsnetz, Anteil des Wegs zum Ziel, ~24 Monate
ATTR, MIN_AN = 1.0, 3                                           # Ziel-Abstand ≥ 1 × Jahresschwankung, ≥ 3 Analysten


def attractive(s: dict) -> float | None:
    """Kursziel-Abstand im Verhältnis zur Jahresschwankung (am Signaltag) – None, wenn nicht attraktiv genug."""
    up, vol, na = s.get("tup"), s.get("vol"), s.get("na") or 0
    if up is None or not vol or vol <= 0 or na < MIN_AN:
        return None
    z = up / vol
    return z if z >= ATTR else None
REGIONS = ("us", "europe")


def new_hits(signals: list, seen: set, D: pd.Timestamp) -> list[dict]:
    return [s for s in signals if s.get("k") == "hit" and s.get("region") in REGIONS and pd.Timestamp(s["d"]) == D
            and f"{s['t']}|{s['d']}" not in seen]


def momentum(x: pd.DataFrame, i: int) -> float:
    C = x["Close"].to_numpy(float)
    return float(C[i - 21] / C[i - 126] - 1) if i >= 126 else float("nan")


SUFFIX_CUR = {"DE": "EUR", "F": "EUR", "PA": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR", "VI": "EUR", "BR": "EUR",
              "HE": "EUR", "LS": "EUR", "IR": "EUR", "L": "GBp", "SW": "CHF", "ST": "SEK", "OL": "NOK", "CO": "DKK",
              "WA": "PLN", "TO": "CAD"}


def currency(t: str) -> str:
    return SUFFIX_CUR.get(t.rsplit(".", 1)[1], "USD") if "." in t else "USD"


def tickers(signals: list, states: list[dict], since: pd.Timestamp) -> list[str]:
    """Titel, für die Tageskurse gebraucht werden: neuere Treffer (US/Europa) + offene/wartende Titel der Depots."""
    out = {s["t"] for s in signals if s.get("k") == "hit" and s.get("region") in REGIONS and pd.Timestamp(s["d"]) >= since}
    for st in states:
        out |= {p["t"] for p in st["positions"]} | {q["t"] for q in st["pending"]} | {a["t"] for a in st.get("armed", [])}
    return sorted(out)


def day(st: dict, mk, D: pd.Timestamp, D_prev: pd.Timestamp, signals: list, equity, close_pos, open_pos) -> None:
    sid = st["sid"]
    st.setdefault("seen", [])
    st.setdefault("armed", [])
    # 1) Eröffnung: vorgemerkte Verkäufe, dann vorgemerkte Käufe (Vorrang je Depot)
    for p in [p for p in st["positions"] if p.get("sell_next")]:
        x = mk.f(p["t"])
        if x is not None and D in x.index:
            close_pos(st, mk, p, float(x.loc[D, "Open"]), "ema20", str(D.date()))
    # Vorrang: schwächeres Vormomentum – seit 29.10.2026 auch KAIRO, wie die App (Depot-Test B60: 2022–26 +11,9 % statt −6,2 % p. a.
    # mit „ruhigere zuerst“; Review 2, W7). KAIROZ: attraktivstes Kursziel zuerst.
    key = {"KAIROZ": lambda a: -(a.get("z") or 0)}.get(sid, lambda a: a["mom"])
    for a in sorted([a for a in st["armed"] if pd.Timestamp(a["after"]) < D], key=lambda a: np.nan_to_num(key(a), nan=9.0)):
        x = mk.f(a["t"])
        if x is None or D not in x.index or any(p["t"] == a["t"] for p in st["positions"]):
            continue
        if len(st["positions"]) >= DESIGN.get(sid, (MAX_OPEN, RISK))[0]:
            st["events"].append(f"{D.date()} {a['t']}: Basis-Einstieg, aber Depot voll")
            continue
        op = float(x.loc[D, "Open"])
        if not (a["lo"] < op <= a["hi"]):
            continue
        if not (RISK_ATR[0] <= (op - a["stop"]) / a["atr"] <= RISK_ATR[1]):
            st["pending"] = [q for q in st["pending"] if q["t"] != a["t"]]
            continue
        n0 = len(st["positions"])
        if sid in LONG:                          # halten bis zum Ziel: Sicherheitsnetz statt Basis-Stop
            goal = op + GOAL_SHARE * (a["tg"] - op) if sid == "KAIROZ" else op * (1 + GOAL_SHARE * (a.get("va") or 0.3))
            if sid == "KAIROZ" and not (a.get("tg") and a["tg"] > op * 1.05):
                st["events"].append(f"{D.date()} {a['t']}: Kurs schon nahe am Kursziel – kein Kauf")
                st["pending"] = [q for q in st["pending"] if q["t"] != a["t"]]
                continue
            open_pos(st, mk, a["t"], str(D.date()), op, op * (1 - CAT), DESIGN[sid][1], {"regime": "-", "days": 0, "goal": round(goal, 4)}, D_prev)
        else:
            open_pos(st, mk, a["t"], str(D.date()), op, a["stop"], DESIGN.get(sid, (MAX_OPEN, RISK))[1], {"regime": "-", "days": 0}, D_prev)
        if len(st["positions"]) > n0:
            st["pending"] = [q for q in st["pending"] if q["t"] != a["t"]]
    st["armed"] = [a for a in st["armed"] if pd.Timestamp(a["after"]) >= D]        # je Vormerkung genau eine Eröffnung
    # 2) Tagesverlauf der offenen Positionen
    for p in list(st["positions"]):
        x = mk.f(p["t"])
        if x is None or D not in x.index:
            continue
        r = x.loc[D]
        p["days"] = p.get("days", 0) + 1
        if p["days"] > 1 and r["Open"] <= p["stop"]:
            close_pos(st, mk, p, float(r["Open"]), "stop_gap", str(D.date())); continue
        if r["Low"] <= p["stop"]:
            close_pos(st, mk, p, float(p["stop"]), "stop", str(D.date())); continue
        if sid in LONG:
            if p.get("goal") and r["High"] >= p["goal"]:
                close_pos(st, mk, p, float(max(p["goal"], r["Open"])), "ziel", str(D.date())); continue
            if p["days"] >= LONG_HOLD:
                close_pos(st, mk, p, float(r["Close"]), "zeit", str(D.date()))
            continue
        if p["days"] >= HOLD:
            close_pos(st, mk, p, float(r["Close"]), "zeit", str(D.date())); continue
        if p["days"] >= 10 and r["Close"] < r["ema20"]:
            p["sell_next"] = True
    # 3) wartende Treffer: Seitwärtsphase prüfen → Kauf für die nächste Eröffnung vormerken
    keep = []
    for q in st["pending"]:
        x = mk.f(q["t"])
        if x is None or D not in x.index:
            keep.append(q); continue
        k = int(x.index.get_loc(D))
        s = int(x.index.get_loc(pd.Timestamp(q["d"]))) if pd.Timestamp(q["d"]) in x.index else None
        if s is None or k - s > WAIT:
            continue
        if float(x["Low"].iloc[k]) < q["inv"]:
            st["events"].append(f"{D.date()} {q['t']}: Treffer gescheitert (neues Tief)"); continue
        keep.append(q)
        if k - s >= CK:
            hi, lo = float(x["High"].iloc[k - CK + 1:k + 1].max()), float(x["Low"].iloc[k - CK + 1:k + 1].min())
            if hi - lo <= CM * q["atr"]:
                st["armed"].append({"t": q["t"], "after": str(D.date()), "lo": lo, "hi": hi,
                                    "stop": lo - BUF * q["atr"], "atr": q["atr"], "mom": q["mom"], "vol": q["vol"],
                                    **{k: q[k] for k in ("tg", "z", "va") if k in q}})
    st["pending"] = keep
    # 4) neue Treffer dieses Tages
    for s in new_hits(signals, set(st["seen"]), D):
        st["seen"].append(f"{s['t']}|{s['d']}")
        x = mk.f(s["t"])
        if x is None or D not in x.index:
            continue
        i = int(x.index.get_loc(D))
        if any(q["t"] == s["t"] for q in st["pending"]) or any(p["t"] == s["t"] for p in st["positions"]):
            continue
        extra = {}
        if sid == "KAIROZ":                      # nur attraktives Kursziel (Stand Signaltag)
            z = attractive(s)
            if z is None:
                continue
            extra = {"tg": float(x["Close"].iloc[i]) * (1 + float(s["tup"])), "z": round(z, 2)}   # Ziel relativ (Währung/Pence-sicher)
        if sid in LONG:
            extra["va"] = s.get("vol") or float(np.log(x["Close"]).diff().iloc[max(1, i - 29):i + 1].std() * np.sqrt(252))
        a14 = float(x["atr"].iloc[i])
        st["pending"].append({"t": s["t"], "d": str(D.date()), "inv": float(x["Low"].iloc[max(0, i - 9):i + 1].min()),
                              "atr": a14, "mom": momentum(x, i), "vol": a14 / float(x["Close"].iloc[i]), **extra})
    st["seen"] = st["seen"][-3000:]
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})
