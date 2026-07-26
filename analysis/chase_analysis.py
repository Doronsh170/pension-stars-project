#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2 - "Chasing returns" simulation.

For every category and every signal year Y we:
  1. Find the fund that ranked #1 (highest annual return) in year Y.
  2. Track that same fund (by FUND_ID) in the following years Y+1, Y+2, Y+3,
     recording its return and its rank within the same category each year.

We then ask whether last year's winner keeps winning (persistence) or drifts
back toward the pack (mean reversion), and we simulate the money outcome of a
saver who chases last year's #1 versus one who simply holds the category
average.

Inputs : analysis/annual_returns.csv  (from build_annual.py)
Outputs: analysis/events.csv          (one row per signal-year winner + follow-ups)
         analysis/category_summary.csv (per-category aggregates)
         analysis/strategy_summary.csv (chase vs stay money outcome)
         console report
"""
import csv, os, statistics
from collections import defaultdict

from source import FAMILIES, TRACK_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, "annual_returns.csv")

MIN_FUNDS = 8      # a category needs at least this many complete funds in a year
                   # for a "#1" ranking to be meaningful
HORIZONS = (1, 2, 3)
FIRST_YEAR = 2010           # study focuses on signal years from 2010 onward
LAST_COMPLETE_YEAR = 2025   # 2026 is only a partial year in the raw data

# The comparison group is the fund family a saver picks (study fund, provident,
# investment provident, child savings) crossed with the fund's investment track
# (`מסלול ממופה`). Two funds only compete for the same money if they sit in the
# same cell, so the ranking never rewards a fund merely for carrying more equity
# than its rivals.

# category string = "<family> | <track>", matching build_annual.py.
CATEGORIES = {
    "gemel": [f"{fam} | {track}" for fam in FAMILIES for track in TRACK_ORDER],
}


def load():
    rows = list(csv.DictReader(open(IN, encoding="utf-8-sig")))
    # keep only complete (12-month) fund-years
    data = defaultdict(dict)   # (domain, category) -> year -> list of (fid, name, ret)
    for r in rows:
        if int(r["n_months"]) != 12:
            continue
        y = int(r["year"])
        if y < FIRST_YEAR or y > LAST_COMPLETE_YEAR:
            continue
        key = (r["domain"], r["category"])
        data[key].setdefault(y, []).append(
            (r["fund_id"], r["fund_name"], float(r["annual_return"])))
    return data


def load_assets():
    """(fund_id, year) -> December total assets, in millions of shekels."""
    out = {}
    for r in csv.DictReader(open(IN, encoding="utf-8-sig")):
        if r["assets_end"]:
            out[(r["fund_id"], int(r["year"]))] = float(r["assets_end"])
    return out


def ranked(funds):
    """Return list sorted best->worst, and a dict fid -> (rank, return, name)."""
    s = sorted(funds, key=lambda x: -x[2])
    info = {}
    for i, (fid, name, ret) in enumerate(s, start=1):
        info[fid] = (i, ret, name)
    return s, info


def percentile(rank, n):
    """Top fund -> 100, bottom fund -> 0."""
    if n <= 1:
        return None
    return (n - rank) / (n - 1) * 100.0


def main():
    data = load()
    assets = load_assets()

    events = []           # detailed rows
    # pooled follow-up percentiles by horizon (for the persistence question)
    pooled = {k: [] for k in HORIZONS}
    pooled_beatmed = {k: [] for k in HORIZONS}   # 1 if winner beat category median that year
    pooled_topq = {k: [] for k in HORIZONS}
    pooled_stillno1 = {k: [] for k in HORIZONS}
    pooled_bottomhalf = {k: [] for k in HORIZONS}

    cat_rows = []
    strat_rows = []

    for domain in ("gemel",):
        for cat in CATEGORIES[domain]:
            key = (domain, cat)
            years = data.get(key, {})
            valid_years = sorted(y for y, f in years.items() if len(f) >= MIN_FUNDS)
            if len(valid_years) < 3:
                continue

            cat_pct = {k: [] for k in HORIZONS}
            cat_beatmed = {k: [] for k in HORIZONS}

            for Y in valid_years:
                s, info = ranked(years[Y])
                win_fid, win_name, win_ret = s[0]
                ev = {
                    "domain": domain, "category": cat, "signal_year": Y,
                    "winner_fund_id": win_fid, "winner_name": win_name,
                    "signal_return": round(win_ret, 2), "signal_n": len(s),
                    "winner_assets": assets.get((win_fid, Y), ""),
                }
                for k in HORIZONS:
                    Yk = Y + k
                    fk = years.get(Yk)
                    if not fk or len(fk) < MIN_FUNDS:
                        ev[f"y{k}_year"] = Yk if fk else ""
                        ev[f"y{k}_status"] = "no_data"
                        continue
                    _, infok = ranked(fk)
                    n = len(fk)
                    med = statistics.median([r for _, _, r in fk])
                    if win_fid in infok:
                        rank, ret, _ = infok[win_fid]
                        pct = percentile(rank, n)
                        ev[f"y{k}_year"] = Yk
                        ev[f"y{k}_status"] = "present"
                        ev[f"y{k}_return"] = round(ret, 2)
                        ev[f"y{k}_rank"] = rank
                        ev[f"y{k}_n"] = n
                        ev[f"y{k}_percentile"] = round(pct, 1)
                        pooled[k].append(pct)
                        cat_pct[k].append(pct)
                        beat = 1 if ret > med else 0
                        pooled_beatmed[k].append(beat)
                        cat_beatmed[k].append(beat)
                        pooled_topq[k].append(1 if rank <= n / 4.0 else 0)
                        pooled_stillno1[k].append(1 if rank == 1 else 0)
                        pooled_bottomhalf[k].append(1 if rank > n / 2.0 else 0)
                    else:
                        ev[f"y{k}_year"] = Yk
                        ev[f"y{k}_status"] = "absent"   # fund merged/closed
                        ev[f"y{k}_n"] = n
                events.append(ev)

            # --- money simulation for this category ---
            # Chase: each year Y (from 2nd valid year on) hold last year's winner,
            # earn its return this year. Stay: hold the equal-weight category average.
            chase_mult, stay_mult, best_mult = 1.0, 1.0, 1.0
            sim_years = []
            all_years = sorted(y for y in years if len(years[y]) >= MIN_FUNDS)
            for i in range(1, len(all_years)):
                prevY = all_years[i - 1]
                Y = all_years[i]
                if Y != prevY + 1:
                    # only chain consecutive years
                    continue
                s_prev, _ = ranked(years[prevY])
                win_fid = s_prev[0][0]
                _, info = ranked(years[Y])
                this_year = years[Y]
                avg_ret = statistics.mean([r for _, _, r in this_year])
                best_ret = max(r for _, _, r in this_year)
                if win_fid in info:
                    chase_ret = info[win_fid][1]
                else:
                    chase_ret = avg_ret   # if winner vanished, fall back to average
                chase_mult *= (1 + chase_ret / 100)
                stay_mult *= (1 + avg_ret / 100)
                best_mult *= (1 + best_ret / 100)
                sim_years.append(Y)
            if sim_years:
                nY = len(sim_years)
                strat_rows.append({
                    "domain": domain, "category": cat,
                    "years": f"{sim_years[0]}-{sim_years[-1]}", "n_years": nY,
                    "chase_total_pct": round((chase_mult - 1) * 100, 1),
                    "stay_total_pct": round((stay_mult - 1) * 100, 1),
                    "chase_annualized_pct": round((chase_mult ** (1 / nY) - 1) * 100, 2),
                    "stay_annualized_pct": round((stay_mult ** (1 / nY) - 1) * 100, 2),
                    "gap_annualized_pp": round(((chase_mult ** (1 / nY)) - (stay_mult ** (1 / nY))) * 100, 2),
                })

            def m(lst):
                return round(statistics.mean(lst), 1) if lst else None
            cat_rows.append({
                "domain": domain, "category": cat,
                "signal_years": len(valid_years),
                "y1_mean_pctile": m(cat_pct[1]), "y1_beat_median_pct": m([x*100 for x in cat_beatmed[1]]),
                "y2_mean_pctile": m(cat_pct[2]),
                "y3_mean_pctile": m(cat_pct[3]),
                "y1_events": len(cat_pct[1]),
            })

    # ---- write events ----
    fields = ["domain", "category", "signal_year", "winner_fund_id", "winner_name",
              "signal_return", "signal_n", "winner_assets"]
    for k in HORIZONS:
        fields += [f"y{k}_year", f"y{k}_status", f"y{k}_return", f"y{k}_rank",
                   f"y{k}_n", f"y{k}_percentile"]
    with open(os.path.join(HERE, "events.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in events:
            w.writerow({k: e.get(k, "") for k in fields})

    with open(os.path.join(HERE, "category_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(cat_rows[0].keys()))
        w.writeheader(); w.writerows(cat_rows)

    with open(os.path.join(HERE, "strategy_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(strat_rows[0].keys()))
        w.writeheader(); w.writerows(strat_rows)

    # ---- console report ----
    print("=" * 70)
    print("POOLED PERSISTENCE OF LAST YEAR'S #1 FUND  (all categories, all years)")
    print("Null hypothesis (no persistence): mean percentile = 50, beat-median = 50%")
    print("=" * 70)
    for k in HORIZONS:
        p = pooled[k]
        if not p:
            continue
        print(f"\nHorizon +{k} year(s):  events={len(p)}")
        print(f"  mean follow-up percentile : {statistics.mean(p):5.1f}   (top=100, bottom=0)")
        print(f"  median follow-up percentile: {statistics.median(p):5.1f}")
        print(f"  beat category median       : {statistics.mean(pooled_beatmed[k])*100:5.1f}%")
        print(f"  still in top quartile      : {statistics.mean(pooled_topq[k])*100:5.1f}%")
        print(f"  still #1                   : {statistics.mean(pooled_stillno1[k])*100:5.1f}%")
        print(f"  fell to BOTTOM half        : {statistics.mean(pooled_bottomhalf[k])*100:5.1f}%")

    print("\n" + "=" * 70)
    print("MONEY OUTCOME: chase last year's #1  vs  hold category average")
    print("=" * 70)
    print(f"{'category':45s} {'yrs':>4} {'chaseCAGR':>9} {'stayCAGR':>8} {'gap(pp)':>7}")
    for s in strat_rows:
        print(f"{(s['domain'][:3]+' '+s['category'])[:45]:45s} {s['n_years']:>4} "
              f"{s['chase_annualized_pct']:>9} {s['stay_annualized_pct']:>8} {s['gap_annualized_pp']:>7}")
    # overall averages of the gap
    gaps = [s["gap_annualized_pp"] for s in strat_rows]
    print(f"\nAverage annualized gap (chase - stay) across categories: {statistics.mean(gaps):+.2f} pp")
    print(f"Categories where chasing WON: {sum(1 for g in gaps if g>0)}/{len(gaps)}")
    print("\nwrote events.csv, category_summary.csv, strategy_summary.csv")


if __name__ == "__main__":
    main()
