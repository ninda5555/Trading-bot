"""TradingView embed widgets — genuinely live charts, streamed by TradingView
directly into the user's browser. No account, no API key, no polling by us.

Important architectural note: these iframes update tick-by-tick on their own.
The rest of the dashboard refreshes its DATA panels via Streamlit fragments,
but the chart itself is never torn down by those refreshes (it lives outside
the refreshing fragments), so the 'live feel' is real, not a page reload.
"""
from __future__ import annotations

import json

import streamlit.components.v1 as components


def advanced_chart(tv_symbol: str, height: int = 520, interval: str = "5"):
    """Full live candlestick chart with volume, dark theme."""
    cfg = {
        "autosize": True,
        "symbol": tv_symbol,
        "interval": interval,
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "in",
        "withdateranges": True,
        "hide_side_toolbar": True,
        "allow_symbol_change": False,
        "studies": ["STD;VWAP", "Volume@tv-basicstudies"],
        "support_host": "https://www.tradingview.com",
    }
    html = f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%">
      <div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {json.dumps(cfg)}
      </script>
    </div>"""
    components.html(html, height=height)


def ticker_tape(tv_symbols: list[tuple[str, str]], height: int = 46):
    """Scrolling live price tape across the top — 'the waves'.
    tv_symbols: list of (tradingview_symbol, display_title)."""
    cfg = {
        "symbols": [{"proName": s, "title": t} for s, t in tv_symbols],
        "showSymbolLogo": False,
        "colorTheme": "dark",
        "isTransparent": True,
        "displayMode": "adaptive",
        "locale": "in",
    }
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
      {json.dumps(cfg)}
      </script>
    </div>"""
    components.html(html, height=height)


def mini_symbol(tv_symbol: str, height: int = 200):
    """Compact live area chart for index context panels."""
    cfg = {
        "symbol": tv_symbol,
        "width": "100%",
        "height": height,
        "locale": "in",
        "dateRange": "1D",
        "colorTheme": "dark",
        "isTransparent": True,
        "autosize": True,
        "chartOnly": True,
    }
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
      {json.dumps(cfg)}
      </script>
    </div>"""
    components.html(html, height=height)
