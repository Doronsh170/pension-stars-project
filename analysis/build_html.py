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

DOM_HE = {"gemel": "גמל", "pension": "פנסיה"}
CAT_ORDER = [
    ("gemel", 'קרנות השתלמות | כללי'), ("gemel", 'תגמולים ואישית לפיצויים | כללי'),
    ("gemel", 'מרכזית לפיצויים | כללי'), ("gemel", 'קרנות השתלמות | מניות'),
    ("gemel", 'תגמולים ואישית לפיצויים | מניות'), ("gemel", 'קרנות השתלמות | אג"ח'),
    ("gemel", 'תגמולים ואישית לפיצויים | אג"ח'), ("pension", 'קרנות חדשות'),
    ("pension", 'קרנות כלליות'),
]
def cshow(c): return c.replace(" | ", " · ")

# ---- pooled persistence ----
pool={1:[],2:[],3:[]}; topq={1:[],2:[],3:[]}; no1={1:[],2:[],3:[]}; bot={1:[],2:[],3:[]}
for e in events:
    for k in (1,2,3):
        if e.get(f"y{k}_status")!="present": continue
        rk=int(e[f"y{k}_rank"]); n=int(e[f"y{k}_n"])
        pool[k].append(float(e[f"y{k}_percentile"]))
        topq[k].append(100 if rk<=n/4 else 0); no1[k].append(100 if rk==1 else 0)
        bot[k].append(100 if rk>n/2 else 0)
def mean(l): return round(statistics.mean(l),1) if l else None
persist=[{"h":k,"n":len(pool[k]),"pctile":mean(pool[k]),"topq":mean(topq[k]),
          "no1":mean(no1[k]),"bot":mean(bot[k])} for k in (1,2,3)]

strat_by={(s["domain"],s["category"]):s for s in strat}
risk_by={(r["domain"],r["category"]):r for r in risk}
strat_data=[{"label":f"{DOM_HE[d]} · {cshow(c)}","dom":d,
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
    cats.append({"label":f"{DOM_HE[d]} · {cshow(c)}","dom":d,
        "rows":[{"y":int(e["signal_year"]),"name":e["winner_name"],
                 "sret":float(e["signal_return"]),"sn":int(e["signal_n"]),
                 "k1":cellobj(e,1),"k2":cellobj(e,2),"k3":cellobj(e,3)} for e in rows]})

DATA=json.dumps({"persist":persist,"strat":strat_data,"cats":cats,
                 "pooled_vol":pooled_vol},ensure_ascii=False)

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
  width:4px;border-radius:4px;background:var(--clay)}
.tldr .lab{font-size:12px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--clay);font-weight:700;margin-bottom:8px}
.tldr p{margin:0;font-size:18.5px;font-weight:500}
.tldr strong{color:var(--ink);font-weight:800}

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
  <div class="kicker">מחקר אמפירי · שוק החיסכון ארוך הטווח</div>
  <h1>לרדוף אחרי כוכב התשואות של אתמול</h1>
  <p class="dek">בכל תחילת שנה החוסך רואה מי הובילה אשתקד ומעביר אליה את כספו.
    בדקנו על 27 שנות נתונים מה קרה באמת לאותן קופות מובילות — והאם המהלך משתלם.</p>
  <div class="sourceline">
    <span><b>מקור:</b> גמלנט · פנסיהנט (רשות שוק ההון)</span>
    <span><b>תקופה:</b> <span class="num">1999–2025</span> גמל · <span class="num">2011–2025</span> פנסיה</span>
    <span><b>היקף:</b> <span class="num">9</span> קטגוריות · <span class="num">160</span> אירועי איתות</span>
  </div>
</div></div>

