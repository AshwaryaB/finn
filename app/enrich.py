"""On-demand enrichment of a pushed announcement, by category."""
import re
from urllib.parse import quote_plus

from . import llm, pdfs, results
from .classify import is_intimation

MGMT_PROMPT = """From this stock-exchange filing, list every management/board change.
Use ONLY the text. If a field is not stated, use null. Do not add outside knowledge.
Return ONLY JSON: {"events":[{"person":"full name","role":"designation","action":"appointed|re-appointed|resigned|retired|ceased|other",
"effective_date":"as stated","background_in_filing":"qualifications/experience/previous roles exactly as stated in the filing, max 40 words, else null"}]}

FILING TEXT:
"""

SUMMARY_PROMPT = """In ONE plain sentence of at most 25 words, say what this stock-exchange filing announces.
Use ONLY the text. No opinion, no outside knowledge.

FILING TEXT:
"""


def _filing_text(text, pdf, pages, chars):
    body = text or ""
    if pdf:
        try:
            body += "\n" + pdfs.fetch_pdf_text(pdf, max_pages=pages, max_chars=chars)
        except Exception:
            pass
    return body


def management(company, text, pdf):
    body = _filing_text(text, pdf, 3, 12_000)
    data = llm.generate_json(MGMT_PROMPT + body, tier="cheap")
    norm = re.sub(r"\W+", " ", body.lower())
    events = []
    for e in data.get("events") or []:
        name = (e.get("person") or "").strip()
        if not name:
            continue
        e["name_verified"] = re.sub(r"\W+", " ", name.lower()) in norm
        e["linkedin_url"] = "https://www.linkedin.com/search/results/people/?keywords=" + quote_plus(f"{name} {company}")
        events.append(e)
    return {"type": "management", "events": events}


def summary(text, pdf):
    body = _filing_text(text, pdf, 2, 6_000)
    if len(body.strip()) < 30:
        return {"type": "error", "error": "Nothing readable to summarise. Open the filing."}
    return {"type": "summary", "summary": llm.generate(SUMMARY_PROMPT + body, tier="cheap").strip()}


def run(category, company, text, pdf):
    if category == "results" and not is_intimation(text):
        if not pdf:
            return {"type": "error", "error": "No filing attached."}
        return results.extract(pdf)
    if category == "management_change":
        return management(company, text, pdf)
    return summary(text, pdf)
