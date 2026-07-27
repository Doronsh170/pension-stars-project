#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 3b - Robustness checks for the two central claims.

All confidence intervals over category-year events use a calendar-year cluster
bootstrap. Categories observed in the same market year share the same market
regime and therefore are not treated as independent draws.

Inputs : annual_returns.csv, annual_gap_events.csv, strategy_summary.csv
Output : console report + robustness_summary.csv
"""
import collections
import csv
import os
import random
import statistics

import chase_analysis as ca
from source import FAMILY_LABEL

HERE = os.path.dirname(os.path.abspath(__file__))
B = 20000


def family(domain, cat):
    """The saver-facing name of the fund family the category belongs to."""
    return FAMILY_LABEL.get(cat.split(" | ")[0], cat.split(" | ")[0])


def clustered_bootstrap(rows, value_key, cluster_key, B=20000, seed=0, h0=None):
    """Observation-weighted mean; full calendar-year clusters are resampled.

    Category-years inside one market year are not independent observations.
    Resampling whole years keeps the effective sample size honest.
    """
    groups = collections.defaultdict(list)
    for row in rows:
        v = row.get(value_key, "")
        if v in (None, ""):
            continue
        groups[int(row[cluster_key])].append(float(v))
    clusters = sorted(groups)
    values = [x for c in clusters for x in groups[c]]
    if len(clusters) < 2 or len(values) < 2:
        return None
    rnd = random.Random(20260726 + seed)
    stats = [(sum(groups[c]), len(groups[c])) for c in clusters]
    boots = []
    for _ in range(B):
        total, n = 0.0, 0
        for _ in range(len(stats)):
            s, k = stats[rnd.randrange(len(stats))]
            total += s
            n += k
        boots.append(total / n)
    boots.sort()
    result = {
        "n": len(values),
        "clusters": len(clusters),
        "estimate": statistics.mean(values),
        "ci_low": boots[int(0.025 * B)],
        "ci_high": boots[int(0.975 * B)],
    }
    if h0 is not None:
        frac_le = sum(1 for x in boots if x <= h0) / B
        frac_ge = sum(1 for x in boots if x >= h0) / B
        result["p_vs_null"] = min(1.0, 2 * min(frac_le, frac_ge))
    return result


def collect_persistence():
    """Gather follow-up outcomes with their follow-up calendar year."""
    data = ca.load()
    persist = {k: [] for k in (1, 2, 3)}
    persist_stress = {k: [] for k in (1, 2, 3)}
    beatmed = {k: [] for k in (1, 2, 3)}
    still1 = {k: [] for k in (1, 2, 3)}
    rand1 = {k: [] for k in (1, 2, 3)}

    for domain in ("gemel",):
        for cat in ca.CATEGORIES[domain]:
            years = data.get((domain, cat), {})
            valid = sorted(y for y, funds in years.items() if len(funds) >= ca.MIN_FUNDS)
            if len(valid) < 3:
                continue
            for signal_year in valid:
                ranked_signal, _ = ca.ranked(years[signal_year])
                winner = ranked_signal[0][0]
                for k in (1, 2, 3):
                    follow_year = signal_year + k
                    follow_funds = years.get(follow_year)
                    if not follow_funds or len(follow_funds) < ca.MIN_FUNDS:
                        continue
                    _, info = ca.ranked(follow_funds)
                    n = len(follow_funds)
                    median_return = statistics.median([r for _, _, r in follow_funds])
                    if winner in info:
                        rank, ret, _ = info[winner]
                        pct = ca.percentile(rank, n)
                        persist[k].append({"follow_year": follow_year, "value": pct})
                        persist_stress[k].append({"follow_year": follow_year, "value": pct})
                        beatmed[k].append({"follow_year": follow_year,
                                           "value": 100.0 if ret > median_return else 0.0})
                        still1[k].append(1 if rank == 1 else 0)
                        rand1[k].append(1.0 / n)
                    else:
                        persist_stress[k].append({"follow_year": follow_year, "value": 0.0})
    return persist, persist_stress, beatmed, still1, rand1


def load_gap_events():
    """Load the category-year gaps emitted by chase_analysis.py."""
    path = os.path.join(HERE, "annual_gap_events.csv")
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        cat = r["category"]
        fam = family(r["domain"], cat)
        track = cat.split(" | ")[1] if " | " in cat else cat
        rows.append({
            "family": fam,
            "label": f"{fam} · {track}",
            "follow_year": int(r["follow_year"]),
            "gap": float(r["gap_pp"]),
            "vanished": str(r["winner_vanished"]).strip().lower() in ("1", "true", "yes"),
        })
    return rows


def load_excluded_cagr_summary():
    rows = list(csv.DictReader(open(os.path.join(HERE, "strategy_summary.csv"),
                                    encoding="utf-8-sig")))
    values = [float(r["gap_annualized_ex_pp"])
              for r in rows if r.get("gap_annualized_ex_pp", "") not in ("", None)]
    return values


def main():
    persist, persist_stress, beatmed, still1, rand1 = collect_persistence()
    diffs = load_gap_events()
    out = []
    seed = 0

    def run_boot(rows, h0):
        nonlocal seed
        result = clustered_bootstrap(rows, "value", "follow_year", B=B, seed=seed, h0=h0)
        seed += 1
        return result

    def append_result(test, result, null, decimals):
        out.append({
            "test": test,
            "n": result["n"],
            "clusters": result["clusters"],
            "estimate": round(result["estimate"], decimals),
            "ci_low": round(result["ci_low"], decimals),
            "ci_high": round(result["ci_high"], decimals),
            "p_vs_null": round(result.get("p_vs_null", 0), 4),
            "null": null,
        })

    print("=" * 78)
    print("Q1  PERSISTENCE — follow-up placement of last year's #1 (null = 50)")
    print("=" * 78)
    print(f"{'horizon':8s} {'n':>4} {'years':>5} {'mean':>6} {'95% interval':>18} {'p':>8}")
    for k in (1, 2, 3):
        result = run_boot(persist[k], 50)
        sig = "above 50" if result["ci_low"] > 50 else "crosses 50"
        print(f"+{k} year  {result['n']:>4} {result['clusters']:>5} {result['estimate']:>6.1f}  "
              f"[{result['ci_low']:>6.1f},{result['ci_high']:>6.1f}]  "
              f"{result['p_vs_null']:>7.3f}  {sig}")
        append_result(f"persistence_pctile_y{k}", result, 50, 1)

    print("\n  beat category median (null = 50%):")
    for k in (1, 2, 3):
        result = run_boot(beatmed[k], 50)
        print(f"   +{k}y: {result['estimate']:>5.1f}%  "
              f"[{result['ci_low']:>5.1f},{result['ci_high']:>5.1f}]  "
              f"p={result['p_vs_null']:.3f}  "
              f"(n={result['n']}, years={result['clusters']})")
        append_result(f"beat_median_y{k}", result, 50, 1)

    print("\n  still #1 vs random baseline (descriptive only):")
    for k in (1, 2, 3):
        obs = statistics.mean(still1[k]) * 100
        base = statistics.mean(rand1[k]) * 100
        print(f"   +{k}y: observed {obs:.1f}% vs random {base:.1f}% (n={len(still1[k])})")

    print("\n  SURVIVORSHIP stress — vanished winner scored at the bottom:")
    for k in (1, 2, 3):
        result = run_boot(persist_stress[k], 50)
        sig = "above 50" if result["ci_low"] > 50 else "crosses 50"
        print(f"   +{k}y: mean {result['estimate']:>5.1f}  "
              f"[{result['ci_low']:>5.1f},{result['ci_high']:>5.1f}]  "
              f"p={result['p_vs_null']:.3f}  ({sig}, n={result['n']}, "
              f"years={result['clusters']})")
        append_result(f"persistence_stress_y{k}", result, 50, 1)

    print("\n" + "=" * 78)
    print("Q2  MONEY — annual chase-minus-stay gap, percentage points (null = 0)")
    print("=" * 78)

    def report(label, rows):
        nonlocal seed
        boot_rows = [{"follow_year": d["follow_year"], "value": d["gap"]} for d in rows]
        if len(boot_rows) < 2:
            print(f"{label:32s} n={len(boot_rows)} (too few)")
            return
        result = clustered_bootstrap(boot_rows, "value", "follow_year", B=B,
                                     seed=seed, h0=0)
        seed += 1
        pos = sum(1 for d in rows if d["gap"] > 0)
        sig = "clear" if (result["ci_low"] > 0 or result["ci_high"] < 0) else "crosses zero"
        print(f"{label:32s} n={result['n']:>3} years={result['clusters']:>2}  "
              f"mean {result['estimate']:+.2f}pp  "
              f"[{result['ci_low']:+.2f},{result['ci_high']:+.2f}]  "
              f"p={result['p_vs_null']:.3f}  {pos}/{result['n']}>0  [{sig}]")
        append_result(f"gap_{label}", result, 0, 2)

    print("-- main (vanished winner falls back to category average) --")
    report("ALL", diffs)
    for fam in FAMILY_LABEL.values():
        rows = [d for d in diffs if d["family"] == fam]
        if rows:
            report(fam, rows)

    print("-- per category (family x track) --")
    for label in sorted({d["label"] for d in diffs}):
        report(label, [d for d in diffs if d["label"] == label])

    print("-- survivorship stress (drop years where the winner had closed) --")
    survivors = [d for d in diffs if not d["vanished"]]
    report("ALL (survivors only)", survivors)

    print("-- year concentration (survivors, gap by follow-up year) --")
    years = sorted({d["follow_year"] for d in survivors})
    contrib = {}
    for year in years:
        gaps = [d["gap"] for d in survivors if d["follow_year"] == year]
        contrib[year] = sum(gaps)
        print(f"   {year}: n={len(gaps):>3}  mean {statistics.mean(gaps):+.2f}pp  "
              f"sum {sum(gaps):+.1f}")
    top2 = sorted(contrib, key=lambda y: -contrib[y])[:2]
    share = sum(contrib[y] for y in top2) / sum(contrib.values()) * 100
    rest = [d for d in survivors if d["follow_year"] not in top2]
    print(f"   the two years carrying most of it: {', '.join(map(str, sorted(top2)))} "
          f"({share:.0f}% of the total)")
    report(f"ALL survivors excl {'_'.join(str(y) for y in sorted(top2))}", rest)

    gaps_ex = load_excluded_cagr_summary()
    ex_years = sorted({d["follow_year"] for d in diffs
                       if d["follow_year"] not in (2020, 2025)})
    out.append({
        "test": "cagr_gap_ex_2020_2025",
        "n": len(gaps_ex),
        "clusters": len(ex_years),
        "estimate": round(statistics.mean(gaps_ex), 2),
        "ci_low": "",
        "ci_high": "",
        "p_vs_null": "",
        "null": 0,
    })
    print("\nAnnualized-gap sensitivity excluding follow-up years 2020 and 2025:")
    print(f"   mean {statistics.mean(gaps_ex):+.2f}pp, median {statistics.median(gaps_ex):+.2f}pp, "
          f"positive categories {sum(1 for x in gaps_ex if x > 0)}/{len(gaps_ex)}")

    fields = ["test", "n", "clusters", "estimate", "ci_low", "ci_high",
              "p_vs_null", "null"]
    with open(os.path.join(HERE, "robustness_summary.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)
    print("\nwrote robustness_summary.csv")


if __name__ == "__main__":
    main()
