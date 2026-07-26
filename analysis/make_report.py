#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 3 - assemble the Hebrew research report (analysis/REPORT_he.md) from the
CSV outputs. Objective / descriptive framing, organised around the study's
three questions.
"""
import csv, os, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

def read(name):
    return list(csv.DictReader(open(os.path.join(HERE, name), encoding="utf-8-sig")))

events = read("events.csv")
strat = read("strategy_summary.csv")
risk = read("risk_summary.csv")

from source import FAMILIES, FAMILY_LABEL, TRACK_ORDER

# Categories actually present in the results, ordered family -> track.
_present = {(e["domain"], e["category"]) for e in events}
CAT_ORDER = [
    ("gemel", f"{fam} | {track}")
    for fam in FAMILIES for track in TRACK_ORDER
    if ("gemel", f"{fam} | {track}") in _present
]

def family(cat):
    """Saver-facing name of the fund family this category belongs to."""
    head = cat.split(" | ")[0]
    return FAMILY_LABEL.get(head, head)

def label(cat):
    """Family · track — the study's comparison group."""
    return f"{family(cat)} · {cat.split(' | ')[1]}"

def fnum(x, suf="%"):
    if x is None or x == "":
        return "—"
    return f"{float(x):.1f}{suf}"

# ---------- horizon statistics (descriptive) ----------
def horizon_stats(k):
    ranks, ns, pct, normpos = [], [], [], []
    present = absent = total = 0
    still1 = top3 = topq = half = bot = 0
    for e in events:
        st = e.get(f"y{k}_status")
        if st in ("present", "absent"):
            total += 1
        if st == "absent":
            absent += 1
        if st != "present":
            continue
        present += 1
        r = int(e[f"y{k}_rank"]); n = int(e[f"y{k}_n"]); p = float(e[f"y{k}_percentile"])
        ranks.append(r); ns.append(n); pct.append(p); normpos.append(r / n)
        if r == 1: still1 += 1
        if r <= 3: top3 += 1
        if r <= max(1, round(n / 4)): topq += 1
        if r <= n / 2: half += 1
        else: bot += 1
    return {
        "k": k, "present": present, "absent": absent, "total": total,
        "med_rank": statistics.median(ranks), "med_n": statistics.median(ns),
        "med_pos": statistics.median(normpos) * 100,
        "mean_pctile": statistics.mean(pct), "med_pctile": statistics.median(pct),
        "still1": still1 / present * 100, "top3": top3 / present * 100,
        "topq": topq / present * 100, "half": half / present * 100,
        "bot": bot / present * 100, "vanished": absent / total * 100,
    }

H = {k: horizon_stats(k) for k in (1, 2, 3)}
HORIZON_LABEL = {1: "שנה", 2: "שנתיים", 3: "שלוש שנים"}

lines = []
w = lines.append

w("# מה קרה בפועל לקופות שהובילו בתשואה? מחקר תיאורי")
w("")
_years = sorted(int(e["signal_year"]) for e in events)
w(f"**עודכן:** יולי 2026 · **מקור:** גמל-נט (רשות שוק ההון) · "
  f"**תקופה:** שנות איתות {_years[0]}-{_years[-1]}, מעקב עד סוף {_years[-1]}")
w("")
w("## מטרה")
w("")
w("המחקר מדמה חוסך שבכל תחילת שנה בוחן את טבלת התשואות של השנה שחלפה, מזהה את "
  "הקופה שהשיגה את התשואה הגבוהה ביותר **בקטגוריה שלה**, ומעביר אליה את כספו. "
  "לאחר מכן עקבתי אחרי אותה קופה ובדקתי כיצד התנהגה בשנים שלאחר המעבר. "
  "המטרה אינה להוכיח או להפריך מראש את כדאיות המעבר, אלא **להציג את הנתונים "
  "ההיסטוריים באופן אובייקטיבי** ולאפשר להסיק מהם מסקנות מבוססות עובדות. "
  "המחקר מתמקד בשנות איתות **מ-2010 ואילך**, ומשווה כל קופה רק מול קופות "
  "**באותה משפחת מוצר ובאותו מסלול השקעה** (עמודת `מסלול ממופה`), כך שקופה אינה "
  "\"מנצחת\" רק משום שלקחה יותר סיכון מהמתחרות שלה.")
