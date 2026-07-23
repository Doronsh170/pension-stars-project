#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 4 - build a self-contained, theme-aware HTML report (analysis/report.html)
from the CSV outputs. Data is inlined so the page is faithful and reproducible.
"""
import csv, os, json, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

def read(n): return list(csv.DictReader(open(os.path.join(HERE, n), encoding="utf-8-sig")))
events = read("events.csv"); strat = read("strategy_summary.csv"); risk = read("risk_summary.csv")

CAT_ORDER = [
    ("gemel", 'קרנות השתלמות | כללי'), ("gemel", 'קרנות השתלמות | מניות'),
    ("gemel", 'קרנות השתלמות | אג"ח'),
    ("gemel", 'תגמולים ואישית לפיצויים | כללי'),
    ("gemel", 'תגמולים ואישית לפיצויים | מניות'),
    ("gemel", 'תגמולים ואישית לפיצויים | אג"ח'),
    ("pension", 'קרנות חדשות'), ("pension", 'קרנות כלליות'),
]
def family(c):
    if c.startswith("קרנות השתלמות"): return "קרן השתלמות"
    if c.startswith("תגמולים"): return "קופת גמל"
    return "קרן פנסיה"
def label(c):
    if c.startswith("קרנות השתלמות") or c.startswith("תגמולים"):
        return family(c) + " · " + c.split(" | ")[1]
    return "קרן פנסיה · " + c

# ---- horizon statistics (descriptive) ----
def hstats(k):
    ranks=[]; ns=[]; pct=[]; normpos=[]; present=absent=total=0
    still1=top3=topq=half=bot=0
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
    r1=lambda x:round(x,1)
    return {"h":k,"present":present,"total":total,
        "med_rank":round(statistics.median(ranks)),"med_n":round(statistics.median(ns)),
        "med_pos":r1(statistics.median(normpos)*100),
        "pctile":r1(statistics.mean(pct)),"med_pctile":r1(statistics.median(pct)),
        "no1":r1(still1/present*100),"top3":r1(top3/present*100),"topq":r1(topq/present*100),
        "half":r1(half/present*100),"bot":r1(bot/present*100),
        "vanished":r1(absent/total*100)}
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
        "rows":[{"y":int(e["signal_year"]),"name":e["winner_name"],
                 "sret":float(e["signal_return"]),"sn":int(e["signal_n"]),
                 "k1":cellobj(e,1),"k2":cellobj(e,2),"k3":cellobj(e,3)} for e in rows]})

DATA=json.dumps({"persist":persist,"strat":strat_data,"cats":cats,
                 "pooled_vol":pooled_vol,"total":TOTAL_EVENTS},ensure_ascii=False)

def _gap(cat):
    s = strat_by.get(("gemel", cat)) or strat_by.get(("pension", cat))
    return f'{float(s["gap_annualized_pp"]):+.2f}'.replace("-", "−") if s else "—"
SG = _gap('קרנות השתלמות | כללי'); PG = _gap('תגמולים ואישית לפיצויים | כללי')

HTML = r"""<div id="page" dir="rtl">
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
.tbl-scroll{overflow-x:auto;border-top:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:560px}
th,td{padding:9px 12px;text-align:start;border-bottom:1px solid var(--line2);white-space:nowrap}
thead th{font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:var(--faint);
  font-weight:700;position:sticky;top:0;background:var(--raised)}
