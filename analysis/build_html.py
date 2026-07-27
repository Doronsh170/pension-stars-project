#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 4 - build a self-contained, theme-aware HTML report (analysis/report.html)
from the CSV outputs. Data is inlined so the page is faithful and reproducible.
"""
import csv, os, json, statistics, re
from collections import defaultdict

# Display-only tidy-up of fund names: the raw source mangles the "&" in "S&P"
# into "1;" or "$" (e.g. "S1;P500", "s$p500", or a bare "s1;p"). Fix the
# ampersand first, then ensure the space in "S&P500". Data files are untouched.
def clean_name(s):
    if not s:
        return s
    s = re.sub(r'[sS](?:1;|\$|&)[pP]', 'S&P', s)   # s1;p / s$p / s&p -> S&P
    s = re.sub(r'S&P(?=500)', 'S&P ', s)            # S&P500 -> S&P 500
    return s

HERE = os.path.dirname(os.path.abspath(__file__))

def read(n): return list(csv.DictReader(open(os.path.join(HERE, n), encoding="utf-8-sig")))
events = read("events.csv"); strat = read("strategy_summary.csv"); risk = read("risk_summary.csv")
rob = {r["test"]: r for r in read("robustness_summary.csv")}

from source import FAMILIES, FAMILY_LABEL, TRACK_ORDER
_present = {(e["domain"], e["category"]) for e in events}
CAT_ORDER = [
    ("gemel", f"{fam} | {track}")
    for fam in FAMILIES for track in TRACK_ORDER
    if ("gemel", f"{fam} | {track}") in _present
]
def family(c):
    head = c.split(" | ")[0]
    return FAMILY_LABEL.get(head, head)
def label(c):
    return family(c) + " · " + c.split(" | ")[1]

# ---- horizon statistics (descriptive) ----
def hstats(k):
    ranks=[]; ns=[]; pct=[]; normpos=[]; present=absent=total=0
    still1=top3=topq=half=bot=0
    # disjoint partition of ALL winners (sums to total): where did each end up?
    s_no1=s_topq=s_half=s_bot=0
    for e in events:
        st=e.get(f"y{k}_status")
        if st in ("present","absent"): total+=1
        if st=="absent": absent+=1
        if st!="present": continue
        present+=1
        rk=int(e[f"y{k}_rank"]); n=int(e[f"y{k}_n"]); p=float(e[f"y{k}_percentile"])
        ranks.append(rk); ns.append(n); pct.append(p); normpos.append(rk/n)
        if rk==1: still1+=1
        if rk<=3: top3+=1
        if rk<=max(1,round(n/4)): topq+=1
        if rk<=n/2: half+=1
        else: bot+=1
        # disjoint bucket
        q=max(1,round(n/4))
        if rk==1: s_no1+=1
        elif rk<=q: s_topq+=1
        elif rk<=n/2: s_half+=1
        else: s_bot+=1
    r1=lambda x:round(x,1)
    return {"h":k,"present":present,"total":total,
        "med_rank":round(statistics.median(ranks)),"med_n":round(statistics.median(ns)),
        "med_pos":r1(statistics.median(normpos)*100),
        "pctile":r1(statistics.mean(pct)),"med_pctile":r1(statistics.median(pct)),
        "no1":r1(still1/present*100),"top3":r1(top3/present*100),"topq":r1(topq/present*100),
        "half":r1(half/present*100),"bot":r1(bot/present*100),
        "vanished":r1(absent/total*100),
        # disjoint partition as % of ALL winners (no1+topq+half+bot+closed = 100)
        "seg":{"no1":r1(s_no1/total*100),"topq":r1(s_topq/total*100),
               "half":r1(s_half/total*100),"bot":r1(s_bot/total*100),
               "closed":r1(absent/total*100)}}
persist=[hstats(k) for k in (1,2,3)]
TOTAL_EVENTS=persist[0]["total"]

strat_by={(s["domain"],s["category"]):s for s in strat}
risk_by={(r["domain"],r["category"]):r for r in risk}
strat_data=[{"label":label(c),"dom":d,"fam":family(c),
             "chase":float(strat_by[(d,c)]["chase_annualized_pct"]),
             "stay":float(strat_by[(d,c)]["stay_annualized_pct"]),
             "gap":float(strat_by[(d,c)]["gap_annualized_pp"]),
             "years":strat_by[(d,c)]["n_years"],
             "vol":float(risk_by[(d,c)]["winner_vol_pctile"]) if risk_by.get((d,c),{}).get("winner_vol_pctile") else None}
            for d,c in CAT_ORDER if (d,c) in strat_by]
pooled_vol=risk_by.get(("POOLED",""),{}).get("winner_vol_pctile")

# ---- per-category tracking ----
ev_by=defaultdict(list)
for e in events: ev_by[(e["domain"],e["category"])].append(e)
def cellobj(e,k):
    st=e.get(f"y{k}_status")
    if st=="present":
        return {"ret":float(e[f"y{k}_return"]),"rank":int(e[f"y{k}_rank"]),"n":int(e[f"y{k}_n"])}
    if st=="absent": return {"closed":True}
    return None
cats=[]
for d,c in CAT_ORDER:
    rows=sorted(ev_by.get((d,c),[]),key=lambda x:int(x["signal_year"]))
    if not rows: continue
    cats.append({"label":label(c),"dom":d,"fam":family(c),
        "rows":[{"y":int(e["signal_year"]),"name":clean_name(e["winner_name"]),
                 "sret":float(e["signal_return"]),"sn":int(e["signal_n"]),
                 "k1":cellobj(e,1),"k2":cellobj(e,2),"k3":cellobj(e,3)} for e in rows]})

# ---- the headline numbers of question 3, straight from the same CSVs ----
GAPS = [float(s["gap_annualized_pp"]) for s in strat]
N_CATS = str(len(GAPS))
N_POS = str(sum(1 for g in GAPS if g > 0))          # categories where chasing won
N_SMALL = str(sum(1 for g in GAPS if abs(g) < 1))   # ...and in how many, barely
MEAN_GAP = f"{statistics.mean(GAPS):+.2f}".replace("-", "\u2212")

# How wide is the universe the winners were picked out of? Count the funds that
# were actually ranked: those with at least one complete (12-month) year inside
# a category-year big enough to have a meaningful "#1".
def _ranked_universe():
    from chase_analysis import MIN_FUNDS, FIRST_YEAR, LAST_COMPLETE_YEAR
    rows = read("annual_returns.csv")
    by = defaultdict(lambda: defaultdict(set))
    for r in rows:
        if int(r["n_months"]) != 12:
            continue
        y = int(r["year"])
        if FIRST_YEAR <= y <= LAST_COMPLETE_YEAR:
            by[(r["domain"], r["category"])][y].add(r["fund_id"])
    funds = set()
    for years in by.values():
        for f in years.values():
            if len(f) >= MIN_FUNDS:
                funds |= f
    return len(funds)

N_FUNDS = str(_ranked_universe())

# How much did a leader beat its category average by in the following year, and
# what is left of that once the two calendar years carrying most of it are
# dropped (both from robustness.py, over the leaders still in the category).
def _pp(test):
    return f'{float(rob[test]["estimate"]):+.2f}'.replace("-", "−")

_EXCL = next(t for t in rob if t.startswith("gap_ALL survivors excl "))
CONC_YEARS = " ו-".join(_EXCL.rsplit(" ", 1)[1].split("_"))
GAP_EVENTS = _pp("gap_ALL (survivors only)")
GAP_EXCL = _pp(_EXCL)
N_SIGNALS = str(len(events))     # every leadership event, 2025 included

def _gap_on_track(track):
    """Mean chase-minus-stay gap on one track, pooled over the families."""
    vals = [float(s["gap_annualized_pp"]) for s in strat
            if s["category"].split(" | ")[1] == track]
    return statistics.mean(vals) if vals else 0.0

# The widest and the narrowest track. The text names them rather than claiming
# a trend across tracks, which these numbers do not show.
_by_track = sorted(((_gap_on_track(t), t) for t in TRACK_ORDER
                    if any(s["category"].endswith(" | " + t) for s in strat)),
                   reverse=True)
WIDE_GAP = f"{_by_track[0][0]:+.2f}".replace("-", "\u2212")
WIDE_TRACK = _by_track[0][1]
NARROW_GAP = f"{_by_track[-1][0]:+.2f}".replace("-", "\u2212")
NARROW_TRACK = _by_track[-1][1]

DATA=json.dumps({"persist":persist,"strat":strat_data,"cats":cats,
                 "pooled_vol":pooled_vol,"total":TOTAL_EVENTS,
                 "track_order":TRACK_ORDER,"wide_track":WIDE_TRACK},ensure_ascii=False)

HTML = r"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>מה קרה בפועל לקופות שהובילו בתשואה? (המחקר המלא)</title>
<style>
:root{
  --paper:#F4F6F8; --raised:#FFFFFF; --ink:#12171E; --muted:#5A6A7A; --faint:#8A97A3;
  --line:#DDE3E9; --line2:#EAEEF2;
  --teal:#0E7C6B; --teal-soft:#0E7C6B22; --gold:#B57F14; --clay:#B4472C;
  --pos:#0E7C6B; --neg:#B4472C; --base:#8A97A3;
  --shadow:0 1px 2px rgba(18,23,30,.04),0 8px 24px rgba(18,23,30,.06);
}
@media (prefers-color-scheme:dark){:root{
  --paper:#0F141A; --raised:#161D26; --ink:#EAEFF4; --muted:#9FB0BE; --faint:#6C7C8A;
  --line:#28323D; --line2:#1E262F;
  --teal:#3BB39D; --teal-soft:#3BB39D22; --gold:#D9A63C; --clay:#E0704F;
  --pos:#3BB39D; --neg:#E0704F; --base:#6C7C8A;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --paper:#0F141A; --raised:#161D26; --ink:#EAEFF4; --muted:#9FB0BE; --faint:#6C7C8A;
  --line:#28323D; --line2:#1E262F; --teal:#3BB39D; --teal-soft:#3BB39D22;
  --gold:#D9A63C; --clay:#E0704F; --pos:#3BB39D; --neg:#E0704F; --base:#6C7C8A;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px rgba(0,0,0,.35);
}
:root[data-theme="light"]{
  --paper:#F4F6F8; --raised:#FFFFFF; --ink:#12171E; --muted:#5A6A7A; --faint:#8A97A3;
  --line:#DDE3E9; --line2:#EAEEF2; --teal:#0E7C6B; --teal-soft:#0E7C6B22;
  --gold:#B57F14; --clay:#B4472C; --pos:#0E7C6B; --neg:#B4472C; --base:#8A97A3;
  --shadow:0 1px 2px rgba(18,23,30,.04),0 8px 24px rgba(18,23,30,.06);
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper)}
.backbar{max-width:860px;margin:0 auto;padding:20px 24px 0}
.backbar a{display:inline-flex;align-items:center;gap:7px;font-size:14px;font-weight:600;
  color:var(--teal);text-decoration:none}
.backbar a:hover{text-decoration:underline}
.backbar .ar{font-size:16px}
#page{background:var(--paper);color:var(--ink);
  font-family:"Segoe UI","Arial Hebrew","Assistant","Heebo",system-ui,-apple-system,sans-serif;
  line-height:1.7;font-size:17px;-webkit-font-smoothing:antialiased;
  font-variant-numeric:tabular-nums;padding:0 0 80px}
.wrap{max-width:860px;margin:0 auto;padding:0 24px}
.num{font-variant-numeric:tabular-nums;direction:ltr;unicode-bidi:isolate}

/* masthead */
.masthead{border-bottom:2px solid var(--ink);padding:56px 0 26px;margin-bottom:8px}
.kicker{font-size:12.5px;letter-spacing:.22em;text-transform:uppercase;color:var(--teal);
  font-weight:700;margin-bottom:18px}
h1{font-size:clamp(30px,5.2vw,46px);line-height:1.12;font-weight:800;letter-spacing:-.01em;
  margin:0 0 18px;text-wrap:balance}
.dek{font-size:19px;color:var(--muted);max-width:62ch;margin:0}
.sourceline{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:24px;font-size:13px;
  color:var(--faint);letter-spacing:.02em}
.sourceline b{color:var(--muted);font-weight:600}

/* bottom-line callout */
.tldr{background:var(--raised);border:1px solid var(--line);border-radius:14px;
  box-shadow:var(--shadow);padding:26px 28px;margin:34px 0 12px;position:relative}
.tldr::before{content:"";position:absolute;inset-inline-start:0;top:16px;bottom:16px;
  width:4px;border-radius:4px;background:var(--teal)}
.tldr .lab{font-size:12px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--teal);font-weight:700;margin-bottom:8px}
.tldr p{margin:0;font-size:18px;font-weight:500}
.tldr strong{color:var(--ink);font-weight:800}
.tldr .qn{display:inline-flex;align-items:center;justify-content:center;width:22px;
  height:22px;border-radius:50%;background:var(--teal);color:#fff;font-size:12.5px;
  font-weight:800;margin-inline-start:2px;vertical-align:middle}
.tldr-note{margin-top:14px!important;font-size:14.5px!important;color:var(--muted);
  font-weight:400!important}

section{padding-top:52px}
.eyebrow{font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint);
  font-weight:700;margin-bottom:10px}
h2{font-size:clamp(23px,3.4vw,30px);line-height:1.2;font-weight:800;margin:0 0 14px;
  letter-spacing:-.01em;text-wrap:balance}
p.body{color:var(--ink);margin:16px 0}
.body .em{color:var(--clay);font-weight:700}
.body .emteal{color:var(--teal);font-weight:700}

.figure{background:var(--raised);border:1px solid var(--line);border-radius:14px;
  box-shadow:var(--shadow);padding:22px 22px 18px;margin:22px 0}
.figure .cap{font-size:13px;color:var(--muted);margin:2px 0 18px;line-height:1.5}
.figure svg{display:block;width:100%;height:auto;overflow:visible}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:var(--muted);
  margin-top:14px;justify-content:center}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:11px;height:11px;border-radius:3px;display:inline-block}

/* stat row */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}
.stat{background:var(--raised);border:1px solid var(--line);border-radius:12px;padding:16px 14px}
.stat .v{font-size:30px;font-weight:800;line-height:1;letter-spacing:-.02em;color:var(--ink)}
.stat .v.warn{color:var(--clay)} .stat .v.good{color:var(--teal)}
.stat .l{font-size:12.5px;color:var(--muted);margin-top:8px;line-height:1.4}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,1fr)}}

/* tables */
.famhead{margin:26px 0 6px;font-size:15px;font-weight:800;color:var(--teal);
  letter-spacing:.02em;display:flex;align-items:center;gap:8px}
.famhead .diamond{font-size:11px;opacity:.8}
.famhead:first-child{margin-top:6px}
details{background:var(--raised);border:1px solid var(--line);border-radius:12px;
  margin:12px 0;overflow:hidden}
summary{cursor:pointer;padding:15px 20px;font-weight:700;font-size:16px;list-style:none;
  display:flex;justify-content:space-between;align-items:center;gap:12px}
summary::-webkit-details-marker{display:none}
summary .chev{color:var(--faint);transition:transform .2s;font-size:13px}
details[open] summary .chev{transform:rotate(90deg)}
summary:hover{background:var(--line2)}
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border-top:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:0;table-layout:fixed}
th,td{padding:8px 8px;text-align:start;border-bottom:1px solid var(--line2);vertical-align:top}
thead th{font-size:11px;letter-spacing:.03em;text-transform:uppercase;color:var(--faint);
  font-weight:700;position:sticky;top:0;background:var(--raised);white-space:nowrap}
td.name{white-space:normal;color:var(--muted);line-height:1.35;word-break:break-word}
/* compact, fixed column widths so all six columns fit without clipping */
col.c-year{width:8%} col.c-name{width:30%} col.c-sig{width:12%}
col.c-follow{width:16.66%}
td .cell{display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px}
td.y{font-weight:700;color:var(--gold)}
.pill{display:inline-flex;gap:5px;align-items:center;font-variant-numeric:tabular-nums;direction:ltr}
.rk{font-size:11px;color:var(--faint)}
.up{color:var(--pos)} .down{color:var(--neg)}
.badge{font-size:11px;padding:1px 7px;border-radius:20px;font-weight:700}
.badge.top{background:var(--teal-soft);color:var(--teal)}
.badge.low{background:#B4472C1f;color:var(--clay)}
tr.closed td{color:var(--faint);font-style:italic}

.conc{margin-top:56px;border-top:2px solid var(--ink);padding-top:34px}
.conc ol{padding-inline-start:22px;margin:18px 0}
.conc li{margin:12px 0}
.foot{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--faint);line-height:1.7}
.foot code{background:var(--line2);padding:1px 6px;border-radius:5px;font-size:12px}
.disclosure{text-align:center;max-width:62ch;margin-inline:auto}
.disclosure .credit{margin-top:10px;text-align:center}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div id="page" dir="rtl">
<div class="backbar"><a href="../index.html"><span class="ar">→</span> חזרה לתקציר</a></div>

<div class="masthead"><div class="wrap">
  <div class="kicker">מחקר תיאורי · שוק החיסכון ארוך הטווח</div>
  <h1>מה קרה בפועל לקופות שהובילו בתשואה?</h1>
  <p class="dek">בכל תחילת שנה בחרתי את הקופה שהשיגה את התשואה הגבוהה ביותר בשנה
    שחלפה, ובדקתי איך הסתדרה בשלוש השנים הבאות. ההשוואה היא תמיד מול קופות באותה
    משפחת מוצר ובאותו מסלול השקעה, ולא מול כל השוק.</p>
  <div class="sourceline">
    <span><b>מקור:</b> גמל-נט (רשות שוק ההון)</span>
    <span><b>תקופה:</b> שנות איתות <span class="num">2010-2024</span> · מעקב עד <span class="num">2025</span></span>
    <span><b>היקף:</b> <span class="num" id="catCount">21</span> קטגוריות · <span class="num" id="evCount">70</span> אירועי איתות</span>
  </div>
</div></div>

<div class="wrap">
  <div class="tldr">
    <div class="lab">שלוש השאלות</div>
    <p><span class="qn num">1</span> האם קופות שהובילו שומרות על מעמדן בהמשך?
      <span class="qn num">2</span> מהו הדירוג האופייני של מובילה לאחר שנה, שנתיים ושלוש?
      <span class="qn num">3</span> האם נמצא יתרון עקבי למעבר אל מובילת אשתקד?</p>
    <p class="tldr-note">המטרה אינה להוכיח או להפריך מראש את כדאיות המעבר, אלא להציג
      את הנתונים ההיסטוריים ולאפשר להסיק מהם מסקנות מבוססות עובדות.</p>
  </div>

  <section>
    <div class="eyebrow">שאלה 01 · שמירת מעמד</div>
    <h2>האם המובילות שומרות על מעמדן?</h2>
    <p class="body">עקבתי אחרי כל קופה שדורגה ראשונה, אל תוך שלוש השנים שאחרי. בשנה
      שאחרי האיתות רק <span class="emteal" id="s_no1">12%</span> מהמובילות חזרו למקום
      הראשון, ובערך <span id="s_top3">27%</span> נשארו בשלושת הראשונים. במקביל
      <span class="em" id="s_bot">38%</span> ירדו כבר לאחר שנה אל המחצית התחתונה של
      הקטגוריה, ועוד <span class="em" id="s_van">10%</span> כלל לא שרדו כקופה נפרדת
      (נסגרו או מוזגו). ככל שחולף הזמן שיעור החזרה למקום הראשון יורד ושיעור ההיעלמות עולה.</p>
    <div class="figure">
      <div class="cap">לאן הגיעה מובילת אשתקד: פילוח מלא (100%) של כלל המובילות לפי
        מיקומן בקטגוריה לאחר שנה, שנתיים ושלוש. כל פס מתחלק לחמישה מצבים נפרדים
        (מימין לשמאל: מהטוב לפחות טוב).</div>
      <svg id="chartKeep" viewBox="0 0 720 260" role="img"
        aria-label="פילוח מיקום המובילות לאורך שלוש שנים"></svg>
      <div class="legend" id="keepLegend"></div>
    </div>
  </section>

  <section>
    <div class="eyebrow">שאלה 02 · דירוג אופייני</div>
    <h2>מהו הדירוג האופייני לאחר 1, 2, 3 שנים?</h2>
    <p class="body">מבין הקופות ששרדו, הדירוג האופייני (החציוני) של מובילת אשתקד בשנה
      שאחרי הוא <span class="emteal" id="s_medrank">מקום 10 מתוך 36</span>, סביב
      השליש העליון של הקטגוריה, לא סמוך למקום הראשון. האחוזון הממוצע גבוה מאמצע
      הקטגוריה, אך מתקרב אליו ככל שחולף הזמן.</p>
    <div class="figure">
      <div class="cap">אחוזון הדירוג של המובילה בשנים שאחרי (100 = מקום ראשון, 50 = אמצע
        הקטגוריה), ממוצע וחציון. הקו המקווקו בגובה 50 מסמן דירוג ממוצע, כלומר ללא יתרון.</div>
      <svg id="chartPctile" viewBox="0 0 720 310" role="img"
        aria-label="אחוזון הדירוג של המובילה לאורך שלוש שנים"></svg>
      <div class="legend">
        <span><i class="dot" style="background:var(--teal)"></i> אחוזון ממוצע</span>
        <span><i class="dot" style="background:var(--gold)"></i> אחוזון חציוני</span>
        <span><i class="dot" style="background:var(--base)"></i> אמצע הקטגוריה (50)</span>
      </div>
    </div>
    <div class="stats" id="statsRank"></div>
  </section>

  <section>
    <div class="eyebrow">שאלה 03 · יתרון עקבי</div>
    <h2>האם נמצא יתרון עקבי?</h2>
    <p class="body"><b>(א) התוצאה הכספית.</b> השוויתי שתי התנהגויות: חוסך
      ש<span class="emteal">רודף</span>, כלומר עובר בכל שנה למובילת אשתקד, מול חוסך
      ש<span class="emteal">נשאר</span> בממוצע הקטגוריה. הפער לטובת הרודף קטן ולא אחיד:
      בממוצע <span class="num">__MEANGAP__</span> נקודות אחוז לשנה, וברוב הקטגוריות
      (<span class="num">__NSMALL__</span> מתוך <span class="num">__NCATS__</span>)
      הוא קטן מנקודה אחת לשנה. הוא הגדול
      ביותר במסלול <span class="em">__WIDETRACK__</span>
      (<span class="num">__WIDEGAP__</span> נק') והקטן ביותר במסלול
      <span class="em">__NARROWTRACK__</span> (<span class="num">__NARROWGAP__</span> נק').</p>
    <div class="figure">
      <div class="cap">פער התשואה השנתית (CAGR) בין "רודף" ל"נשאר", לפי קטגוריה. עמודה
        זהובה (שמאלה) = יתרון לרודף; עמודה חמרה (ימינה) = יתרון לנשאר. בנקודות אחוז.</div>
      <svg id="chartGap" viewBox="0 0 720 430" role="img"
        aria-label="פער התשואה בין רדיפה להישארות לפי קטגוריה"></svg>
    </div>
    <p class="body"><b>(ב) הקשר לסיכון.</b> כדי לבדוק אם הפער הזה הוא בכלל תשלום על
      סיכון, מדדתי לכל מובילה את התנודתיות שלה, כלומר כמה התשואה שלה קופצת מעלה ומטה,
      והשוויתי אותה לשאר הקופות באותה קטגוריה. בסולם אחוזון, שבו 50 היא תנודתיות ממוצעת
      ואילו 100 היא הקופה התנודתית ביותר בקבוצה, המובילה יושבת בממוצע על
      <span class="emteal" id="volInline">61</span>. כלומר גם בתוך מסלול אחיד, המובילה
      נוטה להיות הקופה הנועזת יותר. מכיוון שהתקופה כללה בעיקר שנים של עליות בשווקים,
      חלק מהפער שבסעיף (א) עשוי לשקף סיכון גדול יותר ולא התמדה של ביצועים.</p>
    <div class="figure">
      <div class="cap">אחוזון התנודתיות של המובילה בתוך הקטגוריה
        (50 = תנודתיות ממוצעת, 100 = התנודתית ביותר בקבוצה).</div>
      <svg id="chartRisk" viewBox="0 0 720 400" role="img"
        aria-label="אחוזון התנודתיות של המובילות לפי קטגוריה"></svg>
    </div>
  </section>

  <section>
    <div class="eyebrow">אמינות</div>
    <h2>עד כמה הממצא מוצק?</h2>
    <p class="body">בדקתי במבחנים סטטיסטיים אם התוצאות אמיתיות או סתם מזל אקראי.
      בקצרה: היתרון של מובילת אשתקד מובהק בשנה הראשונה ובשנייה, אבל
      <b>הוא קטן, לא אחיד בין הקטגוריות, ונעלם עד השנה השלישית</b>. כשמכניסים לחשבון גם
      את הקופות שנסגרו או מוזגו בדרך, גם היתרון של השנים הראשונות נחלש.</p>
    <p class="body">בדקתי גם עד כמה היתרון נשען על שנים בודדות. הפער הממוצע על פני כל
      אירועי ההובלה הוא <b>__GAPEV__</b> נקודות אחוז לשנה, אבל שתי שנים
      (__CONCYEARS__) מספקות את רובו: בלעדיהן הוא יורד ל<b>__GAPEX__</b> נקודות אחוז
      ואינו מובהק סטטיסטית. כלומר מדובר ביתרון שהתרכז בשנים חריגות, ולא בתוספת קבועה
      שחוסך יכול לצפות לה בכל שנה.</p>
  </section>

  <section>
    <div class="eyebrow">הנתונים המלאים</div>
    <h2>מעקב שנה אחר שנה, לפי קטגוריה</h2>
    <p class="body">לכל שנת איתות: הקופה שהובילה, תשואתה, והתשואה והדירוג שלה (מקום מתוך
      מספר הקופות בקטגוריה) בכל אחת משלוש השנים שאחרי.</p>
    <div id="tables"></div>
  </section>

  <div class="conc">
    <h2>תמצית הממצאים</h2>
    <p class="body">הנתונים ההיסטוריים מצביעים על התמונה הבאה, המוצגת כעובדות:</p>
    <ol>
      <li><b>שמירת מעמד חלקית וזמנית.</b> רק <span id="c_no1">10%</span> מהמובילות חזרו
        למקום הראשון בשנה שאחרי, <span id="c_bot">49%</span> ירדו למחצית התחתונה, ובתוך
        שלוש שנים <span id="c_van3">40%</span> מהן נסגרו או מוזגו.</li>
      <li><b>הדירוג האופייני הוא "טוב מהממוצע", לא "מוביל".</b> מובילת אשתקד מדורגת
        בשנה שאחרי סביב השליש העליון, והאחוזון הממוצע מתקרב אל האמצע עם הזמן.</li>
      <li><b>היתרון הכספי קטן ולא אחיד.</b> בממוצע
        <span class="num">__MEANGAP__</span> נקודות אחוז לשנה, וברוב הקטגוריות פחות
        מנקודה אחת. הוא הגדול ביותר במסלול <span class="em">__WIDETRACK__</span>, וגם
        בתוך מסלול אחיד המובילה נוטה להיות הקופה התנודתית יותר, בתקופה של שווקים עולים.</li>
    </ol>
    <p class="body">הנתונים המלאים והקוד בתיקיית <code>analysis/</code>. לקורא/ת נותרת
      ההחלטה כיצד לשקלל ממצאים אלה.</p>
  </div>

  <div class="foot disclosure">
    <b>גילוי נאות:</b> התוכן נועד למידע כללי ולמטרות לימודיות בלבד, ואינו מהווה ייעוץ
    או שיווק פנסיוני או השקעות ואינו תחליף לייעוץ אישי המתחשב בנתוניו ובצרכיו של כל אדם.
    הנתונים מבוססים על מקורות פומביים (גמל-נט) וייתכנו בהם אי דיוקים.
    ביצועי עבר אינם מעידים על העתיד.
    <div class="credit">מאת: דורון שרייבמן</div>
  </div>
</div>

<script>
const D=__DATA__;
/* the track carrying the widest chase-vs-stay gap, emphasised in the charts */
const TOP_TRACK=D.wide_track;
const NS="http://www.w3.org/2000/svg";
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function el(t,a){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;}
function txt(x,y,s,o={}){const t=el("text",{x,y,...o});t.textContent=s;return t;}

/* ---- inline figures ---- */
(function(){
  const p1=D.persist[0];
  document.getElementById("evCount").textContent=D.total;
  document.getElementById("catCount").textContent=D.strat.length;
  const _set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};
  _set("c_no1",Math.round(p1.no1)+"%");
  _set("c_bot",Math.round(p1.bot)+"%");
  _set("c_van3",Math.round(D.persist[2].vanished)+"%");
  document.getElementById("s_no1").textContent=Math.round(p1.no1)+"%";
  document.getElementById("s_top3").textContent=Math.round(p1.top3)+"%";
  document.getElementById("s_bot").textContent=Math.round(p1.bot)+"%";
  document.getElementById("s_van").textContent=Math.round(p1.vanished)+"%";
  document.getElementById("s_medrank").textContent=
    "מקום "+p1.med_rank+" מתוך ~"+p1.med_n;
})();

/* ---- Q1: where did last year's #1 end up? 100% stacked partition ---- */
(function(){
  const svg=document.getElementById("chartKeep");
  const segs=[
    {v:d=>d.seg.no1,             lab:"חזרו למקום 1",       col:css("--gold")},
    {v:d=>d.seg.topq+d.seg.half, lab:"שאר המחצית העליונה", col:css("--teal")},
    {v:d=>d.seg.bot,             lab:"ירדו למחצית התחתונה",col:css("--clay")},
    {v:d=>d.seg.closed,          lab:"נסגרו / מוזגו",      col:css("--base")},
  ];
  const W=720, top=16, rowH=46, gap=30, R=W-124, L=54, TW=R-L;
  const H=top+D.persist.length*(rowH+gap);
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const hlab=["אחרי שנה","אחרי שנתיים","אחרי 3 שנים"];
  D.persist.forEach((d,i)=>{
    const y=top+i*(rowH+gap);
    svg.appendChild(txt(W-12,y+rowH/2+5,hlab[i],{fill:css("--ink"),"font-size":13.5,
      "font-weight":700,"text-anchor":"start"}));       // rtl: right-aligned
    let xr=R;                                            // stack from the right (best) leftward
    segs.forEach(s=>{
      const v=s.v(d); if(v<=0) return;
      const w=v/100*TW, xl=xr-w;
      svg.appendChild(el("rect",{x:xl,y:y,width:w,height:rowH,fill:s.col,
        opacity:0.96,stroke:css("--raised"),"stroke-width":1}));
      if(w>24) svg.appendChild(txt((xl+xr)/2,y+rowH/2+5,Math.round(v)+"%",
        {fill:"#fff","font-size":13,"font-weight":800,"text-anchor":"middle",style:"direction:ltr"}));
      xr=xl;
    });
  });
  // HTML legend (avoids the old cramped in-chart legend)
  const lg=document.getElementById("keepLegend");
  lg.innerHTML=segs.map(s=>
    `<span><i class="dot" style="background:${s.col}"></i> ${s.lab}</span>`).join("");
})();

/* ---- Q2: percentile chart, mean + median side by side ----
   Grouped bars rather than two lines: every value gets its own printed label
   above its own bar, so no number can end up sitting on a line or behind a
   marker however close the two series run. ---- */
(function(){
  const svg=document.getElementById("chartPctile");
  const W=720,H=300,mL=48,mR=28,mT=26,mB=54;
  const iw=W-mL-mR, ih=H-mT-mB;
  const y=v=>mT+ih*(1-v/100);
  const gw=iw/D.persist.length, bw=52, gap=10;
  [0,25,50,75,100].forEach(g=>{
    svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(g),y2:y(g),
      stroke:g===50?css("--base"):css("--line"),"stroke-width":g===50?1.5:1,
      "stroke-dasharray":g===50?"5 4":""}));
    svg.appendChild(txt(mL-10,y(g)+4,g,{fill:css("--faint"),"font-size":11,
      "text-anchor":"middle"}));
  });
  D.persist.forEach((d,i)=>{
    const cx=mL+gw*(i+0.5);
    [[d.pctile,css("--teal"),-1],[d.med_pctile,css("--gold"),1]].forEach(([v,col,side])=>{
      const x=cx+side*(gap/2)-(side<0?bw:0), h=y(50-Math.abs(v-50))-y(50);
      // bars grow out of the 50 line: upward above the middle, downward below
      const top=v>=50?y(v):y(50);
      svg.appendChild(el("rect",{x:x,y:top,width:bw,height:Math.max(2,h),rx:4,
        fill:col,opacity:.92}));
      svg.appendChild(txt(x+bw/2,(v>=50?top-9:top+h+19),Math.round(v),
        {fill:col,"font-size":14,"font-weight":800,"text-anchor":"middle",
         style:"direction:ltr"}));
    });
    svg.appendChild(txt(cx,H-mB+30,"שנה +"+d.h,{fill:css("--muted"),"font-size":13,
      "font-weight":700,"text-anchor":"middle"}));
  });
  svg.appendChild(txt(mL+62,y(50)+19,"אמצע הקטגוריה",{fill:css("--base"),
    "font-size":11,"font-weight":700,"text-anchor":"middle"}));
})();

/* stat cards (Q2) */
(function(){
  const s=document.getElementById("statsRank");
  const cards=D.persist.map(d=>[
    "", "מקום "+d.med_rank, "דירוג חציוני לאחר "+d.h+" שנים (מתוך ~"+d.med_n+")"
  ]);
  cards.push(["good",Math.round(D.persist[0].pctile),"אחוזון ממוצע בשנה שאחרי"]);
  cards.forEach(([c,v,l])=>{
    const d=document.createElement("div");d.className="stat";
    d.innerHTML=`<div class="v ${c}"><span class="num">${v}</span></div><div class="l">${l}</div>`;
    s.appendChild(d);
  });
})();

/* Build a family-grouped row layout: a bold header per family, then its
   track rows (labelled by track only). Returns {rows, H}. */
function grouped(items,opt){
  const mT=opt.mT, hH=opt.hH, rowH=opt.rowH, gapH=opt.gapH;
  let y=mT, out=[], lastFam=null;
  items.forEach(d=>{
    if(d.fam!==lastFam){ if(lastFam!==null) y+=gapH; out.push({header:d.fam,y}); y+=hH; lastFam=d.fam; }
    out.push({d,y}); y+=rowH;
  });
  return {rows:out, H:y+opt.mB};
}
const trackOf=d=>d.label.split(" · ").slice(1).join(" · ");

/* ---- gap chart: diverging bars, grouped by family, track labels on right ---- */
(function(){
  const svg=document.getElementById("chartGap");
  const items=D.strat;
  const W=720, opt={mT:12,mB:40,hH:30,rowH:30,gapH:12};
  const {rows,H}=grouped(items,opt);
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const maxGap=Math.max(...items.map(d=>d.gap)), minGap=Math.min(...items.map(d=>d.gap));
  const xLab=W-12;                 // risk labels: right edge (rtl -> flows left)
  const x0=362;                    // zero baseline
  // the right-hand column holds the track names, so a negative bar plus its
  // value label must stay well short of it
  const scale=Math.min((x0-72)/(maxGap*1.1), 110/(Math.abs(minGap)*1.15));
  svg.appendChild(el("line",{x1:x0,x2:x0,y1:opt.mT,y2:H-opt.mB,stroke:css("--ink"),"stroke-width":1.5}));
  rows.forEach(it=>{
    if("header" in it){
      svg.appendChild(txt(xLab,it.y+21,it.header,{fill:css("--ink"),"font-size":15.5,
        "font-weight":800,"text-anchor":"start"}));
      svg.appendChild(el("line",{x1:60,x2:xLab,y1:it.y+28,y2:it.y+28,stroke:css("--line"),"stroke-width":1}));
      return;
    }
    const d=it.d, bh=20, by=it.y+(opt.rowH-bh)/2, bold=trackOf(d)===TOP_TRACK, neg=d.gap<0;
    const col=neg?css("--clay"):css("--gold"), span=Math.abs(d.gap)*scale;
    svg.appendChild(txt(xLab,by+bh/2+5,trackOf(d),{fill:css("--ink"),"font-size":14,
      "font-weight":bold?800:600,"text-anchor":"start"}));
    svg.appendChild(el("rect",{x:neg?x0:x0-span,y:by,width:Math.max(1.5,span),height:bh,rx:4,fill:col,opacity:.95}));
    const lx=neg?x0+span+7:x0-span-7;
    svg.appendChild(txt(lx,by+bh/2+5,(d.gap>=0?"+":"−")+Math.abs(d.gap).toFixed(2),
      {fill:col,"font-size":13.5,"font-weight":800,"text-anchor":neg?"start":"end",style:"direction:ltr"}));
  });
  svg.appendChild(txt(x0,H-opt.mB+22,"0",{fill:css("--muted"),"font-size":12,"text-anchor":"middle","font-weight":700}));
  svg.appendChild(txt(120,H-opt.mB+22,"◄ יתרון לרודף",{fill:css("--faint"),"font-size":12,"text-anchor":"middle"}));
  svg.appendChild(txt(x0+95,H-opt.mB+22,"יתרון לנשאר ►",{fill:css("--faint"),"font-size":12,"text-anchor":"middle"}));
})();

/* ---- risk chart: lollipop around 50, grouped by family ---- */
(function(){
  const svg=document.getElementById("chartRisk");
  const items=D.strat.filter(d=>d.vol!=null);
  const W=720, opt={mT:14,mB:38,hH:30,rowH:30,gapH:12};
  const {rows,H}=grouped(items,opt);
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
  const xLab=W-12, xL=56, xR=W-196, base=50;
  // the axis follows the data: a percentile below 40 used to fall off the panel
  const vals=items.map(d=>d.vol);
  const mn=Math.max(0,Math.floor((Math.min(...vals)-6)/10)*10);
  const mx=Math.min(100,Math.ceil((Math.max(...vals)+6)/10)*10);
  const x=v=>xL+(xR-xL)*(v-mn)/(mx-mn);
  const ticks=[]; for(let g=mn;g<=mx;g+=10) ticks.push(g);
  ticks.forEach(g=>{
    svg.appendChild(el("line",{x1:x(g),x2:x(g),y1:opt.mT,y2:H-opt.mB,
      stroke:g===base?css("--base"):css("--line"),"stroke-width":g===base?1.5:1,
      "stroke-dasharray":g===base?"5 4":""}));
    svg.appendChild(txt(x(g),H-opt.mB+18,g,{fill:g===base?css("--muted"):css("--faint"),
      "font-size":11,"text-anchor":"middle","font-weight":g===base?700:400}));
  });
  svg.appendChild(txt(x(base),opt.mT-2,"אמצע הקטגוריה",{fill:css("--muted"),"font-size":10.5,"text-anchor":"middle"}));
  rows.forEach(it=>{
    if("header" in it){
      svg.appendChild(txt(xLab,it.y+21,it.header,{fill:css("--ink"),"font-size":15.5,
        "font-weight":800,"text-anchor":"start"}));
      return;
    }
    const d=it.d, cy=it.y+opt.rowH/2, bold=trackOf(d)===TOP_TRACK;
    const col=bold?css("--teal"):css("--gold");
    svg.appendChild(txt(xLab,cy+5,trackOf(d),{fill:css("--ink"),"font-size":14,
      "font-weight":bold?800:600,"text-anchor":"start"}));
    svg.appendChild(el("line",{x1:x(base),x2:x(d.vol),y1:cy,y2:cy,stroke:col,"stroke-width":2.5,opacity:.5}));
    svg.appendChild(el("circle",{cx:x(d.vol),cy:cy,r:6,fill:col}));
    const right=d.vol>=base;
    svg.appendChild(txt(x(d.vol)+(right?12:-12),cy+4,Math.round(d.vol),{fill:col,"font-size":12.5,
      "font-weight":800,"text-anchor":right?"start":"end",style:"direction:ltr"}));
  });
})();
document.getElementById("volInline").textContent=Math.round(D.pooled_vol);

/* ---- tracking tables ---- */
(function(){
  const wrap=document.getElementById("tables");
  function cell(c){
    if(!c) return '<span style="color:var(--faint)">אין נתון</span>';
    if(c.closed) return '<span style="color:var(--faint);font-style:italic">נסגרה</span>';
    const dir=c.ret>=0?"up":"down";
    const top=c.rank<=Math.ceil(c.n/4), low=c.rank>c.n/2;
    let b= top?'<span class="badge top">צמרת</span>': low?'<span class="badge low">תחתית</span>':'';
    return `<div class="cell"><span class="pill ${dir}">${c.ret>=0?'+':''}${c.ret.toFixed(1)}%</span>`
      +`<span class="rk num">${c.rank}/${c.n}</span>${b}</div>`;
  }
  let lastFam=null;
  D.cats.forEach((cat,idx)=>{
    if(cat.fam!==lastFam){
      const h=document.createElement("div"); h.className="famhead";
      h.innerHTML=`<span class="diamond">◆</span> ${cat.fam}`;
      wrap.appendChild(h); lastFam=cat.fam;
    }
    const det=document.createElement("details"); if(idx<3)det.open=true;
    const track=cat.label.split(" · ").slice(1).join(" · ");
    let rows=cat.rows.map(r=>`<tr><td class="y num">${r.y}</td>
      <td class="name">${r.name}</td>
      <td class="num" style="font-weight:700;color:var(--gold)">+${r.sret.toFixed(1)}%</td>
      <td>${cell(r.k1)}</td><td>${cell(r.k2)}</td><td>${cell(r.k3)}</td></tr>`).join("");
    det.innerHTML=`<summary><span>${track||cat.label}</span>
      <span class="chev">▸</span></summary>
      <div class="tbl-scroll"><table>
      <colgroup><col class="c-year"><col class="c-name"><col class="c-sig">
      <col class="c-follow"><col class="c-follow"><col class="c-follow"></colgroup>
      <thead><tr><th>שנת איתות</th><th>הקופה שנבחרה</th><th>תשואת האיתות</th>
      <th>שנה +1</th><th>שנה +2</th><th>שנה +3</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
    wrap.appendChild(det);
  });
})();
</script>
</div>
</body>
</html>"""