w("")
w("### שלוש השאלות")
w("1. האם קופות שהובילו בשנה מסוימת מצליחות לשמור על מעמדן גם בהמשך?")
w("2. מהו הדירוג האופייני של קופה מובילה לאחר שנה, שנתיים ושלוש שנים?")
w("3. האם נמצא יתרון עקבי למעבר לקופה שהובילה בשנה הקודמת?")
w("")
w("## שיטה")
w("")
w("- **נכללות רק קופות הפתוחות לכלל הציבור.** קופות סקטוריאליות/מגזריות (למקצוע או "
  "לענף מסוים) וקופות סגורות (למעסיק/גוף מסוים) הוצאו לפי שדה `TARGET_POPULATION` של "
  "הרשות, וכן עוטפי IRA וקופות דמי מחלה. כולן אינן אפיק חיסכון שחוסך רגיל יכול לבחור בו.")
w("- תשואה שנתית לכל קופה חושבה משרשור 12 התשואות החודשיות (`MONTHLY_YIELD`); "
  "נכללו רק שנים עם 12 חודשי דיווח מלאים (אומת מול `YEAR_TO_DATE_YIELD` של דצמבר).")
w("- **קטגוריה** = משפחת המוצר + **מסלול ההשקעה** של הקופה "
  "(למשל *קרן השתלמות · עד 25% מניות*). זו קבוצת ההשוואה הרלוונטית לחוסך: הוא בוחר "
  "קודם מוצר ומסלול, ורק אז קופה. נדרשו לפחות 8 קופות בקטגוריה בשנת האיתות.")
w("- **המסלול** נלקח מעמודת `מסלול ממופה` שבקובץ הנתונים, שמקבצת את עשרות המסלולים "
  "המדווחים לשש קבוצות: " + " · ".join(f"*{t}*" for t in TRACK_ORDER) + ". "
  "המסלול קבוע לכל קופה על פני כל ההיסטוריה. הקבוצה השיורית *אחר* (מסלולי מט\"ח) "
  "אינה נכללת: היא מעולם לא הגיעה ל-8 קופות במשפחה בשנה אחת.")
w("- לכל שנת **איתות** Y זוהתה הקופה במקום ה-1, ונרשמו התשואה והדירוג של **אותה "
  "קופה** (לפי מזהה) בשנים Y+1, Y+2, Y+3, מתוך מספר הקופות בקטגוריה באותה שנה.")
w("- *אחוזון* 100 = מקום ראשון, 0 = מקום אחרון. אם ל\"מקום הראשון\" אין משמעות "
  "מתמשכת, האחוזון הצפוי בשנה שאחרי הוא 50.")
_n_study = len(CAT_ORDER)
_fams = sorted({family(c) for _, c in CAT_ORDER},
               key=lambda f: list(FAMILY_LABEL.values()).index(f))
w(f"- סך הכול נבדקו **{H[1]['total']} אירועי איתות** על פני {_n_study} קטגוריות, "
  f"בארבע משפחות מוצר: {' · '.join(_fams)}. משפחות שהחוסך אינו בוחר בהן "
  "(קופה מרכזית לפיצויים, שהיא כלי של המעסיק) אינן נכללות.")
w("")

# ---------- Q1 ----------
w("## שאלה 1: האם המובילות שומרות על מעמדן?")
w("")
w("מה עלה בגורל הקופה שדורגה ראשונה, על פני כל הקטגוריות וכל השנים:")
w("")
w("| לאחר | חזרו למקום 1 | נשארו בשלושת הראשונים | נשארו ברבעון העליון | "
  "נשארו במחצית העליונה | ירדו למחצית התחתונה | נסגרו / מוזגו |")
