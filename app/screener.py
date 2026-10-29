"""screener.in: document links (annual reports, dated concall transcripts) and standardised tables.
Document-link markup verified by probe 2026-10-27 (<li><div>Jul 2026</div><a>Transcript</a>...).
Table section ids (#quarters, #profit-loss, ...) are NOT yet verified against a live page: parse_tables
returns only what it finds and research reports which sections were missing."""
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
TTL_SECONDS = 24 * 3600

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SECTIONS = {"quarters": "Quarters", "profit-loss": "P&L", "balance-sheet": "BS", "cash-flow": "CF", "ratios": "Ratios"}


def fetch_page(symbol):
    """Live page, cached 24h on disk; if live fetch fails, any cached copy is used."""
    CACHE_DIR.mkdir(exist_ok=True)
    f = CACHE_DIR / f"scr_{symbol}.json"
    if f.exists() and time.time() - f.stat().st_mtime < TTL_SECONDS:
        d = json.loads(f.read_text())
        return d["html"], d["basis"]
    try:
        for basis, path in (("consolidated", "consolidated/"), ("standalone", "")):
            r = requests.get(f"https://www.screener.in/company/{symbol}/{path}",
                             headers={"User-Agent": UA}, timeout=20)
            if r.status_code == 200 and 'id="documents"' in r.text:
                f.write_text(json.dumps({"html": r.text, "basis": basis}))
                return r.text, basis
        raise LookupError(f"{symbol}: not found on screener.in")
    except Exception:
        if f.exists():
            d = json.loads(f.read_text())
            return d["html"], d["basis"]
        raise


def parse_docs(html):
    soup = BeautifulSoup(html, "html.parser")
    annual, transcripts, seen = [], [], set()
    for a in soup.find_all("a", href=True):
        label, href = a.get_text(strip=True), a["href"]
        if href in seen:
            continue
        if label.startswith("Annual Report"):
            seen.add(href)
            annual.append({"label": label, "url": href})
        elif label == "Transcript":
            seen.add(href)
            li = a.find_parent("li")
            d = li.find("div") if li else None
            transcripts.append({"date": d.get_text(strip=True) if d else None, "url": href})
    return {"annual_reports": annual, "transcripts": transcripts}


def parse_tables(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for sid in SECTIONS:
        sec = soup.find(id=sid)
        table = sec.find("table") if sec else None
        if not table:
            continue
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if rows:
            out[sid] = rows
    return out


def table_text(rows, last_cols=8):
    def trim(r):
        return [r[0]] + r[-last_cols:] if len(r) > last_cols + 1 else r
    return "\n".join(" | ".join(trim(r)) for r in rows)
