#!/usr/bin/env python3
"""Download intraday history for backtesting into data/history/.

    python scripts/fetch_history.py                # watchlist, last 55 days of 5m
    python scripts/fetch_history.py --interval 1m  # 1-min bars (Yahoo: ~7 days max)

Sources, honestly ranked:
  * Fyers history API (if you've authenticated today): 1-min bars, ~100 days,
    the good stuff. Used automatically when a token is available.
  * yfinance fallback: 1m limited to ~7 days, 5m to ~60 days, and it's an
    unofficial API that occasionally breaks. Fine to start learning with.
"""
import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import pytz  # noqa: E402

from src.config import load_config  # noqa: E402
from src.universe import to_fyers, to_yahoo  # noqa: E402
from src.replay import HISTORY_DIR  # noqa: E402

IST = pytz.timezone("Asia/Kolkata")


def save(symbol: str, df: pd.DataFrame, interval: str):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    out = HISTORY_DIR / f"{symbol}_{interval}.csv"
    df.to_csv(out, index=False)
    print(f"  saved {len(df):>6} rows -> {out}")


def fetch_fyers(symbol: str, days: int, interval: str) -> pd.DataFrame | None:
    try:
        from src.auth import get_fyers_client
        client = get_fyers_client()
    except Exception:
        return None
    res_map = {"1m": "1", "5m": "5", "15m": "15"}
    frames = []
    end = datetime.now(IST)
    # Fyers limits ~100 days per request for minute data; chunk by 90
    start = end - timedelta(days=days)
    data = client.history({
        "symbol": to_fyers(symbol), "resolution": res_map[interval],
        "date_format": "1", "range_from": start.strftime("%Y-%m-%d"),
        "range_to": end.strftime("%Y-%m-%d"), "cont_flag": "1"})
    if not data or data.get("s") != "ok":
        return None
    df = pd.DataFrame(data["candles"], columns=["epoch", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert(IST)
    return df[["ts", "open", "high", "low", "close", "volume"]]


def fetch_yahoo(symbol: str, days: int, interval: str) -> pd.DataFrame | None:
    import yfinance as yf
    period = f"{min(days, 7 if interval == '1m' else 55)}d"
    df = yf.download(to_yahoo(symbol), period=period, interval=interval,
                     progress=False, auto_adjust=False)
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] for c in df.columns]
    df = df.reset_index().rename(columns={
        "Datetime": "ts", "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume"})
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert(IST)
    return df[["ts", "open", "high", "low", "close", "volume"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="5m", choices=["1m", "5m", "15m"])
    ap.add_argument("--days", type=int, default=55)
    ap.add_argument("--symbols", nargs="*", default=None)
    args = ap.parse_args()

    cfg = load_config()
    symbols = args.symbols or list(cfg["watchlist"]) + ["NIFTY50", "BANKNIFTY"]
    for sym in symbols:
        print(f"{sym}:")
        df = fetch_fyers(sym, args.days, args.interval)
        source = "fyers"
        if df is None:
            df = fetch_yahoo(sym, args.days, args.interval)
            source = "yahoo"
        if df is None or df.empty:
            print("  ❌ no data from any source")
            continue
        print(f"  source={source}")
        save(sym, df, args.interval)
        time.sleep(0.5)  # be polite to the API
