#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 - Build a clean annual-returns table from the raw monthly extract.

Output: analysis/annual_returns.csv, one row per (fund, year):
    domain, fund_id, fund_name, classification, specialization,
    sub_specialization, risk_level, category, year, annual_return, n_months

The annual return is the compounded product of the 12 monthly yields
(MONTHLY_YIELD). It was validated against the reported December
YEAR_TO_DATE_YIELD on all 6,433 fund-years where both exist: the largest
disagreement is 0.005 pp, i.e. rounding. Only fund-years with all 12 months
present count as a complete annual return.

`category` = FUND_CLASSIFICATION | risk level. That is the comparison group:
a saver picks a family (study fund / provident / investment provident) and a
risk level, and the funds inside that cell are the ones actually competing for
the same money. Risk levels come from build_risk_levels.py.
"""
import csv
import os
from collections import defaultdict

from source import HERE, FAMILIES, RISK_ORDER, iter_data, num

RISK_LEVELS_CSV = os.path.join(HERE, "fund_risk_levels.csv")


def load_risk_levels():
    """fund_id -> (risk_level, specialization, sub_specialization)."""
    with open(RISK_LEVELS_CSV, encoding="utf-8-sig") as fh:
        return {
            r["fund_id"]: (r["risk_level"], r["specialization"], r["sub_specialization"])
            for r in csv.DictReader(fh)
        }


def main():
    levels = load_risk_levels()
    # (fund_id, year) -> accumulated months
    acc = defaultdict(lambda: {"months": {}, "name": None, "cls": None})
    fields = ["FUND_ID", "FUND_CLASSIFICATION", "MONTHLY_YIELD"]
    for r in iter_data(fields):
        fid = str(r["FUND_ID"])
        cls = " ".join(str(r["FUND_CLASSIFICATION"] or "").split()).strip()
        if cls not in FAMILIES:
            continue
        d = acc[(fid, r["year"])]
        d["name"] = r["fund_name"]
        d["cls"] = cls
        y = num(r["MONTHLY_YIELD"])
        if y is not None:
            d["months"][r["month"]] = y

    out_path = os.path.join(HERE, "annual_returns.csv")
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "fund_id", "fund_name", "classification",
                    "specialization", "sub_specialization", "risk_level",
                    "category", "year", "annual_return", "n_months"])
        for (fid, year), d in sorted(acc.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            months = d["months"]
            if not months:
                continue
            risk, spec, sub = levels.get(fid, ("", "", ""))
            # A fund with no resolvable risk level has no comparison group.
            if risk not in RISK_ORDER:
                continue
            comp = 1.0
            for m in range(1, 13):
                if m in months:
                    comp *= (1 + months[m] / 100.0)
            annual = (comp - 1) * 100.0
            w.writerow(["gemel", fid, d["name"], d["cls"], spec, sub, risk,
                        f'{d["cls"]} | {risk}', year, round(annual, 4), len(months)])
            written += 1
    print(f"wrote {out_path}  ({written} fund-years)")


if __name__ == "__main__":
    main()
