import yfinance as yf
from datetime import datetime
def fetch_prices(tickers):
    rows=[]
    for t in tickers:
        try:
            y=yf.Ticker(t); info=y.fast_info
            price=float(info.last_price); prev=float(info.previous_close or 0.0)
            chg=((price-prev)/prev*100.0) if prev else 0.0
            rows.append({"ticker":t,"price":price,"change_pct":round(chg,2),"ts":datetime.utcnow().isoformat()+"Z"})
        except Exception: continue
    return rows