<div class="wrap">
  <div class="tldr">
    <div class="lab">השורה התחתונה</div>
    <p>מעבר לקופה שהובילה בשנה הקודמת <strong>אינו מייצר יתרון אמין לאורך זמן</strong>.
      ההובלה נשחקת במהירות, ורוב ה"יתרון" הכספי שנמדד מוסבר בכך שהמנצחת היא כמעט
      תמיד הקופה <strong>המסוכנת יותר</strong> בקטגוריה — פרמיית סיכון בשוק עולה,
      לא כישרון שחוזר על עצמו.</p>
  </div>

  <section>
    <div class="eyebrow">ממצא 01 · התמדה</div>
    <h2>ההובלה מתפוגגת — המנצחת של אשתקד היא הימור, לא ודאות</h2>
    <p class="body">עקבנו אחרי כל קופה שדורגה ראשונה, אל תוך שלוש השנים שאחרי.
      אם ל"מקום הראשון" הייתה משמעות מתמשכת, היינו מצפים לראות אותה נשארת בצמרת.
      במקום זה היא מתכנסת בחזרה אל הממוצע: בשנה שאחרי היא נוחתת סביב האחוזון
      <span class="emteal">60</span> (מעט מעל הטלת מטבע), ורק כ־<span class="em">12%</span>
      מהמנצחות חוזרות למקום הראשון — נתון שקורס לכ־<span class="em">3%</span> תוך שלוש שנים.</p>
    <div class="figure">
      <div class="cap">אחוזון הדירוג הממוצע של המנצחת בשנים שאחרי (100 = ראשונה, 50 = אמצע הקטגוריה),
        לצד שיעור המנצחות ששמרו על המקום הראשון.</div>
      <svg id="chartPersist" viewBox="0 0 720 300" role="img"
        aria-label="גרף שחיקת ההובלה לאורך שלוש שנים"></svg>
      <div class="legend">
        <span><i class="dot" style="background:var(--teal)"></i> אחוזון דירוג ממוצע</span>
        <span><i class="dot" style="background:var(--gold)"></i> נשארו מקום ראשון</span>
        <span><i class="dot" style="background:var(--base)"></i> קו האקראיות (50)</span>
      </div>
    </div>
    <div class="stats" id="statsPersist"></div>
  </section>

  <section>
    <div class="eyebrow">ממצא 02 · כסף</div>
    <h2>ה"יתרון" הכספי מרוכז היכן שהסיכון מעורבב</h2>
    <p class="body">דימינו חוסך ש<span class="emteal">רודף</span> — עובר בכל שנה לקופה
      שהובילה אשתקד — מול חוסך ש<span class="emteal">נשאר</span> ומחזיק את ממוצע
      הקטגוריה. הרדיפה אמנם "ניצחה" בכל הקטגוריות, אבל שימו לב <span class="em">היכן</span>
      הפער גדול: במסלולים <span class="em">הכלליים</span>, שם יושב רוב כספם של החוסכים,
      הוא זניח — כ־<span class="num">0.15</span> נקודות בלבד לשנה. הפערים הגדולים צצים
      דווקא בפנסיה ובמסלולי מניות, קטגוריות שבהן טווח הסיכון בין הקופות רחב.</p>
    <div class="figure">
      <div class="cap">פער התשואה השנתית (CAGR) בין "רודף" ל"נשאר", בנקודות אחוז, לפי קטגוריה.
        ככל שהעמודה ארוכה יותר — כך גדול יותר ה"יתרון" הנמדד.</div>
      <svg id="chartGap" viewBox="0 0 720 430" role="img"
        aria-label="פער התשואה בין רדיפה להישארות לפי קטגוריה"></svg>
    </div>
  </section>

  <section>
    <div class="eyebrow">ממצא 03 · סיכון</div>
    <h2>המנצחת היא כמעט תמיד הקופה התנודתית יותר</h2>
    <p class="body">כאן מתפצח הפער. לכל מנצחת בדקנו את מיקומה בתוך הקטגוריה במונחי
      <span class="emteal">תנודתיות</span> (סטיית תקן). משוקלל על פני הכול, המנצחת יושבת
      באחוזון <span class="em" id="volInline">67</span> — כלומר מי שרודף אחרי המקום הראשון
      בוחר שיטתית קופה מסוכנת מהממוצע. בפנסיה זה חד במיוחד: המנצחות הן כמעט תמיד מסלולי
      מניות או עוקבי <span class="num">S&P 500</span>. בשוק שברובו עלה, הקופה המסוכנת
      מרוויחה יותר — וכשהשוק מתהפך, היא צונחת לתחתית.</p>
    <div class="figure">
      <div class="cap">אחוזון התנודתיות של המנצחת בתוך הקטגוריה (50 = ללא הטיה, 100 = המסוכנת ביותר).
        כמעט הכול מעל קו ה־50.</div>
      <svg id="chartRisk" viewBox="0 0 720 400" role="img"
        aria-label="אחוזון התנודתיות של המנצחות לפי קטגוריה"></svg>
    </div>
  </section>

  <section>
    <div class="eyebrow">הנתונים המלאים</div>
    <h2>מעקב שנה־אחר־שנה, לפי קטגוריה</h2>
    <p class="body">לכל שנת איתות: הקופה שהובילה, תשואתה, ומה עלה בגורלה בשלוש השנים
      שאחרי — התשואה והדירוג (מקום מתוך מספר הקופות בקטגוריה). שימו לב כמה פעמים
      המקום הראשון הופך תוך שנה למחצית התחתונה.</p>
    <div id="tables"></div>
  </section>

  <div class="conc">
    <h2>מסקנה</h2>
    <p class="body">שלושת הממצאים מצטרפים לתמונה אחת: <strong>בחירת קופה לפי טבלת
      התשואות של אשתקד היא רדיפה אחרי העבר, לא השקעה ביתרון עתידי.</strong></p>
    <ol>
      <li><b>ההובלה מתפוגגת.</b> המנצחת מתכנסת חזרה לכיוון הממוצע; רק כ־12% חוזרות
        למקום הראשון, וכ־40% צונחות למחצית התחתונה.</li>
      <li><b>הפער הכספי הוא בעיקר סיכון.</b> הרדיפה מובילה שיטתית לקופות תנודתיות
        יותר; בשוק עולה הן מרוויחות יותר בממוצע. במסלולים הכלליים היתרון מתאדה
        לכ־0.15 נקודות לשנה.</li>
      <li><b>הרדיפה מרכזת סיכון.</b> היא כולאת את החוסך בקופה בודדת ומסוכנת, וחושפת
        אותו לתהפוכות חדות — והכול לפני דמי ניהול, מס ועלויות מעבר שפועלים נגדה.</li>
    </ol>
    <p class="body">עדיף לבחור מסלול ברמת סיכון שמתאימה לגיל ולצרכים, עם דמי ניהול
      נמוכים, ולהחזיק אותו בעקביות — במקום לקפוץ מדי שנה אל כוכב התשואות של אתמול.</p>
  </div>

  <div class="foot">
    כל הנתונים, הקוד והטבלאות בתיקיית <code>analysis/</code>.
    שחזור: <code>build_annual.py</code> → <code>chase_analysis.py</code> →
    <code>risk_check.py</code> → <code>make_report.py</code> / <code>build_html.py</code>.
    תשואה שנתית חושבה משרשור התשואות החודשיות; נכללו רק שנים עם 12 חודשי דיווח.
    הסימולציה אינה מנכה דמי ניהול, מס ועלויות מעבר — כולם פועלים נגד אסטרטגיית הרדיפה.
  </div>
