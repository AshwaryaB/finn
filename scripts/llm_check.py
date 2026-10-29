"""python -m scripts.llm_check
Lists the models your key can call and test-calls the ones set in .env. Never prints your key."""
import os

from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
if not key:
    raise SystemExit("GEMINI_API_KEY is not set in .env")

from google import genai

client = genai.Client(api_key=key)
print("== models visible to your key (generateContent-capable) ==")
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if not actions or "generateContent" in actions:
        print(" ", m.name)

for var in ("GEMINI_MODEL_CHEAP", "GEMINI_MODEL_STRONG"):
    name = os.getenv(var)
    print(f"\n== test call: {var} = {name!r} ==")
    if not name:
        print("  not set")
        continue
    try:
        r = client.models.generate_content(model=name, contents="Reply with the single word: ready")
        print("  OK ->", (r.text or "").strip()[:80])
    except Exception as e:
        print("  FAILED ->", str(e)[:300])
