"""Download a PDF and extract its text (cached on disk). Scanned PDFs yield empty text; callers handle that."""
import hashlib, io
from pathlib import Path

import requests

from . import nse

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
MAX_BYTES = 80_000_000


def _download(url):
    host = url.split("/")[2] if "//" in url else ""
    if host.endswith("nseindia.com"):
        r = nse._get_session().get(url, timeout=60, stream=True)
    else:
        r = requests.get(url, headers={"User-Agent": nse.UA, "Referer": f"https://{host}/"},
                         timeout=60, stream=True)
    r.raise_for_status()
    buf, size = io.BytesIO(), 0
    for chunk in r.iter_content(1 << 16):
        size += len(chunk)
        if size > MAX_BYTES:
            raise RuntimeError("PDF too large")
        buf.write(chunk)
    return buf.getvalue()


def fetch_pdf_text(url, max_pages=None, max_chars=150_000):
    CACHE_DIR.mkdir(exist_ok=True)
    f = CACHE_DIR / ("pdf_" + hashlib.sha1(f"{url}|{max_pages}".encode()).hexdigest()[:20] + ".txt")
    if f.exists():
        txt = f.read_text()
    else:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(_download(url)))
        pages = reader.pages if not max_pages else reader.pages[:max_pages]
        txt = "\n".join((p.extract_text() or "") for p in pages)
        f.write_text(txt)
    return txt[:max_chars]