open(os.path.join(HERE, "report.html"), "w", encoding="utf-8").write(
    HTML.replace("__DATA__", DATA)
        .replace("__MEANGAP__", MEAN_GAP).replace("__NSMALL__", N_SMALL)
        .replace("__NCATS__", N_CATS).replace("__NPOS__", N_POS)
        .replace("__WIDETRACK__", WIDE_TRACK).replace("__WIDEGAP__", WIDE_GAP)
        .replace("__NARROWTRACK__", NARROW_TRACK).replace("__NARROWGAP__", NARROW_GAP)
        .replace("__CONCYEARS__", CONC_YEARS)
        .replace("__GAPEV__", GAP_EVENTS).replace("__GAPEX__", GAP_EXCL))
print("wrote report.html")

# =====================================================================
# Stage 5 - the simple, few-seconds landing page (index.html at repo root).
# Order of the page: research question -> the headline findings -> concrete
# examples -> only then the conclusion. Same source data as the full report,
# so the headline numbers stay in sync.
# =====================================================================
p1 = persist[0]

# ---- concrete illustrations: follow ONE winning fund through time. Each card
#      names the fund and the year it finished #1 in its category, then shows how
#      it ranked one, two and three years later. Straight from events.csv, so the
#      names and places stay exact. ----
def _outcome(e):
    """How the winner ended up one year later — the archetype the card shows."""
    if e.get("y1_status") == "absent":
        return "closed"
    if e.get("y1_status") != "present":
        return None                     # signal year too recent to follow up
    rank, n = int(e["y1_rank"]), int(e["y1_n"])
    if rank == 1:
        return "kept"
    if rank <= max(1, round(n / 4)):
        return "top"
    if rank > n / 2:
        return "bottom"
    return "mid"

