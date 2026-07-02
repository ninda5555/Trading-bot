"""Event-driven signal engine.

Flow: feed (live/delayed/replay) -> SymbolAggregator -> on every candle close
this engine recomputes the five core signals on 5-min candles, checks the
15-min trend filter, checks index alignment, and produces a SignalSnapshot
with a conviction score.

The five signals (each votes +1 bullish / -1 bearish / 0 neutral):
  1. VWAP position     - price above/below the day's volume-weighted avg price
  2. ORB               - price broke above/below the first-15-min range
  3. RSI(9)            - momentum >60 bullish, <40 bearish
  4. MACD(5,13,1)      - fast trend direction on 5-min closes
  5. Volume spike      - >2x avg volume *in the direction of the candle*

Conviction = |sum of agreeing votes|, gated by the 15-min trend filter:
  4-5 agree AND 15-min agrees -> HIGH
  3 agree                     -> MEDIUM
  <=2                         -> LOW / NO SETUP
This is "signal agreement strength" — NOT a win-rate, NOT accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from .candles import Candle, CandleSeries, SymbolAggregator, IST
from . import indicators as ind


@dataclass
class SignalVote:
    name: str
    vote: int          # +1 bullish, -1 bearish, 0 neutral
    detail: str        # plain-English one-liner of what it saw
    value: Optional[float] = None


@dataclass
class SignalSnapshot:
    symbol: str
    ts: datetime
    price: float
    votes: list[SignalVote] = field(default_factory=list)
    bull_count: int = 0
    bear_count: int = 0
    direction: int = 0            # +1 long setup, -1 short setup, 0 none
    trend_15m: Optional[int] = None
    mtf_agrees: bool = False
    market_trend: Optional[int] = None   # NIFTY50 index direction
    market_aligned: Optional[bool] = None
    conviction: str = "NO SETUP"  # HIGH / MEDIUM / LOW / NO SETUP
    vwap: Optional[float] = None
    orb_high: Optional[float] = None
    orb_low: Optional[float] = None
    atr5: Optional[float] = None
    rsi9: Optional[float] = None
    warming_up: bool = False      # not enough candles yet for full signal set

    @property
    def agreeing(self) -> int:
        return max(self.bull_count, self.bear_count)


class SignalEngine:
    """Holds aggregators for all watched symbols + the two index symbols,
    recomputes signals on candle closes, and exposes latest snapshots."""

    INDEX_SYMBOLS = ("NIFTY50", "BANKNIFTY")

    def __init__(self, watchlist: list[str],
                 on_snapshot: Optional[Callable[[SignalSnapshot], None]] = None):
        self.watchlist = list(watchlist)
        self.on_snapshot = on_snapshot
        self.snapshots: dict[str, SignalSnapshot] = {}
        self.index_trend: dict[str, Optional[int]] = {s: None for s in self.INDEX_SYMBOLS}
        self.aggregators: dict[str, SymbolAggregator] = {}
        for sym in list(self.watchlist) + list(self.INDEX_SYMBOLS):
            self.aggregators[sym] = SymbolAggregator(sym, on_candle_close=self._on_close)

    # ---- feed entry points -------------------------------------------------
    def feed_tick(self, symbol: str, ts: datetime, price: float, cum_volume: float):
        agg = self.aggregators.get(symbol)
        if agg:
            agg.feed_tick(ts, price, cum_volume)

    def feed_candle_1m(self, symbol: str, candle: Candle):
        agg = self.aggregators.get(symbol)
        if agg:
            agg.feed_candle_1m(candle)

    # ---- event handler -----------------------------------------------------
    def _on_close(self, symbol: str, timeframe_min: int, series: CandleSeries):
        if symbol in self.INDEX_SYMBOLS:
            if timeframe_min == 5:
                closes = [c.close for c in self.aggregators[symbol].s5.closed_candles()]
                self.index_trend[symbol] = ind.ema_trend(closes, period=20)
            return
        if timeframe_min != 5:   # stock signals recompute on 5-min closes
            return
        snap = self.compute_snapshot(symbol)
        if snap:
            self.snapshots[symbol] = snap
            if self.on_snapshot:
                self.on_snapshot(snap)

    # ---- signal computation ------------------------------------------------
    def compute_snapshot(self, symbol: str) -> Optional[SignalSnapshot]:
        agg = self.aggregators.get(symbol)
        if not agg or agg.last_price is None:
            return None
        c1 = agg.s1.candles
        c5 = agg.s5.closed_candles()
        c15 = agg.s15.closed_candles()
        price = agg.last_price
        snap = SignalSnapshot(symbol=symbol, ts=agg.last_ts or datetime.now(IST), price=price)

        closes5 = [c.close for c in c5]
        votes: list[SignalVote] = []

        # 1. VWAP
        v = ind.vwap(c1)
        snap.vwap = v
        if v is None:
            votes.append(SignalVote("VWAP", 0, "VWAP not available yet (needs volume data)"))
        else:
            gap_pct = (price - v) / v * 100
            if price > v:
                votes.append(SignalVote("VWAP", 1, f"Price is {gap_pct:.2f}% ABOVE VWAP ₹{v:,.2f} — buyers in control today", v))
            elif price < v:
                votes.append(SignalVote("VWAP", -1, f"Price is {abs(gap_pct):.2f}% BELOW VWAP ₹{v:,.2f} — sellers in control today", v))
            else:
                votes.append(SignalVote("VWAP", 0, f"Price sitting right at VWAP ₹{v:,.2f} — tug of war", v))

        # 2. Opening Range Breakout
        orb = ind.opening_range(c1)
        if orb:
            snap.orb_high, snap.orb_low = orb
            if price > orb[0]:
                votes.append(SignalVote("ORB", 1, f"Broke ABOVE the opening range high ₹{orb[0]:,.2f} (first 15 min) — bullish breakout", orb[0]))
            elif price < orb[1]:
                votes.append(SignalVote("ORB", -1, f"Broke BELOW the opening range low ₹{orb[1]:,.2f} (first 15 min) — bearish breakdown", orb[1]))
            else:
                votes.append(SignalVote("ORB", 0, f"Still INSIDE the opening range ₹{orb[1]:,.2f}–₹{orb[0]:,.2f} — no breakout yet"))
        else:
            votes.append(SignalVote("ORB", 0, "Opening range still forming (first 15 min not done)"))

        # 3. RSI(9) on 5-min closes
        r = ind.rsi(closes5, 9)
        snap.rsi9 = r
        if r is None:
            votes.append(SignalVote("RSI(9)", 0, "RSI warming up — needs ~10 closed 5-min candles"))
        elif r > 60:
            votes.append(SignalVote("RSI(9)", 1, f"RSI {r:.0f} — strong upward momentum (>60)", r))
        elif r < 40:
            votes.append(SignalVote("RSI(9)", -1, f"RSI {r:.0f} — strong downward momentum (<40)", r))
        else:
            votes.append(SignalVote("RSI(9)", 0, f"RSI {r:.0f} — neutral zone (40-60), momentum unclear", r))

        # 4. MACD(5,13,1)
        md = ind.macd_direction(closes5)
        if md is None:
            votes.append(SignalVote("MACD", 0, "MACD warming up — needs ~20 closed 5-min candles"))
        elif md > 0:
            votes.append(SignalVote("MACD", 1, "MACD(5,13,1) positive and rising — short-term trend up"))
        elif md < 0:
            votes.append(SignalVote("MACD", -1, "MACD(5,13,1) negative and falling — short-term trend down"))
        else:
            votes.append(SignalVote("MACD", 0, "MACD flat / mixed — no clear short-term trend"))

        # 5. Volume spike (directional: spike on a green candle = bullish)
        vs = ind.volume_spike(c5, lookback=10, multiplier=2.0)
        if vs is None:
            votes.append(SignalVote("Volume", 0, "Volume baseline warming up — needs ~11 closed 5-min candles"))
        elif vs:
            last = c5[-1]
            if last.close > last.open:
                votes.append(SignalVote("Volume", 1, "Volume >2x its 10-candle average on a GREEN candle — real buying interest"))
            elif last.close < last.open:
                votes.append(SignalVote("Volume", -1, "Volume >2x its 10-candle average on a RED candle — real selling pressure"))
            else:
                votes.append(SignalVote("Volume", 0, "Volume spiked but candle closed flat — indecision"))
        else:
            votes.append(SignalVote("Volume", 0, "Volume normal — no unusual activity"))

        snap.votes = votes
        snap.bull_count = sum(1 for v_ in votes if v_.vote > 0)
        snap.bear_count = sum(1 for v_ in votes if v_.vote < 0)
        snap.warming_up = len(c5) < 21  # MACD is the slowest to warm up

        if snap.bull_count > snap.bear_count and snap.bull_count >= 3:
            snap.direction = 1
        elif snap.bear_count > snap.bull_count and snap.bear_count >= 3:
            snap.direction = -1

        # 15-min trend filter (multi-timeframe confirmation)
        closes15 = [c.close for c in c15]
        snap.trend_15m = ind.ema_trend(closes15, period=10)
        snap.mtf_agrees = (snap.trend_15m is not None and snap.direction != 0
                           and snap.trend_15m == snap.direction)

        # Market context (NIFTY50 index trend)
        snap.market_trend = self.index_trend.get("NIFTY50")
        if snap.direction != 0 and snap.market_trend is not None:
            snap.market_aligned = (snap.market_trend == snap.direction) or snap.market_trend == 0

        # ATR for risk engine
        snap.atr5 = ind.atr(c5, period=14)

        # Conviction = signal agreement strength (NOT accuracy / win-rate)
        agree = snap.agreeing
        if snap.direction != 0 and agree >= 4 and snap.mtf_agrees:
            snap.conviction = "HIGH"
        elif snap.direction != 0 and agree >= 4:
            snap.conviction = "MEDIUM"   # 4-5 agree but 15-min disagrees -> demoted
        elif snap.direction != 0 and agree == 3:
            snap.conviction = "MEDIUM" if snap.mtf_agrees else "LOW"
        elif agree >= 1 and snap.direction != 0:
            snap.conviction = "LOW"
        else:
            snap.conviction = "NO SETUP"
        return snap
