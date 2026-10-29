"""Run locally BEFORE deploying: python -m scripts.snapshot [SYMBOL ...]
Saves a 30-day announcement snapshot + EOD prices so the deployed demo still shows data if NSE or
Yahoo block the host's IP. Any symbols given also get a full research run (warms the LLM/PDF caches)."""
import json
import sys
from datetime import datetime, timedelta

from app import nse, prices, research
from app.config import symbols

nse.SNAP_DIR.mkdir(exist_ok=True)
now = datetime.now(nse.IST)
for s in symbols():
    rows = nse.fetch_announcements(s, now - timedelta(days=30), now)
    (nse.SNAP_DIR / f"ann_{s}.json").write_text(json.dumps(rows))
    print("announcements", s, len(rows))
prices.fetch_eod(symbols())
print("prices cached")
for sym in sys.argv[1:]:
    try:
        research.run(sym.upper(), print)
        print("researched", sym)
    except Exception as e:
        print("FAILED", sym, "->", str(e)[:200])
