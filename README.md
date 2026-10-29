# FINN - Financial Investment Agent (ENAM build challenge)

Mobile-first web app. Push: windowed digest + configurable alerts + results QoQ/YoY + management-change cards.
Pull: on-demand research on any NSE ticker, grounded in annual report + concall transcripts.

## Run
    pip install -r requirements.txt
    cp .env.example .env        # add GEMINI_API_KEY and model names (python -m scripts.llm_check lists them)
    uvicorn app.main:app        # open http://127.0.0.1:8000

## Design notes
- Rules classify announcements (free, instant); LLM only runs on demand (results, mgmt change, research).
- Cheap model reads each transcript / annual report once (disk-cached); strong model reasons once per company.
- LLM only READS numbers; arithmetic is done in code; every figure and quote is checked against the source text.
- Fallbacks: stale cache, then committed snapshot (scripts/snapshot.py).
