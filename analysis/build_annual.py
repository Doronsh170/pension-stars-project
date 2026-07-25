#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 - Build a clean annual-returns table from the raw monthly CBS/CMA files.

Output: analysis/annual_returns.csv with one row per (fund, year):
    domain (gemel|pension), fund_id, fund_name, classification, specialization,
    category, year, annual_return, n_months

Annual return is the compounded product of the 12 monthly yields (MONTHLY_YIELD),
which was validated to equal the reported December YEAR_TO_DATE_YIELD.
Only fund-years with all 12 months present are treated as complete annual returns.
"""
import csv, os
from collections import defaultdict
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (file, sheet, domain)
# Single consolidated provident-fund table (gemel + study funds), 2010-2025,
# supplied as one sheet. The study is provident-only; pension funds are not in
# this source. The pipeline still applies the public-access / IRA / sick-pay
# filters below. The investment track for each fund comes from the curated
# `מסלול ממופה` (mapped-route) column, which folds the regulator's many raw
# SPECIALIZATION labels into a clean, stable set of tracks.
SOURCES = [
    ("gemel-mapped-2010-2025.xlsx", "ראשי", "gemel"),
]

# Column holding the curated investment track (see analysis/map_other_bucket.py).
MAPPED_ROUTE_COL = "מסלול ממופה"


def norm(s):
    if s is None:
        return None
    return " ".join(str(s).split()).strip()


def load_rows():
    """Yield (domain, fund_id, fund_name, classification, mapped_route, year, month, monthly_yield)."""
    for fname, sheet, domain in SOURCES:
        path = os.path.join(ROOT, fname)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet]
        it = ws.iter_rows(values_only=True)
        header = list(next(it))
        idx = {h: i for i, h in enumerate(header)}
        c_id = idx["FUND_ID"]
        c_name = idx["FUND_NAME"]
        c_cls = idx["FUND_CLASSIFICATION"]
        c_route = idx[MAPPED_ROUTE_COL]      # curated investment track
        c_tp = idx.get("TARGET_POPULATION")  # gemel only; marks who may join
        c_per = idx.get("REPORT_PERIOD") or idx["תקופת דיווח"]
        c_my = idx["MONTHLY_YIELD"]
        for r in it:
            per = r[c_per]
            if per is None:
                continue
            # REPORT_PERIOD may be a datetime (new file) or a YYYYMM string (old).
            if hasattr(per, "year"):
                per_year, per_month = per.year, per.month
            else:
                per = str(per)
                if len(per) < 6:
                    continue
                per_year, per_month = int(per[:4]), int(per[4:6])
            # Keep only broad funds that are open to the general public. Sectoral
            # funds ("עובדי סקטור מסויים", e.g. a profession) and employer funds
            # ("עובדי מפעל/גוף מסויים", e.g. a single company) are excluded: a
            # typical saver cannot join them, so they are not real "chase" targets.
            # The regulator's own TARGET_POPULATION field marks this (gemel only;
            # pension funds carry no such field and are all open to the public).
            if c_tp is not None:
                tp = norm(r[c_tp])
                if tp and tp != "כלל האוכלוסיה":
                    continue
            name = norm(r[c_name])
            # Exclude self-managed / IRA wrappers ("בניהול אישי"). These are legal
            # shells for member-directed portfolios with no pooled fund yield; they
            # report placeholder ~0% returns that wrongly top the ranking in down
            # years, so they are not comparable investment products for this study.
            if name and ("בניהול אישי" in name or "IRA" in name):
                continue
            # Exclude central sick-pay funds ("דמי מחלה"): these are employer
            # reserve vehicles for paying sick leave, not a personal savings
            # product a saver would ever choose, so they don't belong in the pool.
            if name and "דמי מחלה" in name:
                continue
            route = norm(r[c_route])
            # Skip rows without a resolved track (should be none after mapping).
            if not route or route == "אחר, לבדיקה":
                continue
            yield (domain, r[c_id], name, norm(r[c_cls]), route,
                   per_year, per_month, r[c_my])
        wb.close()


def main():
    # (domain, fund_id, year) -> dict
    acc = defaultdict(lambda: {"months": {}, "name": None, "cls": None, "route": None})
    for domain, fid, name, cls, route, year, month, my in load_rows():
        key = (domain, fid, year)
        d = acc[key]
        d["name"] = name
        d["cls"] = cls
        d["route"] = route
        if my is not None:
            d["months"][month] = float(my)

    out_path = os.path.join(HERE, "annual_returns.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["domain", "fund_id", "fund_name", "classification",
                    "mapped_route", "category", "year", "annual_return", "n_months"])
        for (domain, fid, year), d in sorted(acc.items(), key=lambda x: (x[0][0], x[0][2], x[0][1])):
            months = d["months"]
            n = len(months)
            if n == 0:
                continue
            comp = 1.0
            for m in range(1, 13):
                if m in months:
                    comp *= (1 + months[m] / 100.0)
            annual = (comp - 1) * 100.0
            # category = classification | mapped investment track
            category = f'{d["cls"]} | {d["route"]}'
            w.writerow([domain, fid, d["name"], d["cls"], d["route"], category,
                        year, round(annual, 4), n])
    print("wrote", out_path)


if __name__ == "__main__":
    main()
