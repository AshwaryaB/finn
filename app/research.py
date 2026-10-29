"""Pull side: on-demand company research grounded in annual report + concall transcripts (+ screener's
standardised multi-year tables). No news, no broker notes, no model outside knowledge.
Routing: cheap model reads each transcript / the annual report once (cached); strong model reasons once."""
import json, re, threading, uuid

from . import llm, pdfs, screener

JOBS = {}

TRANSCRIPT_PROMPT = """You are reading ONE earnings-call transcript. Use ONLY this text; no outside knowledge.
Return ONLY JSON:
{"quarter_discussed":"as stated in the text, else null",
 "guidance":[{"metric":"","statement":"management's own forward-looking claim","quote":"verbatim, max 25 words, copied from the text"}],
 "delivered_claims":[{"metric":"","statement":"what management says was achieved","quote":"verbatim, max 25 words, copied from the text"}],
 "analyst_pressure":["what analysts pressed on, max 3"],
 "tone":"one short phrase"}
At most 6 guidance and 6 delivered_claims; only explicit numeric or clearly directional statements. Empty lists if none.

TRANSCRIPT:
"""

BUSINESS_PROMPT = """From these opening pages of an annual report, describe the business. Use ONLY this text.
Return ONLY JSON: {"what_it_does":"max 40 words","segments":[{"name":"","description":"max 20 words","revenue_share":"only if stated in the text, else null"}]}
At most 6 segments.

ANNUAL REPORT TEXT:
"""

SYNTH_PROMPT = """You are an equity research analyst. Use ONLY the material below (screener tables derived from company
filings, per-call transcript digests, annual-report business digest). No outside knowledge, no news, no broker views.
Every string max 30 words. Cite the source in square brackets, e.g. [Quarters], [P&L], [BS], [CF], [Ratios], [T Jul 2026], [AR].
Copy numbers exactly from the tables; never estimate. If the material does not support something, omit it or use null.
No buy/sell advice. Return ONLY JSON:
{"financial_snapshot":{"headline":[{"label":"","value":"","note":""}],"summary":""},
 "trajectory":{"growing":[""],"compressing":[""],"summary":""},
 "balance_sheet":{"points":[""],"summary":""},
 "cash_quality":{"points":[""],"summary":""},
 "narrative_vs_numbers":[{"quarter":"","promised":[""],"delivered":[""],"verdict":"met|missed|mixed|unclear","comment":""}],
 "guidance":[{"metric":"","statement":"","quote":"","call":""}],
 "bull_bear":{"bull":["max 3"],"bear":["max 3"]}}
narrative_vs_numbers: for each of the last four calls, compare what management promised (from the PREVIOUS calls' guidance)
against what the Quarters table shows was delivered; verdict must follow the numbers.

MATERIAL:
"""


def _norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def verify_quotes(items, text):
    n = _norm(text)
    for it in items or []:
        q = _norm(it.get("quote"))
        it["quote_verified"] = bool(q) and q in n
    return items


def transcript_digest(t):
    text = pdfs.fetch_pdf_text(t["url"], max_chars=150_000)
    if len(text.strip()) < 1000:
        return {"call": t["date"], "error": "no readable text"}
    d = llm.generate_json(TRANSCRIPT_PROMPT + text, tier="cheap")
    verify_quotes(d.get("guidance"), text)
    verify_quotes(d.get("delivered_claims"), text)
    d["call"] = t["date"]
    return d


def run(symbol, progress):
    warnings = []
    progress("Fetching company documents")
    html, basis = screener.fetch_page(symbol)
    docs, tables = screener.parse_docs(html), screener.parse_tables(html)
    missing = [k for k in screener.SECTIONS if k not in tables]
    if missing:
        warnings.append("Tables not found on screener.in page: " + ", ".join(missing))

    digests, calls = [], docs["transcripts"][:4]
    if not calls:
        warnings.append("No concall transcripts listed for this company.")
    for i, t in enumerate(calls, 1):
        progress(f"Reading concall transcripts ({i}/{len(calls)})")
        try:
            digests.append(transcript_digest(t))
        except Exception as e:
            warnings.append(f"Transcript {t['date']}: {str(e)[:120]}")

    business = None
    if docs["annual_reports"]:
        progress("Reading annual report")
        ar = docs["annual_reports"][0]
        try:
            txt = pdfs.fetch_pdf_text(ar["url"], max_pages=60, max_chars=120_000)
            if len(txt.strip()) > 1000:
                business = llm.generate_json(BUSINESS_PROMPT + txt, tier="cheap")
                business["source"] = ar["label"]
        except Exception as e:
            warnings.append(f"Annual report: {str(e)[:120]}")

    progress("Analysing")
    parts = [f"[{screener.SECTIONS[k]}]\n{screener.table_text(tables[k])}" for k in screener.SECTIONS if k in tables]
    parts.append("[TRANSCRIPT DIGESTS]\n" + json.dumps(digests, ensure_ascii=False))
    parts.append("[AR]\n" + json.dumps(business, ensure_ascii=False))
    sections = llm.generate_json(SYNTH_PROMPT + "\n\n".join(parts), tier="strong")
    return {"symbol": symbol, "basis": basis, "business": business, "sections": sections,
            "sources": {"transcripts": [d.get("call") for d in digests],
                        "annual_report": business.get("source") if business else None,
                        "tables": [screener.SECTIONS[k] for k in tables]},
            "warnings": warnings}


def start(symbol):
    job = uuid.uuid4().hex[:10]
    JOBS[job] = {"status": "running", "stage": "Starting", "result": None, "error": None}

    def work():
        try:
            JOBS[job]["result"] = run(symbol, lambda s: JOBS[job].update(stage=s))
            JOBS[job]["status"] = "done"
        except Exception as e:
            JOBS[job].update(status="error", error=str(e)[:300])

    threading.Thread(target=work, daemon=True).start()
    return job


def status(job):
    return JOBS.get(job)
