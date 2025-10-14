import os
import json
from datetime import datetime, timedelta

from src.config import (
    TICKERS, COMPANIES, ARXIV_QUERIES, NEWS_KEYWORDS, PATENT_KEYWORDS,
    DATA_JSON, SIGNALS_JSON, STATE_JSON
)
from src.sources.arxiv import fetch_arxiv
from src.sources.sec import fetch_sec_filings
from src.sources.patents import fetch_patents
from src.sources.news import fetch_news
from src.sources.prices import fetch_prices
from src.logic.rules import score_items
from src.notifier import send_discord

# (valgfritt) backtest
try:
    from src.logic.backtest import simulate
except Exception:
    simulate = None


def _utc_iso(dt=None):
    if isinstance(dt, datetime):
        return dt.replace(microsecond=0).isoformat() + "Z"
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def load_state():
    try:
        with open(STATE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"notified_ids": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
    tmp = STATE_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_JSON)


def generate():
    # 1) Hent data
    arxiv = fetch_arxiv(ARXIV_QUERIES)
    sec = fetch_sec_filings()
    patents = fetch_patents(PATENT_KEYWORDS + COMPANIES)
    news = fetch_news(NEWS_KEYWORDS + COMPANIES)
    prices = fetch_prices(TICKERS)

    # 2) Score signals (ts og sort i rules.py)
    signals = score_items(arxiv, sec, patents, news, prices)

    # 3) Tidsvinduer
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    today_prefix = now.date().iso
