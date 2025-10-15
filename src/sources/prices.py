import csv
import io
import json
import urllib.request

def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def _stooq_symbol(ticker: str) -> str:
    return f"{ticker.lower()}.us"

def fetch_quote_stooq(ticker: str):
    sym = _stooq_symbol(ticker)
    url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=json"
    try:
        raw = _http_get(url)
        data = json.loads(raw)
        q = data["symbols"][0]
        price = float(q.get("close") or 0.0)
        prev = float(q.get("previousClose") or 0.0) if q.get("previousClose") else None
        change_pct = ((price - prev) / prev * 100.0) if prev and prev > 0 else None
        return {"price": price, "change_pct": change_pct}
    except Exception:
        return {"price": None, "change_pct": None}

def fetch_history_stooq(ticker: str, days: int = 30):
    sym = _stooq_symbol(ticker)
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    try:
        raw = _http_get(url)
        text = raw.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        closes = []
        for row in reader:
            try:
                closes.append({"date": row["Date"], "close": float(row["Close"])})
            except Exception:
                pass
        return closes[-days:] if len(closes) > days else closes
    except Exception:
        return []

def fetch_prices(tickers):
    out = []
    for t in tickers:
        q = fetch_quote_stooq(t)
        hist = fetch_history_stooq(t, days=30)
        out.append({"ticker": t, "price": q["price"], "change_pct": q["change_pct"], "history": hist})
    return out
