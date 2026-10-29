import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def load_portfolio():
    return json.loads((ROOT / "config" / "portfolio.json").read_text())

def symbols():
    return [c["symbol"] for c in load_portfolio()]
