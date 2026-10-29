"""Run from repo root: python -m scripts.survey
Checks every portfolio symbol on yfinance + NSE, then surveys 60 days of announcements so the
classifier can be tuned on real data. Paste the output back to Claude."""
from collections import Counter
from datetime import datetime, timedelta

from app import nse, prices
from app.classify import VERSION, classify
from app.config import load_portfolio

print("classifier", VERSION)
pf = load_portfolio()
syms = [c["symbol"] for c in pf]
print("== yfinance symbol check ==")
eod = prices.fetch_eod(syms)
for s in syms:
    print(f"{s:12}", "OK" if s in eod else "MISSING")

print("\n== NSE announcements, last 60 days ==")
now = datetime.now(nse.IST)
descs, cats, unclassified, per_sym, results_samples = Counter(), Counter(), [], {}, []
for s in syms:
    try:
        rows = nse.fetch_announcements(s, now - timedelta(days=60), now)
    except Exception as e:
        print(s, "FAILED", e)
        continue
    per_sym[s] = len(rows)
    for r in rows:
        descs[r["desc"]] += 1
        c = classify(r["desc"], r["text"])
        cats[c] += 1
        if c == "results" and len(results_samples) < 6:
            results_samples.append((s, r["time"], r["text"][:100], r["pdf"]))
        if c == "unclassified" and len(unclassified) < 40:
            unclassified.append((s, r["desc"], r["text"][:110]))
print("per symbol:", per_sym)
print("\ndistinct desc values:")
for d, n in descs.most_common():
    print(f"  {n:5}  {d}")
print("\ncategory counts:", dict(cats))
print("\nsample unclassified (symbol | desc | text):")
for u in unclassified:
    print(" ", " | ".join(u))

print("\nsample results filings (symbol | time | text | pdf):")
for x in results_samples:
    print(" ", " | ".join(str(i) for i in x))
