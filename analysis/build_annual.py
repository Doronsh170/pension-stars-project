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
SOURCES = [
    ("gemel-net1999-2022.xlsx", "gemel-net1999-2022", "gemel"),
    ("gemel-net2023.xlsx",      "gemel-net2023",      "gemel"),
    ("2024-2026גמל.xlsx",       "file",               "gemel"),
    ("pensia-net1999-2022.xlsx","pensia-net1999-2022","pension"),
    ("pensia-net2023.xlsx",     "pensia-net2023",     "pension"),
    ("2024-2026פנסיה.xlsx",     "file (1)",           "pension"),
]


def norm(s):
    if s is None:
        return None
    return " ".join(str(s).split()).strip()


def load_rows():
    """Yield (domain, fund_id, fund_name, classification, specialization, year, month, monthly_yield)."""
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
        c_spec = idx.get("SPECIALIZATION")  # pension has no specialization
        c_per = idx["REPORT_PERIOD"]
        c_my = idx["MONTHLY_YIELD"]
        for r in it:
            per = r[c_per]
            if per is None:
                continue
            per = str(per)
            if len(per) < 6:
                continue
            year = int(per[:4]); month = int(per[4:6])
            spec = norm(r[c_spec]) if c_spec is not None else None
            yield (domain, r[c_id], norm(r[c_name]), norm(r[c_cls]), spec,
                   year, month, r[c_my])
        wb.close()


def main():
    # (domain, fund_id, year) -> dict
    acc = defaultdict(lambda: {"months": {}, "name": None, "cls": None, "spec": None})
    for domain, fid, name, cls, spec, year, month, my in load_rows():
        key = (domain, fid, year)
        d = acc[key]
        d["name"] = name
        d["cls"] = cls
        d["spec"] = spec
        if my is not None:
            d["months"][month] = float(my)

    out_path = os.path.join(HERE, "annual_returns.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["domain", "fund_id", "fund_name", "classification",
                    "specialization", "category", "year", "annual_return", "n_months"])
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
            # category: pension -> classification; gemel -> classification | specialization
            if domain == "pension":
                category = d["cls"]
            else:
                category = d["cls"] if not d["spec"] else f'{d["cls"]} | {d["spec"]}'
            w.writerow([domain, fid, d["name"], d["cls"], d["spec"], category,
                        year, round(annual, 4), n])
    print("wrote", out_path)


if __name__ == "__main__":
    main()
