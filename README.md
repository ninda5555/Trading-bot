# 📈 NSE Intraday Trading Assistant

A beginner-friendly, **decision-support** dashboard for intraday trading on
NSE (NIFTY50 stocks). It watches live data, computes classic intraday signals,
and — most importantly — explains **what to do next in plain English**, always
with the reasoning and a risk plan attached.

> ⚠️ **This tool does not place orders and is not financial advice.** It
> measures *signal agreement*, never "accuracy". Most retail intraday traders
> lose money (per SEBI's own studies). Trade only money you can afford to lose.

---

## Quick start (5 minutes, no broker account needed)

```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml       # edit later; defaults work
streamlit run dashboard/app.py
```

Open http://localhost:8501 — you'll be in **Replay mode**: a simulated
practice session streams through the real signal engine so you can learn the
dashboard any time, even at 2 AM. The TradingView chart is always the *real*
live market.

### The three data modes (sidebar)

| Mode | What it is | Needs |
|---|---|---|
| `replay` | Simulated/recorded session played through the engine — practice anytime | nothing |
| `delayed` | Free Yahoo Finance candles, ~1–2 min behind | internet |
| `live` | Real-time ticks via Fyers WebSocket | Fyers API credentials + daily login |

## Going live with Fyers

1. Create an app at https://myapi.fyers.in/dashboard (redirect URL
   `https://127.0.0.1`), put `app_id` + `secret_key` in `config.yaml`.
2. Each trading morning (tokens expire daily — a SEBI requirement, not a bug):
   ```bash
   python scripts/daily_auth.py
   ```
   Log in (2FA), paste the redirected URL, done in ~20 seconds.
3. Set `feed.mode: live` in `config.yaml` (or pick **live** in the sidebar)
   and start the dashboard.

`config.yaml` is gitignored — credentials never leave your machine.

## The signal system

Five signals on 5-minute candles, each voting bullish / bearish / neutral:

1. **VWAP** — price above/below the day's volume-weighted average price
2. **ORB** — breakout above/below the first 15 minutes' range
3. **RSI(9)** — momentum: >60 bullish, <40 bearish
4. **MACD(5,13,1)** — fast trend direction
5. **Volume spike** — >2× the 10-candle average, in the candle's direction

**Conviction = how many agree** (labelled *signal agreement strength*):
- **HIGH** — 4–5 agree **and** the 15-minute trend confirms
- **MEDIUM** — 3–4 agree, or 15-min disagrees
- **LOW / NO SETUP** — ≤2 agree or signals conflict

Every stock also gets flagged **aligned with / against** the live NIFTY50
index trend, and every suggestion ships with an ATR-based stop-loss idea and
a position size that risks only your configured 1–2% of capital.

## Backtesting (honest by construction)

```bash
python scripts/fetch_history.py            # download real intraday history
python scripts/run_backtest.py             # walk-forward test on it
python scripts/run_backtest.py --simulated 30   # engine self-check on fake data
```

Walk-forward means parameters are tuned on a training window and evaluated
only on the *following unseen* days — you never see a metric computed on data
the parameters were fitted to. Costs are simulated. Results are labelled PAST
performance, because that's all they are.

## Trade journal

Every HIGH-conviction signal is auto-logged (timestamp, price, full
reasoning, stop/target), then scored against what price actually did 30/60
minutes later. The **Trade Journal** tab shows the running favorable/adverse
record — that's how you find out, over weeks, whether the system deserves
trust.

## Project layout

```
config.yaml.example   # copy to config.yaml (gitignored) — credentials live there only
requirements.txt
dashboard/app.py      # Streamlit UI (dark, mobile-friendly)
dashboard/tv_widget.py# live TradingView embeds (chart streams in your browser)
src/candles.py        # tick -> 1m/5m/15m aggregation, event-driven
src/indicators.py     # VWAP, ORB, RSI, MACD, ATR, volume-spike math
src/signals.py        # signal engine + conviction scoring + MTF + market context
src/guidance.py       # plain-English "what to do next" + glossary
src/risk.py           # position sizing, ATR stops, daily loss limit
src/feeds.py          # live (Fyers WS) / delayed (Yahoo) / replay feeds
src/auth.py           # Fyers OAuth, daily token refresh, 2FA/TOTP support
src/backtest.py       # walk-forward backtester
src/journal.py        # SQLite journal + outcome scoring
src/replay.py         # session recorder/simulator
scripts/daily_auth.py # morning token ritual
scripts/fetch_history.py
scripts/run_backtest.py
tests/demo_engine.py  # end-to-end engine demo you can run right now
```

## SEBI compliance posture (April 2026 retail algo framework)

This version is decision-support only — **no order placement code exists**.
The auth layer is already shaped for compliant automation later:

- **Mandatory 2FA**: TOTP-based login supported (`totp_secret` in config).
- **Daily re-authentication**: enforced by Fyers token expiry + `daily_auth.py`.
- **Static IP whitelisting**: configured on the Fyers MyAPI dashboard for your
  app; nothing in this codebase needs to change.
- If order placement is ever added, it must go through your broker's
  exchange-registered algo framework with a registered strategy ID.

## Honest limitations

- **Signals are descriptive, not predictive.** Five indicators agreeing means
  the *recent past* is aligned — nothing more.
- **Replay mode's simulated days are random walks with injected trends** —
  good for learning the UI and validating the engine, meaningless for
  judging profitability.
- **yfinance is unofficial** and occasionally breaks or lags; the `delayed`
  mode is for learning, not for split-second entries.
- **Backtest fills are idealized** (no partial fills, queue position, or
  freak-candle slippage beyond the flat cost assumption).
- **Index membership drifts**: update `src/universe.py` when NSE rebalances
  NIFTY50.
