"""Papier-Handel S19 (Hybride Mean Reversion) und S20 (Trendfolge/VCP) mit echten 4-Stunden-Kerzen – reine Logik.

Regeln exakt nach Nutzer-Vorgabe (docs: research/strategy-championship-phase-a, 02_PROTOCOL.md v1.5). Keine Orders, kein
Broker – nur ein virtuelles Depot je Strategie. Alle Entscheidungen nur mit abgeschlossenen Kerzen.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

WINDOW = 5                       # Handelstage, in denen nach dem Tagessignal ein H4-Auslöser kommen darf
FEE = 0.99                       # € je Order unter FEE_FREE_FROM
FEE_FREE_FROM = 250.0            # Scalable PRIME+ (Nutzer-Tarif): ab 250 € Orderwert gebührenfrei (gettex)


def fee(value_eur: float) -> float:
    return 0.0 if value_eur >= FEE_FREE_FROM else FEE
MIN_FILL = 0.5                   # Kauf entfällt, wenn das Cash < 50 % der geplanten Stückzahl erlaubt
SECTOR_ETF = {"Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
              "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
              "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC"}


# ------------------------------------------------------------------ Indikatoren
def rma(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    c = df["Close"]
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(), (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False).mean()


def daily_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Tagesmerkmale für beide Strategien (Kurse wie geliefert, auto_adjust)."""
    x = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    C = x["Close"]
    x["atr"] = atr(x)
    x["ema20"], x["ema50"], x["ema200"] = ema(C, 20), ema(C, 50), ema(C, 200)
    x["std20"] = C.rolling(20).std()
    x["bbw"] = 4 * C.rolling(20).std() / C.rolling(20).mean()
    x["bbw_ma"] = x["bbw"].rolling(20).mean()
    x["h50"], x["l50"] = x["High"].rolling(50).max(), x["Low"].rolling(50).min()
    x["ret3"] = C / C.shift(3) - 1
    x["adv"] = (C * x["Volume"]).rolling(20).mean()
    return x


def to_h4(h: pd.DataFrame) -> pd.DataFrame:
    """Stundenkerzen je Handelstag in 4er-Gruppen (wie TradingView 4H in der Börsenzeit), mit Volumen."""
    if h is None or not len(h):
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume", "day"])
    idx = h.index.tz_convert(None) if h.index.tz is not None else h.index
    h = h.copy()
    h.index = idx
    day = h.index.normalize()
    k = h.groupby(day).cumcount() // 4
    g = h.groupby([day, k])
    b = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(), "Low": g["Low"].min(), "Close": g["Close"].last(),
                      "Volume": g["Volume"].sum(), "t": g.apply(lambda z: z.index[-1])})
    b.index = pd.DatetimeIndex(b["t"].values)
    b = b.drop(columns="t").sort_index()
    b["day"] = b.index.normalize()
    b["ema20"] = ema(b["Close"], 20)
    b["vma20"] = b["Volume"].rolling(20).mean()
    return b


# ------------------------------------------------------------------ Tagessignale
# Varianten (Protokoll v1.7): Überdehnung in Std unter der EMA20, Volumen „strict“ (V_t < V_t−1 < V_t−2) oder „2of3“
# (an mindestens 2 der letzten 3 Tage gesunken). S19 = Nutzer-Original.
S19_VARIANTS = {"S19": (2.5, "strict"), "S19B": (2.5, "2of3"), "S19C": (2.0, "2of3")}


def vol_exhausted(V, i: int, mode: str = "strict") -> bool:
    if mode == "strict":
        return bool(V[i] < V[i - 1] < V[i - 2])
    return (int(V[i] < V[i - 1]) + int(V[i - 1] < V[i - 2]) + int(V[i - 2] < V[i - 3])) >= 2


def s19_signal(x: pd.DataFrame, i: int, sec_ret3: float | None, sigma: float = 2.5, vol: str = "strict") -> dict | None:
    """Hybride Mean Reversion am Tag i (Schluss): Überdehnung ≥ sigma Std unter EMA20, 3 fallende Tage mit sinkendem Volumen,
    stärker gefallen als die eigene Branche. (Qualität/Größe/Regime prüft der Aufrufer.)"""
    if i < 3 or sec_ret3 is None or not np.isfinite(sec_ret3):
        return None
    r = x.iloc[i]
    C, V = x["Close"].to_numpy(), x["Volume"].to_numpy()
    down3 = C[i] < C[i - 1] < C[i - 2] < C[i - 3]
    vex = vol_exhausted(V, i, vol)
    if not (down3 and vex and r["Close"] <= r["ema20"] - sigma * r["std20"] and r["ret3"] < sec_ret3):
        return None
    return {"panic": float(r["Low"]), "atr": float(r["atr"]), "z": float((r["Close"] - r["ema20"]) / r["std20"])}


