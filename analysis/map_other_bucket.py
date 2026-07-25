# -*- coding: utf-8 -*-
"""Classifier for the 'אחר, לבדיקה' bucket -> existing 10 מסלול ממופה labels."""

LABEL_RISK = {
    'כללי': 'בינונית',
    'מניות אקטיבי': 'גבוהה',
    'מניות פאסיבי': 'גבוהה',
    'S&P 500': 'גבוהה',
    'אג"ח עד 25% מניות': 'בינונית',
    'אג"ח ללא מניות': 'נמוכה',
    'אג"ח ממשלתי': 'נמוכה',
    'כספי': 'נמוכה',
    'הלכתי': 'בינונית',
    'מעורב / גמיש': 'בינונית',
    'מבטיח תשואה': 'נמוכה',   # its own category, not folded into gov bonds
}

EXCLUDE = '__EXCLUDE_IRA__'


def nrm(s):
    if s is None:
        return ''
    return ' '.join(str(s).replace('_x000D_', ' ').split()).strip()


def classify(name, spec, sub):
    """Return a מסלול ממופה label (one of LABEL_RISK keys) or EXCLUDE."""
    n = nrm(name)
    spec = nrm(spec)
    sub = nrm(sub)

    # 0) IRA / self-managed -> excluded downstream anyway
    if 'בניהול אישי' in n or 'IRA' in n:
        return EXCLUDE

    # 1) Age / lifecycle bands (by name, overrides spec/sub)
    if 'לבני 50 ומטה' in n or 'לגילאי 50 ומטה' in n or 'גילאי 50 ומטה' in n \
            or ('עד 50' in n and ('מסלול' in n or 'מדרגות' in n or 'מסלולית' in n or spec in ('מדרגות', 'מתמחה אחר'))):
        return 'כללי'                    # under-50 band -> כללי (per user)
    if 'בין 50 ל-60' in n or 'בין 50 ל 60' in n:
        return 'כללי'                    # matches existing מדרגות/50-60 -> כללי
    if '60 פלוס' in n or '60 ומעלה' in n or 'מסלול 60' in n:
        return 'אג"ח עד 25% מניות'       # matches existing מדרגות/60+ -> אג"ח עד 25%

    # 2) מתמחה אחר / אוכלוסיית יעד - horizon/veteran based
    if spec == 'מתמחה אחר':
        if 'לטווח ארוך' in n or 'מעל 6 שנות' in n:
            return 'כללי'
        if 'לטווח קצר' in n or 'עד 6 שנות' in n:
            return 'אג"ח ללא מניות'
        return 'כללי'

    # 3) Guaranteed return -> its own category (not folded into gov bonds)
    if spec == 'מבטיח תשואה':
        return 'מבטיח תשואה'

    # 4) Foreign currency (מט"ח) -> money-market-like
    if spec == 'מט"ח':
        return 'כספי'

    # 5) Shekel money market
    if spec == 'שיקלי':
        return 'כספי'

    # 6) Foreign (חו"ל / ללא סיווג=חו"ל / מדד=חו"ל)
    if spec in ('חו"ל', 'ללא סיווג') or (spec == 'מדד' and sub == 'חו"ל') \
            or (spec == 'אג"ח' and 'חו"ל' in sub):
        if 'אג"ח' in n:                          # foreign bond track
            return 'אג"ח ללא מניות'
        if 'פאסיב' in n or 'מדד' in n or 'מחקה' in n or sub == 'פאסיבי':
            return 'מניות פאסיבי'                # foreign passive equity
        return 'מניות אקטיבי'                     # foreign active equity

    # 7) מדד (index) group  -> per user: צמוד מדד = bonds; equity index = passive equity
    if spec == 'מדד':
        if 'אג"ח' in sub or 'אג"ח' in n:
            return 'אג"ח ללא מניות'
        if any(k in n.upper() for k in ('STOXX', 'S&P', 'SP500', 'S&P500')) \
                or 'מניות' in n or 'מניות' in sub:
            return 'מניות פאסיבי'
        return 'אג"ח ללא מניות'                   # generic 'מדד'/'צמוד מדד' -> CPI-linked bonds

    # 8) Israel equity
    if spec == 'ישראל':
        return 'מניות אקטיבי'

    # 9) Cohorts / lifecycle model
    if spec == 'קוהורטות':
        return 'כללי'

    # 10) Bonds family (אג"ח)
    if spec == 'אג"ח':
        if 'משולב' in sub or 'עד 25%' in n or 'עד 25 %' in n:
            return 'אג"ח עד 25% מניות'
        if 'אג"ח 85' in n or 'אג\"ח 85' in n:
            return 'אג"ח עד 25% מניות'            # 85/15 bond-heavy mixed
        return 'אג"ח ללא מניות'

    # 11) Blank spec -> decide by name
    if spec in ('', '(ריק)') or spec is None:
        if 'עוקב מדדים' in n and 'גמיש' in n:
            return 'מעורב / גמיש'
        if 'אג"ח' in n:
            return 'אג"ח ללא מניות'
        if 'מדד' in n and 'מניות' in n:
            return 'מניות פאסיבי'
        return None  # flag

    return None  # flag unhandled
