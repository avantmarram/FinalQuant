import csv
import io
import json
import urllib.request
from datetime import datetime, timedelta

# Enkle hentere fra Stooq:
# - Nåpris hentes via JSON-endepunkt (quote)
# - Historikk (daglige closes) via CSV
#
# Merk: Stooq bruker .us-suffiks for US-aksjer (rgti.us, qbts.us, ionq.us, qubt.us)

def _http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def _stooq_symbol(ticker: str) -> str:
    return f"{ticker.lower()}.us"

def fetch_quote_stooq(ticker: str):
    sym = _stooq_symbol(ticker)
    # Stooq JSON “q/l” er enkel å parse
    url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=json"
    try:
        raw = _http_get(url)
        data = json.loads(raw)
        quote = data["symbols"][0]
        # Close = nåværende (forsinket) pris; change = prosent vs forrige close
        price = float(quote.get("close") or 0.0)
        prev = float(quote.get("previousClose") or 0.0) if quote.get("previousClose") else None
        change_pct = 0.0
        if prev and prev > 0:
            change_pct = (price - prev) / prev * 100.0
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
            # CSV har feltene: Date,Open,High,Low,Close,Volume
            try:
                d = row["Date"]
                c = float(row["Close"])
                closes.append({"date": d, "close": c})
            except Exception:
                pass
        closes = closes[-days:] if len(closes) > days else closes
        return closes
    except Exception:
        return []

def fetch_prices(tickers):
    out = []
    for t in tickers:
        q = fetch_quote_stooq(t)
        hist = fetch_history_stooq(t, days=30)
        out.append({
            "ticker": t,
            "price": q.get("price"),
            "change_pct": q.get("change_pct"),
            "history": hist,  # liste av {date, close}
        })
    return out