def _full_followup(e):
    """Every card shows three follow-up years, so only fully-tracked winners."""
    return all(e.get(f"y{k}_status") in ("present", "absent") for k in (1, 2, 3))

# The cards are meant to be recognisable, so they are drawn from the largest
# funds of the recent years rather than from the whole 2010-2025 history. The
# outcome mix is whatever those funds actually did — no archetype is forced in.
EXAMPLE_FIRST_YEAR = 2016
N_EXAMPLES = 8

def _house(name):
    """First word of the fund name — a good enough stand-in for the manager,
    used only to keep one house from taking over the card grid."""
    return name.split()[0] if name.split() else name

def _pick_examples():
    pool = [e for e in events
            if _outcome(e) and _full_followup(e) and e["winner_assets"]
            and int(e["signal_year"]) >= EXAMPLE_FIRST_YEAR]
    pool.sort(key=lambda e: -float(e["winner_assets"]))
    picked, used_funds, used_houses, used_cats = [], set(), [], []
    for e in pool:
        if len(picked) >= N_EXAMPLES:
            break
        if e["winner_name"] in used_funds:
            continue
        if used_houses.count(_house(e["winner_name"])) >= 2:
            continue
        if used_cats.count(e["category"]) >= 2:
            continue
        picked.append((e["domain"], e["category"], e["signal_year"]))
        used_funds.add(e["winner_name"])
        used_houses.append(_house(e["winner_name"]))
        used_cats.append(e["category"])
    picked.sort(key=lambda k: k[2])
    return picked

