# src/logic/trend.py
# Enkel, robust trend-/reversalradar basert på daglige data (yfinance).
# Signalene er designet for å være lave på støy, høye på nytte.

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict
from statistics import mean
from datetime import datetime, timedelta
import yfinance as yf
import math

@dataclass
class TrendPoint:
    ticker: str
    status: str     # "UP" | "WATCH" | "DOWN"
    score: int
    rsi: float
    ema5: float
    ema20: float
    close: float
    change_pct: float
    vol: float
    vol_avg20: float
    notes: List[str]
    asof: str

def _ema(values: List[float], n: int) -> float:
    if not values: return float("nan")
    k = 2 / (n + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema

def _rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1: return float("nan")
    gains, losses = [], []
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(-min(ch, 0.0))
    avg_gain = mean(gains)
    avg_loss = mean(losses) or 1e-9
    for i in range(period + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gain = max(ch, 0.0); loss = -min(ch, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    rs = avg_gain / (avg_loss or 1e-9)
    return 100 - (100 / (1 + rs))

def _bearish_divergence(closes: List[float], rsis: List[float]) -> bool:
    # Higher high i pris, lower high i RSI i siste ~15 bars
    if len(closes) < 20 or len(rsis) != len(closes): return False
    window = closes[-20:]
    rwin   = rsis[-20:]
    try:
        hi1_idx = window.index(max(window[:10]))
        hi2_idx = 10 + window[10:].index(max(window[10:]))
        price_higher = window[hi2_idx] > window[hi1_idx] * 0.995
        rsi_lower    = rwin[hi2_idx] < rwin[hi1_idx] - 2
        return price_higher and rsi_lower
    except Exception:
        return False

def compute_trend_for(ticker: str) -> TrendPoint | None:
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df is None or df.empty or len(df) < 25:
            return None
        closes = [float(x) for x in df["Close"].tolist()]
        opens  = [float(x) for x in df["Open"].tolist()]
        vols   = [float(x) for x in df["Volume"].tolist()]
        ema5   = _ema(closes[-25:], 5)
        ema20  = _ema(closes[-25:], 20)
        rsi14  = _rsi(closes[-25:], 14)
        close  = closes[-1]
        change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100.0
        vol_last = vols[-1]
        vol_avg20 = mean(vols[-20:]) if len(vols) >= 20 else mean(vols)
        red_day = closes[-1] < opens[-1]
        high_red_vol = red_day and vol_last > 1.5 * (vol_avg20 or 1)

        # grov RSI-serie til divergens-sjekk
        rsiser = []
        for i in range(len(closes)):
            rsiser.append(_rsi(closes[: i + 1][-25:], 14))
        div = _bearish_divergence(closes, rsiser)

        score = 0
        notes = []

        # Trend retning
        if ema5 > ema20: score += 2; notes.append("EMA5>EMA20 (trend opp)")
        else:            score -= 2; notes.append("EMA5<EMA20 (trend ned)")

        # Slope av EMA5 (enkel)
        if len(closes) >= 7:
            ema5_prev = _ema(closes[-7:-1], 5)
            if ema5 > ema5_prev: score += 1; notes.append("EMA5 stiger")
            else:                score -= 1; notes.append("EMA5 faller")

        # RSI
        if rsi14 >= 80:  score -= 2; notes.append(f"RSI {rsi14:.0f} (overkjøpt)")
        elif rsi14 >= 70: score -= 1; notes.append(f"RSI {rsi14:.0f} (høy)")
        elif rsi14 >= 50: score += 1; notes.append(f"RSI {rsi14:.0f} (ok)")

        # Volum-distribusjon
        if high_red_vol: score -= 2; notes.append("Rød dag med høyt volum (distribusjon)")

        # Bearish divergens
        if div: score -= 2; notes.append("Bearish divergens (pris↑, RSI↓)")

        # Klassifisering
        status = "UP" if score >= 2 else ("DOWN" if score <= -2 else "WATCH")

        return TrendPoint(
            ticker=ticker,
            status=status,
            score=int(score),
            rsi=float(rsi14),
            ema5=float(ema5),
            ema20=float(ema20),
            close=float(close),
            change_pct=float(change_pct),
            vol=float(vol_last),
            vol_avg20=float(vol_avg20),
            notes=notes,
            asof=datetime.utcnow().isoformat()+"Z",
        )
    except Exception:
        return None

def compute_trend_all(tickers: List[str]) -> List[Dict]:
    out = []
    for t in tickers:
        tp = compute_trend_for(t)
        if tp:
            out.append(asdict(tp))
    # sorter viktigst først: DOWN -> WATCH -> UP, deretter lav score
    order = {"DOWN": 0, "WATCH": 1, "UP": 2}
    out.sort(key=lambda x: (order.get(x["status"], 1), x["score"]))
    return out