td.name{white-space:normal;min-width:200px;color:var(--muted)}
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
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="masthead"><div class="wrap">
  <div class="kicker">מחקר תיאורי · שוק החיסכון ארוך הטווח</div>
  <h1>מה קרה בפועל לקופות שהובילו בתשואה?</h1>
  <p class="dek">חוסך בוחן בכל תחילת שנה את טבלת התשואות של אשתקד, מזהה את המובילה
    בקטגוריה שלו ומעביר אליה את כספו. עקבנו אחרי אותן קופות מובילות — בהפרדה בין
    קרן השתלמות, קופת גמל וקרן פנסיה — כדי להציג באופן אובייקטיבי כיצד התנהגו בשנים שאחרי.</p>
  <div class="sourceline">
    <span><b>מקור:</b> גמלנט · פנסיהנט (רשות שוק ההון)</span>
    <span><b>תקופה:</b> שנות איתות <span class="num">2010–2024</span> · מעקב עד <span class="num">2025</span></span>
    <span><b>היקף:</b> <span class="num">8</span> קטגוריות · <span class="num" id="evCount">104</span> אירועי איתות</span>
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
    <p class="body">עקבנו אחרי כל קופה שדורגה ראשונה, אל תוך שלוש השנים שאחרי. בשנה
      שאחרי האיתות <span class="emteal" id="s_no1">12%</span> מהמובילות בלבד חזרו למקום
      הראשון, וכ־<span id="s_top3">27%</span> נשארו בשלושת הראשונים. במקביל,
      <span class="em" id="s_bot">38%</span> ירדו כבר לאחר שנה אל המחצית התחתונה של
      הקטגוריה, וכ־<span class="em" id="s_van">10%</span> כלל לא שרדו כקופה נפרדת (נסגרו
      או מוזגו). לאורך זמן שיעור החזרה למקום הראשון יורד ושיעור ההיעלמות עולה.</p>
    <div class="figure">
      <div class="cap">שיעור המובילות שנשארו במקום 1, בשלושת הראשונים, ברבעון העליון,
        או שירדו למחצית התחתונה / חדלו להתקיים — לאחר 1, 2 ו־3 שנים.</div>
      <svg id="chartKeep" viewBox="0 0 720 340" role="img"
        aria-label="שמירת מעמד של המובילות לאורך שלוש שנים"></svg>
    </div>
  </section>

  <section>
    <div class="eyebrow">שאלה 02 · דירוג אופייני</div>
    <h2>מהו הדירוג האופייני לאחר 1, 2, 3 שנים?</h2>
    <p class="body">מבין הקופות ששרדו, הדירוג האופייני (החציוני) של מובילת אשתקד בשנה
      שאחרי הוא כ־<span class="emteal" id="s_medrank">מקום 10 מתוך 36</span> — סביב
      השליש העליון של הקטגוריה, לא סמוך למקום הראשון. האחוזון הממוצע גבוה מ־50 אך הולך
      ומתכנס אל עבר האמצע ככל שחולף הזמן.</p>
    <div class="figure">
      <div class="cap">אחוזון הדירוג של המובילה בשנים שאחרי (100 = מקום ראשון, 50 = אמצע
        הקטגוריה), ממוצע וחציון. קו ה־50 מסמן דירוג ממוצע ("ללא יתרון").</div>
      <svg id="chartPctile" viewBox="0 0 720 300" role="img"
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
    <p class="body"><b>(א) תוצאה כספית.</b> חוסך ש<span class="emteal">רודף</span> (עובר
      בכל שנה למובילת אשתקד) מול חוסך ש<span class="emteal">נשאר</span> בממוצע הקטגוריה.
      גודל הפער אינו אחיד: במסלולים <span class="em">הכלליים</span>, בהם מרוכז רוב
      כספם של החוסכים, הפער זעום ואף שלילי — כ־<span class="num">__SG__</span> נק' בקרן
      השתלמות כללי אך <span class="num">__PG__</span> נק' בקופת גמל כללי — והפערים
      הגדולים מופיעים במסלולי המניות ובקרנות הפנסיה.</p>
    <div class="figure">
      <div class="cap">פער התשואה השנתית (CAGR) בין "רודף" ל"נשאר", בנקודות אחוז, לפי קטגוריה.</div>
      <svg id="chartGap" viewBox="0 0 720 430" role="img"
        aria-label="פער התשואה בין רדיפה להישארות לפי קטגוריה"></svg>
    </div>
    <p class="body"><b>(ב) הקשר לסיכון.</b> המובילה יושבת בממוצע באחוזון תנודתיות
      <span class="emteal" id="volInline">67</span> בתוך הקטגוריה — היא נוטה להיות מהקופות
      המסוכנות יותר בקבוצתה (בפנסיה: כמעט תמיד מסלולי מניות או עוקבי
      <span class="num">S&P 500</span>). מאחר שהתקופה כללה בעיקר שנים של עליות, קופות
      בעלות חשיפה מנייתית גבוהה השיגו בממוצע תשואות גבוהות יותר — כך שהפער הכספי שבסעיף
      (א) קשור במידה רבה לרמת הסיכון, ולא בהכרח להתמדה של ביצועים.</p>
    <div class="figure">
      <div class="cap">אחוזון התנודתיות של המובילה בתוך הקטגוריה (50 = ללא הטיה, 100 = המסוכנת ביותר).</div>
      <svg id="chartRisk" viewBox="0 0 720 400" role="img"
        aria-label="אחוזון התנודתיות של המובילות לפי קטגוריה"></svg>
    </div>
  </section>

  <section>
    <div class="eyebrow">הנתונים המלאים</div>
    <h2>מעקב שנה־אחר־שנה, לפי קטגוריה</h2>
    <p class="body">לכל שנת איתות: הקופה שהובילה, תשואתה, והתשואה והדירוג שלה (מקום מתוך
      מספר הקופות בקטגוריה) בכל אחת משלוש השנים שאחרי.</p>
    <div id="tables"></div>
  </section>

  <div class="conc">
    <h2>תמצית הממצאים</h2>
    <p class="body">הנתונים ההיסטוריים מצביעים על התמונה הבאה, המוצגת כעובדות:</p>
    <ol>
      <li><b>שמירת מעמד חלקית וזמנית.</b> רק כ־12% מהמובילות חזרו למקום הראשון בשנה
        שאחרי, כ־40% ירדו למחצית התחתונה, ובתוך שלוש שנים כרבע מהן נסגרו או מוזגו.</li>
      <li><b>הדירוג האופייני הוא "טוב מהממוצע", לא "מוביל".</b> מובילת אשתקד מדורגת
        בשנה שאחרי סביב השליש העליון, והאחוזון הממוצע מתכנס אל עבר האמצע עם הזמן.</li>
      <li><b>היתרון הכספי אינו אחיד וקשור לסיכון.</b> במסלולים הכלליים הפער זעום ואף
        שלילי (קרן השתלמות כללי <span class="num">__SG__</span> נק', קופת גמל כללי
        <span class="num">__PG__</span> נק' לשנה), והפערים הגדולים מופיעים במסלולי
        המניות ובקרנות הפנסיה — היכן שהמובילה נוטה להיות הקופה המסוכנת יותר,
        בתקופה של שווקים עולים.</li>
    </ol>
    <p class="body">הנתונים המלאים והקוד בתיקיית <code>analysis/</code>. לקורא/ת נותרת
      ההחלטה כיצד לשקלל ממצאים אלה.</p>
  </div>

  <div class="foot">
    שחזור: <code>build_annual.py</code> → <code>chase_analysis.py</code> →
    <code>risk_check.py</code> → <code>make_report.py</code> / <code>build_html.py</code>.
    תשואה שנתית חושבה משרשור התשואות החודשיות; נכללו רק שנים עם 12 חודשי דיווח.
    הסימולציה הכספית אינה מנכה דמי ניהול, מס ועלויות מעבר.
  </div>
</div>

<script>
const D=__DATA__;
const NS="http://www.w3.org/2000/svg";
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function el(t,a){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;}
function txt(x,y,s,o={}){const t=el("text",{x,y,...o});t.textContent=s;return t;}

/* ---- inline figures ---- */
(function(){
  const p1=D.persist[0];
  document.getElementById("evCount").textContent=D.total;
  document.getElementById("s_no1").textContent=Math.round(p1.no1)+"%";
  document.getElementById("s_top3").textContent=Math.round(p1.top3)+"%";
  document.getElementById("s_bot").textContent=Math.round(p1.bot)+"%";
  document.getElementById("s_van").textContent=Math.round(p1.vanished)+"%";
  document.getElementById("s_medrank").textContent=
    "מקום "+p1.med_rank+" מתוך ~"+p1.med_n;
})();

/* ---- Q1: keep-status grouped bars (share %, per horizon) ---- */
(function(){
  const svg=document.getElementById("chartKeep");
  const W=720,H=340,mL=40,mR=16,mT=16,mB=44;
  const iw=W-mL-mR, ih=H-mT-mB;
  const groups=[
    {k:"no1",lab:"מקום 1",col:css("--gold")},
    {k:"top3",lab:"שלושה ראשונים",col:css("--teal")},
    {k:"topq",lab:"רבעון עליון",col:css("--teal")},
    {k:"bot",lab:"מחצית תחתונה",col:css("--clay")},
    {k:"vanished",lab:"נסגרו/מוזגו",col:css("--base")},
  ];
  const y=v=>mT+ih*(1-v/100);
  [0,25,50,75,100].forEach(g=>{
    svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(g),y2:y(g),stroke:css("--line"),"stroke-width":1}));
    svg.appendChild(txt(mL-8,y(g)+4,g+"%",{fill:css("--faint"),"font-size":10.5,"text-anchor":"end"}));
  });
  const gw=iw/groups.length;
  groups.forEach((g,gi)=>{
    const gx=mL+gw*gi, bw=gw*0.2, pad=gw*0.1;
    D.persist.forEach((d,hi)=>{
      const v=d[g.k]; const bx=gx+pad+bw*hi+ (gw*0.06)*hi;
      svg.appendChild(el("rect",{x:bx,y:y(v),width:bw,height:mT+ih-y(v),rx:2.5,
        fill:g.col,opacity:0.45+0.27*hi}));
      svg.appendChild(txt(bx+bw/2,y(v)-5,Math.round(v),{fill:g.col,"font-size":10.5,
        "font-weight":700,"text-anchor":"middle"}));
    });
    svg.appendChild(txt(gx+gw/2,H-mB+18,g.lab,{fill:css("--ink"),"font-size":12,
      "font-weight":600,"text-anchor":"middle"}));
  });
  // horizon legend
  const lx=mL+4; ["+1 שנה","+2 שנים","+3 שנים"].forEach((t,i)=>{
    const cx=lx+i*92;
    svg.appendChild(el("rect",{x:cx,y:H-14,width:11,height:11,rx:2,fill:css("--muted"),opacity:0.45+0.27*i}));
    svg.appendChild(txt(cx+16,H-4,t,{fill:css("--muted"),"font-size":11,"text-anchor":"start"}));
  });
})();