EXAMPLES = _pick_examples()
_evx = {(e["domain"], e["category"], e["signal_year"]): e for e in events}
def _rank_cls(rank, n):
    if rank <= (n + 3) // 4: return "top"
    if rank > n / 2: return "low"
    return "mid"
def _ex_card(dom, cat, yr):
    e = _evx[(dom, cat, yr)]
    steps = []
    for k, when in ((1, "אחרי שנה"), (2, "אחרי שנתיים"), (3, "אחרי שלוש שנים")):
        st = e.get(f"y{k}_status")
        if st == "present":
            rk, n, ret = int(e[f"y{k}_rank"]), int(e[f"y{k}_n"]), float(e[f"y{k}_return"])
            place = (f'<span class="ex-place {_rank_cls(rk, n)}">מקום {rk} מתוך {n} '
                     f'<span class="ex-ret num">{ret:+.0f}%</span></span>')
        elif st == "absent":
            place = '<span class="ex-place low">נסגרה או מוזגה</span>'
        else:
            place = '<span class="ex-place none">אין נתונים</span>'
        steps.append(f'<div class="ex-step"><span class="ex-when">{when}</span>{place}</div>')
    return (f'<div class="ex-card">'
            f'<div class="ex-fund">{clean_name(e["winner_name"])}</div>'
            f'<div class="ex-won">{label(cat)} · מקום 1 בשנת <span class="num">{yr}</span> '
            f'(<span class="num">{float(e["signal_return"]):+.0f}%</span>)</div>'
            f'<div class="ex-track">{"".join(steps)}</div></div>')
