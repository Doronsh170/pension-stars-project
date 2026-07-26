#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 - Build a clean annual-returns table from the raw monthly extract.

Output: analysis/annual_returns.csv, one row per (fund, year):
    domain, fund_id, fund_name, classification, track, category, year,
    annual_return, n_months, assets_end

The annual return is the compounded product of the 12 monthly yields
(MONTHLY_YIELD). It is validated here against the reported December
YEAR_TO_DATE_YIELD: the largest disagreement is rounding-sized. Only
fund-years with all 12 months present count as a complete annual return.

`category` = FUND_CLASSIFICATION | מסלול ממופה. That is the comparison group:
a saver picks a family (study fund / provident / investment provident / child
savings) and an investment track, and the funds inside that cell are the ones
actually competing for the same money. The track comes straight from the
source workbook's `מסלול ממופה` column, which is stable per fund.

`assets_end` is the fund's December TOTAL_ASSETS (millions of shekels). It is
carried through only so the report can illustrate the finding with the large,
well-known funds rather than with marginal ones.
"""
import csv
import os
from collections import defaultdict

from source import HERE, FAMILIES, TRACK_ORDER, TRACK_EXCLUDE, iter_data, norm, num


def main():
    # (fund_id, year) -> accumulated months
    acc = defaultdict(lambda: {"months": {}, "assets": {}, "ytd": None,
                               "name": None, "cls": None, "track": None})
    fields = ["FUND_ID", "FUND_CLASSIFICATION", "MONTHLY_YIELD",
              "YEAR_TO_DATE_YIELD", "TOTAL_ASSETS", "מסלול ממופה"]
    for r in iter_data(fields):
        cls = norm(r["FUND_CLASSIFICATION"])
        track = norm(r["מסלול ממופה"])
        if cls not in FAMILIES or track in TRACK_EXCLUDE:
            continue
        d = acc[(str(r["FUND_ID"]), r["year"])]
        d["name"] = r["fund_name"]
        d["cls"] = cls
        d["track"] = track
        y = num(r["MONTHLY_YIELD"])
        if y is not None:
            d["months"][r["month"]] = y
        a = num(r["TOTAL_ASSETS"])
        if a is not None:
            d["assets"][r["month"]] = a
        if r["month"] == 12:
            d["ytd"] = num(r["YEAR_TO_DATE_YIELD"])

    out_path = os.path.join(HERE, "annual_returns.csv")
    written, checked, worst = 0, 0, 0.0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "fund_id", "fund_name", "classification", "track",
                    "category", "year", "annual_return", "n_months", "assets_end"])
        for (fid, year), d in sorted(acc.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            months = d["months"]
            if not months or d["track"] not in TRACK_ORDER:
                continue
            comp = 1.0
            for m in range(1, 13):
                if m in months:
                    comp *= (1 + months[m] / 100.0)
            annual = (comp - 1) * 100.0
            if len(months) == 12 and d["ytd"] is not None:
                checked += 1
                worst = max(worst, abs(annual - d["ytd"]))
            assets = d["assets"].get(max(d["assets"])) if d["assets"] else ""
            w.writerow(["gemel", fid, d["name"], d["cls"], d["track"],
                        f'{d["cls"]} | {d["track"]}', year, round(annual, 4),
                        len(months), round(assets, 1) if assets != "" else ""])
            written += 1
    print(f"wrote {out_path}  ({written} fund-years)")
    print(f"compounded vs reported December YTD: {checked} fund-years checked, "
          f"largest gap {worst:.4f} pp")


if __name__ == "__main__":
    main()
