"""Indicator math on candle series. Pure functions: candles in, numbers out.

Beginner cheat-sheet (also surfaced as tooltips in the dashboard):

VWAP  - Volume-Weighted Average Price. The "fair price" of the day so far,
        weighted by how much volume traded at each level. Price above VWAP =
        buyers in control today; below = sellers in control.
ORB   - Opening Range Breakout. The high/low of the first 15 minutes
        (9:15-9:30). Breaking above that high with volume is a classic
        bullish intraday trigger; breaking below the low, bearish.
RSI   - Relative Strength Index (0-100). Momentum gauge. >60 = strong upward
        momentum, <40 = strong downward. We use a fast RSI(9) for intraday.
MACD  - Trend/momentum crossover of two moving averages. MACD line above its
        signal line = bullish momentum, below = bearish. We use the fast
        (5,13,1) intraday variant.
ATR   - Average True Range: how much the stock *typically* moves per candle.
        Used to place stop-losses at a realistic distance instead of a guess.
"""
from __future__ import annotations

from datetime import time as dtime
from typing import Optional

import numpy as np

from .candles import Candle, CandleSeries, IST


# ---------- VWAP (session-anchored, from 1-min candles) ----------

def vwap(candles_1m: list[Candle]) -> Optional[float]:
    """Volume-weighted average price for the current session's candles."""
    if not candles_1m:
        return None
    pv, vol = 0.0, 0.0
    for c in candles_1m:
        typical = (c.high + c.low + c.close) / 3.0
        pv += typical * c.volume
        vol += c.volume
    if vol <= 0:
        return None
    return pv / vol


# ---------- Opening Range (first 15 minutes: 9:15 - 9:30 IST) ----------

def opening_range(candles_1m: list[Candle]) -> Optional[tuple[float, float]]:
    """(high, low) of the first 15 minutes. None until 9:30 has passed."""
    orb = [c for c in candles_1m
           if dtime(9, 15) <= c.ts.astimezone(IST).time() < dtime(9, 30)]
    if not orb:
        return None
    complete = all(c.closed for c in orb)
    after = [c for c in candles_1m if c.ts.astimezone(IST).time() >= dtime(9, 30)]
    if not (complete and after):  # range only usable once it's finished forming
        return None
    return max(c.high for c in orb), min(c.low for c in orb)


# ---------- RSI ----------

def rsi(closes: list[float], period: int = 9) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(np.asarray(closes, dtype=float))
    seed_gain = np.clip(deltas[:period], 0, None).mean()
    seed_loss = -np.clip(deltas[:period], None, 0).mean()
    avg_gain, avg_loss = seed_gain, seed_loss
    for d in deltas[period:]:  # Wilder smoothing
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


# ---------- MACD ----------

def _ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1.0)
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def macd(closes: list[float], fast: int = 5, slow: int = 13, signal: int = 1
         ) -> Optional[tuple[float, float, float]]:
    """Returns (macd_line, signal_line, histogram). Needs ~slow*2 candles."""
    if len(closes) < slow + signal + 5:
        return None
    arr = np.asarray(closes, dtype=float)
    line = _ema(arr, fast) - _ema(arr, slow)
    sig = _ema(line, signal) if signal > 1 else line
    return float(line[-1]), float(sig[-1]), float(line[-1] - sig[-1])


def macd_direction(closes: list[float], fast: int = 5, slow: int = 13,
                   signal: int = 1) -> Optional[int]:
    """+1 bullish, -1 bearish, 0 flat. With signal=1 the signal line equals the
    MACD line, so direction comes from the line's slope + sign."""
    m = macd(closes, fast, slow, signal)
    if m is None:
        return None
    line_now = m[0]
    prev = macd(closes[:-1], fast, slow, signal)
    if prev is None:
        return 0
    slope = line_now - prev[0]
    if line_now > 0 and slope > 0:
        return 1
    if line_now < 0 and slope < 0:
        return -1
    return 0


# ---------- ATR ----------

def atr(candles: list[Candle], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    trs = []
    for prev, cur in zip(candles[-period - 1:-1], candles[-period:]):
        trs.append(max(cur.high - cur.low,
                       abs(cur.high - prev.close),
                       abs(cur.low - prev.close)))
    return float(np.mean(trs))


# ---------- Volume spike ----------

def volume_spike(candles: list[Candle], lookback: int = 10,
                 multiplier: float = 2.0) -> Optional[bool]:
    """True if the latest closed candle's volume > multiplier x the average
    of the previous `lookback` candles."""
    if len(candles) < lookback + 1:
        return None
    recent = candles[-1]
    baseline = candles[-lookback - 1:-1]
    avg = np.mean([c.volume for c in baseline])
    if avg <= 0:
        return None
    return recent.volume > multiplier * avg


# ---------- Simple trend (for 15-min filter & index context) ----------

def ema_trend(closes: list[float], period: int = 20) -> Optional[int]:
    """+1 if price above rising EMA, -1 if below falling EMA, else 0."""
    if len(closes) < period + 3:
        return None
    arr = np.asarray(closes, dtype=float)
    e = _ema(arr, period)
    above = arr[-1] > e[-1]
    rising = e[-1] > e[-3]
    if above and rising:
        return 1
    if (not above) and (not rising):
        return -1
    return 0
