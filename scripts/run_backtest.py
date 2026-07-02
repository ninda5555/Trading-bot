#!/usr/bin/env python3
"""Run the walk-forward backtest on whatever history exists in data/history/.

    python scripts/run_backtest.py
    python scripts/run_backtest.py --simulated 30   # 30 simulated days (engine demo)

If no downloaded history is found it refuses to invent results unless you
explicitly pass --simulated N, and then labels everything as simulated.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import pytz  # noqa: E402

from src.backtest import walk_forward  # noqa: E402
from src.candles import Candle  # noqa: E402
from src.config import load_config  # noqa: E402
from src.replay import HISTORY_DIR, build_session  # noqa: E402

IST = pytz.timezone("Asia/Kolkata")


def load_history_days() -> dict:
    """Group downloaded CSVs (data/history/SYMBOL_1m.csv or _5m.csv) by day."""
    days: dict = defaultdict(dict)
    for path in sorted(HISTORY_DIR.glob("*_1m.csv")) + sorted(HISTORY_DIR.glob("*_5m.csv")):
        symbol = path.stem.rsplit("_", 1)[0]
        df = pd.read_csv(path, parse_dates=["ts"])
        for day, g in df.groupby(df["ts"].dt.strftime("%Y-%m-%d")):
            candles = [Candle(ts=row.ts.to_pydatetime(), open=row.open, high=row.high,
                              low=row.low, close=row.close, volume=row.volume,
                              closed=True)
                       for row in g.itertuples()]
            days[day][symbol] = candles
    return dict(days)


def simulated_days(n_days: int, symbols: list[str]) -> dict:
    days = {}
    for i in range(n_days):
        session, _ = build_session(symbols, seed=1000 + i)
        day_key = f"sim-day-{i + 1:03d}"
        days[day_key] = session
    return days


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulated", type=int, default=0,
                    help="use N simulated days instead of downloaded history")
    ap.add_argument("--train", type=int, default=10)
    ap.add_argument("--test", type=int, default=5)
    args = ap.parse_args()

    cfg = load_config()
    if args.simulated:
        print(f"⚠️  SIMULATED DATA MODE: {args.simulated} generated days. "
              "This validates the ENGINE, not the strategy. Real conclusions "
              "need real history (scripts/fetch_history.py).\n")
        days = simulated_days(args.simulated, list(cfg["watchlist"])[:4])
    else:
        days = load_history_days()
        if not days:
            print("No history in data/history/. Either run "
                  "scripts/fetch_history.py first, or pass --simulated 30.")
            sys.exit(1)
        print(f"Loaded {len(days)} days of recorded history.\n")

    result = walk_forward(days, train_days=args.train, test_days=args.test)
    print("=== WALK-FORWARD RESULT (out-of-sample only) ===")
    print(json.dumps(result["out_of_sample"], indent=2))
    print(f"\nFolds: {len(result['folds'])}")
    for f in result["folds"]:
        print(f"  train {f['train'][0]}..{f['train'][1]} -> test {f['test'][0]}..{f['test'][1]}: "
              f"{f['test_metrics'].get('trades', 0)} trades, "
              f"expectancy {f['test_metrics'].get('expectancy_pct_per_trade', 'n/a')}%/trade")
    print(f"\n{result['note']}")