/* ---- Q2: percentile line (mean + median) ---- */
(function(){
  const svg=document.getElementById("chartPctile");
  const W=720,H=300,mL=44,mR=44,mT=24,mB=52;
  const iw=W-mL-mR, ih=H-mT-mB;
  const xs=D.persist.map((_,i)=>mL+iw*(i+0.5)/D.persist.length);
  const y=v=>mT+ih*(1-v/100);
  [0,25,50,75,100].forEach(g=>{
    svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(g),y2:y(g),
      stroke:g===50?css("--base"):css("--line"),"stroke-width":g===50?1.5:1,
      "stroke-dasharray":g===50?"5 4":""}));
    svg.appendChild(txt(mL-10,y(g)+4,g,{fill:css("--faint"),"font-size":11,"text-anchor":"end"}));
  });
  svg.appendChild(txt(W-mR+8,y(50)+4,"50",{fill:css("--base"),"font-size":11,"font-weight":700}));
  const line=(key,col,dash)=>{
    const p=D.persist.map((d,i)=>[xs[i],y(d[key])]);
    svg.appendChild(el("path",{d:"M"+p.map(q=>q.join(",")).join(" L"),fill:"none",
      stroke:col,"stroke-width":dash?2.5:3,"stroke-dasharray":dash||"",
      "stroke-linecap":"round","stroke-linejoin":"round"}));
  };
  line("med_pctile",css("--gold"),"2 5");
  line("pctile",css("--teal"),null);
  D.persist.forEach((d,i)=>{
    svg.appendChild(el("circle",{cx:xs[i],cy:y(d.med_pctile),r:4,fill:css("--gold")}));
    svg.appendChild(el("circle",{cx:xs[i],cy:y(d.pctile),r:5.5,fill:css("--teal")}));
    svg.appendChild(txt(xs[i],y(d.pctile)-13,Math.round(d.pctile),{fill:css("--teal"),
      "font-size":14,"font-weight":800,"text-anchor":"middle"}));
    svg.appendChild(txt(xs[i],H-mB+26,"שנה +"+d.h,{fill:css("--muted"),"font-size":13,
      "font-weight":700,"text-anchor":"middle"}));
  });
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

