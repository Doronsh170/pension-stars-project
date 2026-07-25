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
# filters below, so the exact fund pool is unchanged from the earlier run.
SOURCES = [
    ("gemel-merged-2010-2025.xlsx", "‏‏צרף1", "gemel"),
]


def norm(s):
    if s is None:
        return None
    return " ".join(str(s).split()).strip()


# --- track refinement inside the two provident families -------------------
# The regulator's SPECIALIZATION for stocks/general is coarse, and a number of
# single-index tracker products ("קרנות סל" / "מחקות מדד" / Phoenix's "שיטת
# הפניקס" index line) are filed under the *general* ("כללי") track even though
# they hold a single asset (a bond index at ~0% equity, or ת"א 25 at ~98%).
# They are not diversified general funds and even topped the general track in
# 2014-2015, so we drop them from "כללי". Genuine conservative general funds
# (e.g. "מסלול קלאסי", "עד 10% מניות") are kept.
_TRACKER_MARKS = ("סל עוקב", "מחקה מדד", "עוקב מדד", "שיטת הפניקס")


def is_index_tracker(name):
    name = name or ""
    return any(m in name for m in _TRACKER_MARKS)


# Stock funds ("מניות") are split by geography read from the fund name, because
# the regulator does not carry it as a field for most of them. Foreign/global
# and Israel index products are separated out from the plain "מניות" mandate
# funds; the small geo buckets fall below the study's fund-count threshold and
# drop out on their own, leaving an actively-managed general-stock track.
_FOREIGN_MARKS = ('חו"ל', "חו”ל", "s&p", "s$p", "s1;p", "msci", "נאסד", "nasdaq",
                  "עולמי", "גלובל", "global", "world", "דאו", "יורוסטוק",
                  "אירופ", 'ארה"ב', "מפותח", "מתעורר", "ג'ונס")
_ISRAEL_MARKS = ('ת"א', "ת”א", "תל אביב", "ישראל")


def stock_geo(name):
    low = (name or "").lower()
    if any(m in low for m in _FOREIGN_MARKS):
        return 'חו"ל'
    if any(m in (name or "") for m in _ISRAEL_MARKS):
        return "ישראל"
    return "כללי"


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
        c_tp = idx.get("TARGET_POPULATION")  # gemel only; marks who may join
        c_per = idx["REPORT_PERIOD"]
        c_my = idx["MONTHLY_YIELD"]
        for r in it:
            per = r[c_per]
            if per is None:
                continue
            per = str(per)
            if len(per) < 6:
                continue
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
            year = int(per[:4]); month = int(per[4:6])
            spec = norm(r[c_spec]) if c_spec is not None else None
            yield (domain, r[c_id], name, norm(r[c_cls]), spec,
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
            # category: pension -> classification; gemel -> classification | track.
            # Within gemel we refine the track: single-index trackers are dropped
            # from "כללי", and "מניות" is split by geography (see helpers above).
            if domain == "pension":
                category = d["cls"]
            else:
                spec = d["spec"]
                if spec == "כללי" and is_index_tracker(d["name"]):
                    continue  # single-index tracker mislabeled as a general fund
                if spec == "מניות":
                    track = f'מניות · {stock_geo(d["name"])}'
                elif spec:
                    track = spec
                else:
                    track = None
                category = f'{d["cls"]} | {track}' if track else d["cls"]
            w.writerow([domain, fid, d["name"], d["cls"], d["spec"], category,
                        year, round(annual, 4), n])
    print("wrote", out_path)


if __name__ == "__main__":
    main()
