"""Sparplan × Marktampel (23.11.2026): Bringt Nachkaufen bei roter Ampel mehr als stur monatlich? – VORAB FESTGELEGT.

S&P 500 und Nasdaq 100 (Kursindex + 1,8 % bzw. 0,8 % Dividenden p. a. grob), monatlich 100 € ab 1996 (nach 200 Tagen Vorlauf).
  A  stur: jeden Monat 100 € kaufen
  B  Reserve: bei Ampel Grün nur 50 € kaufen, 50 € in Reserve (0 % Zins, ehrlich-vorsichtig: 2 % Zins als Variante B2);
     bei Orange/Rot die ganze Reserve + 100 € kaufen
  C  Bonus ohne Reserve-Warten: jeden Monat 100 €, bei Rot zusätzlich 100 € (mehr eingezahlt → Vergleich je eingezahltem Euro)
Kennzahl: Endvermögen je eingezahltem Euro (Ende 10/2026), dazu je Start-Jahrzehnt. Bestanden für B: besser als A in
mindestens 2 von 3 Start-Jahrzehnten (1996, 2006, 2016) UND gesamt.

    python tools/research/dca_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def run(price, lv, start, mode, rate=0.0):
    p = price[price.index >= start]
    m = p.resample("ME").last()
    l = lv.reindex(m.index, method="ffill")
    units, paid, res = 0.0, 0.0, 0.0
    for d, px in m.items():
        g = l.get(d)
        res *= (1 + rate) ** (1 / 12)
        if mode == "A":
            amt, paid = 100.0, paid + 100
        elif mode == "B":
            paid += 100
            if g is not None and g >= 3:
                amt, res = 50.0, res + 50
            elif g is not None and g <= 1:
                amt, res = 100 + res, 0.0
            else:
                amt = 100.0
        else:
            amt = 100.0 + (100.0 if g is not None and g == 0 else 0.0)
            paid += amt
        units += amt / px
    return (units * m.iloc[-1] + res) / paid


def main():
    from profit_study import market_levels
    lv, h = market_levels()
    for name, t, div in (("S&P 500", "^GSPC", 0.018), ("Nasdaq 100", "^NDX", 0.008)):
        c = h[t]["Close"]
        tr = c * (1 + div) ** ((c.index - c.index[0]).days / 365.25)
        print(f"\n===== {name} (mit {div * 100:.1f} % Dividende p. a. grob) – Endvermögen je eingezahltem Euro =====")
        wins = 0
        for st in ("1996-01-01", "2006-01-01", "2016-01-01"):
            a, b, b2, cc = (run(tr, lv, st, "A"), run(tr, lv, st, "B"), run(tr, lv, st, "B", 0.02), run(tr, lv, st, "C"))
            wins += b > a
            print(f"  Start {st[:4]}:  A stur {a:.2f} € · B Reserve {b:.2f} € (mit 2 % Zins {b2:.2f} €) · C Bonus bei Rot {cc:.2f} €")
        print(f"  → B besser als A in {wins} von 3 Start-Jahrzehnten: {'BESTANDEN' if wins >= 2 else 'nicht bestanden'}")


if __name__ == "__main__":
    main()
