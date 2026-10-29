"""End-of-day price/volume via yfinance (>=1.7 returns two-level columns: (Price, Ticker))."""
import hashlib, json, time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE = dtime(15, 30)
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
TTL_SECONDS = 3600


def _cache_file(symbols):
    key = hashlib.md5(",".join(sorted(symbols)).encode()).hexdigest()[:12]
    return CACHE_DIR / f"eod_{key}.json"


def fetch_eod(symbols, period="3mo"):
    """{symbol: {"dates": [...], "close": [...], "volume": [...]}} for NSE (.NS). Cached 1h;
    falls back to a stale cache if the live fetch fails."""
    import yfinance as yf  # lazy so tests run without it
    CACHE_DIR.mkdir(exist_ok=True)
    f = _cache_file(symbols)
    if f.exists() and time.time() - f.stat().st_mtime < TTL_SECONDS:
        return json.loads(f.read_text())
    try:
        tickers = [f"{s}.NS" for s in symbols]
        df = yf.download(tickers, period=period, progress=False, threads=True)
        if df.empty:
            raise RuntimeError("yfinance returned no data")
        close, vol = df["Close"], df["Volume"]
        out = {}
        for s in symbols:
            t = f"{s}.NS"
            if t not in close.columns:
                continue
            c = close[t].dropna()
            if c.empty:
                continue
            v = vol[t].reindex(c.index).fillna(0)
            out[s] = {
                "dates": [d.strftime("%Y-%m-%d") for d in c.index],
                "close": [float(x) for x in c],
                "volume": [int(x) for x in v],
            }
        f.write_text(json.dumps(out))
        return out
    except Exception:
        if f.exists():
            return json.loads(f.read_text())
        raise


def drop_partial_bar(series, now=None):
    """If the last bar is today's and the market hasn't closed, drop it: its volume is incomplete."""
    now = now or datetime.now(IST)
    if series["dates"] and series["dates"][-1] == now.strftime("%Y-%m-%d") and now.time() < MARKET_CLOSE:
        return {k: v[:-1] for k, v in series.items()}
    return series


def signals(series, window=20):
    """Latest completed day: % move vs previous close, volume vs trailing `window`-day average."""
    c, v, d = series["close"], series["volume"], series["dates"]
    if len(c) < window + 2:
        return None
    avg = sum(v[-window - 1:-1]) / window
    return {
        "date": d[-1],
        "close": round(c[-1], 2),
        "pct": round((c[-1] / c[-2] - 1) * 100, 2),
        "volume": v[-1],
        "avg_volume": int(avg),
        "vol_ratio": round(v[-1] / avg, 2) if avg else None,
    }
