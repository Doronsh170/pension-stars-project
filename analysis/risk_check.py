#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robustness check: are the yearly category winners simply the higher-risk funds
(more equity, more volatility)?  If so, the apparent "chasing edge" is a risk
premium harvested in a rising market, not persistence of skill.

Risk proxies (year-end snapshot, size-independent):
  * equity share  = STOCK_MARKET_EXPOSURE / TOTAL_ASSETS * 100
  * volatility     = STANDARD_DEVIATION
We report the winner's within-category percentile on each proxy
(50 = no tilt, 100 = always the riskiest in its category).
"""
import csv, os, statistics
from collections import defaultdict
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SOURCES = [
    ("gemel-net1999-2022.xlsx", "gemel-net1999-2022", "gemel"),
    ("gemel-net2023.xlsx", "gemel-net2023", "gemel"),
    ("2024-2026גמל.xlsx", "file", "gemel"),
    ("pensia-net1999-2022.xlsx", "pensia-net1999-2022", "pension"),
    ("pensia-net2023.xlsx", "pensia-net2023", "pension"),
    ("2024-2026פנסיה.xlsx", "file (1)", "pension"),
]

# (domain,fund_id,year) -> {month: (equity_pct, std)}
risk = defaultdict(dict)
for fname, sheet, domain in SOURCES:
    wb = openpyxl.load_workbook(os.path.join(ROOT, fname), read_only=True, data_only=True)
    ws = wb[sheet]; it = ws.iter_rows(values_only=True); h = list(next(it))
    idx = {x: i for i, x in enumerate(h)}
    se = idx.get('STOCK_MARKET_EXPOSURE'); sd = idx.get('STANDARD_DEVIATION')
    ta = idx.get('TOTAL_ASSETS'); fi = idx['FUND_ID']; pi = idx['REPORT_PERIOD']
    for r in it:
        p = r[pi]
        if not p: continue
        p = str(p); y = int(p[:4]); mo = int(p[4:6])
        eq = None
        if se is not None and ta is not None and r[se] is not None and r[ta] not in (None, 0):
            try: eq = float(r[se]) / float(r[ta]) * 100
            except ZeroDivisionError: eq = None
        std = float(r[sd]) if (sd is not None and r[sd] is not None) else None
        risk[(domain, str(r[fi]), y)][mo] = (eq, std)
    wb.close()

def yearend(domain, fid, y, which):
    d = risk.get((domain, str(fid), y), {})
    for m in range(12, 0, -1):
        if m in d and d[m][which] is not None:
            return d[m][which]
    return None

ann = list(csv.DictReader(open(os.path.join(HERE, "annual_returns.csv"), encoding="utf-8-sig")))
cat_members = defaultdict(list)
for r in ann:
    if int(r["n_months"]) == 12:
        cat_members[(r["domain"], r["category"], int(r["year"]))].append(r["fund_id"])
events = list(csv.DictReader(open(os.path.join(HERE, "events.csv"), encoding="utf-8-sig")))

def pctile(val, pool):
    pool = [x for x in pool if x is not None]
    if val is None or len(pool) < 4: return None
    below = sum(1 for x in pool if x < val)
    return below / (len(pool) - 1) * 100

per_cat = defaultdict(lambda: {"eq": [], "vol": []})
for e in events:
    dom, cat, Y = e["domain"], e["category"], int(e["signal_year"])
    if Y < 2008: continue
    members = cat_members.get((dom, cat, Y), [])
    eq_pool = [yearend(dom, m, Y, 0) for m in members]
    vol_pool = [yearend(dom, m, Y, 1) for m in members]
    eqp = pctile(yearend(dom, e["winner_fund_id"], Y, 0), eq_pool)
    volp = pctile(yearend(dom, e["winner_fund_id"], Y, 1), vol_pool)
    if eqp is not None: per_cat[(dom, cat)]["eq"].append(eqp)
    if volp is not None: per_cat[(dom, cat)]["vol"].append(volp)

print("WINNER's within-category RISK percentile (50 = no tilt, 100 = riskiest)")
print(f"{'domain':7s} {'category':38s} {'nEq':>3} {'equity%ile':>10} {'nVol':>4} {'vol%ile':>8}")
alleq, allvol = [], []
for (dom, cat), d in per_cat.items():
    eq = d["eq"]; vol = d["vol"]
    alleq += eq; allvol += vol
    eqm = f"{statistics.mean(eq):.0f}" if eq else "-"
    volm = f"{statistics.mean(vol):.0f}" if vol else "-"
    print(f"{dom:7s} {cat[:38]:38s} {len(eq):>3} {eqm:>10} {len(vol):>4} {volm:>8}")
print("-"*72)
print(f"{'POOLED':7s} {'':38s} {len(alleq):>3} {statistics.mean(alleq):>10.0f} "
      f"{len(allvol):>4} {statistics.mean(allvol):>8.0f}")
print(f"\nWinner in top-third of equity exposure in its category: "
      f"{100*sum(1 for x in alleq if x>=66.7)/len(alleq):.0f}% of years")
print(f"Winner in top-third of volatility in its category:      "
      f"{100*sum(1 for x in allvol if x>=66.7)/len(allvol):.0f}% of years")

with open(os.path.join(HERE, "risk_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["domain", "category", "n_eq", "winner_equity_pctile",
                "n_vol", "winner_vol_pctile"])
    for (dom, cat), d in per_cat.items():
        eq, vol = d["eq"], d["vol"]
        w.writerow([dom, cat, len(eq),
                    round(statistics.mean(eq), 1) if eq else "",
                    len(vol), round(statistics.mean(vol), 1) if vol else ""])
    w.writerow(["POOLED", "", len(alleq), round(statistics.mean(alleq), 1),
                len(allvol), round(statistics.mean(allvol), 1)])
print("wrote risk_summary.csv")
