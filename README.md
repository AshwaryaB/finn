# FINN: a financial investment agent

Live demo: https://finn-r2ek.onrender.com (free instance: the first load after idle takes about a minute)

FINN is a mobile-first web app for a public-markets investor. **Push** tells you what changed and why it matters. **Pull** researches any NSE company on demand.

## What it does

**Push**
- **Windowed digest.** Every NSE filing across a 20-stock portfolio for the window you pick (24h, 3d, 7d, 30d or custom hours). Filings are classified into the reference categories and ranked; routine ones are collapsed.
- **Triggered alerts.** You set the volume multiple (vs the 20-day average), the daily price move (±%) and which announcement types matter. With watching switched on, the open page checks every 2 minutes and can raise browser notifications.
- **Results.** Revenue, EBITDA, PBT and PAT, this quarter vs the previous quarter (QoQ) and the year-ago quarter (YoY), read from the filing itself.
- **Management changes.** Person, role, effective date and the background the filing states, plus a LinkedIn search link.
- **Scheduled results.** "Board meeting scheduled to approve results" notices are recognised and summarised instead of being parsed for numbers.

**Pull** (any NSE ticker): business snapshot, financial snapshot, trajectory, balance sheet, cash quality, narrative vs numbers (promised vs delivered over the last four calls), guidance, bull vs bear.

## How it works

```
NSE announcements API ─┐
yfinance (EOD, .NS) ───┼─> FastAPI ─> rule classifier ─> digest / alerts ──> single-page web UI
screener.in (links +   │                    │
  standardised tables) ┘                    └─> Gemini (on demand): results, mgmt change, research
filing / transcript / annual-report PDFs (pypdf) ───────┘
```

## Design decisions

1. **Rules first, LLM on demand.** Classification is rule-based over NSE's `desc` field and the filing text, tuned on 60 days of filings across the 20 portfolio stocks. The LLM only runs when you open a filing or request research.
2. **Model routing and caching.** A cheap Gemini model reads each filing, each transcript and the annual report once. A stronger model reasons once per company. Caches: LLM outputs (by prompt hash), PDF text, prices (1 hour), announcements (10 minutes), screener pages (24 hours).
3. **The model reads, code calculates.** Numbers are extracted by the model; QoQ, YoY and derived EBITDA are computed in code. Every figure, quote and person name is checked against the source text, and anything not found literally is marked with a warning.
4. **Resilience.** If NSE, Yahoo or screener.in block the host, the app falls back to stale cache and then to a committed snapshot (`snapshot/`, `cache/`).

## Trade-offs and limits

- **EBITDA is derived** (PBT + finance costs + depreciation - other income) because filings rarely state it. It is not shown for banks.
- **Pull sources.** Annual report (first 60 pages), the last four concall transcripts, and screener.in's standardised multi-year tables (derived from company filings). No news, broker notes or model outside knowledge; the prompts say "use only the material". Screener tables are a convenience, not a raw filing.
- **Management bios** stop at what the filing states. LinkedIn is not scraped; the card links to a LinkedIn search.
- **Alerts** are checked by the open page, not pushed from a server.
- **Not benchmarked.** Extraction accuracy has not been measured against ground truth. The checks catch invented numbers, not a misread column.
- **Scanned PDFs** have no text and show an error.
- **Hosting.** Free instances sleep after 15 idle minutes, and a free Gemini key can rate-limit under bursts.

## Next

Server-side alert scheduler with mobile push; a ground-truth test set of results filings; links from each figure back to the page of the filing it came from; editable portfolio.

## Run locally

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # add GEMINI_API_KEY and model names (python -m scripts.llm_check lists them)
python -m uvicorn app.main:app
```
Open http://127.0.0.1:8000. Tests: `pip install -r requirements-dev.txt && python -m pytest -q`.

Before deploying, `python -m scripts.snapshot TICKER ...` saves a data snapshot and warms the research cache for the tickers you list.
