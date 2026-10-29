# Deploy on Render (free web service)
- Build command:  pip install -r requirements.txt
- Start command:  python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
- Instance type:  Free
- Environment variables: GEMINI_API_KEY, GEMINI_MODEL_CHEAP, GEMINI_MODEL_STRONG, PYTHON_VERSION=3.11.9
- Health check path: /api/health
Free instances sleep after 15 idle minutes (first request takes about a minute) and their disk resets on every
restart, so the repo ships cached data (cache/, snapshot/) created by `python -m scripts.snapshot`.