</div>

<script>
const D=__DATA__;
const NS="http://www.w3.org/2000/svg";
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function el(t,a){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;}
function txt(x,y,s,o={}){const t=el("text",{x,y,...o});t.textContent=s;return t;}

/* ---- persistence chart ---- */
(function(){
  const svg=document.getElementById("chartPersist");
  const W=720,H=300,mL=44,mR=44,mT=24,mB=52;
  const iw=W-mL-mR, ih=H-mT-mB;
  const xs=D.persist.map((_,i)=>mL+iw*(i+0.5)/D.persist.length);
  const y=v=>mT+ih*(1-v/100);
  // gridlines
  [0,25,50,75,100].forEach(g=>{
    svg.appendChild(el("line",{x1:mL,x2:W-mR,y1:y(g),y2:y(g),
      stroke:g===50?css("--base"):css("--line"),"stroke-width":g===50?1.5:1,
      "stroke-dasharray":g===50?"5 4":""}));
    svg.appendChild(txt(mL-10,y(g)+4,g,{fill:css("--faint"),"font-size":11,"text-anchor":"end"}));
  });
  svg.appendChild(txt(W-mR+8,y(50)+4,"50",{fill:css("--base"),"font-size":11,"font-weight":700}));
  // percentile line
  const pts=D.persist.map((d,i)=>[xs[i],y(d.pctile)]);
  let path="M"+pts.map(p=>p.join(",")).join(" L");
  svg.appendChild(el("path",{d:path,fill:"none",stroke:css("--teal"),"stroke-width":3,
    "stroke-linecap":"round","stroke-linejoin":"round"}));
  // no1 line
  const p2=D.persist.map((d,i)=>[xs[i],y(d.no1)]);
  svg.appendChild(el("path",{d:"M"+p2.map(p=>p.join(",")).join(" L"),fill:"none",
    stroke:css("--gold"),"stroke-width":2.5,"stroke-dasharray":"2 5","stroke-linecap":"round"}));
  D.persist.forEach((d,i)=>{
    svg.appendChild(el("circle",{cx:xs[i],cy:y(d.pctile),r:5.5,fill:css("--teal")}));
    svg.appendChild(txt(xs[i],y(d.pctile)-13,d.pctile,{fill:css("--teal"),"font-size":14,
      "font-weight":800,"text-anchor":"middle"}));
    svg.appendChild(el("circle",{cx:xs[i],cy:y(d.no1),r:4,fill:css("--gold")}));
    svg.appendChild(txt(xs[i],y(d.no1)+20,d.no1+"%",{fill:css("--gold"),"font-size":12,
      "font-weight":700,"text-anchor":"middle"}));
    svg.appendChild(txt(xs[i],H-mB+26,"שנה +"+d.h,{fill:css("--muted"),"font-size":13,
      "font-weight":700,"text-anchor":"middle"}));
  });
})();

