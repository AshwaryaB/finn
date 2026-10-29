from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import enrich, nse, prices, research
from .alerts import announcement_alerts, price_volume_alerts
from .classify import PRIORITY, classify, is_intimation
from .config import load_portfolio, symbols

app = FastAPI(title="FINN")
IST = nse.IST


def _collect(hours):
    now = datetime.now(IST)
    start = now - timedelta(hours=hours)

    def one(sym):
        try:
            return sym, nse.fetch_announcements(sym, start, now), None
        except Exception as e:  # report per-symbol failure, keep going
            return sym, [], str(e)

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(one, symbols()))
    items, errors, seen = [], {}, set()
    for sym, rows, err in results:
        if err:
            errors[sym] = err
        for r in rows:
            if not r["time"] or r["id"] in seen:
                continue
            seen.add(r["id"])
            if datetime.fromisoformat(r["time"]) < start:
                continue
            cat = classify(r["desc"], r["text"])
            items.append({**r, "category": cat, "priority": PRIORITY[cat],
                          "upcoming": cat == "results" and is_intimation(r["text"])})
    items.sort(key=lambda i: (i["priority"], -datetime.fromisoformat(i["time"]).timestamp()))
    return items, errors


@app.get("/api/health")
def health():
    return {"ok": True, "ui": "v4", "classifier": classify.__module__ and __import__("app.classify", fromlist=["VERSION"]).VERSION}


@app.get("/api/portfolio")
def portfolio():
    return load_portfolio()


@app.get("/api/digest")
def digest(hours: int = Query(24, ge=1, le=24 * 30)):
    items, errors = _collect(hours)
    shown = [i for i in items if i["priority"] < 3]
    collapsed = [i for i in items if i["priority"] == 3]
    return {"window_hours": hours, "generated_at": datetime.now(IST).isoformat(),
            "counts": {"shown": len(shown), "collapsed": len(collapsed)},
            "items": shown, "collapsed": collapsed, "errors": errors}


@app.get("/api/alerts")
def alerts(vol_mult: float = 2.0, pct: float = 3.0,
           types: str = "results,M&A,management_change", hours: int = 24):
    items, errors = _collect(hours)
    try:
        eod = prices.fetch_eod(symbols())
        sig = {s: prices.signals(prices.drop_partial_bar(v)) for s, v in eod.items()}
        market, price_error = price_volume_alerts(sig, vol_mult, pct), None
    except Exception as e:
        market, price_error = [], str(e)
    return {"params": {"vol_mult": vol_mult, "pct": pct, "types": types, "hours": hours},
            "announcements": announcement_alerts(items, [t for t in types.split(",") if t]),
            "market": market, "errors": {**errors, **({"prices": price_error} if price_error else {})}}


class EnrichReq(BaseModel):
    category: str
    company: str = ""
    text: str = ""
    pdf: str | None = None


@app.post("/api/enrich")
def enrich_item(req: EnrichReq):
    if req.pdf and not req.pdf.startswith("https://nsearchives.nseindia.com/"):
        raise HTTPException(400, "Only NSE archive filings can be read")
    try:
        return enrich.run(req.category, req.company, req.text, req.pdf)
    except Exception as e:
        return {"type": "error", "error": str(e)[:300]}


class ResearchReq(BaseModel):
    symbol: str


@app.post("/api/research")
def research_start(req: ResearchReq):
    sym = req.symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9&-]{1,20}", sym):
        raise HTTPException(400, "Invalid NSE symbol")
    return {"job": research.start(sym)}


@app.get("/api/research/{job}")
def research_status(job: str):
    j = research.status(job)
    if not j:
        raise HTTPException(404, "Unknown job")
    return j


STATIC = Path(__file__).resolve().parent.parent / "static"
if STATIC.exists():
    app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
