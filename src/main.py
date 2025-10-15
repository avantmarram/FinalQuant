import os, json, time
from datetime import datetime, timezone

from src.sources.prices import fetch_prices
from src.sources.news import fetch_news  # eksisterer fra før
from src.sources.sec import fetch_filings  # eksisterer fra før
from src.sources.patents import fetch_patents  # eksisterer fra før
from src.sources.arxiv import fetch_arxiv  # eksisterer fra før
from src.logic.rules import score_items  # eksisterer fra før
from src.notifier import send_discord

from src.config import (
    TICKERS, COMPANIES, ARXIV_QUERIES,
    NEWS_KEYWORDS, PATENT_KEYWORDS,
    DATA_JSON, SIGNALS_JSON, STATE_JSON
)

# ---------- enkle signal-/trendberegninger på pris-historikk ----------

def ema(values, span):
    k = 2 / (span + 1)
    ema_val = None
    out = []
    for v in values:
        if ema_val is None:
            ema_val = v
        else:
            ema_val = v * k + ema_val * (1 - k)
        out.append(ema_val)
    return out

def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        chg = values[i] - values[i-1]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsis = [None]*(period)
    for i in range(period, len(values)-1):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rs = 999
        else:
            rs = avg_gain / avg_loss
        rsis.append(100 - (100 / (1 + rs)))
    rsis.append(rsis[-1])
    return rsis[-1]

def build_trend_blocks(prices_payload):
    """Lager trenddata per ticker basert på 30 dagers closes."""
    trend = []
    for p in prices_payload:
        hist = p.get("history", [])
        closes = [h["close"] for h in hist][-30:]
        if len(closes) < 5:
            trend.append({"ticker": p["ticker"], "status": "WATCH"})
            continue
        ema5 = ema(closes, 5)[-1]
        ema20 = ema(closes, 20)[-1] if len(closes) >= 20 else closes[-1]
        _rsi = rsi(closes, 14) or 50
        status = "UP" if closes[-1] > ema20 else "DOWN"
        trend.append({
            "ticker": p["ticker"],
            "ema5": round(ema5, 4),
            "ema20": round(ema20, 4),
            "rsi": round(_rsi, 1),
            "status": status
        })
    return trend

# ---------- IO helpers ----------

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# ------------------------------- MAIN --------------------------------

def main():
    started = time.time()

    # 1) Hent priser (nå + 30 dagers historikk)
    prices_payload = fetch_prices(TICKERS)

    # 2) Hent kilder
    news_items = fetch_news(NEWS_KEYWORDS, COMPANIES)
    sec_items = fetch_filings(COMPANIES)
    patent_items = fetch_patents(PATENT_KEYWORDS + COMPANIES)
    arxiv_items = fetch_arxiv(ARXIV_QUERIES)

    # 3) Score & lag “dagens nye”
    all_items = (news_items or []) + (sec_items or []) + (patent_items or []) + (arxiv_items or [])
    scored = score_items(all_items)
    signals_today = [x for x in scored if x.get("is_new")]

    # 4) Trend-data for frontenden
    trend_blocks = build_trend_blocks(prices_payload)

    # 5) Les/oppdater state
    state = read_json(STATE_JSON, {"last_run": None, "signals_seen": set()})
    seen = set(state.get("signals_seen", []))
    new_for_alert = []
    for s in signals_today:
        sig_id = s.get("id") or (s.get("type","") + "|" + s.get("title",""))[:256]
        if sig_id not in seen:
            new_for_alert.append(s)
            seen.add(sig_id)

    # 6) Varsling (Discord webhook / DM)
    if new_for_alert:
        lines = [f"**{len(new_for_alert)} nye signal(er)**"]
        for s in sorted(new_for_alert, key=lambda x: -x.get("score", 0))[:10]:
            t = s.get("ticker") or "—"
            lines.append(f"- [{t}] {s.get('type','?')} • score {s.get('score',0)} • {s.get('title','')[:120]}")
        send_discord("\n".join(lines))

    # 7) Skriv “signals.json” (for historikk)
    write_json(SIGNALS_JSON, scored)

    # 8) Skriv “data.json” (front-end)
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tickers": TICKERS,
        "prices": prices_payload,
        "trend": trend_blocks,
        "counts": {
            "signals_today": len(new_for_alert),
            "signals_total": len(scored)
        }
    }
    write_json(DATA_JSON, data)

    # 9) Oppdater state
    write_json(STATE_JSON, {"last_run": datetime.utcnow().isoformat()+"Z", "signals_seen": list(seen)})

    elapsed = round(time.time() - started, 1)
    print(f"Radar ferdig på {elapsed}s • {len(new_for_alert)} nye signaler")

if __name__ == "__main__":
    main()
