#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 3b - Robustness & significance checks for the two central claims.

  Q1 (persistence): is last year's #1 fund's follow-up percentile really
      above 50 (the "no persistence" null), or could that be noise?
  Q2 (money):      is the chase-vs-stay return gap really different from 0?

For each we report the point estimate, a 95% bootstrap confidence interval
and a two-sided bootstrap p-value against the null. We also run a
SURVIVORSHIP sensitivity: every result is shown (a) as in the main study
(follow-up stats over surviving funds; a vanished winner falls back to the
category average in the money sim) and (b) a stress version that does NOT
ignore closures (a vanished winner is scored at the bottom / dropped), to
show how much the closed funds move the answer.

Reuses the exact loading & ranking rules of chase_analysis.py so nothing
diverges. Stdlib only (bootstrap instead of scipy).

Input : annual_returns.csv        Output: console report + robustness_summary.csv
"""
import csv, os, statistics, random, math
import chase_analysis as ca
from source import FAMILY_LABEL

random.seed(20260724)
HERE = os.path.dirname(os.path.abspath(__file__))
B = 20000  # bootstrap resamples


def family(domain, cat):
    """The saver-facing name of the fund family the category belongs to."""
    return FAMILY_LABEL.get(cat.split(" | ")[0], cat.split(" | ")[0])


def boot_ci(xs, h0, stat=statistics.mean):
    """95% CI for the statistic and a two-sided bootstrap p-value vs h0."""
    n = len(xs)
    if n < 2:
        return (None, None, None)
    means = []
    for _ in range(B):
        s = [xs[random.randrange(n)] for _ in range(n)]
        means.append(stat(s))
    means.sort()
    lo = means[int(.025 * B)]
    hi = means[int(.975 * B)]
    frac_le = sum(1 for m in means if m <= h0) / B
    frac_ge = sum(1 for m in means if m >= h0) / B
    p = min(1.0, 2 * min(frac_le, frac_ge))
    return (lo, hi, p)


def collect():
    """Walk every category/signal-year once, gathering the raw material for
    both questions, in a 'main' and a 'stress' (closures-not-ignored) form."""
    data = ca.load()
    persist = {k: [] for k in (1, 2, 3)}         # follow-up percentiles, survivors only
    persist_stress = {k: [] for k in (1, 2, 3)}  # + vanished winners scored at 0 (bottom)
    beatmed = {k: [] for k in (1, 2, 3)}         # 1/0 winner beat category median
    still1 = {k: [] for k in (1, 2, 3)}
    rand1 = {k: [] for k in (1, 2, 3)}           # random baseline 1/n for "still #1"
    diffs = []          # per consecutive year: dict(family, gap, winner_vanished)

    for domain in ("gemel",):
        for cat in ca.CATEGORIES[domain]:
            years = data.get((domain, cat), {})
            valid = sorted(y for y, f in years.items() if len(f) >= ca.MIN_FUNDS)
            if len(valid) < 3:
                continue
            fam = family(domain, cat)
            # --- persistence ---
            for Y in valid:
                s, _ = ca.ranked(years[Y])
                win = s[0][0]
                for k in (1, 2, 3):
                    fk = years.get(Y + k)
                    if not fk or len(fk) < ca.MIN_FUNDS:
                        continue
                    _, infok = ca.ranked(fk)
                    n = len(fk)
                    med = statistics.median([r for _, _, r in fk])
                    if win in infok:
                        rank, ret, _ = infok[win]
                        pc = ca.percentile(rank, n)
                        persist[k].append(pc)
                        persist_stress[k].append(pc)
                        beatmed[k].append(1 if ret > med else 0)
                        still1[k].append(1 if rank == 1 else 0)
                        rand1[k].append(1.0 / n)
                    else:
                        persist_stress[k].append(0.0)  # vanished -> bottom
            # --- money: chase vs stay, per consecutive year ---
            all_years = sorted(y for y in years if len(years[y]) >= ca.MIN_FUNDS)
            for i in range(1, len(all_years)):
                prevY, Y = all_years[i - 1], all_years[i]
                if Y != prevY + 1:
                    continue
                s_prev, _ = ca.ranked(years[prevY])
                win = s_prev[0][0]
                _, info = ca.ranked(years[Y])
                rets = [r for _, _, r in years[Y]]
                avg = statistics.mean(rets)
                vanished = win not in info
                chase = info[win][1] if not vanished else avg
                track = cat.split(" | ")[1] if " | " in cat else cat
                diffs.append({"family": fam, "label": f"{fam} · {track}",
                              "year": Y, "gap": chase - avg, "vanished": vanished})
    return persist, persist_stress, beatmed, still1, rand1, diffs


def main():
    persist, persist_stress, beatmed, still1, rand1, diffs = collect()
    out = []

    print("=" * 74)
    print("Q1  PERSISTENCE — follow-up percentile of last year's #1 (null = 50)")
    print("=" * 74)
    print(f"{'horizon':8s} {'n':>4} {'mean':>6} {'95% CI':>16} {'p vs 50':>9}  interpretation")
    for k in (1, 2, 3):
        xs = persist[k]
        m = statistics.mean(xs)
        lo, hi, p = boot_ci(xs, 50)
        sig = "real (CI>50)" if lo > 50 else "not clear"
        print(f"+{k} year  {len(xs):>4} {m:>6.1f}   [{lo:>5.1f},{hi:>5.1f}]  {p:>8.3f}  {sig}")
        out.append({"test": f"persistence_pctile_y{k}", "n": len(xs), "estimate": round(m, 1),
                    "ci_low": round(lo, 1), "ci_high": round(hi, 1), "p_vs_null": round(p, 4),
                    "null": 50})
    print("\n  beat category median (null = 50%):")
    for k in (1, 2, 3):
        xs = [x * 100 for x in beatmed[k]]
        m = statistics.mean(xs); lo, hi, p = boot_ci(xs, 50)
        print(f"   +{k}y: {m:>5.1f}%  [{lo:>5.1f},{hi:>5.1f}]  p={p:.3f}  (n={len(xs)})")
        out.append({"test": f"beat_median_y{k}", "n": len(xs), "estimate": round(m, 1),
                    "ci_low": round(lo, 1), "ci_high": round(hi, 1), "p_vs_null": round(p, 4),
                    "null": 50})
    print("\n  still #1 vs random baseline (1/n):")
    for k in (1, 2, 3):
        obs = statistics.mean(still1[k]) * 100
        base = statistics.mean(rand1[k]) * 100
        print(f"   +{k}y: observed {obs:.1f}%  vs random {base:.1f}%  (n={len(still1[k])})")

    print("\n  SURVIVORSHIP stress — vanished winner scored at the BOTTOM (pctile 0):")
    for k in (1, 2, 3):
        xs = persist_stress[k]
        m = statistics.mean(xs); lo, hi, p = boot_ci(xs, 50)
        sig = "still >50" if lo > 50 else "no longer clear"
        print(f"   +{k}y: mean {m:>5.1f}  [{lo:>5.1f},{hi:>5.1f}]  p={p:.3f}  ({sig}, n={len(xs)})")
        out.append({"test": f"persistence_stress_y{k}", "n": len(xs), "estimate": round(m, 1),
                    "ci_low": round(lo, 1), "ci_high": round(hi, 1), "p_vs_null": round(p, 4),
                    "null": 50})

    print("\n" + "=" * 74)
    print("Q2  MONEY — annual (chase - stay) return gap, percentage points (null = 0)")
    print("=" * 74)

    def report(label, rows):
        gaps = [d["gap"] for d in rows]
        if len(gaps) < 2:
            print(f"{label:24s} n={len(gaps)} (too few)"); return
        m = statistics.mean(gaps); lo, hi, p = boot_ci(gaps, 0)
        pos = sum(1 for g in gaps if g > 0)
        sig = "sig" if (lo > 0 or hi < 0) else "n.s."
        print(f"{label:24s} n={len(gaps):>3}  mean {m:+.2f}pp  [{lo:+.2f},{hi:+.2f}]  "
              f"p={p:.3f}  {pos}/{len(gaps)}>0  [{sig}]")
        out.append({"test": f"gap_{label}", "n": len(gaps), "estimate": round(m, 2),
                    "ci_low": round(lo, 2), "ci_high": round(hi, 2), "p_vs_null": round(p, 4),
                    "null": 0})

    print("-- main (vanished winner falls back to category average) --")
    report("ALL", diffs)
    for fam in FAMILY_LABEL.values():
        rows = [d for d in diffs if d["family"] == fam]
        if rows:
            report(fam, rows)
    print("-- per category (family x track) --")
    for lab in sorted({d["label"] for d in diffs}):
        report(lab, [d for d in diffs if d["label"] == lab])
    print("-- survivorship stress (drop years where the winner had closed) --")
    surv = [d for d in diffs if not d["vanished"]]
    report("ALL (survivors only)", surv)

    # -- how much of the gap rests on a couple of calendar years? --
    # An average that survives only because of two exceptional years is not the
    # same finding as one spread over the period, so the two years that carry
    # the most of it are identified by their share of the total and dropped.
    # Measured on the surviving winners, the same basis the pages quote.
    print("-- year concentration (survivors, gap by follow-up year) --")
    years = sorted({d["year"] for d in surv})
    contrib = {}
    for y in years:
        g = [d["gap"] for d in surv if d["year"] == y]
        contrib[y] = sum(g)
        print(f"   {y}: n={len(g):>3}  mean {statistics.mean(g):+.2f}pp  "
              f"sum {sum(g):+.1f}")
    top2 = sorted(contrib, key=lambda y: -contrib[y])[:2]
    share = sum(contrib[y] for y in top2) / sum(contrib.values()) * 100
    rest = [d for d in surv if d["year"] not in top2]
    print(f"   the two years carrying most of it: {', '.join(map(str, sorted(top2)))}"
          f"  ({share:.0f}% of the total)")
    report(f"ALL survivors excl {'_'.join(str(y) for y in sorted(top2))}", rest)

    with open(os.path.join(HERE, "robustness_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["test", "n", "estimate", "ci_low", "ci_high", "p_vs_null", "null"])
        w.writeheader(); w.writerows(out)
    print("\nwrote robustness_summary.csv")


if __name__ == "__main__":
    main()
