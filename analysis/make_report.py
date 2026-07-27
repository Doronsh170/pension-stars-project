#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 3 - assemble the Hebrew research report (analysis/REPORT_he.md) from the
CSV outputs. Objective / descriptive framing, organised around the study's
two questions.
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
w("### שתי השאלות")
w("1. האם קופות שהובילו בשנה מסוימת מצליחות לשמור על מעמדן גם בהמשך?")
w("2. מהו הדירוג החציוני של קופה מובילה לאחר שנה, שנתיים ושלוש שנים?")
w("")
w("## שיטה")
w("")
w("- **נכללות רק קופות הפתוחות לכלל הציבור.** קופות סקטוריאליות/מגזריות (למקצוע או "
  "לענף מסוים) וקופות סגורות (למעסיק/גוף מסוים) הוצאו לפי שדה `TARGET_POPULATION` של "
  "הרשות, וכן עוטפי IRA וקופות דמי מחלה. כולן אינן אפיק חיסכון שחוסך רגיל יכול לבחור בו.")
w("- **קופות מבטיחות תשואה הוצאו.** קופות כמו *מנורה מבטחים יותר*, *מיטב ביטחון* או "
  "*הפניקס גמולה* מזכות בשיעור הקבוע בתקנון (4.5%/5.5% לשנה או הצמדה למדד) ולא בתשואת "
  "תיק השקעות, הן סגורות למצטרפים חדשים, ואינן מדווחות תשואה חודשית כלל. דירוגן מול "
  "קופות כספיות היה משווה הבטחה לתוצאת שוק.")
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
w("## שאלה 2: מהו הדירוג החציוני לאחר 1, 2, 3 שנים?")
w("")
w("הדירוג החציוני של הקופה המובילה, מבין הקופות ששרדו בקטגוריה:")
w("")
w("| לאחר | דירוג חציוני | מיקום חציוני יחסי | אחוזון ממוצע | אחוזון חציוני |")
w("|---|---:|---:|---:|---:|")
for k in (1, 2, 3):
    h = H[k]
    w(f"| {HORIZON_LABEL[k]} | מקום {h['med_rank']:.0f} מתוך ~{h['med_n']:.0f} | "
      f"{h['med_pos']:.0f}% מהצמרת | {h['mean_pctile']:.0f} | {h['med_pctile']:.0f} |")
w("")
w(f"**מהנתונים:** הדירוג החציוני של מובילת אשתקד בשנה שאחרי הוא בערך מקום "
  f"{H[1]['med_rank']:.0f} מתוך ~{H[1]['med_n']:.0f}, כלומר סביב השליש העליון של "
  f"הקטגוריה ({H[1]['med_pos']:.0f}% מהצמרת), ולא סמוך למקום הראשון. "
  f"האחוזון הממוצע (~{H[1]['mean_pctile']:.0f}) גבוה מ-50, אך מתקרב אל "
  f"האמצע ככל שחולף הזמן: מ-{H[1]['mean_pctile']:.0f} לאחר שנה אל "
  f"{H[3]['mean_pctile']:.0f} לאחר שלוש שנים.")
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

# ---------- output ----------
out = os.path.join(HERE, "REPORT_he.md")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print("wrote", out)
