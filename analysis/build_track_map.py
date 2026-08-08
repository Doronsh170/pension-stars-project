#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
מסלול ממופה — map every fund in the study universe onto one short track label.

The regulator's own `SPECIALIZATION` / `SUB_SPECIALIZATION` pair takes 67
distinct values over this universe, and 209 funds carry no value at all, so it
cannot be the study's comparison dimension as it stands. This stage collapses it
into a small set of tracks that describe what a fund actually holds, so that two
funds in the same track are genuinely comparable.

Method, in priority order (the first rule that matches wins, and the rule that
fired is recorded per fund in the output so any label can be traced):

  1. Product constraints that override the asset mix — מבטיח תשואה, הלכתי.
  2. Explicit "no equity" / "capped equity" wording in the track name. These are
     handled before any מניות match, because `ללא מניות` and `עד 15% מניות`
     both contain the word מניות while meaning close to its opposite.
  3. The regulator's track labels, where they are unambiguous.
  4. For the genuinely ambiguous remainder — blank labels, geographic tracks
     (`חו"ל`, `ישראל`), `קיימות`, `עוקב מדדים גמיש` — the fund's own median
     equity exposure, measured as a share of its assets, decides.

Geography is deliberately not treated as an asset class: `מסלול חו"ל` is a
general track that invests abroad and sits near 34% equity, not an equity fund.

Age-banded tracks (`מדרגות`, `מודל חכ"מ`, `קוהורטות`) are dissolved into the
mix tracks by their measured equity share, since one age ladder spans 0% to 99%
equity and a "winner" inside it would only be the fund in the youngest band.
Set DISSOLVE_AGE_BANDS = False to keep them as one standalone track instead.

Outputs
  analysis/fund_track_map.csv   one row per fund: track, rule, measured mix
  track-map-review.xlsx         same, as a workbook, worst-supported rows first

Manual corrections go in `track-overrides.csv` (FUND_NAME, מסלול ממופה) at the
repository root; they are applied last and always win over the rules.
"""
import csv
import os
import re
import statistics
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source import (DATA_XLSX, FAMILIES, ROOT, TRACKS, _data_sheet,
                    excluded_fund, load_risk_map, norm, num)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(HERE, "fund_track_map.csv")
REVIEW_XLSX = os.path.join(ROOT, "track-map-review.xlsx")
OVERRIDES_CSV = os.path.join(ROOT, "track-overrides.csv")

# Dissolve the age ladders into the mix tracks (see module docstring).
DISSOLVE_AGE_BANDS = True

AGE_TRACK = "תלוי גיל (מדרגות)"

# `ללא מניות` and `עד 15% מניות` contain the word מניות but are not equity
# tracks. Both must be tested before any plain מניות match. The cap pattern
# requires the % sign or an immediately following מניות so that an age band
# such as `עד 50` cannot be read as an equity cap.
RE_NO_EQUITY = re.compile(r"ללא\s+מניות")
RE_CAPPED_EQUITY = re.compile(r"עד\s*\d+\s*%\s*מניות|עד\s*\d+\s*מניות")


def _has(text, *words):
    return any(w in text for w in words)


def classify(name, spec, sub, equity_pct):
    """Return (track, rule). `equity_pct` is the fund's median equity share."""

    # --- product constraints, ahead of any asset-mix reasoning --------------
    if spec == "מבטיח תשואה" or _has(name, "מבטיח תשואה"):
        return "מבטיח תשואה", "guaranteed"
    if spec == "הלכתי" or _has(name, "הלכה", "שריעה", "מורשת"):
        return "הלכתי", "halachic"

    is_age_band = spec in ("מדרגות", "מודל חכ\"מ אחר", "קוהורטות") or _has(
        name, "לבני 50", "ומטה", "בין 50 ל", "60 ומעלה", "60 פלוס", "לבני 60",
        "מודל חכ\"ם")
    if is_age_band and not DISSOLVE_AGE_BANDS:
        return AGE_TRACK, "age-band"

    # --- money market ------------------------------------------------------
    if spec in ("שיקלי", "מט\"ח") or _has(name, "כספי", "כספית", "טווח קצר",
                                          "מט\"ח", "דולר"):
        return "כספי ושקלי קצר", "money-market"

    # --- government bonds --------------------------------------------------
    if sub in ("אג\"ח ממשלתי", "אג\"ח ממשלות") or _has(
            name, "ממשלתי", "ממשלתיות", "ממשלות"):
        return "אג\"ח ממשלתי", "gov-bond"

    # --- tracks that name their own equity cap -----------------------------
    # Matched per field, never on the concatenation: `גמל חכם עד 40` (an age
    # band) followed by a `מניות` sub-label would otherwise read as a 40% cap.
    if any(RE_NO_EQUITY.search(t) for t in (name, sub)):
        return "אג\"ח ללא מניות", "no-equity"
    if any(RE_CAPPED_EQUITY.search(t) for t in (name, sub)):
        return "אג\"ח עם עד 25% מניות", "capped-equity"

    bondish = _has(name, "אג\"ח", "אגח") or _has(sub, "אג\"ח")

    # `צמוד מדד` is a CPI-linked bond track, not an index-tracking equity one.
    if _has(name, "צמוד מדד") or (
            spec == "מדד" and (bondish or (_has(sub, "מדד") and
                                           (equity_pct is None or equity_pct < 10)))):
        return "אג\"ח ללא מניות", "cpi-linked"

    passive = (_has(name, "מחקה", "עוקב", "פאסיב")
               or sub in ("פאסיבי", "חו\"ל - פאסיבי") or spec == "עוקבי מדדים")

    # Geography is not an asset class: only an explicit מניות marks equity.
    equity = (spec == "מניות" or _has(sub, "מניות") or _has(name, "מניות")
              or _has(name.upper(), "S&P", "MSCI", "NASDAQ", "STOXX"))
    if equity and not bondish:
        return ("מניות מחקות מדד", "passive-eq") if passive else (
            "מניות אקטיבי", "active-eq")

    if spec == "אג\"ח" or bondish or sub in ("אג\"ח סחיר", "עוקב מדדי אג\"ח",
                                             "אשראי ואג\"ח"):
        if _has(sub, "משולב") or _has(name, "משולב", "85/15", "90/10"):
            return "אג\"ח עם עד 25% מניות", "bond+eq"
        return "אג\"ח ללא מניות", "bond"

    # --- ambiguous: the measured mix decides -------------------------------
    if equity_pct is not None:
        if equity_pct >= 85:
            return ("מניות מחקות מדד", "mix%-passive") if passive else (
                "מניות אקטיבי", "mix%-active")
        if equity_pct < 5:
            return "אג\"ח ללא מניות", "mix%-bond"
        if equity_pct < 25:
            return "אג\"ח עם עד 25% מניות", "mix%-bond25"

    return "כללי", "general"