/* ---- gap chart (natural RTL: labels on right, bars grow left) ---- */
(function(){
  const svg=document.getElementById("chartGap");
  const W=720,H=430,mT=14,mB=30,rowH=(H-mT-mB)/D.strat.length;
  const maxGap=Math.max(...D.strat.map(d=>d.gap));
  const xLab=W-10;                       // labels anchored at far right
  const x0=250;                          // baseline (0), right side of bars
  const iw=x0-55;                        // positive bars grow leftward
  const scale=iw/(maxGap*1.08);
  D.strat.forEach((d,i)=>{
    const cy=mT+rowH*i, bh=Math.min(24,rowH*0.54), by=cy+(rowH-bh)/2;
    const isGen=d.label.endsWith("כללי");
    const neg=d.gap<0;
    const col=neg?css("--clay"):(isGen?css("--base"):(d.dom==="pension"?css("--clay"):css("--gold")));
    const span=Math.abs(d.gap)*scale;
    svg.appendChild(txt(xLab,by+bh/2+5,d.label,{fill:css("--ink"),"font-size":13,
      "font-weight":isGen?500:600,"text-anchor":"start"}));  // rtl: right edge at xLab
    const bx=neg?x0:x0-span;
    svg.appendChild(el("rect",{x:bx,y:by,width:Math.max(1,span),height:bh,rx:4,fill:col,
      opacity:isGen&&!neg?0.6:0.92}));
    const lx=neg?x0+span+7:x0-span-7;
    svg.appendChild(txt(lx,by+bh/2+5,(d.gap>=0?"+":"−")+Math.abs(d.gap).toFixed(2),
      {fill:col,"font-size":13,"font-weight":800,"text-anchor":neg?"start":"end",
       style:"direction:ltr"}));
  });
  svg.appendChild(el("line",{x1:x0,x2:x0,y1:mT,y2:H-mB,stroke:css("--ink"),"stroke-width":1.5}));
  svg.appendChild(txt(x0,H-mB+18,"0",{fill:css("--muted"),"font-size":12,"text-anchor":"middle","font-weight":700}));
  svg.appendChild(txt(x0-iw,H-mB+18,"פער שנתי (נק' אחוז)",{fill:css("--faint"),
    "font-size":11.5,"text-anchor":"start",style:"direction:rtl"}));
})();

