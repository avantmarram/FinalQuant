# src/main.py
# Quantum Radar — V3 med Trend Reversal + Discord DM-varsler (regler)
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
from src.notifier import send_discord, notify  # notify = DM først, fallback webhook

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
        return {"notified_ids": [], "trend_status": {}, "sent_alerts": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
    tmp = STATE_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_JSON)


# ---------------------- ALERT-REGLER (DM) ----------------------
BUY_ZONES = {
    # justér nivåene om du ønsker
    "RGTI": [52.00, 50.00, 49.20, 47.80],
    "QBTS": [38.00, 36.00, 34.50],
}
NEAR_BAND_PCT = 0.004  # 0.4% bånd rundt nivået
MOMENTUM_UP = 5.0      # +5% intradag
MOMENTUM_DOWN = -7.0   # -7% intradag

def _near_level(price: float, level: float, band_pct: float) -> bool:
    if price is None or level is None or level <= 0:
        return False
    return abs(price - level) / level <= band_pct

def run_alert_rules(state: dict, prices: list, trend: list):
    """
    Sender DM-varsler (notify) for:
      - Nær kjøpssoner (BUY_ZONES) med band
      - Momentum spikes (+5% / -7%)
      - Trend 'UP' + RSI>=50 og grønn dag (bekreftelse)
    Dedupliseres via state['sent_alerts'].
    """
    sent = set(state.get("sent_alerts", []))
    price_map = {p["ticker"]: p for p in (prices or [])}
    trend_map = {t["ticker"]: t for t in (trend or [])}

    for ticker, p in price_map.items():
        price = p.get("price")
        chg = p.get("change_pct", 0.0) or 0.0
        t = trend_map.get(ticker, {})

        # 1) Kjøpssoner
        for lvl in BUY_ZONES.get(ticker, []):
            key = f"{ticker}_zone_{lvl:.2f}"
            if key not in sent and _near_level(price, lvl, NEAR_BAND_PCT):
                rsi = t.get("rsi")
                status = t.get("status", "?")
                msg = (
                    f"🟢 {ticker} nær kjøpssone {lvl:.2f} • pris {price:.2f} ({chg:+.2f}%)\n"
                    f"Trend: {status} • RSI: {rsi:.0f}  — vurder kjøp i z {lvl:.2f} (band {NEAR_BAND_PCT*100:.1f}%)."
                )
                notify(msg)
                sent.add(key)

        # 2) Momentum
        key_up = f"{ticker}_mom_up"
        key_dn = f"{ticker}_mom_dn"
        if chg >= MOMENTUM_UP and key_up not in sent:
            notify(f"⚡ {ticker} momentum opp: {chg:+.2f}% • pris {price:.2f}.")
            sent.add(key_up)
        if chg <= MOMENTUM_DOWN and key_dn not in sent:
            notify(f"⚠️ {ticker} momentum ned: {chg:+.2f}% • pris {price:.2f}. Se støtteområder.")
            sent.add(key_dn)

        # 3) Trend bekreftelse (UP + RSI>=50 og grønn dag)
        tstat = t.get("status")
        rsi = t.get("rsi", 0.0) or 0.0
        key_tr = f"{ticker}_trend_up_conf"
        if tstat == "UP" and rsi >= 50 and chg > 0 and key_tr not in sent:
            notify(f"✅ {ticker} trend bekreftet: {tstat}, RSI {rsi:.0f}, dag {chg:+.2f}%.")
            sent.add(key_tr)

    state["sent_alerts"] = list(sent)
    return state
# --------------------------------------------------------------


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

    # 6) Varsler (topp-signaler + trend + DM-regler)
    state = load_state()
    already = set(state.get("notified_ids", []))
    prev_trend = state.get("trend_status", {})
    new_ids = []

    # topp tre nye signaler (fortsatt webhook-beskjed for oversikt)
    for s in signals[:3]:
        sid = json.dumps(s, sort_keys=True)
        if sid not in already:
            send_discord(f"**{s.get('type')}** • score {s.get('score')}\n{json.dumps(s, ensure_ascii=False)}")
            new_ids.append(sid)

    # trend reversals (UP→WATCH/DOWN, WATCH→DOWN)
    for t in trend:
        tkr = t["ticker"]; status = t["status"]; sc = t["score"]
        prev = prev_trend.get(tkr)
        if prev is None:
            pass
        elif prev == "UP" and status in ("WATCH","DOWN"):
            notify(f"⚠️ Trend endres for {tkr}: {prev} → {status} (score {sc})")
            new_ids.append(f"trend_{tkr}_{status}")
        elif prev == "WATCH" and status == "DOWN":
            notify(f"🔴 {tkr}: WATCH → DOWN (score {sc})")
            new_ids.append(f"trend_{tkr}_{status}")

    # kjør DM-regler (kjøpssoner, momentum, trend-bekreftelse)
    state = run_alert_rules(state, prices, trend)

    if new_ids:
        state["notified_ids"] = list(already.union(new_ids))
    state["trend_status"] = {t["ticker"]: t["status"] for t in trend}
    save_state(state)

    print("OK: wrote dashboard data (with trend + alerts)")


def main():
    generate()


if __name__ == "__main__":
    main()