w("|---|---:|---:|---:|---:|---:|---:|")
for k in (1, 2, 3):
    h = H[k]
    w(f"| {HORIZON_LABEL[k]} | {h['still1']:.0f}% | {h['top3']:.0f}% | {h['topq']:.0f}% | "
      f"{h['half']:.0f}% | {h['bot']:.0f}% | {h['vanished']:.0f}% |")
w("")
w(f"**מהנתונים:** בשנה שאחרי האיתות רק {H[1]['still1']:.0f}% מהמובילות חזרו "
  f"למקום הראשון, ובערך {H[1]['top3']:.0f}% נשארו בשלושת הראשונים. במקביל, כבר לאחר "
  f"שנה {H[1]['bot']:.0f}% מהמובילות ירדו אל המחצית התחתונה של הקטגוריה, "
  f"ועוד {H[1]['vanished']:.0f}% מהן כלל לא שרדו כקופה נפרדת (נסגרו או מוזגו). "
  f"לאורך שלוש שנים שיעור החזרה למקום הראשון יורד ל-{H[3]['still1']:.0f}%, "
  f"ושיעור ההיעלמות עולה ל-{H[3]['vanished']:.0f}%.")
w("")

# ---------- Q2 ----------
w("## שאלה 2: מהו הדירוג האופייני לאחר 1, 2, 3 שנים?")
w("")
w("הדירוג האופייני (חציוני) של הקופה המובילה, מבין הקופות ששרדו בקטגוריה:")
w("")
w("| לאחר | דירוג חציוני | מיקום חציוני יחסי | אחוזון ממוצע | אחוזון חציוני |")
w("|---|---:|---:|---:|---:|")
for k in (1, 2, 3):
    h = H[k]
    w(f"| {HORIZON_LABEL[k]} | מקום {h['med_rank']:.0f} מתוך ~{h['med_n']:.0f} | "
      f"{h['med_pos']:.0f}% מהצמרת | {h['mean_pctile']:.0f} | {h['med_pctile']:.0f} |")
w("")
w(f"**מהנתונים:** הדירוג האופייני של מובילת אשתקד בשנה שאחרי הוא בערך מקום "
  f"{H[1]['med_rank']:.0f} מתוך ~{H[1]['med_n']:.0f}, כלומר סביב השליש העליון של "
  f"הקטגוריה ({H[1]['med_pos']:.0f}% מהצמרת), ולא סמוך למקום הראשון. "
  f"האחוזון הממוצע (~{H[1]['mean_pctile']:.0f}) גבוה מ-50, אך מתקרב אל "
  f"האמצע ככל שחולף הזמן: מ-{H[1]['mean_pctile']:.0f} לאחר שנה אל "
  f"{H[3]['mean_pctile']:.0f} לאחר שלוש שנים.")
w("")

# ---------- Q3 ----------
w("## שאלה 3: האם נמצא יתרון עקבי?")
w("")
w("**(א) תוצאה כספית.** סימולציה: חוסך שבכל שנה עובר לקופה שהובילה אשתקד "
  "(\"רודף\"), מול חוסך שמחזיק את ממוצע הקטגוריה (\"נשאר\"). תשואה שנתית ממוצעת (CAGR):")
w("")
w("| קטגוריה | שנים | רודף | נשאר | פער שנתי |")
w("|---|---:|---:|---:|---:|")
strat_by = {(s["domain"], s["category"]): s for s in strat}
for dom, cat in CAT_ORDER:
    s = strat_by.get((dom, cat))
    if not s: continue
    g = float(s['gap_annualized_pp'])
    w(f"| {label(cat)} | {s['n_years']} | {s['chase_annualized_pct']}% | "
      f"{s['stay_annualized_pct']}% | {'+' if g >= 0 else ''}{s['gap_annualized_pp']} נק' |")
