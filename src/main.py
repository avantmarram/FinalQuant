# src/main.py
# Quantum Radar — backend aggregator (V2)
# - Henter data fra arXiv, SEC, PatentsView, GDELT, yfinance
# - Lager tidsvinduer (i dag / siste uke) og totalsummer
# - Sorterer og lagrer til /docs for dashboardet
# - (Valgfritt) sender toppsignaler til Discord
# - Vedlikeholder enkel "state" for å unngå duplikat-varsler

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

# --- (valgfritt) enkel backtest-innkobling ---
try:
    from src.logic.backtest import simulate  # hvis du har lagt til backtest-filen
except Exception:
    simulate = None


def _utc_iso(dt: datetime | str | None = None) -> str:
    """Returner ISO-8601 UTC med 'Z' suffix."""
    if isinstance(dt, datetime):
        return dt.replace(microsecond=0).isoformat() + "Z"
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def load_state() -> dict:
    """Les state (hva vi har varslet før)."""
    try:
        with open(STATE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"notified_ids": []}


def save_state(state: dict) -> None:
    """Skriv state.json på en trygg måte."""
    os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
    tmp = STATE_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_JSON)


def generate():
    """Hovedpipeline: hent → score → summer → lagre → evt. varsle."""
    # --- Hent rådata ---
    arxiv = fetch_arxiv(ARXIV_QUERIES)
    sec = fetch_sec_filings()
    patents = fetch_patents(PATENT_KEYWORDS + COMPANIES)
    news = fetch_news(NEWS_KEYWORDS + COMPANIES)
    prices = fetch_prices(TICKERS)

    # --- Lag signaler (inkl. ts og dedup/boost i rules.py) ---
    signals = score_items(arxiv, sec, patents, news, prices)

    # --- Tidsvinduer ---
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    today_prefix = now.date().isoformat()  # "YYYY-MM-DD"

    signals_today = [s for s in signals if (s.get("ts", "") or "").startswith(today_prefix)]
    signals_week = [s for s in signals if (s.get("ts", "") or "") >= week_ago.isoformat()]

    # --- Bygg dashboard-data ---
    data = {
        "generated_at": _utc_iso(now),
        "tickers": TICKERS,
        "prices": prices,
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

    # (valgfritt) Backtest hvis funksjonen finnes
    if callable(simulate):
        try:
            bt = simulate(signals, TICKERS)
            data["backtest"] = bt  # {"trades":..., "winrate":..., "avg_ret":...}
        except Exception:
            # Ikke la en backtest-feil stoppe resten
            data["backtest"] = {"trades": 0, "winrate": 0, "avg_ret": 0}

    # --- Lagre JSON til /docs ---
    os.makedirs(os.path.dirname(DATA_JSON), exist_ok=True)
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(SIGNALS_JSON, "w", encoding="utf-8") as f:
        # Begrens størrelsen så Pages laster raskt
        json.dump(signals[:200], f, ensure_ascii=False, indent=2)

    # --- Discord-varsler: send kun nye topp-3 for ikke å spamme ---
    state = load_state()
    already = set(state.get("notified_ids", []))
    new_ids = []

    # Sorter topp tre sterkeste NYE i dag/uke (allerede sortert i rules.py)
    for s in signals[:3]:
        sid = json.dumps(s, sort_keys=True)
        if sid not in already:
            msg = f"**{s.get('type')}** • score {s.get('score')}  \n{json.dumps(s, ensure_ascii=False)}"
            send_discord(msg)  # try/except håndteres i notifier
            new_ids.append(sid)

    if new_ids:
        state["notified_ids"] = list(already.union(new_ids))
        save_state(state)

    print("OK: wrote docs/data.json and docs/signals.json")


def main():
    generate()


if __name__ == "__main__":
    main()