def scan_universe():
    """One pass over the monthly extract: identity + measured mix per fund."""
    wb = openpyxl.load_workbook(DATA_XLSX, read_only=True, data_only=True)
    ws = _data_sheet(wb)
    it = ws.iter_rows(values_only=True)
    idx = {h: i for i, h in enumerate(norm(h) for h in next(it))}
    funds = {}
    for r in it:
        name = norm(r[idx["FUND_NAME"]])
        family = norm(r[idx["FUND_CLASSIFICATION"]])
        if not name or family not in FAMILIES or excluded_fund(name):
            continue
        # Keyed by FUND_ID, the identity the rest of the pipeline joins on.
        fid = str(r[idx["FUND_ID"]])
        f = funds.get(fid)
        if f is None:
            f = funds[fid] = {
                "fund_id": fid, "fund_name": name,
                "family": family,
                "specialization": norm(r[idx["SPECIALIZATION"]]),
                "sub_specialization": norm(r[idx["SUB_SPECIALIZATION"]]),
                "months": 0, "_eq": [], "_fx": [], "_assets": [],
            }
        f["fund_name"] = name   # keep the latest spelling
        f["months"] += 1
        assets = num(r[idx["TOTAL_ASSETS"]])
        equity = num(r[idx["STOCK_MARKET_EXPOSURE"]])
        foreign = num(r[idx["FOREIGN_EXPOSURE"]])
        if assets and assets > 0:
            f["_assets"].append(assets)
            if equity is not None:
                f["_eq"].append(100.0 * equity / assets)
            if foreign is not None:
                f["_fx"].append(100.0 * foreign / assets)
    wb.close()
    return funds


def load_overrides():
    if not os.path.exists(OVERRIDES_CSV):
        return {}
    with open(OVERRIDES_CSV, encoding="utf-8-sig") as fh:
        return {norm(r["FUND_NAME"]): norm(r["מסלול ממופה"])
                for r in csv.DictReader(fh) if norm(r.get("FUND_NAME"))}