EX_CARDS = "".join(_ex_card(d, c, y) for d, c, y in EXAMPLES)

IDX = {
    "no1":   f"{round(p1['no1'])}%",
    "bot":   f"{round(p1['bot'])}%",
    "rank":  f"{p1['med_rank']}",
    "van1":  f"{round(p1['vanished'])}%",
    "van3":  f"{round(persist[2]['vanished'])}%",
    "nfunds": N_FUNDS,       # funds that were actually ranked somewhere
    "signals": N_SIGNALS,    # leadership events behind the page
    "concyears": CONC_YEARS, # the two years carrying most of the money gap
    "gapev": GAP_EVENTS,     # the leader's edge over its category average
    "ex_cards": EX_CARDS,
}

INDEX = r"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>מה קרה לקופות שהובילו בתשואה בשנים שלאחר מכן?</title>
<style>
:root{
  --paper:#F4F6F8; --raised:#FFFFFF; --ink:#12171E; --muted:#5A6A7A; --faint:#8A97A3;
  --line:#DDE3E9; --line2:#EAEEF2; --teal:#0E7C6B; --teal-d:#0B6153; --gold:#B57F14;
  --clay:#B4472C; --shadow:0 1px 2px rgba(18,23,30,.04),0 10px 30px rgba(18,23,30,.07);
}
@media (prefers-color-scheme:dark){:root{
  --paper:#0F141A; --raised:#161D26; --ink:#EAEFF4; --muted:#9FB0BE; --faint:#6C7C8A;
  --line:#28323D; --line2:#1E262F; --teal:#3BB39D; --teal-d:#2E9E89; --gold:#D9A63C;
  --clay:#E0704F; --shadow:0 1px 2px rgba(0,0,0,.3),0 12px 34px rgba(0,0,0,.4);
}}
:root[data-theme="dark"]{
  --paper:#0F141A; --raised:#161D26; --ink:#EAEFF4; --muted:#9FB0BE; --faint:#6C7C8A;
  --line:#28323D; --line2:#1E262F; --teal:#3BB39D; --teal-d:#2E9E89; --gold:#D9A63C;
  --clay:#E0704F; --shadow:0 1px 2px rgba(0,0,0,.3),0 12px 34px rgba(0,0,0,.4);
}
:root[data-theme="light"]{
  --paper:#F4F6F8; --raised:#FFFFFF; --ink:#12171E; --muted:#5A6A7A; --faint:#8A97A3;
  --line:#DDE3E9; --line2:#EAEEF2; --teal:#0E7C6B; --teal-d:#0B6153; --gold:#B57F14;
  --clay:#B4472C; --shadow:0 1px 2px rgba(18,23,30,.04),0 10px 30px rgba(18,23,30,.07);
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper)}
body{color:var(--ink);
  font-family:"Segoe UI","Arial Hebrew","Assistant","Heebo",system-ui,-apple-system,sans-serif;
  line-height:1.7;font-size:18px;-webkit-font-smoothing:antialiased;
  font-variant-numeric:tabular-nums;
  min-height:100vh;display:flex;align-items:center;justify-content:center;padding:48px 20px}
