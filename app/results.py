"""Quarterly results -> Revenue / EBITDA / PBT / PAT, QoQ and YoY.
The LLM only READS numbers out of the filing; all arithmetic is done here, and every figure is
checked for literal presence in the filing text (verified flag) so invented numbers are flagged."""
import re

from . import llm, pdfs

FIELDS = ["revenue_from_operations", "other_income", "finance_costs", "depreciation", "pbt", "pat"]
COLS = ["current", "previous_quarter", "year_ago"]

PROMPT = """You extract numbers from an Indian listed company's QUARTERLY financial results filing.
Use ONLY the text below. If a number is not present, use null. Never use outside knowledge or estimate.
If both consolidated and standalone results appear, use CONSOLIDATED and set basis accordingly.
The quarterly table has three quarter columns: the current quarter, the immediately preceding quarter,
and the corresponding quarter of the previous year. Map them using the column headers.
Numbers in brackets are negative. Copy numbers exactly as printed (no rounding, no unit conversion).
Return ONLY JSON:
{"basis":"consolidated|standalone|unknown","unit":"as printed, e.g. Rs. crore / Rs. lakh / Rs. million",
 "quarter_label":"current quarter as printed, e.g. Quarter ended 30 September 2026",
 "current":{"revenue_from_operations":0,"other_income":0,"finance_costs":0,"depreciation":0,"pbt":0,"pat":0},
 "previous_quarter":{same keys},"year_ago":{same keys}}
If the filer is a bank or NBFC, use Total income as revenue_from_operations and use null for finance_costs and depreciation unless printed.
pat = net profit for the period after tax. pbt = profit before tax (after exceptional items if shown).

FILING TEXT:
"""


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def pct(cur, base):
    """% change; None (n.m.) if either side missing or the base is zero/negative."""
    if cur is None or base is None or base <= 0:
        return None
    return round((cur / base - 1) * 100, 1)


def ebitda(d):
    """Derived: PBT + finance costs + depreciation - other income (not reported by companies)."""
    if any(d.get(k) is None for k in ("pbt", "finance_costs", "depreciation", "other_income")):
        return None
    return round(d["pbt"] + d["finance_costs"] + d["depreciation"] - d["other_income"], 2)


def normalize_text(text):
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def grounded(v, norm):
    """True if the number appears literally in the (comma-stripped) filing text."""
    if v is None:
        return None
    a = abs(v)
    cands = {str(int(a))} if a == int(a) else {f"{a:.2f}", f"{a:.1f}", f"{a:.2f}".rstrip("0").rstrip(".")}
    return any(re.search(rf"(?<![\d.]){re.escape(c)}(?!\d)", norm) for c in cands)


def build(data, text):
    norm = normalize_text(text)
    cols = {}
    for c in COLS:
        raw = data.get(c) or {}
        cols[c] = {k: _num(raw.get(k)) for k in FIELDS}
        cols[c]["ebitda"] = ebitda(cols[c])
    metrics = []
    for key, label in [("revenue_from_operations", "Revenue"), ("ebitda", "EBITDA (derived)"),
                       ("pbt", "PBT"), ("pat", "PAT")]:
        cur, prev, ya = (cols[c][key] for c in COLS)
        if key == "ebitda":
            parts = [grounded(cols[c][k], norm) for c in COLS for k in ("pbt", "finance_costs", "depreciation", "other_income")]
        else:
            parts = [grounded(v, norm) for v in (cur, prev, ya)]
        metrics.append({"key": key, "label": label, "current": cur, "previous_quarter": prev, "year_ago": ya,
                        "qoq_pct": pct(cur, prev), "yoy_pct": pct(cur, ya),
                        "verified": all(p is not False for p in parts)})
    no_ebitda = all(m["current"] is None for m in metrics if m["key"] == "ebitda")
    return {"type": "results", "ebitda_na": no_ebitda, "basis": data.get("basis", "unknown"), "unit": data.get("unit"),
            "quarter_label": data.get("quarter_label"), "metrics": metrics,
            "note": "EBITDA is derived by FINN as PBT + finance costs + depreciation - other income. "
                    "EBITDA is not shown when finance costs/depreciation are not in the filing (e.g. banks). 'n.m.' = base is zero or negative. A warning mark means a number was not found "
                    "literally in the filing text; check the filing."}


def extract(pdf_url):
    text = pdfs.fetch_pdf_text(pdf_url, max_pages=15, max_chars=70_000)
    if len(text.strip()) < 500:
        return {"type": "error", "error": "No readable text in this filing (probably a scanned PDF). Open the filing."}
    data = llm.generate_json(PROMPT + text, tier="cheap")
    return build(data, text)
