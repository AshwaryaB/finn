"""NSE corporate announcements. Endpoint + fields verified by probe on 2026-10-27:
GET /api/corporate-announcements?index=equities&symbol=X[&from_date=dd-mm-yyyy&to_date=dd-mm-yyyy]
returns a JSON list. The homepage returns 403 but the API call still works after hitting it once."""
import hashlib, json, threading, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Asia/Kolkata")  # NSE publishes timestamps in IST
URL = "https://www.nseindia.com/api/corporate-announcements"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
SNAP_DIR = Path(__file__).resolve().parent.parent / "snapshot"  # committed fallback (see scripts/snapshot.py)
TTL_SECONDS = 600

_session = None
_lock = threading.Lock()


def _get_session(reset=False):
    global _session
    with _lock:
        if _session is None or reset:
            s = requests.Session()
            s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                              "Referer": "https://www.nseindia.com/"})
            try:
                s.get("https://www.nseindia.com", timeout=20)  # 403 is fine; sets cookies
            except requests.RequestException:
                pass
            _session = s
        return _session


def normalize(x):
    try:
        ts = datetime.strptime(x["an_dt"], "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
    except (KeyError, ValueError, TypeError):
        ts = None
    return {
        "id": x.get("seq_id"),
        "symbol": x.get("symbol"),
        "company": x.get("sm_name"),
        "time": ts.isoformat() if ts else None,
        "desc": x.get("desc") or "",
        "text": x.get("attchmntText") or "",
        "pdf": x.get("attchmntFile"),
        "has_xbrl": bool(x.get("hasXbrl")),
    }


def fetch_announcements(symbol, from_dt, to_dt, retries=3):
    CACHE_DIR.mkdir(exist_ok=True)
    key = hashlib.md5(f"{symbol}{from_dt:%Y%m%d}{to_dt:%Y%m%d}".encode()).hexdigest()[:12]
    f = CACHE_DIR / f"ann_{key}.json"
    if f.exists() and time.time() - f.stat().st_mtime < TTL_SECONDS:
        return json.loads(f.read_text())
    params = {"index": "equities", "symbol": symbol,
              "from_date": from_dt.strftime("%d-%m-%Y"), "to_date": to_dt.strftime("%d-%m-%Y")}
    last_err = None
    for i in range(retries):
        try:
            r = _get_session(reset=i > 0).get(URL, params=params, timeout=20)
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("data", [])
                out = [normalize(x) for x in rows]
                f.write_text(json.dumps(out))
                return out
            last_err = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            last_err = str(e)
        time.sleep(1.5 * (i + 1))
    if f.exists():
        return json.loads(f.read_text())
    snap = SNAP_DIR / f"ann_{symbol}.json"
    if snap.exists():
        return json.loads(snap.read_text())
    raise RuntimeError(f"NSE fetch failed for {symbol}: {last_err}")
