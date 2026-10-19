"""Papier-Depots KAIRO / KAIROS: handeln die echten Scanner-Treffer (signals.json im Branch kairo-data, k = "hit") nach der
Kairo-Basisregel aus der Forschung (S01-B, Protokoll v2.3 bestanden) – nur US und Europa (wie getestet).

Nach dem Treffer-Tag bis zu 10 Handelstage: Treffer verworfen, sobald ein Tief unter das tiefste Tief der 10 Tage bis zum
Treffer fällt. Ab dem 5. Tag: bilden die letzten 5 Kerzen eine Seitwärtsphase (Hoch − Tief ≤ 1,5 ATR), Kauf zur nächsten
Eröffnung, wenn sie in der Spanne liegt (Tief < Eröffnung ≤ Hoch) und der Abstand zum Stop 0,5–3 ATR beträgt.
Stop = Basis-Tief − 0,25 ATR, Risiko 1 % des Depots, max. 5 Positionen. Ausstieg: Stop; ab Tag 10 Schluss unter EMA20 →
Verkauf zur nächsten Eröffnung; spätestens Schluss von Tag 60 (v2.5).
KAIRO: Vorrang ruhigere Titel (kleineres ATR ÷ Kurs, wie im Backtest). KAIROS: Vorrang schwächeres Vormomentum
(Rendite Monat −6…−1, Merkmal v2.4 bestätigt). Die Depots laufen einen Handelstag hinter dem Scan (Scan muss fertig sein).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WAIT, CK, CM, BUF, RISK_ATR = 10, 5, 1.5, 0.25, (0.5, 3.0)
MAX_OPEN, RISK = 5, 0.01
# Depot-Aufbau je Variante: KAIRO = Backtest-Original (5 × 1 %), KAIROS = bester Aufbau aus v2.7 (20 × 0,25 %, 20.000 € virtuell)
DESIGN = {"KAIRO": (5, 0.01), "KAIROS": (20, 0.0025)}
HOLD = 60                        # spätestens Tag 60 (Forschung v2.5: in allen drei Zeiträumen besser als Tag 40, p 0,0002)
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
    key = (lambda a: a["mom"]) if sid == "KAIROS" else (lambda a: a["vol"])
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
                                    "stop": lo - BUF * q["atr"], "atr": q["atr"], "mom": q["mom"], "vol": q["vol"]})
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
        a14 = float(x["atr"].iloc[i])
        st["pending"].append({"t": s["t"], "d": str(D.date()), "inv": float(x["Low"].iloc[max(0, i - 9):i + 1].min()),
                              "atr": a14, "mom": momentum(x, i), "vol": a14 / float(x["Close"].iloc[i])})
    st["seen"] = st["seen"][-3000:]
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})
