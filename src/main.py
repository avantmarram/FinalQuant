# src/main.py
import os, json, time, traceback
from datetime import datetime, timezone

# Kilder
from src.sources.prices import fetch_prices
try:
    from src.sources.news import fetch_news
except Exception:
    fetch_news = None
try:
    from src.sources.sec import fetch_filings
except Exception:
    fetch_filings = None
try:
    from src.sources.patents import fetch_patents
except Exception:
    fetch_patents = None
try:
    from src.sources.arxiv import fetch_arxiv
except Exception:
    fetch_arxiv = None

from src.logic.rules import score_items
from src.notifier import send_discord

from src.config import (
    TICKERS, COMPANIES, ARXIV_QUERIES,
    NEWS_KEYWORDS, PATENT_KEYWORDS,
    DATA_JSON, SIGNALS_JSON, STATE_JSON
)

# ---------- helpers ----------
def ema(vals, span):
    if not vals: return None
    k = 2 / (span + 1)
    e = None
    out = []
    for v in vals:
        e = v if e is None else (v * k + e * (1 - k))
        out.append(e)
    return out

def rsi(vals, period=14):
    if len(vals) <= period: return None
    gains, losses = [], []
    for i in range(1, len(vals)):
        d = vals[i] - vals[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rsis = [None]*period
    for i in range(period, len(vals)-1):
        avg_g = (avg_g*(period-1) + gains[i]) / period
        avg_l = (avg_l*(period-1) + losses[i]) / period
        rs = (avg_g / avg_l) if avg_l else 999
        rsis.append(100 - (100/(1+rs)))
    rsis.append(rsis[-1])
    return rsis[-1]

def build_trend_blocks(prices_payload):
    trend = []
    for p in prices_payload:
        hist = p.get("history", []) or []
        closes = [h["close"] for h in hist][-30:]
        if len(closes) < 5:
            trend.append({"ticker": p["ticker"], "status": "WATCH"})
            continue
        e5  = ema(closes, 5)[-1]
        e20 = ema(closes, 20)[-1] if len(closes) >= 20 else closes[-1]
        _rsi = rsi(closes, 14) or 50
        status = "UP" if closes[-1] > e20 else "DOWN"
        trend.append({
            "ticker": p["ticker"],
            "ema5": round(e5, 4),
            "ema20": round(e20, 4),
            "rsi": round(_rsi, 1),
            "status": status
        })
    return trend

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

def safe_call(name, fn, *a, **k):
    try:
        if fn is None:
            raise RuntimeError(f"{name} modul ikke tilgjengelig")
        return fn(*a, **k) or []
    except Exception as e:
        print(f"[WARN] {name} feilet: {e}")
        traceback.print_exc()
        return []

# ------------------------------- MAIN --------------------------------

def main():
    started = time.time()

    # 1) Priser (nå + 30 dagers historikk)
    prices_payload = safe_call("prices", fetch_prices, TICKERS)

    # 2) Kilder (robust)
    news_items   = safe_call("news",    fetch_news,    NEWS_KEYWORDS, COMPANIES)
    sec_items    = safe_call("sec",     fetch_filings, COMPANIES)
    patent_items = safe_call("patents", fetch_patents, PATENT_KEYWORDS + COMPANIES)
    arxiv_items  = safe_call("arxiv",   fetch_arxiv,   ARXIV_QUERIES)

    # 3) Score
    all_items = news_items + sec_items + patent_items + arxiv_items
    scored = []
    try:
        scored = score_items(all_items) or []
    except Exception as e:
        print(f"[WARN] score_items feilet: {e}")
        traceback.print_exc()
        scored = []

    signals_today = [x for x in scored if x.get("is_new")]

    # 4) Trend-data
    trend_blocks = build_trend_blocks(prices_payload)

    # 5) State + nye varsler
    state = read_json(STATE_JSON, {"last_run": None, "signals_seen": []})
    seen = set(state.get("signals_seen") or [])
    new_for_alert = []
    for s in signals_today:
        sig_id = s.get("id") or (s.get("type","") + "|" + s.get("title",""))[:256]
        if sig_id not in seen:
            new_for_alert.append(s); seen.add(sig_id)

    # 6) Varsling
    if new_for_alert:
        lines = [f"**{len(new_for_alert)} nye signal(er)**"]
        for s in sorted(new_for_alert, key=lambda x: -x.get("score", 0))[:10]:
            t = s.get("ticker") or "—"
            lines.append(f"- [{t}] {s.get('type','?')} • score {s.get('score',0)} • {s.get('title','')[:120]}")
        send_discord("\n".join(lines))

    # 7) Skriv ut filer
    write_json(SIGNALS_JSON, scored)
    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tickers": TICKERS,
        "prices": prices_payload,
        "trend": trend_blocks,
        "counts": { "signals_today": len(new_for_alert), "signals_total": len(scored) }
    }
    write_json(DATA_JSON, data)
    write_json(STATE_JSON, {"last_run": datetime.utcnow().isoformat()+"Z", "signals_seen": list(seen)})

    print(f"Radar ferdig • {round(time.time()-started,1)}s • {len(new_for_alert)} nye signaler")

if __name__ == "__main__":
    main()