def main():
    funds = scan_universe()
    risk_map = load_risk_map()
    overrides = load_overrides()

    rows = []
    for f in funds.values():
        # The curated map's labels are cleaner than the raw extract's; prefer
        # them where the fund appears in it.
        spec, sub = f["specialization"], f["sub_specialization"]
        mapped = risk_map.get(f["fund_name"])
        if mapped and (mapped["specialization"] or mapped["sub_specialization"]):
            spec = mapped["specialization"] or spec
            sub = mapped["sub_specialization"] or sub

        equity_pct = round(statistics.median(f["_eq"]), 1) if f["_eq"] else None
        foreign_pct = round(statistics.median(f["_fx"]), 1) if f["_fx"] else None
        track, rule = classify(f["fund_name"], spec, sub, equity_pct)
        if f["fund_name"] in overrides:
            track, rule = overrides[f["fund_name"]], "override"

        rows.append({
            "FUND_ID": f["fund_id"], "FUND_NAME": f["fund_name"],
            "משפחה": f["family"], "SPECIALIZATION": spec,
            "SUB_SPECIALIZATION": sub, "מסלול ממופה": track,
            "חשיפה מנייתית %": equity_pct,
            "חשיפה לחו\"ל %": foreign_pct,
            "נכסים חציוני": round(statistics.median(f["_assets"]), 1) if f["_assets"] else None,
            "חודשי דיווח": f["months"], "כלל": rule,
        })

    cols = list(rows[0].keys())
    rows.sort(key=lambda r: (r["מסלול ממופה"], -(r["חשיפה מנייתית %"] or 0)))
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    _write_review(rows, cols)
    _report(rows)


def _write_review(rows, cols):
    """Workbook for eyeballing: the least-supported labels sort to the top."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "מסלול ממופה"
    ws.sheet_view.rightToLeft = True

    # Rows whose track was decided by measured mix, or whose mix sits far from
    # its track's median, are the ones worth a human eye.
    med = {}
    for t in {r["מסלול ממופה"] for r in rows}:
        vals = [r["חשיפה מנייתית %"] for r in rows
                if r["מסלול ממופה"] == t and r["חשיפה מנייתית %"] is not None]
        med[t] = statistics.median(vals) if vals else 0.0

    def doubt(r):
        eq = r["חשיפה מנייתית %"]
        gap = 0.0 if eq is None else abs(eq - med[r["מסלול ממופה"]])
        if eq is None:
            gap = 50.0
        return gap + (25.0 if r["כלל"].startswith("mix%") else 0.0)

    ws.append(cols + ["מרחק מחציון הקטגוריה"])
    for c in ws[1]:
        c.font = openpyxl.styles.Font(bold=True)
    ws.freeze_panes = "A2"
    for r in sorted(rows, key=doubt, reverse=True):
        ws.append([r[c] for c in cols] + [round(doubt(r), 1)])
    for col, width in zip("ABCDEFGHIJKL", (9, 62, 26, 24, 24, 22, 14, 14, 14, 12, 14, 14)):
        ws.column_dimensions[col].width = width
    ws.auto_filter.ref = ws.dimensions
    wb.save(REVIEW_XLSX)


def _report(rows):
    tracks = sorted({r["מסלול ממופה"] for r in rows},
                    key=lambda t: TRACKS.index(t) if t in TRACKS else 99)
    print("%d funds -> %d tracks\n" % (len(rows), len(tracks)))
    print("%-24s %6s %8s %14s" % ("מסלול ממופה", "קופות", "חציון", "10-90%"))
    for t in tracks:
        eq = sorted(r["חשיפה מנייתית %"] for r in rows
                    if r["מסלול ממופה"] == t and r["חשיפה מנייתית %"] is not None)
        n = sum(1 for r in rows if r["מסלול ממופה"] == t)
        if eq:
            print("%-24s %6d %7.0f%% %7.0f%% - %-5.0f%%" %
                  (t, n, statistics.median(eq), eq[int(.1 * len(eq))],
                   eq[int(.9 * len(eq))]))
        else:
            print("%-24s %6d %8s" % (t, n, "-"))
    print("\nwrote %s\nwrote %s" % (OUT_CSV, REVIEW_XLSX))


if __name__ == "__main__":
    main()