/* ---- risk chart (lollipop around 50) ---- */
(function(){
  const svg=document.getElementById("chartRisk");
  const items=D.strat.filter(d=>d.vol!=null);
  const W=720,H=400,mT=12,mB=34,rowH=(H-mT-mB)/items.length;
  const xL=250,xR=W-40, base=50, mn=40,mx=100;
  const x=v=>xL+(xR-xL)*(v-mn)/(mx-mn);
  // grid
  [40,50,60,70,80,90,100].forEach(g=>{
    svg.appendChild(el("line",{x1:x(g),x2:x(g),y1:mT,y2:H-mB,
      stroke:g===base?css("--base"):css("--line"),"stroke-width":g===base?1.5:1,
      "stroke-dasharray":g===base?"5 4":""}));
    svg.appendChild(txt(x(g),H-mB+18,g,{fill:g===base?css("--muted"):css("--faint"),
      "font-size":11,"text-anchor":"middle","font-weight":g===base?700:400}));
  });
  svg.appendChild(txt(x(base),mT-1,"אמצע",{fill:css("--muted"),"font-size":10.5,"text-anchor":"middle"}));
  items.forEach((d,i)=>{
    const cy=mT+rowH*(i+0.5);
    const col=d.dom==="pension"?css("--clay"):(d.label.includes("כללי")?css("--teal"):css("--gold"));
    svg.appendChild(txt(xL-12,cy+4,d.label,{fill:css("--ink"),"font-size":13,"text-anchor":"end"}));
    svg.appendChild(el("line",{x1:x(base),x2:x(d.vol),y1:cy,y2:cy,stroke:col,"stroke-width":2.5,opacity:.5}));
    svg.appendChild(el("circle",{cx:x(d.vol),cy:cy,r:6,fill:col}));
    svg.appendChild(txt(x(d.vol)+ (d.vol>92?-14:12),cy+4,Math.round(d.vol),{fill:col,"font-size":12.5,
      "font-weight":800,"text-anchor":d.vol>92?"end":"start"}));
  });
})();
document.getElementById("volInline").textContent=Math.round(D.pooled_vol);

/* ---- tracking tables ---- */
(function(){
  const wrap=document.getElementById("tables");
  function cell(c){
    if(!c) return '<span style="color:var(--faint)">—</span>';
    if(c.closed) return '<span style="color:var(--faint);font-style:italic">נסגרה</span>';
    const dir=c.ret>=0?"up":"down";
    const top=c.rank<=Math.ceil(c.n/4), low=c.rank>c.n/2;
    let b= top?'<span class="badge top">צמרת</span>': low?'<span class="badge low">תחתית</span>':'';
    return `<span class="pill ${dir}">${c.ret>=0?'+':''}${c.ret.toFixed(1)}%</span>`
      +` <span class="rk num">${c.rank}/${c.n}</span> ${b}`;
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
      <td class="num" style="font-weight:700">+${r.sret.toFixed(1)}%</td>
      <td>${cell(r.k1)}</td><td>${cell(r.k2)}</td><td>${cell(r.k3)}</td></tr>`).join("");
    det.innerHTML=`<summary><span>${track||cat.label}</span>
      <span class="chev">▸</span></summary>
      <div class="tbl-scroll"><table>
      <thead><tr><th>שנת איתות</th><th>הקופה שנבחרה</th><th>תשואת האיתות</th>
      <th>שנה +1</th><th>שנה +2</th><th>שנה +3</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
    wrap.appendChild(det);
  });
})();
</script>
</div>"""

open(os.path.join(HERE, "report.html"), "w", encoding="utf-8").write(
    HTML.replace("__DATA__", DATA).replace("__SG__", SG).replace("__PG__", PG))
print("wrote report.html")
