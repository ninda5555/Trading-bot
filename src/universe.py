"""NIFTY50 universe + symbol mappings across data providers.

One stock, three names:
  NSE symbol    -> RELIANCE
  Fyers symbol  -> NSE:RELIANCE-EQ        (WebSocket/API)
  Yahoo symbol  -> RELIANCE.NS            (yfinance, free/delayed)
  TradingView   -> NSE:RELIANCE           (live chart widget)
"""
from __future__ import annotations

# NIFTY50 constituents (as of mid-2026; index membership changes ~2x/year —
# update this list when NSE rebalances).
NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]

# Index instruments
INDICES = {
    "NIFTY50": {"fyers": "NSE:NIFTY50-INDEX", "yahoo": "^NSEI", "tv": "NSE:NIFTY"},
    "BANKNIFTY": {"fyers": "NSE:NIFTYBANK-INDEX", "yahoo": "^NSEBANK", "tv": "NSE:BANKNIFTY"},
}


def to_fyers(nse_symbol: str) -> str:
    if nse_symbol in INDICES:
        return INDICES[nse_symbol]["fyers"]
    return f"NSE:{nse_symbol}-EQ"


def to_yahoo(nse_symbol: str) -> str:
    if nse_symbol in INDICES:
        return INDICES[nse_symbol]["yahoo"]
    # Yahoo uses '-' stripped tickers for a few names (M&M -> M%26M won't work; it's M&M.NS quirk)
    return f"{nse_symbol.replace('&', '%26')}.NS" if "&" in nse_symbol else f"{nse_symbol}.NS"


def to_tradingview(nse_symbol: str) -> str:
    if nse_symbol in INDICES:
        return INDICES[nse_symbol]["tv"]
    return f"NSE:{nse_symbol.replace('&', '_').replace('-', '_')}"


def from_fyers(fyers_symbol: str) -> str:
    """NSE:RELIANCE-EQ -> RELIANCE ; NSE:NIFTY50-INDEX -> NIFTY50"""
    for name, m in INDICES.items():
        if m["fyers"] == fyers_symbol:
            return name
    return fyers_symbol.split(":", 1)[-1].replace("-EQ", "")
