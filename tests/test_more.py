from app import enrich, llm, pdfs, research, results, screener

# Fixture copied from the REAL screener.in markup pasted from probe 2 (shortened).
HTML = '''<section id="documents"><ul class="list-links"><li class="flex"><div class="ink-600">Jul 2026</div>
<a class="button-chip" href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=aaa.pdf" title="Raw Transcript">Transcript</a>
<button>AI Summary</button></li><li><div>Apr 2026</div><a href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=bbb.pdf">Transcript</a></li>
<li><a href="https://www.bseindia.com/x/2026.pdf">Annual Report 2026</a></li><li><a href="https://www.bseindia.com/x/2025.pdf">Annual Report 2025</a></li>
<li><a href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=aaa.pdf">Transcript</a></li></ul></section>
<section id="quarters"><table><tr><th></th><th>Jun 2025</th><th>Sep 2025</th></tr><tr><td>Sales +</td><td>100</td><td>110</td></tr></table></section>'''

FILING = """Particulars Quarter ended 30.09.2026 30.06.2026 30.09.2025
Revenue from operations 1,20,000 1,00,000 80,000
Other income 2,000 1,500 1,000
Finance costs 3,000 3,000 3,500
Depreciation 5,000 4,500 4,000
Profit before tax 15,000 12,000 9,000
Net profit after tax 11,000.50 9,000 -500 """ + "x" * 600


def test_screener_docs():
    d = screener.parse_docs(HTML)
    assert [t["date"] for t in d["transcripts"]] == ["Jul 2026", "Apr 2026"]  # AI Summary ignored, duplicate dropped
    assert [a["label"] for a in d["annual_reports"]] == ["Annual Report 2026", "Annual Report 2025"]
    t = screener.parse_tables(HTML)
    assert t["quarters"][1][0] == "Sales +"
    assert "Sales +" in screener.table_text(t["quarters"])


def test_results_math_and_grounding():
    data = {"basis": "consolidated", "unit": "Rs. million", "quarter_label": "Quarter ended 30 Sep 2026",
            "current": {"revenue_from_operations": 120000, "other_income": 2000, "finance_costs": 3000, "depreciation": 5000, "pbt": 15000, "pat": 11000.5},
            "previous_quarter": {"revenue_from_operations": 100000, "other_income": 1500, "finance_costs": 3000, "depreciation": 4500, "pbt": 12000, "pat": 9000},
            "year_ago": {"revenue_from_operations": 80000, "other_income": 1000, "finance_costs": 3500, "depreciation": 4000, "pbt": 9000, "pat": -500}}
    out = results.build(data, FILING)
    m = {x["key"]: x for x in out["metrics"]}
    assert m["revenue_from_operations"]["qoq_pct"] == 20.0 and m["revenue_from_operations"]["yoy_pct"] == 50.0
    assert m["ebitda"]["current"] == 21000.0          # 15000+3000+5000-2000
    assert m["pat"]["yoy_pct"] is None                # negative base -> n.m.
    assert all(x["verified"] for x in out["metrics"])
    data["current"]["pbt"] = 14999                    # invented number must be flagged
    m = {x["key"]: x for x in results.build(data, FILING)["metrics"]}
    assert m["pbt"]["verified"] is False


def test_extract_pipeline_mocked(monkeypatch=None):
    orig = (pdfs.fetch_pdf_text, llm.generate_json)
    try:
        pdfs.fetch_pdf_text = lambda *a, **k: FILING
        llm.generate_json = lambda *a, **k: {"basis": "consolidated", "unit": "Rs. million", "quarter_label": "Q",
            "current": {"revenue_from_operations": 120000, "pat": 11000.5}, "previous_quarter": {}, "year_ago": {}}
        out = results.extract("https://x/y.pdf")
        assert out["type"] == "results" and out["metrics"][0]["current"] == 120000
        pdfs.fetch_pdf_text = lambda *a, **k: "scanned"
        assert results.extract("https://x/y.pdf")["type"] == "error"
    finally:
        pdfs.fetch_pdf_text, llm.generate_json = orig


def test_management_event_verification():
    orig = (pdfs.fetch_pdf_text, llm.generate_json)
    try:
        pdfs.fetch_pdf_text = lambda *a, **k: ""
        llm.generate_json = lambda *a, **k: {"events": [
            {"person": "Asha Rao", "role": "CFO", "action": "appointed"},
            {"person": "Invented Person", "role": "CEO", "action": "resigned"}, {"person": ""}]}
        out = enrich.management("Acme Ltd", "Board approved appointment of Asha Rao as CFO", None)
        ev = out["events"]
        assert len(ev) == 2 and ev[0]["name_verified"] is True and ev[1]["name_verified"] is False
        assert "keywords=Asha+Rao+Acme+Ltd" in ev[0]["linkedin_url"]
    finally:
        pdfs.fetch_pdf_text, llm.generate_json = orig


def test_quote_verification():
    items = [{"quote": "We expect margins to improve"}, {"quote": "made up line"}]
    research.verify_quotes(items, "Management said: we expect margins  to improve next year.")
    assert items[0]["quote_verified"] is True and items[1]["quote_verified"] is False


def test_screener_cache_fallback(tmp_path=None):
    import os, tempfile, time
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    old = (screener.CACHE_DIR, screener.requests.get)
    try:
        screener.CACHE_DIR = d
        class R:
            status_code = 200
            text = '<div id="documents"></div>'
        screener.requests.get = lambda *a, **k: R()
        html, basis = screener.fetch_page("ABC")
        assert basis == "consolidated"
        def boom(*a, **k):
            raise RuntimeError("net down")
        screener.requests.get = boom
        f = d / "scr_ABC.json"
        os.utime(f, (time.time() - 99999, time.time() - 99999))   # make it stale
        assert screener.fetch_page("ABC")[0] == html               # stale copy still served
    finally:
        screener.CACHE_DIR, screener.requests.get = old