.num{font-variant-numeric:tabular-nums;direction:ltr;unicode-bidi:isolate}
.card{width:100%;max-width:680px}
.kicker{font-size:12.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--teal);
  font-weight:700;margin-bottom:16px;text-align:center}
h1{font-size:clamp(28px,5.6vw,42px);line-height:1.15;font-weight:800;letter-spacing:-.01em;
  margin:0 0 16px;text-align:center;text-wrap:balance}
.lede{font-size:18px;color:var(--muted);margin:0 auto 8px;max-width:52ch;text-align:center}
.divider{height:1px;background:var(--line);margin:34px 0 30px}

.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:0 0 8px}
.stat{background:var(--raised);border:1px solid var(--line);border-radius:16px;
  box-shadow:var(--shadow);padding:22px 16px;text-align:center}
.stat .v{font-size:clamp(34px,7vw,44px);font-weight:800;line-height:1;letter-spacing:-.02em}
.stat.a .v{color:var(--gold)} .stat.b .v{color:var(--teal)} .stat.c .v{color:var(--clay)}
.stat .l{font-size:13.5px;color:var(--muted);margin-top:12px;line-height:1.45}
@media(max-width:560px){.stats{grid-template-columns:1fr;gap:12px}
  .stat{display:flex;align-items:center;gap:18px;text-align:start;padding:18px 20px}
  .stat .v{font-size:38px} .stat .l{margin-top:0}}

