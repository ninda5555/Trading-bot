"""Tick -> candle aggregation, event-driven.

Every live tick (price + cumulative volume) flows in here. We build 1-minute
candles as ticks arrive, and roll finished 1-min candles up into 5-min and
15-min series. Indicators are recomputed the moment a candle updates — no
polling timers anywhere.

Volume note: Fyers ticks carry *cumulative day volume* (vol_traded_today).
Per-candle volume = cumulative at candle end - cumulative at candle start.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import pytz

IST = pytz.timezone("Asia/Kolkata")

MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)


def is_market_open(now: Optional[datetime] = None) -> bool:
    now = now.astimezone(IST) if now else datetime.now(IST)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    open_t = now.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0)
    close_t = now.replace(hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0)
    return open_t <= now <= close_t


@dataclass
class Candle:
    ts: datetime          # candle START time (IST)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0   # per-candle volume (not cumulative)
    closed: bool = False  # True once its time window has fully elapsed

    def update(self, price: float):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price


def floor_ts(ts: datetime, minutes: int) -> datetime:
    return ts.replace(minute=(ts.minute // minutes) * minutes, second=0, microsecond=0)


@dataclass
class CandleSeries:
    """A rolling series of candles for one symbol at one timeframe."""
    timeframe_min: int
    candles: list[Candle] = field(default_factory=list)
    max_len: int = 500

    @property
    def current(self) -> Optional[Candle]:
        return self.candles[-1] if self.candles else None

    def closed_candles(self) -> list[Candle]:
        return [c for c in self.candles if c.closed]

    def on_tick(self, ts: datetime, price: float, candle_volume_so_far: float) -> bool:
        """Feed one tick. Returns True if a candle just CLOSED (signal moment)."""
        bucket = floor_ts(ts, self.timeframe_min)
        cur = self.current
        closed_one = False
        if cur is None or cur.ts != bucket:
            if cur is not None and not cur.closed:
                cur.closed = True
                closed_one = True
            self.candles.append(Candle(bucket, price, price, price, price, candle_volume_so_far))
            if len(self.candles) > self.max_len:
                self.candles = self.candles[-self.max_len:]
        else:
            cur.update(price)
            cur.volume = candle_volume_so_far
        return closed_one

    def on_candle(self, candle: Candle) -> None:
        """Ingest an already-built candle (delayed/replay feeds, or 1m->5m rollup)."""
        bucket = floor_ts(candle.ts, self.timeframe_min)
        cur = self.current
        if cur is None or cur.ts != bucket:
            if cur is not None:
                cur.closed = True
            self.candles.append(Candle(bucket, candle.open, candle.high,
                                       candle.low, candle.close, candle.volume,
                                       closed=candle.closed))
            if len(self.candles) > self.max_len:
                self.candles = self.candles[-self.max_len:]
        else:
            cur.high = max(cur.high, candle.high)
            cur.low = min(cur.low, candle.low)
            cur.close = candle.close
            cur.volume += candle.volume
            if candle.closed and floor_ts(candle.ts + timedelta(minutes=1), self.timeframe_min) != bucket:
                cur.closed = True


class SymbolAggregator:
    """Per-symbol: raw ticks -> 1m -> 5m -> 15m series, with callbacks.

    on_candle_close(symbol, timeframe_min, series) fires the moment any
    candle completes — this is what makes the signal engine event-driven.
    """

    def __init__(self, symbol: str,
                 on_candle_close: Optional[Callable[[str, int, "CandleSeries"], None]] = None,
                 on_tick: Optional[Callable[[str, float], None]] = None):
        self.symbol = symbol
        self.s1 = CandleSeries(1)
        self.s5 = CandleSeries(5)
        self.s15 = CandleSeries(15)
        self.on_candle_close = on_candle_close
        self.on_tick_cb = on_tick
        self.last_price: Optional[float] = None
        self.last_ts: Optional[datetime] = None
        self._day_cum_volume: float = 0.0
        self._vol_at_1m_open: float = 0.0
        self._vol_at_5m_open: float = 0.0
        self._vol_at_15m_open: float = 0.0

    def feed_tick(self, ts: datetime, price: float, cum_volume: float):
        """cum_volume = cumulative traded volume for the day (Fyers convention)."""
        ts = ts.astimezone(IST)
        self.last_price, self.last_ts = price, ts
        if cum_volume < self._day_cum_volume:  # new session started
            self._vol_at_1m_open = self._vol_at_5m_open = self._vol_at_15m_open = cum_volume
        self._day_cum_volume = cum_volume

        for series, attr in ((self.s1, "_vol_at_1m_open"),
                             (self.s5, "_vol_at_5m_open"),
                             (self.s15, "_vol_at_15m_open")):
            bucket = floor_ts(ts, series.timeframe_min)
            cur = series.current
            if cur is None or cur.ts != bucket:
                setattr(self, attr, cum_volume)  # reset volume baseline at candle open
            closed = series.on_tick(ts, price, max(0.0, cum_volume - getattr(self, attr)))
            if closed and self.on_candle_close:
                self.on_candle_close(self.symbol, series.timeframe_min, series)
        if self.on_tick_cb:
            self.on_tick_cb(self.symbol, price)

    def feed_candle_1m(self, candle: Candle):
        """For delayed (yfinance) and replay feeds that deliver whole 1m candles."""
        self.last_price = candle.close
        self.last_ts = candle.ts
        for series in (self.s1, self.s5, self.s15):
            before = len(series.closed_candles())
            series.on_candle(candle)
            if len(series.closed_candles()) > before and self.on_candle_close:
                self.on_candle_close(self.symbol, series.timeframe_min, series)
