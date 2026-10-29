"""Rule-based announcement classifier (free, instant). Categories follow the reference doc.
Rules are matched on lower-cased "<desc> <attachment text>", first match wins, order matters.
Rules were written from the reference doc and the three NSE `desc` values seen so far
(Credit Rating, General Updates, Updates); run `python -m scripts.survey` to tune on real data."""
import re

VERSION = "v2"  # v2: desc-based rules from the 60-day NSE survey

PRIORITY = {  # 1 = shown first, 3 = collapsed by default
    "results": 1, "M&A": 1, "fund_raise": 1, "management_change": 1, "litigation": 1, "pledging": 1,
    "earnings_call": 2, "credit_rating": 2, "dividend": 2, "bonus_split": 2, "capex": 2,
    "insider_trading": 2, "press_release": 2, "investor_meetings": 3,
    "postal_ballot": 3, "agm_egm": 3, "unclassified": 3,
}

MGMT_ROLES = (r"\b(ceo|cfo|chief executive|chief financial|managing director|whole[- ]time director|"
              r"independent director|director|key managerial|senior management)\b")
MGMT_EVENTS = r"(appoint|resign|cessation|retire|change in|re-appoint|reappoint)"

RULES = [
    ("credit_rating", [r"credit rating", r"\b(crisil|icra|india ratings|brickwork|acuite)\b.*\brating",
                       r"\brating\b.*\b(crisil|icra|india ratings|brickwork|acuite)\b"]),
    ("earnings_call", [r"earnings call", r"conference call", r"\bconcall\b", r"transcript",
                       r"audio (/ ?video )?recording", r"call with media"]),
    ("results", [r"financial results?", r"\bresults? for\b", r"quarterly results?",
                 r"financial statements for the (quart|half|year)", r"(quarter|half[- ]year|annual) results?",
                 r"earnings presentation",
                 r"un-?audited (standalone|consolidated|financial)", r"results? (presentation|deck)",
                 r"shareholders?['’]?s? letter"]),
    ("unclassified", [r"\besop\b", r"employee stock", r"compliance certificate", r"\besg\b", r"\bbrsr\b",
                      r"sustainability report", r"auditor", r"unpaid dividend", r"\biepf\b", r"trading window",
                      r"secretarial compliance", r"regulation 74\(5\)", r"regulation 40\(9\)",
                      r"share certificate", r"newspaper"]),
    ("bonus_split", [r"bonus (issue|shares)", r"stock split", r"sub-?division of"]),
    ("dividend", [r"dividend"]),
    ("fund_raise", [r"rights issue", r"\bqip\b", r"qualified institutions? placement",
                    r"preferential (issue|allotment)", r"buy-?back", r"commercial paper",
                    r"non-?convertible debenture", r"\bncds?\b", r"fund[- ]?raising", r"raising of funds",
                    r"initial public offer", r"\bipo\b", r"\bfpo\b"]),
    ("M&A", [r"acquisition", r"\bacquir", r"merger", r"amalgamation", r"demerger", r"joint venture",
             r"scheme of arrangement", r"(sale|sell|divest|disposal).{0,40}(stake|shares)",
             r"(incorporation|investment|invest|stake|sale).{0,60}subsidiary",
             r"subsidiary.{0,60}(incorporation|investment|stake|sale)"]),
    ("management_change", []),  # handled by function below
    ("litigation", [r"litigation", r"lawsuit", r"\bcourt\b", r"tribunal", r"\bnclt\b", r"penalt",
                    r"show[- ]cause", r"sebi order", r"adjudication", r"insolvency", r"winding[- ]up",
                    r"search (and|&) seizure", r"\bfine\b", r"regulatory action", r"demand notice",
                    r"tax (demand|order)"]),
    ("pledging", [r"\bpledg", r"encumbrance", r"invocation of"]),
    ("insider_trading", [r"insider trading", r"\bpit\b regulations?", r"regulation 7\(", r"regulation 29\("]),
    ("capex", [r"\bcapex\b", r"capital expenditure", r"new (plant|facility|unit|factory)",
               r"capacity expansion", r"greenfield", r"brownfield", r"expansion of [\w\s]{0,30}(capacity|plant|facility|center|centre|campus)"]),
    ("postal_ballot", [r"postal ballot"]),
    ("agm_egm", [r"annual general meeting", r"extra-?ordinary general meeting", r"\bagm\b", r"\begm\b"]),
    ("investor_meetings", [r"investor meet", r"analysts?\b", r"institutional investors?", r"one[- ]on[- ]one",
                           r"group meeting", r"investor conference"]),
    ("press_release", [r"press release", r"media (release|statement)", r"\border(s)? (win|received|bagged)",
                       r"bagged", r"letter of award", r"clarification", r"partnership", r"collaborat",
                       r"\blaunch"]),
]


DESC_RULES = [  # (substrings of lower-cased NSE `desc`, category); checked after call/results text rules
    (("options to purchase", "esop", "allotment of securities", "trading window", "certificate under sebi",
      "copy of newspaper", "corrigendum", "change in auditors"), "unclassified"),
    (("change in management", "change in director", "resignation", "appointment"), "management_change"),
    (("action(s) taken or orders", "action(s) initiated or orders", "pendency of litigation",
      "corporate insolvency"), "litigation"),
    (("acquisition", "amalgamation", "scheme of arrangement", "diversification", "disinvestment",
      "sale or disposal", "other restructuring"), "M&A"),
    (("bagging/receiving", "agreements", "disclosure of material issue", "press release"), "press_release"),
    (("commencement of commercial",), "capex"),
    (("trading plan under pit",), "insider_trading"),
    (("shareholders meeting",), "agm_egm"),
    (("analysts/institutional investor", "investor presentation"), "investor_meetings"),
]


def _by_desc(desc, text):
    d = desc.lower()
    for keys, cat in DESC_RULES:
        if any(k in d for k in keys):
            if cat == "management_change" and "auditor" in text:
                return "unclassified"
            return cat
    return None


def is_intimation(text):
    """True for 'board meeting scheduled to approve results' style notices (no numbers inside yet)."""
    t = (text or "").lower()
    notice = re.search(r"(is scheduled|are scheduled|will be held|to be held|intimation|to announce .{0,40}results)", t)
    done = re.search(r"(has submitted|submitted to the exchange|outcome of|press release dated)", t)
    return bool(notice) and not done


def _hit(text, pats):
    return any(re.search(p, text) for p in pats)


def classify(desc, text):
    t = f"{desc} {text}".lower()
    for cat, pats in RULES[:3]:  # credit_rating, earnings_call, results: text beats desc
        if _hit(t, pats):
            return cat
    by_desc = _by_desc(desc, text.lower())
    if by_desc:
        return by_desc
    for cat, pats in RULES[3:]:
        if cat == "management_change":
            if re.search(MGMT_ROLES, t) and re.search(MGMT_EVENTS, t):
                return cat
        elif _hit(t, pats):
            return cat
    return "unclassified"