def s20_setup(x: pd.DataFrame, i: int) -> dict | None:
    """Trendfolge/VCP am Tag i: Kurs > EMA50 > EMA200, Bollinger-Bandbreite unter ihrem 20-T.-Schnitt, Kurs ≤ 1,5 % an der EMA50
    oder in der 50–61,8-%-Retracement-Zone des 50-T.-Bereichs (± 1,5 %). (Regime prüft der Aufrufer.)"""
    r = x.iloc[i]
    if not (r["Close"] > r["ema50"] > r["ema200"] and r["bbw"] < r["bbw_ma"]):
        return None
    rng = r["h50"] - r["l50"]
    hi, lo = r["h50"] - 0.5 * rng, r["h50"] - 0.618 * rng
    near = abs(r["Close"] / r["ema50"] - 1) <= 0.015 or (lo * 0.985 <= r["Close"] <= hi * 1.015)
    if not near:
        return None
    return {"atr": float(r["atr"])}


# ------------------------------------------------------------------ H4-Auslöser
def s19_trigger(b: pd.DataFrame, j: int) -> bool:
    """Kerze j schließt grün und über dem Hoch der letzten roten Kerze davor."""
    if j < 1:
        return False
    bar = b.iloc[j]
    if not bar["Close"] > bar["Open"]:
        return False
    prev = b.iloc[:j]
    red = prev[prev["Close"] < prev["Open"]]
    return bool(len(red) and bar["Close"] > red["High"].iloc[-1])


def s20_trigger(b: pd.DataFrame, j: int) -> bool:
    """Kerze j schließt deutlich (≥ 1 %) über der H4-EMA20 mit Volumen über dem H4-Volumen-Schnitt 20."""
    bar = b.iloc[j]
    return bool(np.isfinite(bar["vma20"]) and bar["Close"] > bar["ema20"] * 1.01 and bar["Volume"] > bar["vma20"])


# ------------------------------------------------------------------ Positionen
def size(equity_eur: float, cash_eur: float, risk_frac: float, entry: float, stop: float, fx: float, spread: float) -> int:
    """Stückzahl: Risiko (Einstieg bis Stop) = risk_frac × Depotwert; begrenzt durch Cash; Mindestgröße 50 %."""
    px = entry * (1 + spread / 2)
    per = (px - stop) / fx
    if per <= 0:
        return 0
    plan = int(math.floor(equity_eur * risk_frac / per))
    cap = int(math.floor(max(0.0, cash_eur - FEE) / (px / fx)))
    q = min(plan, cap)
    return q if q > 0 and q >= MIN_FILL * plan else 0


def step_position(p: dict, bar: pd.Series, prev_bar: pd.Series | None, tp_level: float | None) -> tuple[float, str] | None:
    """Eine abgeschlossene H4-Kerze für eine offene Position. → (Ausstiegskurs, Grund) oder None.
    S19: Stop zuerst (vorsichtig), dann Ziel = EMA20 (Tageslinie des Vortags). S20: Break-even ab +2 ATR, danach Stop unter
    das Tief der jeweils letzten abgeschlossenen H4-Kerze."""
    if p["sid"] == "S20" and p.get("be") and prev_bar is not None:
        p["stop"] = max(p["stop"], float(prev_bar["Low"]))
    o, h, l = float(bar["Open"]), float(bar["High"]), float(bar["Low"])
    if o <= p["stop"]:
        return o, "stop_gap"
    if l <= p["stop"]:
        return p["stop"], "stop" if p["stop"] < p["entry"] else "trail"
    if p["sid"].startswith("S19") and tp_level is not None and np.isfinite(tp_level) and h >= tp_level:
        return max(tp_level, o), "ziel_ema20"
    if p["sid"] == "S20" and not p.get("be") and h >= p["entry"] + 2 * p["atr"]:
        p["be"] = True
        p["stop"] = max(p["stop"], p["entry"])
    return None
