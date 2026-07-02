"""Three interchangeable data feeds, all driving the same SignalEngine.

  LiveFyersFeed    — real ticks over Fyers WebSocket (market hours + token)
  DelayedYahooFeed — free yfinance 1-min candles, polled; ~1-2 min behind.
                     Zero broker setup needed. Good enough to learn with.
  ReplayFeed       — plays a recorded or simulated session back through the
                     engine at any speed. Practice mode / demos / testing.

The engine cannot tell them apart: everything arrives as ticks or 1-min
candles. That's the point — the signal logic is tested identically in all modes.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import pytz

from .candles import Candle, IST
from .signals import SignalEngine
from .universe import to_fyers, to_yahoo, from_fyers, INDICES


class BaseFeed:
    def __init__(self, engine: SignalEngine):
        self.engine = engine
        self.running = False

    def start(self):
        raise NotImplementedError

    def stop(self):
        self.running = False


# --------------------------------------------------------------------------
class LiveFyersFeed(BaseFeed):
    """Fyers v3 data WebSocket -> engine.feed_tick. Event-driven end to end."""

    def __init__(self, engine: SignalEngine, access_token: str, app_id: str):
        super().__init__(engine)
        # data socket wants "APPID:TOKEN"
        self._token = f"{app_id}:{access_token}"
        self._ws = None
        self.status = "disconnected"
        self.last_tick_at: Optional[datetime] = None

    def start(self):
        from fyers_apiv3.FyersWebsocket import data_ws
        symbols = [to_fyers(s) for s in
                   list(self.engine.watchlist) + list(self.engine.INDEX_SYMBOLS)]

        def on_message(msg: dict):
            # SymbolUpdate payload: {'symbol': 'NSE:RELIANCE-EQ', 'ltp': ...,
            #  'vol_traded_today': ..., 'last_traded_time': epoch, ...}
            try:
                sym = from_fyers(msg.get("symbol", ""))
                ltp = msg.get("ltp")
                if ltp is None:
                    return
                epoch = msg.get("last_traded_time") or time.time()
                ts = datetime.fromtimestamp(epoch, tz=pytz.utc).astimezone(IST)
                cum_vol = float(msg.get("vol_traded_today") or 0.0)
                self.last_tick_at = datetime.now(IST)
                self.engine.feed_tick(sym, ts, float(ltp), cum_vol)
            except Exception:
                pass  # never let one bad tick kill the socket callback

        def on_open():
            self.status = "connected"
            self._ws.subscribe(symbols=symbols, data_type="SymbolUpdate")
            self._ws.keep_running()

        def on_error(err):
            self.status = f"error: {err}"

        def on_close(msg):
            self.status = "disconnected"

        self._ws = data_ws.FyersDataSocket(
            access_token=self._token, log_path="", litemode=False,
            write_to_file=False, reconnect=True,
            on_connect=on_open, on_close=on_close,
            on_error=on_error, on_message=on_message,
        )
        self.running = True
        self.status = "connecting"
        threading.Thread(target=self._ws.connect, daemon=True).start()


# --------------------------------------------------------------------------
class DelayedYahooFeed(BaseFeed):
    """Polls yfinance for 1-min candles. Honest label: data is delayed and
    yfinance is unofficial — fine for learning, not for split-second entries."""

    POLL_SECONDS = 60

    def __init__(self, engine: SignalEngine):
        super().__init__(engine)
        self._seen: dict[str, datetime] = {}
        self.status = "stopped"
        self._thread: Optional[threading.Thread] = None

    def _poll_once(self):
        import yfinance as yf
        symbols = list(self.engine.watchlist) + list(self.engine.INDEX_SYMBOLS)
        for sym in symbols:
            try:
                df = yf.download(to_yahoo(sym), period="1d", interval="1m",
                                 progress=False, auto_adjust=False)
                if df is None or df.empty:
                    continue
                if hasattr(df.columns, "levels"):  # flatten MultiIndex
                    df.columns = [c[0] for c in df.columns]
                for ts, row in df.iterrows():
                    ts = ts.tz_convert(IST) if ts.tzinfo else IST.localize(ts)
                    if sym in self._seen and ts <= self._seen[sym]:
                        continue
                    self._seen[sym] = ts
                    self.engine.feed_candle_1m(sym, Candle(
                        ts=ts, open=float(row["Open"]), high=float(row["High"]),
                        low=float(row["Low"]), close=float(row["Close"]),
                        volume=float(row.get("Volume", 0.0)), closed=True))
            except Exception as e:
                self.status = f"poll error on {sym}: {e}"

    def start(self):
        self.running = True
        self.status = "polling"

        def loop():
            while self.running:
                self._poll_once()
                time.sleep(self.POLL_SECONDS)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()


# --------------------------------------------------------------------------
class ReplayFeed(BaseFeed):
    """Plays a session (list of per-symbol 1-min candles) through the engine.

    speed=0 -> instant (backfill/testing); speed=60 -> 1 candle per real
    second; speed=1 -> true real-time pace.
    """

    def __init__(self, engine: SignalEngine,
                 session: dict[str, list[Candle]], speed: float = 0):
        super().__init__(engine)
        self.session = session
        self.speed = speed
        self.status = "ready"
        self.progress = 0.0

    def start(self):
        self.running = True
        self.status = "replaying"
        # interleave all symbols' candles in time order, exactly like a live day
        events: list[tuple[datetime, str, Candle]] = []
        for sym, candles in self.session.items():
            events.extend((c.ts, sym, c) for c in candles)
        events.sort(key=lambda e: e[0])

        def run():
            n = len(events)
            for i, (ts, sym, candle) in enumerate(events):
                if not self.running:
                    break
                self.engine.feed_candle_1m(sym, candle)
                self.progress = (i + 1) / n
                if self.speed > 0:
                    time.sleep(60.0 / self.speed / max(len(self.session), 1))
            self.status = "finished"

        if self.speed == 0:
            run()  # synchronous: used by tests and dashboard warm start
        else:
            threading.Thread(target=run, daemon=True).start()