.sec-eyebrow{font-size:12px;letter-spacing:.16em;font-weight:700;color:var(--faint);
  margin:0 0 12px;text-align:center}
.sec-eyebrow.teal{color:var(--teal)}
.framing{font-size:14.5px;color:var(--faint);text-align:center;margin:16px auto 0;max-width:50ch}

.example{background:var(--raised);border:1px solid var(--line);border-radius:16px;
  box-shadow:var(--shadow);padding:22px 24px;margin:22px 0 0}
.example .sec-eyebrow{text-align:start;margin-bottom:12px}
.ex-intro{margin:0 0 16px;font-size:15.5px}
.ex-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:620px){.ex-grid{grid-template-columns:1fr}}
.ex-card{background:var(--paper);border:1px solid var(--line2);border-radius:12px;padding:14px 16px}
.ex-fund{font-weight:700;font-size:14.5px;line-height:1.35}
.ex-won{font-size:12.5px;color:var(--muted);margin-top:4px}
.ex-track{margin-top:12px;display:flex;flex-direction:column}
.ex-step{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
  padding:8px 0;border-top:1px solid var(--line2)}
.ex-step:first-child{border-top:none}
.ex-when{font-size:13px;color:var(--muted);white-space:nowrap}
.ex-place{font-size:13.5px;font-weight:700;color:var(--muted);text-align:start}
.ex-place.top{color:var(--teal)} .ex-place.low{color:var(--clay)}
.ex-place.none{color:var(--faint);font-weight:400}
.ex-ret{font-weight:600;font-size:12px;color:var(--faint);margin-inline-start:2px}
.ex-note{margin:16px 0 0;font-size:13px;color:var(--faint)}