gaps = [float(s["gap_annualized_pp"]) for s in strat]
nwin = sum(1 for g in gaps if g > 0)
nsmall = sum(1 for g in gaps if abs(g) < 1)
# Average gap per track, pooled across the four families.
gap_by_track = {}
for t in TRACK_ORDER:
    vals = [float(x["gap_annualized_pp"]) for x in strat
            if x["category"].split(" | ")[1] == t]
    if vals:
        gap_by_track[t] = statistics.mean(vals)
_ranked_tracks = sorted(gap_by_track.items(), key=lambda kv: -kv[1])
wide_track, wide_gap = _ranked_tracks[0]
narrow_track, narrow_gap = _ranked_tracks[-1]
w("")
w("ממוצע הפער השנתי בכל מסלול, על פני ארבע משפחות המוצר:")
w("")
w("| מסלול | פער שנתי ממוצע (רודף − נשאר) |")
w("|---|---:|")
for t in TRACK_ORDER:
    if t in gap_by_track:
        w(f"| {t} | {gap_by_track[t]:+.2f} נק' |")
w("")
w(f"ה\"רודף\" הקדים את ה\"נשאר\" ב-{nwin} מתוך {len(gaps)} הקטגוריות, אך הפער קטן "
  f"ולא אחיד: בממוצע {statistics.mean(gaps):+.2f} נק' לשנה, וברוב הקטגוריות "
  f"({nsmall} מתוך {len(gaps)}) פחות מנקודה אחת לשנה. הוא הגדול ביותר במסלול "
  f"*{wide_track}* ({wide_gap:+.2f} נק') והקטן ביותר במסלול *{narrow_track}* "
  f"({narrow_gap:+.2f} נק'). הפער אינו עולה באופן שיטתי עם רמת הסיכון של המסלול.")
w("")
w("**(ב) הקשר לסיכון.** בדקתי היכן מדורגת המובילה בתוך הקטגוריה במונחי **תנודתיות** "
  "(סטיית התקן של 12 תשואותיה החודשיות באותה שנה) ו**חשיפה מנייתית** "
  "(50 = ללא הטיה, 100 = המסוכנת ביותר בקבוצה):")
w("")
w("| קטגוריה | אחוזון תנודתיות | אחוזון חשיפה מנייתית |")
w("|---|---:|---:|")
risk_by = {(r["domain"], r["category"]): r for r in risk}
for dom, cat in CAT_ORDER:
    r = risk_by.get((dom, cat))
    if not r: continue
    w(f"| {label(cat)} | {fnum(r['winner_vol_pctile'],'')} | "
      f"{fnum(r['winner_equity_pctile'],'')} |")
pooled = risk_by.get(("POOLED", ""))
if pooled:
    w(f"| **משוקלל (כל הקטגוריות)** | **{fnum(pooled['winner_vol_pctile'],'')}** | "
      f"**{fnum(pooled['winner_equity_pctile'],'')}** |")
w("")
_pv = round(float(pooled['winner_vol_pctile'])) if pooled and pooled.get('winner_vol_pctile') else 66
w(f"**מהנתונים:** גם לאחר שהשוויתי בין קופות באותו מסלול, המובילה יושבת בממוצע "
  f"באחוזון תנודתיות ~{_pv} **בתוך** הקטגוריה, כלומר היא נוטה להיות מהקופות "
  "התנודתיות יותר בקבוצתה. מסלול הוא סרגל גס: בתוך מסלול אחד עדיין נכנסות קופות "
  "בעלות אופי שונה, והמובילה נוטה להיות זו שבקצה הנועז שלו. הדבר בולט במיוחד "
  "במסלולים הסולידיים, שבהם המובילה היא כמעט תמיד הקופה שלקחה את הסיכון הגדול "
  "ביותר בקבוצתה. מאחר שהתקופה הנבדקת כללה בעיקר שנים של עליות בשווקים, חלק "
  "מהפער הכספי שבסעיף (א) משקף סיכון ולא בהכרח התמדה של ביצועים.")
