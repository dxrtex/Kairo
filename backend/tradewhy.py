"""Warum ist ein Kairo-Trade gescheitert – und ließe sich das vorher erkennen? Ursachensuche und Lern-Bericht.

Grundlage sind die unveränderlichen Momentaufnahmen (backend/snapshots.py). Für jeden abgeschlossenen Treffer – Verlierer
UND Gewinner, sonst ließe sich nichts vergleichen – hält dieser Schritt einmalig fest (Feld „why“):

  Vorher erkennbar (am Signaltag bekannt → mögliche Filter):
    eng          Stop enger als 1 ATR                   weit         Stop weiter als 2,5 ATR
    momentum     Vormomentum über +25 %                  unruhig      ATR über 5 % des Kurses
    markt_rot    Marktlage am Signaltag rot              index_u200   Index unter seiner 200-Tage-Linie
    sektor_u50   Sektor-ETF unter seiner 50-Tage-Linie   zahlen_bald  Quartalszahlen ≤ 20 Handelstage nach dem Signal
    spaet        Signal erst nach einem Scan-Ausfall erkannt
  Erst hinterher sichtbar (Erklärung, kein Filter):
    markt_fiel   Index in der Haltezeit ≤ −3 %           sektor_fiel  Sektor-ETF in der Haltezeit ≤ −4 %
    eigenschwach Aktie ≥ 5 Prozentpunkte schwächer als der Index
    luecke       über den Stop gerissen (R < −1,15)     schnell      Stop in den ersten 3 Tagen
    zahlen       Quartalszahlen fielen in die Haltezeit

Der Lern-Bericht (report) vergleicht je „vorher erkennbarem“ Merkmal das Ø-Ergebnis mit und ohne Merkmal. Ein Merkmal
wird erst zum Kandidaten, wenn es genug Fälle hat, deutlich schlechter ist UND in der früheren wie der späteren Hälfte
der Trades in dieselbe Richtung zeigt. Kandidaten ändern die Regel NIE automatisch: Nächster Schritt ist der Backtest über
2008–2026 (13.241 Trades) mit Zeit-Trennung, danach ein Schattentest auf künftigen Signalen – und erst dann, mit Freigabe,
der Scanner. Merkmale, die schon getestet und verworfen wurden, stehen in TESTED und werden nicht erneut vorgeschlagen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRE = {"eng": "Stop enger als 1 ATR", "weit": "Stop weiter als 2,5 ATR", "momentum": "Vormomentum über +25 %",
       "unruhig": "Schwankung (ATR) über 5 % des Kurses", "markt_rot": "Marktlage am Signaltag rot",
       "index_u200": "Index unter der 200-Tage-Linie", "sektor_u50": "Sektor unter der 50-Tage-Linie",
       "zahlen_bald": "Quartalszahlen ≤ 20 Handelstage nach dem Signal", "spaet": "Signal verspätet erkannt (Scan-Ausfall)",
       # Kombinationen „11 Kriterien + X“ (Kontext am Signaltag, snapshots.context) – unbekannt bleibt unbekannt
       "ins_kauf": "Insider-Kauf in den 90 Tagen davor", "ins_cluster": "Mehrere Insider kauften (≥ 2)",
       "ins_gezielt": "Gezielter Insider-Kauf (kein Routine-Käufer)", "analyst_kauf": "Analysten im Schnitt „Kaufen“ (≤ 2,0)",
       "analyst_ziel": "Kursziel ≥ 25 % über dem Kurs", "news_neg": "Schlagzeilen überwiegend negativ",
       "sektor_rot": "Sektor in roter Lage", "guenstig": "KGV unter 15"}
# Vorab festgelegte Paare (nur diese – je mehr Paare, desto mehr Zufallsfunde)
PAIRS = (("ins_kauf", "index_u200"), ("analyst_ziel", "momentum"), ("ins_kauf", "analyst_kauf"), ("guenstig", "markt_rot"))
FDR_Q = 0.10                        # Benjamini-Hochberg: höchstens ~10 % Zufallsfunde unter den Kandidaten
POST = {"markt_fiel": "Gesamtmarkt fiel in der Haltezeit", "sektor_fiel": "Sektor fiel in der Haltezeit",
        "eigenschwach": "Aktie deutlich schwächer als der Markt", "luecke": "Kurslücke über den Stop",
        "schnell": "Stop schon in den ersten 3 Tagen", "zahlen": "Quartalszahlen in der Haltezeit"}
# Schon geprüft (Forschung 2026) – nicht erneut vorschlagen, sondern mit dem Ergebnis anzeigen
# Historischer Lern-Test 01.11.2026 (research/reversal/learn.py, 13.241 B60-Trades 2008–2026, Stress-Kosten):
TESTED = {"unruhig": "2008–26: unruhige Aktien (ATR > 5 %) sogar besser (+0,19 R gegen −0,07 R) – kein Filter",
          "index_u200": "2008–26: Markt unter 200-Tage-Linie sogar besser (+0,18 R gegen −0,15 R) – kein Filter",
          "eng": "2008–26: Stop < 1 ATR nicht beständig schlechter (Holdout besser) – kein Filter",
          "zahlen_bald": "Quartalszahlen-Filter (N1, Ultimate 10/2026): nicht bestanden",
          "momentum": "2008–26: in allen Zeiträumen schwächer (−0,14 R gegen −0,01 R); die Regel nimmt bei vollem Depot "
                      "schon das schwächere Vormomentum zuerst – als eigener Filter knapp nicht bestanden"}
INDEX = {"us": "^GSPC", "europe": "^STOXX", "asia": "^GSPC"}
SECTOR_ETF = {"Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Consumer Cyclical": "XLY",
              "Consumer Defensive": "XLP", "Energy": "XLE", "Industrials": "XLI", "Basic Materials": "XLB",
              "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC"}
MIN_N, MIN_DIFF = 10, 0.25          # Kandidat: je ≥ 10 Fälle mit/ohne, Ø-Ergebnis mindestens 0,25 R schlechter


def _close(df) -> pd.Series | None:
    if df is None or getattr(df, "empty", True) or "Close" not in df:
        return None
    c = df["Close"].dropna()
    return c if len(c) else None


def _at(c: pd.Series, d) -> int:
    return int(c.index.searchsorted(pd.Timestamp(d), side="right") - 1)


def _ret(c: pd.Series | None, a, b) -> float | None:
    if c is None:
        return None
    i, j = _at(c, a), _at(c, b)
    if i < 0 or j <= i:
        return None
    return float(c.iloc[j] / c.iloc[i] - 1)


def _below(c: pd.Series | None, d, n: int) -> bool | None:
    if c is None:
        return None
    i = _at(c, d)
    if i < n - 1:
        return None
    return bool(c.iloc[i] < c.iloc[i - n + 1: i + 1].mean())


def _bdays(a, b) -> int:
    try:
        return int(np.busday_count(pd.Timestamp(a).date(), pd.Timestamp(b).date()))
    except Exception:
        return 99


def explain(sn: dict, stock=None, ctx: dict | None = None) -> dict:
    """Ursachen eines abgeschlossenen Treffers. stock = Tageskerzen der Aktie, ctx = Index-/Sektor-Kerzen (Ticker → DataFrame)."""
    g, x, ctx = sn["sig"], sn.get("exit") or {}, ctx or {}
    d, end = sn["d"], x.get("seen") or sn["d"]
    fl = g.get("flags") or {}
    idx = _close(ctx.get(INDEX.get(g.get("region") or "us", "^GSPC")))
    sec = _close(ctx.get(SECTOR_ETF.get(g.get("sector") or "", "")))
    st = _close(stock)
    pre = {
        "eng": g.get("stop_atr") is not None and g["stop_atr"] < 1.0,
        "weit": g.get("stop_atr") is not None and g["stop_atr"] > 2.5,
        "momentum": g.get("mom") is not None and g["mom"] > 0.25,
        "unruhig": (fl.get("atr_pct") or 0) > 0.05,
        "markt_rot": (g.get("market") or {}).get("tone") == "red",
        "index_u200": _below(idx, d, 200),
        "sektor_u50": _below(sec, d, 50),
        "zahlen_bald": bool(g.get("earn")) and 0 <= _bdays(d, g["earn"]) <= 20,
        "spaet": (sn.get("late") or 0) >= 2,
    }
    c = g.get("ctx") or {}
    ins = c.get("ins")
    nz = lambda v, f: None if v is None else bool(f(v))
    pre.update({
        "ins_kauf": None if ins is None else ins.get("n", 0) > 0,
        "ins_cluster": None if ins is None else ins.get("buyers", 0) >= 2,
        "ins_gezielt": None if ins is None else ins.get("opp", 0) > 0,
        "analyst_kauf": nz(c.get("an_m"), lambda v: v <= 2.0),
        "analyst_ziel": nz(c.get("tgt_up"), lambda v: v >= 0.25),
        "news_neg": nz(c.get("news"), lambda v: v == -1),
        "sektor_rot": nz(c.get("sec_tone"), lambda v: v == "red"),
        "guenstig": nz(c.get("pe"), lambda v: 0 < v < 15),
    })
    ri, rs, rk = _ret(idx, d, end), _ret(sec, d, end), _ret(st, d, end)
    r = x.get("r")
    post = {
        "markt_fiel": ri is not None and ri <= -0.03,
        "sektor_fiel": rs is not None and rs <= -0.04,
        "eigenschwach": rk is not None and ri is not None and rk - ri <= -0.05,
        "luecke": x.get("res") == "stop" and r is not None and r < -1.15,
        "schnell": x.get("res") == "stop" and (x.get("days") or 99) <= 3,
        "zahlen": bool(g.get("earn")) and d <= g["earn"] <= end,
    }
    return {"pre": sorted(k for k, v in pre.items() if v), "post": sorted(k for k, v in post.items() if v),
            "unk": sorted(k for k, v in pre.items() if v is None),
            "idx": None if ri is None else round(ri, 4), "sec": None if rs is None else round(rs, 4),
            "stock": None if rk is None else round(rk, 4)}


MAX_NEWS = 10                       # Schlagzeilen-Suche für höchstens so viele Verlierer je Lauf (Laufzeit)


def headlines(sn: dict, name: str, rss=None) -> dict:
    """Was nannten die Medien in der Haltezeit als Grund für die Kursbewegung? (Google News, wie bei den Quartalszahlen)"""
    from . import earnings as E
    from . import earnwhy as EW
    rss = rss or E._rss
    d, end = pd.Timestamp(sn["d"]), pd.Timestamp((sn.get("exit") or {}).get("seen") or sn["d"])
    words = E._words(name or sn["t"], sn["t"])
    q = f"{words[0]} stock OR shares after:{(d - pd.Timedelta(days=1)).date()} before:{(end + pd.Timedelta(days=2)).date()}"
    heads = EW._move_titles(rss(q), words)
    return {"news": EW.tags(heads), "head": heads[:3]}


def analyze(snaps: dict, data: dict | None = None, ctx: dict | None = None, names: dict | None = None, rss=None) -> int:
    """Ergänzt „why“ für abgeschlossene Treffer, die noch keine Ursachensuche haben; bei Verlierern zusätzlich die
    Schlagzeilen der Haltezeit (höchstens MAX_NEWS je Lauf, der Rest im nächsten). Rückgabe: Anzahl neu untersucht."""
    n = news = 0
    for sn in snaps.values():
        x = sn.get("exit") or {}
        if sn.get("k") != "hit" or x.get("r") is None:
            continue
        try:
            if "why" not in sn:
                sn["why"] = explain(sn, (data or {}).get(sn["t"]), ctx)
                n += 1
            if x["r"] <= 0 and "news" not in sn["why"] and news < MAX_NEWS:
                news += 1
                sn["why"].update(headlines(sn, (names or {}).get(sn["t"]) or sn["t"], rss))
        except Exception as exc:                     # darf den Scan nie stoppen
            print("Ursachensuche Trade:", sn.get("t"), repr(exc)[:100])
    return n


def _mean(v):
    return round(float(np.mean(v)), 3) if v else None


def report(snaps: dict) -> dict:
    """Lern-Bericht: häufigste Gründe bei Verlusten und vorher erkennbare Merkmale mit/ohne – inkl. Zeit-Trennung."""
    rows = sorted([sn for sn in snaps.values() if sn.get("k") == "hit" and "why" in sn and (sn.get("exit") or {}).get("r") is not None],
                  key=lambda s: s["d"])
    n = len(rows)
    out = {"n": n, "min_n": MIN_N, "losses": sum(s["exit"]["r"] <= 0 for s in rows), "avg_r": _mean([s["exit"]["r"] for s in rows]),
           "post": [], "pre": [], "recent": []}
    loss = [s for s in rows if s["exit"]["r"] <= 0]
    win = [s for s in rows if s["exit"]["r"] > 0]
    for k, lbl in POST.items():                      # Erklärungen: bei Verlusten häufiger als bei Gewinnen?
        fl = sum(k in s["why"]["post"] for s in loss)
        fw = sum(k in s["why"]["post"] for s in win)
        if fl or fw:
            out["post"].append({"k": k, "l": lbl, "loss": fl, "loss_pct": round(fl / len(loss), 3) if loss else None,
                                "win": fw, "win_pct": round(fw / len(win), 3) if win else None})
    out["post"].sort(key=lambda p: -(p["loss_pct"] or 0))
    half = n // 2
    feats = list(PRE.items()) + [(f"{a}+{b}", f"{PRE[a]} UND {PRE[b]}") for a, b in PAIRS]
    has = lambda s, k: all(x in s["why"]["pre"] for x in k.split("+"))
    unk = lambda s, k: any(x in s["why"].get("unk", []) for x in k.split("+"))
    for k, lbl in feats:
        known = [s for s in rows if not unk(s, k)]
        w = [s["exit"]["r"] for s in known if has(s, k)]
        wo = [s["exit"]["r"] for s in known if not has(s, k)]
        if not w:
            continue
        diff = (np.mean(w) - np.mean(wo)) if wo else None
        halves = []
        for part in (rows[:half], rows[half:]):
            a = [s["exit"]["r"] for s in part if has(s, k)]
            b = [s["exit"]["r"] for s in part if not has(s, k) and not unk(s, k)]
            halves.append(round(float(np.mean(a) - np.mean(b)), 3) if a and b else None)
        enough = len(w) >= MIN_N and len(wo) >= MIN_N
        live_bad = enough and diff is not None and diff <= -MIN_DIFF and all(h is not None and h < 0 for h in halves)
        live_good = enough and diff is not None and diff >= MIN_DIFF and all(h is not None and h > 0 for h in halves)
        pval = _pvalue(w, wo) if enough else None
        if k in TESTED:                              # historisch geprüft – live trotzdem beobachtet: widerspricht live der Forschung?
            status = "live auffällig – erneut prüfen" if live_bad else "schon getestet"
        elif len(w) < MIN_N or len(wo) < MIN_N:
            status = "zu wenig Fälle"
        elif live_bad:
            status = "Kandidat – Backtest"
        elif live_good:
            status = "Verstärker – Backtest"
        else:
            status = "kein Hinweis"
        out["pre"].append({"k": k, "l": lbl, "n": len(w), "r": _mean(w), "r_ohne": _mean(wo),
                           "diff": None if diff is None else round(float(diff), 3), "halves": halves, "status": status, "p": pval,
                           "note": TESTED.get(k)})
    _bh(out["pre"])                                  # Mehrfachtest-Korrektur: Kandidat nur, wenn auch nach BH nicht zufällig
    for p in out["pre"]:
        if p["status"] in ("Kandidat – Backtest", "Verstärker – Backtest", "live auffällig – erneut prüfen") and not (p.get("q") is not None and p["q"] <= FDR_Q):
            p["status"] = "Hinweis – noch zufallsverdächtig"
    flagged = ("Kandidat – Backtest", "Verstärker – Backtest", "live auffällig – erneut prüfen")
    out["pre"].sort(key=lambda p: (p["status"] not in flagged, p["diff"] if p["diff"] is not None else 9))
    out["candidates"] = [p["k"] for p in out["pre"] if p["status"] in flagged]
    nt: dict = {}                                    # Schlagzeilen-Gründe bei Verlusten (Ausblick, Analysten, Marge …)
    for s in loss:
        for t in s["why"].get("news", []):
            nt[t] = nt.get(t, 0) + 1
    out["news"] = sorted(([k, v] for k, v in nt.items()), key=lambda kv: -kv[1])[:6]
    out["news_n"] = sum("news" in s["why"] for s in loss)
    pre_stat = {p["k"]: p for p in out["pre"]}
    for s in sorted(loss, key=lambda s: s["exit"].get("seen") or s["d"], reverse=True)[:8]:
        out["recent"].append({"t": s["t"], "d": s["d"], "r": s["exit"]["r"], "res": s["exit"]["res"],
                              "pre": [PRE[k] for k in s["why"]["pre"]], "post": [POST[k] for k in s["why"]["post"]],
                              "news": s["why"].get("news", []), "head": (s["why"].get("head") or [None])[0],
                              "lesson": lesson(s["why"], pre_stat)})
    return out


def _pvalue(a: list, b: list) -> float | None:
    """Zweiseitiger p-Wert für den Unterschied der Mittelwerte (Welch, Normalnäherung – genug für ≥ 10 Fälle je Seite)."""
    from math import erf, sqrt
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = np.var(a, ddof=1) / len(a), np.var(b, ddof=1) / len(b)
    if va + vb <= 0:
        return 0.0 if np.mean(a) != np.mean(b) else 1.0
    z = abs(np.mean(a) - np.mean(b)) / sqrt(va + vb)
    return round(float(2 * (1 - 0.5 * (1 + erf(z / sqrt(2))))), 5)


def _bh(rows: list[dict]) -> None:
    """Benjamini-Hochberg q-Werte über alle getesteten Merkmale (setzt row["q"])."""
    ps = sorted([(r["p"], i) for i, r in enumerate(rows) if r.get("p") is not None])
    m, prev = len(ps), 1.0
    for rank in range(m, 0, -1):
        p, i = ps[rank - 1]
        prev = min(prev, p * m / rank)
        rows[i]["q"] = round(prev, 5)


def lesson(why: dict, pre_stat: dict) -> str:
    """Was lehrt dieser Verlust? Vorher sichtbare Merkmale werden mit ihrer Bilanz bewertet, sonst: nicht vermeidbar."""
    if why.get("pre"):
        parts = []
        for k in why["pre"]:
            p = pre_stat.get(k) or {}
            if p.get("status") == "Verstärker – Backtest":
                parts.append(f"{PRE[k]}: mit diesem Merkmal liefen Trades bisher besser – wird geprüft")
            elif p.get("status") in ("Kandidat – Backtest", "live auffällig – erneut prüfen"):
                parts.append(f"{PRE[k]}: schadet bisher beständig – wird als Filter geprüft")
            elif k in TESTED:
                parts.append(f"{PRE[k]}: über 18 Jahre kein beständiger Nachteil – kein Filter")
            else:
                parts.append(f"{PRE[k]}: wird beobachtet ({p.get('n', 0)} Fälle)")
        return " · ".join(parts)
    if why.get("post") or why.get("news"):
        return "Vorher nicht erkennbar – normales Risiko, der Stop hat den Verlust begrenzt"
    return "Kein klarer Grund – normaler Verlust, wie er bei rund 2 von 3 Trades vorkommt"
