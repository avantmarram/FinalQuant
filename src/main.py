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
from src.logic.trend import compute_trend_all
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
        return {"notified_ids": [], "trend_status": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
    tmp = STATE_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_JSON)


def generate():
    # 1) Hent data
    arxiv   = fetch_arxiv(ARXIV_QUERIES)
    sec     = fetch_sec_filings()
    patents = fetch_patents(PATENT_KEYWORDS + COMPANIES)
    news    = fetch_news(NEWS_KEYWORDS + COMPANIES)
    prices  = fetch_prices(TICKERS)

    # 2) Signals + Trend
    signals = score_items(arxiv, sec, patents, news, prices)
    trend   = compute_trend_all(TICKERS)

    # 3) Tidsvinduer
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    today_prefix = now.date().isoformat()

    signals_today = [s for s in signals if (s.get("ts","") or "").startswith(today_prefix)]
    signals_week  = [s for s in signals if (s.get("ts","") or "") >= week_ago.isoformat()]

    # 4) Dashboard-data
    data = {
        "generated_at": _utc_iso(now),
        "tickers": TICKERS,
        "prices": prices,
        "trend": trend,
        "counts": {
            "arxiv": len(arxiv),
            "sec": len(sec),
            "patents": len(patents),
            "news": len(news),
            "signals": len(signals),
            "signals_today": len(signals_today),
            "signals_week": len(signals_week),
        },
    }

    if callable(simulate):
        try:
            data["backtest"] = simulate(signals, TICKERS)
        except Exception:
            data["backtest"] = {"trades":0, "winrate":0, "avg_ret":0}

    # 5) Lagre JSON
    os.makedirs(os.path.dirname(DATA_JSON), exist_ok=True)
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(SIGNALS_JSON, "w", encoding="utf-8") as f:
        json.dump(signals[:200], f, ensure_ascii=False, indent=2)

    # 6) Varsler (topp-signaler + trend)
    state = load_state()
    already = set(state.get("notified_ids", []))
    prev_trend = state.get("trend_status", {})
    new_ids = []

    # topp tre nye signaler
    for s in signals[:3]:
        sid = json.dumps(s, sort_keys=True)
        if sid not in already:
            msg = f"**{s.get('type')}** • score {s.get('score')}\n{json.dumps(s, ensure_ascii=False)}"
            send_discord(msg)
            new_ids.append(sid)

    # trend reversals
    for t in trend:
        tkr = t["ticker"]; status = t["status"]; sc = t["score"]
        prev = prev_trend.get(tkr)
        if prev is None:
            pass
        elif prev == "UP" and status in ("WATCH","DOWN"):
            send_discord(f"⚠️ Trend endres for {tkr}: {prev} → {status} (score {sc})")
            new_ids.append(f"trend_{tkr}_{status}")
        elif prev == "WATCH" and status == "DOWN":
            send_discord(f"🔴 {tkr}: WATCH → DOWN (score {sc})")
            new_ids.append(f"trend_{tkr}_{status}")

    if new_ids:
        state["notified_ids"] = list(already.union(new_ids))
    state["trend_status"] = {t["ticker"]: t["status"] for t in trend}
    save_state(state)

    print("OK: wrote dashboard data (with trend)")


def main():
    generate()


if __name__ == "__main__":
    main()
