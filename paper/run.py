"""Täglicher Papier-Handel S19 / S20 (nach US-Börsenschluss). Keine Orders – nur virtuelle Depots.

python -m paper.run --state state            (state/ = Checkout des Branches paper-data)

Ablauf je neuem Handelstag D (Kalender S&P 500):
  1. Abgeschlossene H4-Kerzen von D chronologisch: offene Positionen (Stop/Ziel/Trailing), dann wartende Tagessignale
     (Auslöser → Kauf zum Schluss der Auslöse-Kerze).
  2. Depotwert zum Tagesschluss (EUR).
  3. Neue Tagessignale aus dem Schluss von D → warten bis zu 5 Handelstage auf den H4-Auslöser.
Der erste Lauf startet vorwärts (kein Nachrechnen der Vergangenheit).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import core

HERE = Path(__file__).resolve().parent
START_CASH = 2000.0                                # Nutzer-Startkapital (18.10.2026)
MAX_OPEN = 5
FX_T = {"USD": "EURUSD=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X", "SEK": "EURSEK=X", "NOK": "EURNOK=X",
        "DKK": "EURDKK=X", "PLN": "EURPLN=X", "CAD": "EURCAD=X", "JPY": "EURJPY=X"}
ETFS = sorted(set(core.SECTOR_ETF.values())) + ["SPY", "ACWI"]


# ------------------------------------------------------------------ Daten
def download(tickers, period="2y", interval="1d", batch=80):
    import yfinance as yf
    out, todo = {}, list(dict.fromkeys(tickers))
    for _ in range(2):
        failed = []
        for i in range(0, len(todo), batch):
            part = todo[i:i + batch]
            try:
                d = yf.download(part, period=period, interval=interval, auto_adjust=True, progress=False, threads=True,
                                group_by="ticker")
                for t in part:
                    try:
                        x = (d[t] if isinstance(d.columns, pd.MultiIndex) else d)[["Open", "High", "Low", "Close", "Volume"]]
                        x = x.dropna(subset=["Open", "High", "Low", "Close"])
                        (out.__setitem__(t, x) if len(x) > 20 else failed.append(t))
                    except Exception:
                        failed.append(t)
            except Exception as e:
                print("Download-Fehler", repr(e)[:150])
                failed += part
            time.sleep(1)
        if not failed:
            break
        todo = failed
        time.sleep(10)
    return out


def refresh_fund(path: Path, uni: pd.DataFrame, max_age_days=7) -> dict:
    """Wöchentlich: heutige Marktkapitalisierung, operative Marge, Branche (Yahoo) für große US-Titel."""
    cache = json.loads(path.read_text()) if path.exists() else {}
    ts = cache.get("ts")
    if ts and (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).days < max_age_days:
        return cache["data"]
    import yfinance as yf
    us = uni[(uni["region"] == "us") & ~uni["ticker"].str.endswith(".TO") & (uni["market_cap_usd"].fillna(0) >= 5e9)]
    data = {}
    for t in us["ticker"]:
        for n in range(3):
            try:
                inf = yf.Ticker(t).get_info()
                data[t] = {"mcap": inf.get("marketCap"), "opm": inf.get("operatingMargins"), "sector": inf.get("sector")}
                break
            except Exception:
                time.sleep(2 * (n + 1))
        time.sleep(0.15)
    path.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "data": data}))
    print(f"Fundamentaldaten aktualisiert: {len(data)} Titel")
    return data


# ------------------------------------------------------------------ Zustand
def load_state(d: Path, sid: str) -> dict:
    p = d / f"{sid.lower()}.json"
    if p.exists():
        st = json.loads(p.read_text())
        if st.get("start_cash") != START_CASH and not st["trades"] and not st["positions"]:
            # Startkapital geändert, bevor gehandelt wurde: Depot neu aufsetzen, wartende Signale behalten
            st.update(start_cash=START_CASH, cash=START_CASH,
                      equity=[{"date": e["date"], "eur": START_CASH, "open": 0} for e in st["equity"]])
            st["events"].append(f"Startkapital auf {START_CASH:,.0f} € gesetzt (vor dem ersten Trade)")
        return st
    return {"sid": sid, "start": None, "start_cash": START_CASH, "cash": START_CASH, "positions": [], "pending": [],
            "trades": [], "equity": [], "events": [], "last_day": None}


def save_state(d: Path, st: dict) -> None:
    st["events"] = st["events"][-600:]
    (d / f"{st['sid'].lower()}.json").write_text(json.dumps(st, indent=1, default=str, ensure_ascii=False))


class Market:
    def __init__(self, uni, daily, fx):
        self.cur = dict(zip(uni["ticker"], uni["currency"].fillna("USD")))
        self.region = dict(zip(uni["ticker"], uni["region"]))
        self.daily, self.fx = daily, fx
        self.feat = {}
        self.h4 = {}

    def f(self, t):
        if t not in self.feat and t in self.daily:
            self.feat[t] = core.daily_frame(self.daily[t])
        return self.feat.get(t)

    def rate(self, t, d) -> float:
        c = self.cur.get(t, "USD")
        if c == "EUR":
            return 1.0
        base, mult = ("GBP", 100.0) if c in ("GBp", "GBX") else (c, 1.0)
        s = self.fx.get(base)
        if s is None or not len(s):
            return float("nan")
        v = s[s.index <= d]
        return float((v.iloc[-1] if len(v) else s.iloc[0]) * mult)

    def spread(self, t, d) -> float:
        x = self.f(t)
        adv = float(x["adv"][x.index <= d].iloc[-1]) if x is not None and len(x[x.index <= d]) else 0.0
        usd = adv / (self.rate(t, d) if self.cur.get(t, "USD") != "USD" else 1.0) * (self.rate("SPY", d) if self.cur.get(t) != "USD" else 1.0)
        if usd < 20e6:
            return 0.003
        return 0.0015 if self.region.get(t) == "eu" else 0.001

    def last_close(self, t, d) -> float | None:
        x = self.daily.get(t)
        if x is None:
            return None
        v = x["Close"][x.index <= d]
        return float(v.iloc[-1]) if len(v) else None


def equity(st: dict, mk: Market, d) -> float:
    v = st["cash"]
    for p in st["positions"]:
        c = mk.last_close(p["t"], d) or p["entry"]
        v += p["qty"] * c / mk.rate(p["t"], d)
    return v


def close_pos(st, mk, p, px, why, ts):
    sp = mk.spread(p["t"], pd.Timestamp(ts).normalize())
    rate = mk.rate(p["t"], pd.Timestamp(ts).normalize())
    sell = px * (1 - sp / 2)
    f_out = core.fee(p["qty"] * sell / rate)
    st["cash"] += p["qty"] * sell / rate - f_out
    pnl = p["qty"] * sell / rate - f_out - p["cost_eur"]
    R = (px - p["entry"]) / (p["entry"] - p["stop0"]) if p["entry"] > p["stop0"] else None
    rn = pnl / p["risk_eur"] if p.get("risk_eur") else None      # netto: nach Gebühren und Spread, je eingesetztem Risiko
    st["trades"].append({**{k: p[k] for k in ("t", "entry_ts", "entry", "stop0", "qty", "regime")}, "exit_ts": str(ts), "exit": px,
                         "why": why, "pnl_eur": round(pnl, 2), "R": None if R is None else round(R, 3),
                         "R_net": None if rn is None else round(rn, 3)})
    st["positions"].remove(p)
    st["events"].append(f"{ts} VERKAUF {p['t']} {why} @ {px:.4g} PnL {pnl:+.2f} €")


def open_pos(st, mk, t, ts, entry, stop, risk, extra, d_prev):
    sp = mk.spread(t, d_prev)
    rate = mk.rate(t, d_prev)
    if not math.isfinite(rate):
        st["events"].append(f"{ts} {t}: kein Wechselkurs – kein Kauf")
        return
    eq = equity(st, mk, d_prev)
    q = core.size(eq, st["cash"], risk, entry, stop, rate, sp)
    if q <= 0:
        st["events"].append(f"{ts} {t}: Auslöser, aber zu wenig Cash/Mindestgröße – kein Kauf")
        return
    px = entry * (1 + sp / 2)
    cost = q * px / rate + core.fee(q * px / rate)
    st["cash"] -= cost
    st["positions"].append({"sid": st["sid"], "t": t, "entry_ts": str(ts), "entry": entry, "stop": stop, "stop0": stop, "qty": q,
                            "cost_eur": cost, "risk_eur": round(q * (px - stop) / rate, 2), **extra})
    st["events"].append(f"{ts} KAUF {t} {q} Stk @ {entry:.4g}, Stop {stop:.4g}, Risiko {risk:.1%}")


# ------------------------------------------------------------------ ein Handelstag
def process_day(st: dict, mk: Market, D: pd.Timestamp, D_prev: pd.Timestamp, cal: pd.DatetimeIndex, bull_prev: bool):
    """Kerzen von D chronologisch. Je Zeitpunkt: (1) vorgemerkte Käufe zur Eröffnung dieser Kerze (Auslöser kam mit der
    vorherigen Kerze; bei mehreren zuerst das stärkste Signal), (2) offene Positionen, (3) neue Auslöser zum Kerzenschluss →
    Kauf vormerken für die Eröffnung der nächsten Kerze (real nachhandelbar, wie das Kairo-4H-System)."""
    sid = st["sid"]
    st.setdefault("armed", [])
    tick = sorted({p["t"] for p in st["positions"]} | {q["t"] for q in st["pending"]} | {a["t"] for a in st["armed"]})
    slots: dict = {}
    for t in tick:
        b = mk.h4.get(t)
        if b is None or not len(b):
            continue
        m = (b["day"] > D_prev) & (b["day"] <= D)
        for j in np.flatnonzero(m.to_numpy()):
            slots.setdefault(b.index[j], []).append((t, j))
    for ts in sorted(slots):
        here = dict(slots[ts])
        # (1) Käufe zur Eröffnung
        due = sorted([a for a in st["armed"] if a["t"] in here and pd.Timestamp(a["trigger_ts"]) < ts], key=lambda a: -a["prio"])
        for a in due:
            st["armed"].remove(a)
            bar = mk.h4[a["t"]].iloc[here[a["t"]]]
            op = float(bar["Open"])
            if any(p["t"] == a["t"] for p in st["positions"]):
                continue
            cap = a.get("cap")
            if len(st["positions"]) >= MAX_OPEN or (cap is not None and len(st["positions"]) >= cap):
                st["events"].append(f"{ts} {a['t']}: Auslöser, aber Depot voll")
                continue
            stop = a["stop"] if sid.startswith("S19") else op - 1.5 * a["atr"]
            if op <= stop:
                st["events"].append(f"{ts} {a['t']}: Eröffnung {op:.4g} schon unter dem Stop – kein Kauf")
                continue
            extra = {"regime": a["regime"]}
            extra.update({"crv": a["crv"]} if sid.startswith("S19") else {"atr": a["atr"], "be": False})
            open_pos(st, mk, a["t"], ts, op, stop, a["risk"], extra, D_prev)
        # (2) offene Positionen (eine eben eröffnete zählt ab ihrer Eröffnung mit)
        for t, j in slots[ts]:
            b = mk.h4[t]
            bar, prev = b.iloc[j], (b.iloc[j - 1] if j > 0 else None)
            for p in [p for p in st["positions"] if p["t"] == t]:
                if pd.Timestamp(p["entry_ts"]) > ts:
                    continue
                tp = None
                if sid.startswith("S19"):
                    x = mk.f(t)
                    v = x["ema20"][x.index < bar["day"]]
                    tp = float(v.iloc[-1]) if len(v) else None
                r = core.step_position(p, bar, prev if pd.Timestamp(p["entry_ts"]) < ts else None, tp)
                if r:
                    close_pos(st, mk, p, r[0], r[1], ts)
        # (3) neue Auslöser zum Kerzenschluss
        for t, j in slots[ts]:
            b = mk.h4[t]
            bar = b.iloc[j]
            for q in [q for q in st["pending"] if q["t"] == t]:
                if not (pd.Timestamp(q["day"]) < bar["day"] <= pd.Timestamp(q["expiry"])):
                    continue
                if any(p["t"] == t for p in st["positions"]) or any(a["t"] == t for a in st["armed"]):
                    st["pending"].remove(q)
                    continue
                if sid.startswith("S19"):
                    lows = b["Low"][(b["day"] > pd.Timestamp(q["day"])) & (b.index <= ts)]
                    q["panic"] = min(q["panic"], float(lows.min())) if len(lows) else q["panic"]
                    if not core.s19_trigger(b, j):
                        continue
                    st["pending"].remove(q)
                    c = float(bar["Close"])
                    sl = q["panic"] - 0.5 * q["atr"]
                    x = mk.f(t)
                    v = x["ema20"][x.index < bar["day"]]
                    tp = float(v.iloc[-1]) if len(v) else float("nan")
                    crv = (tp - c) / (c - sl) if c > sl else -1
                    if not crv >= 2:
                        st["events"].append(f"{ts} {t}: H4-Auslöser, CRV {crv:.2f} < 2 – kein Trade")
                        continue
                    st["armed"].append({"t": t, "trigger_ts": str(ts), "stop": sl, "crv": round(crv, 2), "prio": -q.get("z", 0),
                                        "risk": 0.01 if bull_prev else 0.005, "cap": None if bull_prev else 2,
                                        "regime": "bull" if bull_prev else "bear"})
                else:
                    if not bull_prev or not core.s20_trigger(b, j):
                        continue
                    st["pending"].remove(q)
                    vr = float(bar["Volume"] / bar["vma20"]) if bar["vma20"] else 0.0
                    st["armed"].append({"t": t, "trigger_ts": str(ts), "atr": q["atr"], "prio": vr, "risk": 0.01, "regime": "bull"})
                st["events"].append(f"{ts} {t}: H4-Auslöser – Kauf zur Eröffnung der nächsten 4H-Kerze vorgemerkt")
    st["pending"] = [q for q in st["pending"] if pd.Timestamp(q["expiry"]) > D]
    st["equity"].append({"date": str(D.date()), "eur": round(equity(st, mk, D), 2), "open": len(st["positions"])})


def s19_funnel(x: pd.DataFrame, i: int, sec_ret3, sigma: float = 2.5, vol: str = "strict") -> list[bool]:
    """Die S19-Stufen einzeln (für die Filter-Übersicht): überdehnt, 3 Tage fallend, Volumen sinkt, schwächer als Branche."""
    r, C, V = x.iloc[i], x["Close"].to_numpy(), x["Volume"].to_numpy()
    return [bool(r["Close"] <= r["ema20"] - sigma * r["std20"]), bool(C[i] < C[i - 1] < C[i - 2] < C[i - 3]),
            core.vol_exhausted(V, i, vol), bool(sec_ret3 is not None and np.isfinite(sec_ret3) and r["ret3"] < sec_ret3)]


def new_setups(st: dict, mk: Market, D: pd.Timestamp, cal: pd.DatetimeIndex, tickers, bull_D: bool, fund: dict, sec3: dict,
               dry: bool = False):
    sid = st["sid"]
    ov = f"≥ {str(core.S19_VARIANTS.get(sid, (2.5,))[0]).replace('.', ',')} Std unter EMA20"
    fun = {"Qualität": 0, "Kursdaten": 0, "liquide": 0, ov: 0, "3 Tage fallend": 0, "Volumen sinkt": 0,
           "schwächer als Branche": 0, "Branchen-ETF fehlt": 0}
    k = int(np.searchsorted(cal.values, np.datetime64(D)))
    expiry = cal[min(k + core.WINDOW, len(cal) - 1)] if k + core.WINDOW < len(cal) else D + pd.tseries.offsets.BDay(core.WINDOW)
    busy = {p["t"] for p in st["positions"]} | {q["t"] for q in st["pending"]} | {a["t"] for a in st.get("armed", [])}
    found = 0
    for t in tickers:
        if t in busy:
            continue
        if sid.startswith("S19"):
            fun["Qualität"] += 1
        x = mk.f(t)
        if x is None or D not in x.index:
            continue
        i = int(x.index.get_loc(D))
        if i < 210:
            continue
        r = x.iloc[i]
        if sid.startswith("S19"):
            fun["Kursdaten"] += 1
        usd = 1.0 if mk.cur.get(t, "USD") == "USD" else mk.rate("SPY", D) / mk.rate(t, D)
        if not (r["adv"] * usd >= 5e6 and r["Close"] * usd >= 1.0):
            continue
        if sid.startswith("S19"):
            fd = fund.get(t) or {}
            if not ((fd.get("mcap") or 0) >= 10e9 and (fd.get("opm") or 0) > 0):
                continue
            fun["liquide"] += 1
            etf = core.SECTOR_ETF.get(fd.get("sector"), "SPY")
            sr = sec3.get(etf, {}).get(D)
            if sr is None:
                fun["Branchen-ETF fehlt"] += 1
            sg, vm = core.S19_VARIANTS[sid]
            f4 = s19_funnel(x, i, sr, sg, vm)
            for k, key in enumerate([ov, "3 Tage fallend", "Volumen sinkt", "schwächer als Branche"]):
                if not all(f4[:k + 1]):
                    break
                fun[key] += 1
            s = core.s19_signal(x, i, sr, sg, vm)
            if s and not dry:
                st["pending"].append({"t": t, "day": str(D.date()), "expiry": str(pd.Timestamp(expiry).date()), **s})
            found += bool(s)
        else:
            if not bull_D:
                return
            s = core.s20_setup(x, i)
            if s:
                st["pending"].append({"t": t, "day": str(D.date()), "expiry": str(pd.Timestamp(expiry).date()),
                                      "vr": float(r["Volume"] / x["Volume"].rolling(20).mean().iloc[i]), **s})
                found += 1
    if sid.startswith("S19"):
        st["funnel"] = {"date": str(D.date()), **fun, "Signale": found}
        st["events"].append(f"{D.date()} Filter: " + " → ".join(f"{k} {v}" for k, v in fun.items() if k != "Branchen-ETF fehlt")
                            + (f" (Branchen-ETF fehlt bei {fun['Branchen-ETF fehlt']})" if fun["Branchen-ETF fehlt"] else ""))
    if not dry:
        st["events"].append(f"{D.date()} neue Tagessignale: {found} (wartend gesamt {len(st['pending'])})")


# ------------------------------------------------------------------ Bericht
def stats(st: dict) -> dict:
    eq = pd.Series([e["eur"] for e in st["equity"]], index=[e["date"] for e in st["equity"]], dtype=float)
    tr = pd.DataFrame(st["trades"])
    out = {"start": st["start"], "tage": len(eq), "depot_eur": round(float(eq.iloc[-1]), 2) if len(eq) else st["start_cash"],
           "rendite": float(eq.iloc[-1] / st["start_cash"] - 1) if len(eq) else 0.0,
           "max_dd": float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0, "trades": int(len(tr)),
           "offen": len(st["positions"]), "wartend": len(st["pending"]), "vorgemerkt": len(st.get("armed", []))}
    if len(tr):
        rc = tr["R_net"] if "R_net" in tr and tr["R_net"].notna().any() else tr["R"]
        out.update(trefferquote=float((tr["pnl_eur"] > 0).mean()), avg_R=float(rc.dropna().mean()) if rc.notna().any() else None,
                   pnl_eur=round(float(tr["pnl_eur"].sum()), 2))
    return out


def run_shadow(sd: Path, mk: Market, cal, bull, s19_t, s20_t, fund, sec3) -> dict | None:
    """Schattenbuch (paper/shadow.py) – reine Forschung; ein Fehler hier darf die Depots nicht stören."""
    from . import shadow
    try:
        sb = shadow.load(sd)
        last = cal[-1]
        if sb["last_day"] is None:
            sb["start"] = sb["last_day"] = str(last.date())
            shadow.collect(sb, mk, last, cal, s19_t, s20_t, bool(bull.loc[last]), fund, sec3)
        for D in [d for d in cal if d > pd.Timestamp(sb["last_day"])]:
            prev = cal[cal < D][-1]
            miss = sorted(({q["t"] for q in sb["pending"]} | {x["t"] for x in sb["open"]}) - set(mk.h4))
            if miss:
                for t, h in download(miss, period="60d", interval="60m", batch=40).items():
                    mk.h4[t] = core.to_h4(h)
            shadow.step_day(sb, mk, D, prev, cal, bool(bull.loc[prev]))
            shadow.collect(sb, mk, D, cal, s19_t, s20_t, bool(bull.loc[D]), fund, sec3)
            sb["last_day"] = str(D.date())
        shadow.save(sd, sb)
        return shadow.summary(sb)
    except Exception as e:                             # noqa: BLE001
        print("Schattenbuch-Fehler:", repr(e)[:300])
        return None


def report(d: Path, states: list[dict], bench: list[dict] | None = None, shadow: dict | None = None) -> None:
    lines = ["# Papier-Handel S19 / S19-B / S19-C / S20 (echte 4-Stunden-Kerzen, keine echten Orders)", "",
             f"Stand: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Startkapital je Strategie {START_CASH:,.0f} € · "
             "Regeln exakt nach Nutzer-Vorgabe (Protokoll v1.5; S19-B/-C: v1.7). Kosten: Scalable PRIME+ (ab 250 € Orderwert gebührenfrei, sonst 0,99 €) + halber Spread je Seite.", ""]
    summ = {}
    for st in states:
        s = stats(st)
        summ[st["sid"]] = s
        name = {"S19": "S19 Hybride Mean Reversion (Original)", "S19B": "S19-B (Volumen 2 von 3 Tagen)",
                "S19C": "S19-C (2,0 Std, Volumen 2 von 3)"}.get(st["sid"], "S20 Trendfolge / VCP")
        lines += [f"## {name}", "", f"- Start: {s['start']} · Handelstage: {s['tage']}",
                  f"- Depot: **{s['depot_eur']:,.2f} €** ({s['rendite']:+.2%}) · größter Rückgang {s['max_dd']:.1%}",
                  f"- Abgeschlossene Trades: {s['trades']}" + (f" · Trefferquote {s['trefferquote']:.0%} · Ø R {s['avg_R']:+.2f}"
                                                               if s.get("avg_R") is not None else ""),
                  f"- Offen: {s['offen']} · warten auf H4-Auslöser: {s['wartend']}", ""]
        if st["positions"]:
            lines += ["| Titel | Kauf | Einstieg | Stop | Stück |", "|---|---|---|---|---|"]
            lines += [f"| {p['t']} | {p['entry_ts'][:16]} | {p['entry']:.4g} | {p['stop']:.4g} | {p['qty']} |" for p in st["positions"]]
            lines.append("")
        if st["trades"]:
            lines += ["Letzte Trades:", "", "| Titel | Kauf | Verkauf | Grund | R | PnL € |", "|---|---|---|---|---|---|"]
            lines += [f"| {x['t']} | {x['entry_ts'][:10]} | {x['exit_ts'][:10]} | {x['why']} | {x['R']} | {x['pnl_eur']:+.2f} |"
                      for x in st["trades"][-15:]]
            lines.append("")
        lines += ["Letzte Ereignisse:", "", *[f"- {e}" for e in st["events"][-12:]], ""]
    lines += ["---", "Grenzen: Kauf zur Eröffnung der 4H-Kerze nach dem Auslöser, Yahoo-Stundenkerzen (teils verzögert),",
              "heutige Fundamentaldaten (Yahoo, wöchentlich), Sektor-ETFs der US-Branchen. Keine Anlageberatung."]
    (d / "README.md").write_text("\n".join(lines))
    (d / "summary.json").write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **summ, "bench": bench or [],
                                                "shadow": shadow},
                                               indent=1, default=str))


# ------------------------------------------------------------------ Lauf
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="state")
    ap.add_argument("--recheck", action="store_true", help="S19-Filterübersicht für den letzten Tag neu zählen (ohne neue Signale)")
    a = ap.parse_args(argv)
    sd = Path(a.state)
    sd.mkdir(parents=True, exist_ok=True)
    uni = pd.read_csv(HERE / "universe.csv")
    fund = refresh_fund(sd / "fund_cache.json", uni)
    s19_t = [t for t, v in fund.items() if (v.get("mcap") or 0) >= 10e9 and (v.get("opm") or 0) > 0]
    s20_t = list(uni["ticker"])
    states = [load_state(sd, "S19"), load_state(sd, "S19B"), load_state(sd, "S19C"), load_state(sd, "S20")]
    need = set(s19_t) | set(s20_t) | {p["t"] for s in states for p in s["positions"]}
    daily = download(sorted(need) + ["^GSPC"] + ETFS)
    fxd = download(list(FX_T.values()), period="2y")
    fx = {c: fxd[t]["Close"] for c, t in FX_T.items() if t in fxd}
    fx_usd = fx.get("USD")
    mk = Market(uni, daily, fx)
    mk.cur["SPY"] = "USD"
    g = daily["^GSPC"]["Close"]
    bull = g > core.ema(g, 200)
    cal = g.index
    ny = pd.Timestamp.now(tz="America/New_York")
    if cal[-1].date() == ny.date() and (ny.hour, ny.minute) < (16, 45):
        cal = cal[:-1]                                 # heutiger Handelstag noch nicht beendet
    sec3 = {e: core.daily_frame(daily[e])["ret3"].to_dict() for e in ETFS if e in daily}
    last = cal[-1]
    for st in states:
        if st["last_day"] is None:                     # erster Lauf: vorwärts ab heute
            st["start"] = str(last.date())
            st["equity"].append({"date": str(last.date()), "eur": st["start_cash"], "open": 0})
            new_setups(st, mk, last, cal, s19_t if st["sid"].startswith("S19") else s20_t, bool(bull.loc[last]), fund, sec3)
            st["last_day"] = str(last.date())
            continue
        if a.recheck and st["sid"].startswith("S19"):
            new_setups(st, mk, pd.Timestamp(st["last_day"]), cal, s19_t, bool(bull.loc[pd.Timestamp(st["last_day"])]), fund, sec3,
                       dry=True)
        days = [d for d in cal if d > pd.Timestamp(st["last_day"])]
        for D in days:
            prev = cal[cal < D][-1]
            tick = sorted({p["t"] for p in st["positions"]} | {q["t"] for q in st["pending"]} | {a["t"] for a in st.get("armed", [])})
            miss = [t for t in tick if t not in mk.h4]
            if miss:
                hx = download(miss, period="60d", interval="60m", batch=40)
                for t, h in hx.items():
                    mk.h4[t] = core.to_h4(h)
            process_day(st, mk, D, prev, cal, bool(bull.loc[prev]))
            new_setups(st, mk, D, cal, s19_t if st["sid"].startswith("S19") else s20_t, bool(bull.loc[D]), fund, sec3)
            st["last_day"] = str(D.date())
    bench = []
    if "ACWI" in daily and fx_usd is not None and states[0]["start"]:
        a = daily["ACWI"]["Close"] / fx_usd.reindex(daily["ACWI"].index, method="ffill")
        a = a[a.index >= pd.Timestamp(states[0]["start"])].dropna()
        if len(a):
            bench = [{"date": str(i.date()), "eur": round(START_CASH * v / a.iloc[0], 2)} for i, v in a.items()]
    for st in states:
        save_state(sd, st)
    report(sd, states, bench, run_shadow(sd, mk, cal, bull, s19_t, s20_t, fund, sec3))
    print(json.dumps({s["sid"]: stats(s) for s in states}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