.summary{background:var(--raised);border:1px solid var(--line);border-radius:16px;
  box-shadow:var(--shadow);padding:24px 26px;margin:26px 0 30px;position:relative;overflow:hidden}
.summary::before{content:"";position:absolute;inset-inline-start:0;top:0;bottom:0;
  width:4px;background:var(--teal)}
.summary .sec-eyebrow{text-align:start;margin-bottom:14px}
.summary p{margin:0;font-size:16.5px} .summary p + p{margin-top:12px}
.summary b{font-weight:800}
.summary p.fine{font-size:14px;color:var(--muted)}

.cta{display:flex;flex-direction:column;align-items:center;gap:14px}
.btn{display:inline-flex;align-items:center;gap:10px;background:var(--teal);color:#fff;
  text-decoration:none;font-size:17px;font-weight:700;padding:15px 30px;border-radius:999px;
  box-shadow:var(--shadow);transition:background .15s,transform .15s}
.btn:hover{background:var(--teal-d);transform:translateY(-1px)}
.btn .ar{font-size:18px}
.subnote{font-size:13px;color:var(--faint);text-align:center}
.src{margin-top:36px;text-align:center;font-size:12.5px;color:var(--faint);line-height:1.7}
.src b{color:var(--muted);font-weight:600}
.disclaimer{margin:22px auto 0;max-width:60ch;text-align:center;font-size:11.5px;
  color:var(--faint);line-height:1.65}
.disclaimer-title{margin:0 0 7px;text-align:center;font-size:14px;font-weight:800;color:var(--muted)}
.disclaimer p{margin:0}
.credit{margin:9px 0 0;text-align:center;font-size:11.5px;color:var(--faint)}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<main class="card">
  <div class="kicker">חיסכון ארוך טווח · נתוני רשות שוק ההון</div>
  <h1>מה קרה לקופות שהובילו בתשואה בשנים שלאחר מכן?</h1>
  <p class="lede">המחקר כלל <b><span class="num">__NFUNDS__</span> קופות ומסלולי השקעה</b>
    בשנים <span class="num">2010-2025</span>. בכל שנה נבחרה המובילה בכל קטגוריה,
    ונבדק הדירוג שלה בשלוש השנים הבאות. ההשוואה נעשתה בין קופות מאותה קטגוריה.</p>
  <div class="divider"></div>

  <div class="sec-eyebrow">הממצאים</div>
  <div class="stats">
    <div class="stat a">
      <div class="v num">__NO1__</div>
      <div class="l">מהמובילות חזרו למקום הראשון בשנה שאחרי</div>
    </div>
    <div class="stat b">
      <div class="v num">__RANK__</div>
      <div class="l">הדירוג החציוני של המובילה שנה אחרי</div>
    </div>
    <div class="stat c">
      <div class="v num">__BOT__</div>
      <div class="l">מהמובילות ירדו למחצית התחתונה כבר אחרי שנה</div>
    </div>
  </div>

  <p class="framing">שיעור הקופות שלא נצפו באותה קטגוריה עלה
    מ<span class="num">__VAN1__</span> בשנה הראשונה
    ל<span class="num">__VAN3__</span> עד השנה השלישית.</p>

  <div class="example">
    <div class="sec-eyebrow teal">דוגמאות מוחשיות: קופה אחת לאורך זמן</div>
    <p class="ex-intro">כל דוגמה עוקבת אחרי קופה גדולה ומוכרת שסיימה במקום הראשון
      בקטגוריה שלה, ומראה היכן דורגה שנה, שנתיים ושלוש שנים לאחר מכן. לעיתים שמרה על
      מקומה, ולעיתים צנחה אל תחתית הקטגוריה.</p>
    <div class="ex-grid">__EX_CARDS__</div>
    <p class="ex-note">הקופות הגדולות ביותר שהובילו בקטגוריה שלהן משנת 2016 ואילך,
      להמחשה בלבד. המעקב המלא, בכל הקטגוריות ובכל השנים, נמצא במחקר המלא.</p>
  </div>

  <section class="summary">
    <div class="sec-eyebrow teal">המסקנה</div>
    <p><b>מקום ראשון בשנה אחת לא מבטיח המשך הובלה.</b> רוב המובילות לא נשארו במקום הראשון בשנה שאחרי.</p>
    <p>בממוצע הן השיגו <span class="num">__GAPEV__</span> נקודות אחוז יותר מממוצע
      הקטגוריה. אבל רוב הפער נוצר בשנים __CONCYEARS__. בלעדיהן הוא כמעט נעלם.</p>
    <p class="fine">התשואות הן לפני דמי ניהול. ההשוואה היא לממוצע הקופות באותה קטגוריה.</p>
  </section>

  <div class="cta">
    <a class="btn" href="analysis/report.html">
      <span>למחקר המלא, למתודולוגיה ולטבלאות</span><span class="ar">←</span>
    </a>
    <div class="subnote">טבלאות שנה אחר שנה לכל קטגוריה · מתודולוגיה · הקוד המלא</div>
  </div>

  <div class="src">
    <span><b>מקור:</b> גמל-נט (רשות שוק ההון)</span> ·
    <span><b>תקופה:</b> <span class="num">2010-2025</span></span> ·
    <span><b>היקף:</b> <span class="num">__NFUNDS__</span> קופות ומסלולים,
      <span class="num">__SIGNALS__</span> אירועי הובלה,
      <span class="num">__NCAT__</span> קטגוריות</span>
  </div>
  <div class="disclaimer">
    <div class="disclaimer-title">גילוי נאות</div>
    <p>התוכן נועד למידע כללי ולמטרות לימודיות בלבד, ואינו
    מהווה ייעוץ או שיווק פנסיוני או השקעות ואינו תחליף לייעוץ אישי המתחשב בנתוניו ובצרכיו
    של כל אדם. הנתונים מבוססים על מקור פומבי (גמל-נט) וייתכנו בהם אי דיוקים.
    ביצועי עבר אינם מעידים על העתיד.</p>
  </div>
  <p class="credit">מאת: דורון שרייבמן</p>
</main>
</body>
</html>"""

idx_out = INDEX
for k, v in {"__NO1__":IDX["no1"], "__BOT__":IDX["bot"], "__RANK__":IDX["rank"],
             "__VAN1__":IDX["van1"], "__VAN3__":IDX["van3"],
             "__SIGNALS__":IDX["signals"], "__NCAT__":str(len(CAT_ORDER)),
             "__NFUNDS__":IDX["nfunds"], "__CONCYEARS__":IDX["concyears"],
             "__GAPEV__":IDX["gapev"],
             "__EX_CARDS__":IDX["ex_cards"]}.items():
    idx_out = idx_out.replace(k, v)
open(os.path.join(HERE, os.pardir, "index.html"), "w", encoding="utf-8").write(idx_out)
print("wrote index.html")
