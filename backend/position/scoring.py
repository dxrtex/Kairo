"""3. Multi-Faktor-Ranking: 50 % Momentum, 30 % Qualität, 20 % Value – Perzentile (0–100) über alle Kandidaten des Tages.

Momentum „clenow“: Steigung der linearen Regression über 90 Handelstage auf log-Kurse, annualisiert (e^(252·b) − 1),
multipliziert mit R² (Andreas Clenow, „Stocks on the Move“). Alternativ „6-1“: Rendite von t-126 bis t-21.
Qualität: hohe Eigenkapitalrendite (ROE) und niedrige Nettoverschuldung/EBITDA. Value: niedriges PEG und Forward-KGV
im Verhältnis zum eigenen 5-Jahres-Durchschnitts-KGV. Fehlt ein Teil-Score ganz → neutral 50.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .config import CFG, Config


def clenow(C: pd.DataFrame, n: int = 90) -> pd.DataFrame:
    """Rollende Regression über n Tage, vollständig vektorisiert über Summen (keine Python-Schleife je Aktie).
    Nur Fenster ohne Lücke werden gewertet."""
    y = np.log(C.where(C > 0)).to_numpy(dtype=float)
    T, _ = y.shape
    ok = np.isfinite(y)
    y0 = np.where(ok, y, 0.0)
    i = np.arange(T, dtype=float)[:, None]

    def csum(a):
        out = np.zeros((a.shape[0] + 1, a.shape[1]))
        np.cumsum(a, axis=0, out=out[1:])
        return out

    S_y, S_iy, S_yy, S_ok = csum(y0), csum(i * y0), csum(y0 * y0), csum(ok.astype(float))
    out_slope = np.full_like(y, np.nan)
    out_r2 = np.full_like(y, np.nan)
    if T >= n:
        b = np.arange(n - 1, T)                     # Fensterende (inkl.)
        a = b - n + 1                               # Fensteranfang
        sy = S_y[b + 1] - S_y[a]
        siy = S_iy[b + 1] - S_iy[a]
        syy = S_yy[b + 1] - S_yy[a]
        cnt = S_ok[b + 1] - S_ok[a]
        sxy = siy - a[:, None] * sy                 # Σ x·y mit x = 0..n-1
        sx, sxx = n * (n - 1) / 2.0, (n - 1) * n * (2 * n - 1) / 6.0
        vx = n * sxx - sx * sx
        cov = n * sxy - sx * sy
        vy = n * syy - sy * sy
        slope = cov / vx
        with np.errstate(invalid="ignore", divide="ignore"):
            r2 = np.where(vy > 0, cov * cov / (vx * vy), 0.0)
        full = cnt == n
        out_slope[n - 1:] = np.where(full, slope, np.nan)
        out_r2[n - 1:] = np.where(full, r2, np.nan)
    ann = np.expm1(np.clip(out_slope * 252.0, -50, 50))
    return pd.DataFrame(ann * out_r2, index=C.index, columns=C.columns)


def mom_6_1(C: pd.DataFrame) -> pd.DataFrame:
    return C.shift(21) / C.shift(126) - 1


def momentum(C: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    return clenow(C, cfg.clenow_days) if cfg.momentum == "clenow" else mom_6_1(C)


def pct(s: pd.Series, higher_better: bool = True) -> pd.Series:
    """Perzentil-Rang 0–100 unter den vorhandenen Werten (NaN bleibt NaN, ±∞ zählt als bester/schlechtester Wert). Einzelwert → 50."""
    v = s.astype(float)
    if not higher_better:
        v = -v
    n = int(v.notna().sum())
    if n == 0:
        return pd.Series(np.nan, index=s.index)
    if n == 1:
        return v.where(v.isna(), 50.0)
    r = v.rank(method="average")
    return (r - 1) / (n - 1) * 100.0


def _composite(parts: list[pd.Series], neutral: float) -> pd.Series:
    """Mittel der vorhandenen Teil-Perzentile, danach erneut als Perzentil über alle Kandidaten; ganz fehlend → neutral."""
    m = pd.concat(parts, axis=1).mean(axis=1, skipna=True)
    out = pct(m)
    return out.fillna(neutral)


def score_day(cands: list[str], mom: pd.Series, f: pd.DataFrame | None, cfg: Config = CFG) -> pd.DataFrame:
    """Teil-Scores und Gesamt-Score für die Kandidaten eines Tages, absteigend sortiert.
    f: Fundamentaldaten je Ticker mit Spalten roe, nde (Nettoverschuldung/EBITDA), peg, fpe_rel (Forward-KGV / 5-J.-KGV)."""
    idx = pd.Index(cands)
    if not len(idx):
        return pd.DataFrame(columns=["mom", "qual", "val", "total"])
    f = (f.reindex(idx) if f is not None else pd.DataFrame(index=idx)).copy()
    for c in ("roe", "nde", "peg", "fpe_rel"):
        if c not in f:
            f[c] = np.nan
    ms = pct(mom.reindex(idx)).fillna(cfg.neutral)
    q = _composite([pct(f["roe"]), pct(f["nde"], higher_better=False)], cfg.neutral)
    peg = f["peg"].where(f["peg"] > 0, np.inf).where(f["peg"].notna())            # PEG ≤ 0 = schlechtester Rang
    rel = f["fpe_rel"].where(f["fpe_rel"] > 0, np.inf).where(f["fpe_rel"].notna())
    v = _composite([pct(peg, higher_better=False), pct(rel, higher_better=False)], cfg.neutral)
    tot = cfg.w_momentum * ms + cfg.w_quality * q + cfg.w_value * v
    out = pd.DataFrame({"mom": ms, "qual": q, "val": v, "total": tot, "mom_raw": mom.reindex(idx)})
    return out.sort_values(["total", "mom_raw"], ascending=False)


def select(scored: pd.DataFrame, sectors: dict[str, str], cfg: Config = CFG, held: dict[str, str] | None = None,
           slots: int | None = None) -> list[str]:
    """Top-Auswahl absteigend nach Score mit Sektor-Cap (max. 3 je Sektor, bestehende Positionen zählen mit)."""
    cnt: dict[str, int] = {}
    for t, s in (held or {}).items():
        cnt[s] = cnt.get(s, 0) + 1
    want = cfg.top_n if slots is None else slots
    out = []
    for t in scored.index:
        if held and t in held:
            continue
        s = sectors.get(t) or "?"
        if s != "?" and cnt.get(s, 0) >= cfg.sector_cap:
            continue
        out.append(t)
        cnt[s] = cnt.get(s, 0) + 1
        if len(out) >= want:
            break
    return out


def top_quantile(scored: pd.DataFrame, q: float) -> set[str]:
    """Die besten q-Anteile des Gesamt-Rankings (mindestens 1)."""
    k = max(1, math.ceil(len(scored) * q))
    return set(scored.index[:k])
