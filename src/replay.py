"""Replay sessions: real recorded CSVs if available, else a SIMULATED session.

The simulator is honest about what it is — random-walk price paths with
realistic NSE session shape (U-shaped volume, opening volatility burst,
occasional breakout trends). It exists so you can practice reading the
dashboard and so the engine can be tested end-to-end when the market is shut.
It teaches you the TOOL, not the market. Real recorded data always wins:
drop CSVs into data/history/<SYMBOL>_1m.csv and they'll be used instead.

CSV format: ts,open,high,low,close,volume  (ts in IST, 1-minute bars)
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pytz

from .candles import Candle, IST
from .config import PROJECT_ROOT

HISTORY_DIR = PROJECT_ROOT / "data" / "history"

# Rough mid-2026 price anchors so simulated numbers look familiar
PRICE_ANCHORS = {
    "RELIANCE": 1520, "HDFCBANK": 1980, "ICICIBANK": 1450, "INFY": 1620,
    "TCS": 3450, "SBIN": 810, "TATAMOTORS": 990, "AXISBANK": 1180,
    "NIFTY50": 25400, "BANKNIFTY": 57200,
}


def load_recorded_session(symbol: str) -> Optional[list[Candle]]:
    path = HISTORY_DIR / f"{symbol}_1m.csv"
    if not path.exists():
        return None
    candles = []
    with open(path) as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["ts"])
            ts = ts.astimezone(IST) if ts.tzinfo else IST.localize(ts)
            candles.append(Candle(ts=ts, open=float(row["open"]),
                                  high=float(row["high"]), low=float(row["low"]),
                                  close=float(row["close"]),
                                  volume=float(row["volume"]), closed=True))
    return candles or None


def simulate_session(symbol: str, day: Optional[datetime] = None,
                     seed: Optional[int] = None,
                     regime: Optional[str] = None) -> list[Candle]:
    """One full NSE session (9:15-15:30, 375 one-minute candles), simulated.

    regime: 'trend_up' | 'trend_down' | 'choppy' | None (random)
    """
    rng = np.random.default_rng(seed if seed is not None
                                else abs(hash(symbol)) % (2**32))
    day = day or datetime.now(IST)
    start = day.astimezone(IST).replace(hour=9, minute=15, second=0, microsecond=0)
    n = 375
    anchor = PRICE_ANCHORS.get(symbol, 1000.0)

    if regime is None:
        regime = rng.choice(["trend_up", "trend_down", "choppy"], p=[0.35, 0.35, 0.30])
    drift_map = {"trend_up": 0.9, "trend_down": -0.9, "choppy": 0.0}
    total_drift_pct = drift_map[regime] * rng.uniform(0.6, 1.4)

    minutes = np.arange(n)
    # Volatility: high at open, settles midday, picks up at close (smile)
    vol_curve = 0.030 + 0.070 * np.exp(-minutes / 45) + 0.030 * np.exp(-(n - minutes) / 60)
    base_step_pct = vol_curve * rng.uniform(0.8, 1.2)

    # Trend days often "break out" after the opening range settles
    drift = np.zeros(n)
    if regime != "choppy":
        breakout_at = int(rng.uniform(15, 45))
        drift[breakout_at:] = total_drift_pct / (n - breakout_at)
        # brief volume/vol burst at the breakout itself
        burst = slice(breakout_at, min(breakout_at + 8, n))
        base_step_pct[burst] *= 2.2

    rets = rng.normal(drift, base_step_pct) / 100.0
    closes = anchor * np.cumprod(1 + rets)
    opens = np.concatenate([[anchor], closes[:-1]])
    spread = np.abs(rng.normal(0, base_step_pct / 100.0 * anchor, n)) + anchor * 0.0002
    highs = np.maximum(opens, closes) + spread * rng.uniform(0.3, 1.0, n)
    lows = np.minimum(opens, closes) - spread * rng.uniform(0.3, 1.0, n)

    # U-shaped volume, spiking with the breakout
    base_vol = 60000 if symbol not in ("NIFTY50", "BANKNIFTY") else 0  # indices: no volume
    u = 1.0 + 2.5 * np.exp(-minutes / 40) + 1.5 * np.exp(-(n - minutes) / 50)
    vols = rng.gamma(2.0, base_vol / 2.0, n) * u
    if regime != "choppy" and base_vol:
        vols[burst] *= rng.uniform(2.5, 4.0)

    return [Candle(ts=start + timedelta(minutes=int(i)),
                   open=round(float(opens[i]), 2), high=round(float(highs[i]), 2),
                   low=round(float(lows[i]), 2), close=round(float(closes[i]), 2),
                   volume=float(vols[i]), closed=True)
            for i in range(n)]


def build_session(symbols: list[str], seed: Optional[int] = None,
                  coordinated: bool = True) -> tuple[dict[str, list[Candle]], dict[str, str]]:
    """Session for many symbols. coordinated=True makes stocks loosely follow
    the index regime (realistic: most stocks move with the market).
    Returns (session, regimes) — regimes maps symbol -> its simulated regime,
    so demos can be honest about what was generated."""
    rng = np.random.default_rng(seed)
    regimes: dict[str, str] = {}
    market_regime = rng.choice(["trend_up", "trend_down", "choppy"], p=[0.4, 0.35, 0.25])
    session: dict[str, list[Candle]] = {}
    all_syms = list(symbols) + ["NIFTY50", "BANKNIFTY"]
    for i, sym in enumerate(all_syms):
        recorded = load_recorded_session(sym)
        if recorded:
            session[sym] = recorded
            regimes[sym] = "recorded"
            continue
        if coordinated and sym in ("NIFTY50", "BANKNIFTY"):
            regime = market_regime
        elif coordinated:
            regime = market_regime if rng.random() < 0.65 else \
                rng.choice(["trend_up", "trend_down", "choppy"])
        else:
            regime = None
        s = int(rng.integers(0, 2**31)) if seed is not None else None
        session[sym] = simulate_session(sym, seed=s, regime=regime)
        regimes[sym] = regime or "random"
    return session, regimes
