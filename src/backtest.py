"""Walk-forward backtest of the conviction system on intraday 1-min data.

Honesty rules baked in:
  * WALK-FORWARD: parameters may only be tuned on the TRAIN window; results
    are reported ONLY from the untouched TEST window that follows it. The
    window then rolls forward and the process repeats. You never see a number
    that came from data the parameters were fitted on.
  * Trades pay costs (brokerage-ish + slippage, configurable).
  * Metrics are PAST performance on the data provided. They do not predict
    the future, and simulated fills are cleaner than real ones.

Trade simulation per HIGH-conviction signal:
  enter at next 1-min open after the signal candle closes,
  exit on stop-loss hit, target hit, or 15:15 square-off (whichever first).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Optional

import numpy as np

from .candles import Candle, IST
from .risk import atr_stop
from .signals import SignalEngine, SignalSnapshot


@dataclass
class BTParams:
    rsi_bull: float = 60.0
    rsi_bear: float = 40.0
    vol_multiplier: float = 2.0
    atr_stop_mult: float = 1.5
    reward_multiple: float = 2.0
    min_agreeing: int = 4          # HIGH conviction threshold
    cost_pct_per_side: float = 0.03  # brokerage+taxes+slippage per side, of notional


@dataclass
class BTTrade:
    symbol: str
    day: str
    entry_ts: datetime
    direction: int
    entry: float
    stop: float
    target: float
    exit_ts: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    pnl_pct: float = 0.0           # signed % return on the position, after costs


@dataclass
class BTReport:
    trades: list[BTTrade] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.trades)

    def metrics(self) -> dict:
        if not self.trades:
            return {"trades": 0}
        rets = np.array([t.pnl_pct for t in self.trades])
        wins, losses = rets[rets > 0], rets[rets <= 0]
        win_rate = len(wins) / len(rets) * 100
        avg_win = wins.mean() if len(wins) else 0.0
        avg_loss = losses.mean() if len(losses) else 0.0
        expectancy = rets.mean()
        equity = np.cumprod(1 + rets / 100)
        peak = np.maximum.accumulate(equity)
        max_dd = ((equity - peak) / peak).min() * 100
        return {"trades": int(len(rets)),
                "win_rate_pct": round(float(win_rate), 1),
                "avg_win_pct": round(float(avg_win), 3),
                "avg_loss_pct": round(float(avg_loss), 3),
                "expectancy_pct_per_trade": round(float(expectancy), 3),
                "max_drawdown_pct": round(float(max_dd), 2),
                "total_return_pct": round(float((equity[-1] - 1) * 100), 2)}


def _simulate_day(symbol: str, candles: list[Candle], params: BTParams) -> list[BTTrade]:
    """Feed one day through a fresh engine; trade its HIGH-conviction snapshots."""
    trades: list[BTTrade] = []
    open_trade: Optional[BTTrade] = None
    fired: list[SignalSnapshot] = []

    engine = SignalEngine([symbol])
    engine.index_trend["NIFTY50"] = 0  # per-symbol test: market filter neutral
    engine.on_snapshot = lambda s: fired.append(s)

    day_str = candles[0].ts.strftime("%Y-%m-%d") if candles else "?"
    idx_by_ts = {c.ts: i for i, c in enumerate(candles)}

    for c in candles:
        # manage any open trade against this candle first
        if open_trade and open_trade.exit_ts is None:
            t = open_trade
            hit_stop = c.low <= t.stop if t.direction > 0 else c.high >= t.stop
            hit_tgt = c.high >= t.target if t.direction > 0 else c.low <= t.target
            squareoff = c.ts.astimezone(IST).time() >= dtime(15, 15)
            if hit_stop:   # conservative: assume stop fills before target in same bar
                t.exit_ts, t.exit_price, t.exit_reason = c.ts, t.stop, "stop"
            elif hit_tgt:
                t.exit_ts, t.exit_price, t.exit_reason = c.ts, t.target, "target"
            elif squareoff:
                t.exit_ts, t.exit_price, t.exit_reason = c.ts, c.close, "squareoff"
            if t.exit_ts is not None:
                gross = (t.exit_price - t.entry) / t.entry * 100 * t.direction
                t.pnl_pct = gross - 2 * params.cost_pct_per_side
                trades.append(t)
                open_trade = None

        engine.feed_candle_1m(symbol, c)

        # act on new HIGH-conviction snapshots (one open trade at a time)
        while fired:
            snap = fired.pop(0)
            if open_trade or snap.conviction != "HIGH" or snap.atr5 is None:
                continue
            if snap.agreeing < params.min_agreeing:
                continue
            if c.ts.astimezone(IST).time() >= dtime(14, 45):
                continue  # too late in the day to start a new trade
            i = idx_by_ts.get(c.ts)
            if i is None or i + 1 >= len(candles):
                continue
            entry_candle = candles[i + 1]
            entry = entry_candle.open
            structure = snap.orb_low if snap.direction > 0 else snap.orb_high
            stop = atr_stop(entry, snap.atr5, snap.direction,
                            multiplier=params.atr_stop_mult,
                            structure_level=structure)
            per_share = abs(entry - stop)
            if per_share <= 0:
                continue
            target = round(entry + snap.direction * params.reward_multiple * per_share, 2)
            open_trade = BTTrade(symbol=symbol, day=day_str, entry_ts=entry_candle.ts,
                                 direction=snap.direction, entry=entry,
                                 stop=stop, target=target)

    if open_trade and open_trade.exit_ts is None:  # force close at last bar
        t, c = open_trade, candles[-1]
        t.exit_ts, t.exit_price, t.exit_reason = c.ts, c.close, "eod"
        gross = (t.exit_price - t.entry) / t.entry * 100 * t.direction
        t.pnl_pct = gross - 2 * params.cost_pct_per_side
        trades.append(t)
    return trades


def run_backtest(days: dict[str, dict[str, list[Candle]]],
                 params: Optional[BTParams] = None) -> BTReport:
    """days: {'2026-06-01': {'RELIANCE': [candles...], ...}, ...}"""
    params = params or BTParams()
    report = BTReport()
    for day in sorted(days):
        for symbol, candles in days[day].items():
            if symbol in ("NIFTY50", "BANKNIFTY") or not candles:
                continue
            report.trades.extend(_simulate_day(symbol, candles, params))
    return report


def walk_forward(days: dict[str, dict[str, list[Candle]]],
                 train_days: int = 10, test_days: int = 5,
                 param_grid: Optional[list[BTParams]] = None) -> dict:
    """Roll a train/test window across the days. Tune on train (pick the grid
    row with best train expectancy), evaluate on the FOLLOWING unseen test
    window only. Returns combined out-of-sample report + per-fold detail."""
    param_grid = param_grid or [
        BTParams(atr_stop_mult=1.5, reward_multiple=2.0),
        BTParams(atr_stop_mult=2.0, reward_multiple=2.0),
        BTParams(atr_stop_mult=1.5, reward_multiple=1.5),
    ]
    ordered = sorted(days)
    folds = []
    oos = BTReport()
    i = 0
    while i + train_days + test_days <= len(ordered):
        train_keys = ordered[i:i + train_days]
        test_keys = ordered[i + train_days:i + train_days + test_days]
        train_slice = {d: days[d] for d in train_keys}
        test_slice = {d: days[d] for d in test_keys}

        best, best_exp = None, -np.inf
        for p in param_grid:
            m = run_backtest(train_slice, p).metrics()
            exp = m.get("expectancy_pct_per_trade", -np.inf) if m.get("trades", 0) >= 3 else -np.inf
            if exp > best_exp:
                best, best_exp = p, exp
        best = best or param_grid[0]

        test_report = run_backtest(test_slice, best)
        oos.trades.extend(test_report.trades)
        folds.append({"train": (train_keys[0], train_keys[-1]),
                      "test": (test_keys[0], test_keys[-1]),
                      "chosen_params": {"atr_stop_mult": best.atr_stop_mult,
                                        "reward_multiple": best.reward_multiple},
                      "test_metrics": test_report.metrics()})
        i += test_days

    return {"out_of_sample": oos.metrics(), "folds": folds,
            "note": ("All reported metrics are OUT-OF-SAMPLE (walk-forward): "
                     "parameters were chosen on earlier data and evaluated on "
                     "later, unseen data. PAST performance only — not a "
                     "prediction. Simulated fills are cleaner than real ones.")}