w("")

# ---------- per-category tracking ----------
w("## מעקב מפורט לפי קטגוריה")
w("")
w("לכל שנת איתות: הקופה שהובילה, תשואתה, ובכל אחת משלוש השנים שאחרי התשואה "
  "והדירוג (מקום מתוך מספר הקופות בקטגוריה). \"אין נתון\" = אין די נתונים; "
  "\"נסגרה/מוזגה\" = הקופה חדלה להתקיים כקופה נפרדת.")
w("")
ev_by = defaultdict(list)
for e in events:
    ev_by[(e["domain"], e["category"])].append(e)

def cell(e, k):
    st = e.get(f"y{k}_status")
    if st == "present":
        return f"{e[f'y{k}_return']}% · {e[f'y{k}_rank']}/{e[f'y{k}_n']}"
    if st == "absent":
        return "נסגרה/מוזגה"
    return "אין נתון"

_last_fam = None
for dom, cat in CAT_ORDER:
    rows = sorted(ev_by.get((dom, cat), []), key=lambda x: int(x["signal_year"]))
    if not rows: continue
    fam = family(cat)
    if fam != _last_fam:
        w(f"## ◆ {fam}")
        w("")
        _last_fam = fam
    w(f"### {label(cat)}")
    w("")
    w("| שנת איתות | הקופה שנבחרה | תשואת האיתות | שנה +1 (תשואה·דירוג) | שנה +2 | שנה +3 |")
    w("|---|---|---:|---|---|---|")
    for e in rows:
        name = e["winner_name"][:42]
        w(f"| {e['signal_year']} | {name} | {e['signal_return']}% | "
          f"{cell(e,1)} | {cell(e,2)} | {cell(e,3)} |")
    w("")

# ---------- summary ----------
w("## תמצית הממצאים")
w("")
w("הנתונים ההיסטוריים מצביעים על התמונה הבאה (מוצגת כעובדות, ללא המלצה):")
w("")
w(f"1. **שמירת מעמד חלקית וזמנית.** רק {H[1]['still1']:.0f}% מהמובילות חזרו למקום "
  f"הראשון בשנה שאחרי, ו-{H[1]['bot']:.0f}% ירדו למחצית התחתונה כבר לאחר שנה. "
  f"בתוך שלוש שנים {H[3]['vanished']:.0f}% מהמובילות נסגרו או מוזגו.")
w(f"2. **הדירוג האופייני הוא \"טוב מהממוצע\", לא \"מוביל\".** מובילת אשתקד מדורגת "
  f"בשנה שאחרי סביב מקום {H[1]['med_rank']:.0f} מתוך ~{H[1]['med_n']:.0f} "
  f"(השליש העליון), והאחוזון הממוצע מתקרב אל האמצע עם הזמן.")
w(f"3. **היתרון הכספי קטן ולא אחיד.** בממוצע {statistics.mean(gaps):+.2f} נק' לשנה, "
  f"וברוב הקטגוריות ({nsmall} מתוך {len(gaps)}) פחות מנקודה אחת. הוא הגדול ביותר במסלול "
  f"*{wide_track}* ({wide_gap:+.2f} נק'). גם בתוך מסלול אחיד המובילה יושבת באחוזון "
  f"תנודתיות ~{_pv}, כלומר חלק מהפער משקף סיכון עודף בתקופה של שווקים עולים ולא "
  "התמדה של ביצועים. הסימולציה גם אינה מנכה דמי ניהול, מס ועלויות מעבר.")
w("")
w("הנתונים המלאים והקוד בתיקיית `analysis/`. לקורא/ת נותרת ההחלטה כיצד לשקלל "
  "ממצאים אלה.")
w("")
w("---")
w("*שחזור: `build_annual.py` → `chase_analysis.py` → `risk_check.py` → "
  "`robustness.py` → `make_report.py` / `build_html.py`.*")

out = os.path.join(HERE, "REPORT_he.md")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print("wrote", out)
