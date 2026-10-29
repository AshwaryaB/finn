"""Gemini wrapper: two tiers (cheap for bulk extraction, strong for reasoning), disk cache, retry on 429/503.
Model IDs come from env so nothing is hard-coded to names that may change."""
import hashlib, json, os, re, time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


def _model(tier):
    name = os.getenv("GEMINI_MODEL_STRONG" if tier == "strong" else "GEMINI_MODEL_CHEAP")
    if not name:
        raise RuntimeError(f"Set GEMINI_MODEL_{'STRONG' if tier == 'strong' else 'CHEAP'} in .env "
                           "(run: python -m scripts.llm_check)")
    return name


def generate(prompt, tier="cheap", retries=4):
    model = _model(tier)
    CACHE_DIR.mkdir(exist_ok=True)
    f = CACHE_DIR / ("llm_" + hashlib.sha256(f"{model}\n{prompt}".encode()).hexdigest()[:24] + ".txt")
    if f.exists():
        return f.read_text()
    from google import genai
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing in .env")
    client = genai.Client(api_key=key)
    for i in range(retries):
        try:
            text = client.models.generate_content(model=model, contents=prompt).text or ""
            f.write_text(text)
            return text
        except Exception as e:
            if any(k in str(e) for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                time.sleep(5 * 2 ** i)
                continue
            raise
    raise RuntimeError("Gemini rate-limited after retries; try again in a minute")


def _clean(raw):
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())


def generate_json(prompt, tier="cheap"):
    try:
        return json.loads(_clean(generate(prompt, tier)))
    except json.JSONDecodeError:
        retry = prompt + "\n\nYour previous reply was not valid JSON. Reply with ONLY valid JSON."
        return json.loads(_clean(generate(retry, tier)))
