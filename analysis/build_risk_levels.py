#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 0 - Give every fund in the source one stable risk level.

The study compares each fund against funds of the *same* risk level, so the
risk label has to be a property of the fund, not of the year. Two things make
that non-trivial:

1. The consolidated extract carries a `רמת סיכון` column, but it buckets funds
   by their *shekel* equity exposure rather than by their equity *share*. A
   pure-equity fund therefore drifts through all five levels as it grows
   (`אנליסט גמל מניות` is labelled נמוך, נמוך-בינוני, בינוני and גבוה in
   different years). That column is not used.

2. The curated `fund-risk-map.xlsx` has the right label, but it is a snapshot of
   funds trading today: 704 of the 1,274 funds in the 2010-2025 history. Funds
   that closed or merged before the snapshot are missing.

So the level is taken from the mapping table where it exists, and otherwise
imputed from the fund's own reported behaviour:

  a. the fund's track (SPECIALIZATION | SUB_SPECIALIZATION), when the mapping
     table assigns that track one dominant level (>=3 funds, >=85% agreement);
  b. otherwise the fund's median equity share of assets
     (STOCK_MARKET_EXPOSURE / TOTAL_ASSETS), splitting the two no-equity levels
     by median volatility (STANDARD_DEVIATION);
  c. otherwise volatility alone, for the early years that report no exposure.

Validated against the 640 funds the mapping table labels: 90% exact agreement,
99% within one level (see the console summary). Every fund's level and its
source are written out so the assignment is auditable.

Output: analysis/fund_risk_levels.csv
"""
import csv
import os
import statistics
from collections import Counter, defaultdict

from source import HERE, RISK_ORDER, iter_data, load_risk_map, num

# Imputation cut-points. (a) equity share of assets, in percent:
EQ_CUTS = [(75, "גבוה"), (25, "בינוני"), (5, "נמוך-בינוני")]
SD_SPLIT_NO_EQUITY = 1.5   # below this, a no-equity fund is `נמוך מאוד`
# (b) volatility fallback when the fund never reported equity exposure:
SD_CUTS = [(10, "גבוה"), (5.5, "בינוני"), (3.5, "נמוך-בינוני"), (1.5, "נמוך")]

# A track only lends its level to unmapped funds when the mapping table is
# nearly unanimous about it.
TRACK_MIN_FUNDS = 3
TRACK_MIN_PURITY = 0.85


def track_priors(risk_map):
    """Track -> risk level, for tracks the mapping table agrees on."""
    by_track = defaultdict(list)
    for info in risk_map.values():
        key = (info["specialization"], info["sub_specialization"])
        if not any(key) or not info["risk"] or info["risk"] not in RISK_ORDER:
            continue
        by_track[key].append(info["risk"])
    priors = {}
    for key, levels in by_track.items():
        top, n_top = Counter(levels).most_common(1)[0]
        if len(levels) >= TRACK_MIN_FUNDS and n_top / len(levels) >= TRACK_MIN_PURITY:
            priors[key] = top
    return priors


def impute(track, eq, sd, priors):
    """Risk level for a fund the mapping table does not cover."""
    if track in priors:
        return priors[track], "track"
    if eq is not None:
        for cut, level in EQ_CUTS:
            if eq >= cut:
                return level, "equity"
        no_eq = "נמוך מאוד" if (sd is not None and sd < SD_SPLIT_NO_EQUITY) else "נמוך"
        return no_eq, "equity"
    if sd is not None:
        for cut, level in SD_CUTS:
            if sd >= cut:
                return level, "volatility"
        return "נמוך מאוד", "volatility"
    return "", ""


def collect_funds():
    """FUND_ID -> the fund's names, latest track, and risk-proxy medians."""
    funds = defaultdict(lambda: {
        "names": {}, "tracks": Counter(), "eq": [], "sd": [], "cls": Counter(),
    })
    fields = ["FUND_ID", "FUND_CLASSIFICATION", "SPECIALIZATION",
              "SUB_SPECIALIZATION", "STOCK_MARKET_EXPOSURE", "TOTAL_ASSETS",
              "STANDARD_DEVIATION"]
    for r in iter_data(fields):
        f = funds[str(r["FUND_ID"])]
        # keep the most recent spelling of the name for the map lookup
        f["names"][(r["year"], r["month"])] = r["fund_name"]
        f["cls"][r["FUND_CLASSIFICATION"]] += 1
        track = (r["SPECIALIZATION"] or "", r["SUB_SPECIALIZATION"] or "")
        track = tuple(" ".join(str(t).split()).strip() for t in track)
        if any(track):
            f["tracks"][track] += 1
        assets, exposure = num(r["TOTAL_ASSETS"]), num(r["STOCK_MARKET_EXPOSURE"])
        if assets and exposure is not None:
            f["eq"].append(exposure / assets * 100)
        sd = num(r["STANDARD_DEVIATION"])
        if sd is not None:
            f["sd"].append(sd)
    return funds


def main():
    risk_map = load_risk_map()
    priors = track_priors(risk_map)
    funds = collect_funds()

    rows, checked, exact, within1 = [], 0, 0, 0
    for fid, f in funds.items():
        names = [f["names"][k] for k in sorted(f["names"], reverse=True)]
        latest = names[0]
        track = f["tracks"].most_common(1)[0][0] if f["tracks"] else ("", "")
        eq = statistics.median(f["eq"]) if f["eq"] else None
        sd = statistics.median(f["sd"]) if f["sd"] else None

        mapped = next((risk_map[n] for n in names if n in risk_map), None)
        guess, guess_src = impute(track, eq, sd, priors)
        if mapped and mapped["risk"] in RISK_ORDER:
            level, src = mapped["risk"], "map"
            if guess:                       # accuracy of the imputation rule
                checked += 1
                exact += (guess == level)
                within1 += abs(RISK_ORDER.index(guess) - RISK_ORDER.index(level)) <= 1
        else:
            level, src = guess, guess_src
        if mapped and any((mapped["specialization"], mapped["sub_specialization"])):
            track = (mapped["specialization"], mapped["sub_specialization"])

        rows.append({
            "fund_id": fid, "fund_name": latest,
            "classification": f["cls"].most_common(1)[0][0] if f["cls"] else "",
            "specialization": track[0], "sub_specialization": track[1],
            "risk_level": level, "risk_source": src,
            "equity_pct_median": round(eq, 1) if eq is not None else "",
            "std_dev_median": round(sd, 2) if sd is not None else "",
            "months": sum(f["cls"].values()),
        })

    rows.sort(key=lambda r: (r["classification"], r["risk_level"], r["fund_name"]))
    out = os.path.join(HERE, "fund_risk_levels.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    src_counts = Counter(r["risk_source"] for r in rows)
    print(f"funds: {len(rows)}")
    for src in ("map", "track", "equity", "volatility", ""):
        if src_counts[src]:
            label = src or "unresolved"
            print(f"  risk level from {label:11s}: {src_counts[src]:4d}")
    print(f"\nimputation rule vs the {checked} funds the mapping table labels:")
    print(f"  exact match     : {exact / checked * 100:.1f}%")
    print(f"  within one level: {within1 / checked * 100:.1f}%")
    print("\nwrote", out)


if __name__ == "__main__":
    main()