/* stat cards */
(function(){
  const s=document.getElementById("statsPersist");
  const p1=D.persist[0];
  const cards=[
    ["good",p1.pctile,"אחוזון ממוצע בשנה שאחרי"],
    ["warn",p1.no1+"%","חזרו למקום הראשון"],
    ["",p1.topq+"%","נשארו ברבעון העליון"],
    ["warn",p1.bot+"%","צנחו למחצית התחתונה"],
  ];
  cards.forEach(([c,v,l])=>{
    const d=document.createElement("div");d.className="stat";
    d.innerHTML=`<div class="v ${c}"><span class="num">${v}</span></div><div class="l">${l}</div>`;
    s.appendChild(d);
  });
})();

/* ---- gap chart (horizontal bars, RTL) ---- */
(function(){
  const svg=document.getElementById("chartGap");
  const W=720,H=430,mT=10,mB=28,rowH=(H-mT-mB)/D.strat.length;
  const maxGap=Math.max(...D.strat.map(d=>d.gap));
  const x0=250, iw=W-x0-70;             // bars grow leftward (RTL)
  const x=v=>x0 - iw*(v/(maxGap*1.08)); // more gap -> further left
  D.strat.forEach((d,i)=>{
    const cy=mT+rowH*i, bh=Math.min(24,rowH*0.56), by=cy+(rowH-bh)/2;
    const isGen=d.label.includes("כללי");
    const col=isGen?css("--base"):(d.dom==="pension"?css("--clay"):css("--gold"));
    svg.appendChild(txt(x0+12,by+bh/2+5,d.label,{fill:css("--ink"),"font-size":13,
      "font-weight":isGen?500:600,"text-anchor":"start"}));
    svg.appendChild(el("rect",{x:x(d.gap),y:by,width:x0-x(d.gap),height:bh,rx:4,fill:col,
      opacity:isGen?0.55:0.92}));
    svg.appendChild(txt(x(d.gap)-8,by+bh/2+5,"+"+d.gap.toFixed(2),{fill:col,"font-size":13,
      "font-weight":800,"text-anchor":"end"}));
  });
  // baseline
  svg.appendChild(el("line",{x1:x0,x2:x0,y1:mT,y2:H-mB,stroke:css("--ink"),"stroke-width":1.5}));
  svg.appendChild(txt(x0,H-mB+18,"0 נק'",{fill:css("--muted"),"font-size":12,"text-anchor":"middle","font-weight":700}));
  svg.appendChild(txt(x(maxGap),H-mB+18,"פער שנתי (נק' אחוז) ⟵",{fill:css("--faint"),"font-size":11.5,"text-anchor":"start"}));
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
  D.cats.forEach((cat,idx)=>{
    const det=document.createElement("details"); if(idx<2)det.open=true;
    let rows=cat.rows.map(r=>`<tr><td class="y num">${r.y}</td>
      <td class="name">${r.name}</td>
      <td class="num" style="font-weight:700">+${r.sret.toFixed(1)}%</td>
      <td>${cell(r.k1)}</td><td>${cell(r.k2)}</td><td>${cell(r.k3)}</td></tr>`).join("");
    det.innerHTML=`<summary><span>${cat.label}</span>
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
    HTML.replace("__DATA__", DATA))
print("wrote report.html")
