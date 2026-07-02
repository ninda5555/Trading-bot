"""NSE Intraday Trading Assistant — Streamlit dashboard.

Run:  streamlit run dashboard/app.py

Architecture in one breath: a background feed (Fyers live / yfinance delayed /
replay) pushes ticks into the SignalEngine, which recomputes signals on every
candle close. The dashboard reads the engine's latest snapshots inside
`st.fragment(run_every=...)` blocks — so data panels refresh every few seconds
while the TradingView chart (its own live iframe) is never reloaded.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from src.candles import IST, is_market_open
from src.config import load_config, has_fyers_credentials
from src.feeds import DelayedYahooFeed, LiveFyersFeed, ReplayFeed
from src.guidance import GLOSSARY, build_guidance
from src.journal import TradeJournal
from src.replay import build_session
from src.signals import SignalEngine
from src.universe import to_tradingview, INDICES

from dashboard.style import CSS, badge
from dashboard import tv_widget

st.set_page_config(page_title="NSE Intraday Assistant", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)

DISCLAIMER = ("⚠️ Educational decision-support tool. Signals measure indicator "
              "agreement, not probability of profit. Position sizes and stops are "
              "common-practice illustrations, not financial advice. Intraday "
              "trading carries real risk of loss — most retail intraday traders "
              "lose money (SEBI's own studies). Never trade money you can't afford to lose.")


# ----------------------------------------------------------------------------
# Engine + feed boot (singleton across reruns)
# ----------------------------------------------------------------------------
@st.cache_resource
def boot(mode: str, _token_ok: bool = False):
    # _token_ok is part of the cache key: connecting to Fyers mid-session
    # rebuilds the feed with the fresh token.
    cfg = load_config()
    watch = list(cfg["watchlist"])
    engine = SignalEngine(watch)
    journal = TradeJournal()
    info = {"mode": mode, "regimes": {}, "source_label": ""}

    def maybe_log(snap):
        if snap.conviction == "HIGH" and not journal.already_logged_recently(
                snap.symbol, snap.direction, within_minutes=30):
            stop = tgt = None
            if snap.atr5:
                from src.risk import build_risk_plan
                plan = build_risk_plan(snap.price, snap.atr5, snap.direction,
                                       cfg["risk"]["capital"],
                                       cfg["risk"]["risk_per_trade_pct"],
                                       snap.orb_low if snap.direction > 0 else snap.orb_high)
                stop, tgt = plan.stop_loss, plan.target
            journal.log_signal(snap, stop, tgt,
                               source="replay-sim" if mode == "replay" else mode)
    engine.on_snapshot = maybe_log

    if mode == "live":
        from src.auth import load_cached_token
        token = load_cached_token()
        if token:
            feed = LiveFyersFeed(engine, token, cfg["fyers"]["app_id"])
            feed.start()
            info["source_label"] = "LIVE · Fyers WebSocket (real-time ticks)"
        else:
            info["source_label"] = "⛔ No Fyers token for today — run scripts/daily_auth.py, then restart"
            feed = None
    elif mode == "delayed":
        feed = DelayedYahooFeed(engine)
        feed.start()
        info["source_label"] = "DELAYED · free Yahoo Finance candles (~1-2 min behind; unofficial source)"
    else:
        session, regimes = build_session(list(cfg["watchlist"]))
        info["regimes"] = regimes
        n_backfill = 255  # instantly play ~9:15->13:30, then stream the rest live-style
        backfill = {s: c[:n_backfill] for s, c in session.items()}
        stream = {s: c[n_backfill:] for s, c in session.items()}
        ReplayFeed(engine, backfill, speed=0).start()
        feed = ReplayFeed(engine, stream, speed=240)
        feed.start()
        recorded = [s for s, r in regimes.items() if r == "recorded"]
        info["source_label"] = ("REPLAY · recorded data" if recorded else
                                "REPLAY · SIMULATED practice session (not real market data)")
    return engine, feed, journal, cfg, info


def price_at(engine: SignalEngine, symbol: str, ts: datetime):
    agg = engine.aggregators.get(symbol)
    if not agg:
        return None
    for c in agg.s1.candles:
        if c.ts >= ts:
            return c.close
    return None


def trend_chip(label: str, trend) -> str:
    if trend is None:
        word, cls = "warming up", "trend-flat"
    elif trend > 0:
        word, cls = "▲ UPTREND", "trend-up"
    elif trend < 0:
        word, cls = "▼ DOWNTREND", "trend-down"
    else:
        word, cls = "→ SIDEWAYS", "trend-flat"
    return f'<span class="ctx-chip">{label}: <span class="{cls}">{word}</span></span>'


# ----------------------------------------------------------------------------
# Sidebar — mode + risk settings
# ----------------------------------------------------------------------------
cfg_initial = load_config()
with st.sidebar:
    st.markdown("### 🔑 Fyers connection")
    from src.auth import (FyersAuthError, exchange_code_for_token,
                          extract_auth_code, get_login_url, load_cached_token)
    from src.config import save_credentials

    if not has_fyers_credentials(cfg_initial):
        st.caption("Optional — only needed for LIVE real-time data. "
                   "Replay & delayed modes work without it.")
        with st.expander("First-time setup: enter your Fyers app keys"):
            in_app = st.text_input("App ID (looks like AB12345-100)")
            in_sec = st.text_input("Secret key", type="password")
            if st.button("💾 Save keys on this computer"):
                if in_app.strip() and in_sec.strip():
                    save_credentials(in_app.strip(), in_sec.strip())
                    st.success("Saved locally (config.yaml — never uploaded anywhere).")
                    st.rerun()
                else:
                    st.error("Please fill in both boxes first.")
        token_ok = False
    else:
        token_ok = load_cached_token() is not None
        if token_ok:
            st.success("🟢 Connected to Fyers for today's session")
        else:
            st.warning("🔴 Not logged in today (Fyers requires a fresh "
                       "login every trading day — that's a SEBI rule)")
            try:
                st.link_button("Step 1 · Open Fyers login page",
                               get_login_url(cfg_initial), use_container_width=True)
            except Exception as e:
                st.error(f"Could not build login link: {e}")
            st.caption("After logging in, the browser shows a page that looks "
                       "broken (https://127.0.0.1/...). That's normal! Copy the "
                       "WHOLE address from the address bar and paste it below.")
            pasted = st.text_input("Step 2 · Paste that address here")
            if st.button("Step 3 · Connect ✅", use_container_width=True):
                try:
                    exchange_code_for_token(extract_auth_code(pasted), cfg_initial)
                    st.success("Connected! Now pick 'live' under Data feed below.")
                    st.rerun()
                except FyersAuthError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Login failed: {e}. Try the login link again — "
                             "each code works only once and expires fast.")

    st.markdown("### ⚙️ Settings")
    mode_options = ["replay", "delayed", "live"]
    mode_help = ("replay = practice session (works anytime) · delayed = free "
                 "Yahoo data (~1-2 min lag) · live = Fyers WebSocket real-time")
    default_mode = cfg_initial["feed"].get("mode", "replay")
    if default_mode == "live" and not has_fyers_credentials(cfg_initial):
        default_mode = "replay"
    mode = st.radio("Data feed", mode_options,
                    index=mode_options.index(default_mode), help=mode_help)
    if mode == "live" and not token_ok:
        st.error("Live mode needs today's Fyers login — use the steps above. "
                 "Falling back to replay until then.")
        mode = "replay"
    st.markdown("### 💰 Your risk settings")
    capital = st.number_input("Trading capital (₹)", min_value=1000,
                              value=int(cfg_initial["risk"]["capital"]), step=10000,
                              help=GLOSSARY["Position size"])
    risk_pct = st.slider("Risk per trade (%)", 0.5, 2.0,
                         float(cfg_initial["risk"]["risk_per_trade_pct"]), 0.25,
                         help="Common practice: risk only 1-2% of capital on any single trade.")
    st.caption(DISCLAIMER)

engine, feed, journal, cfg, feed_info = boot(mode, token_ok)

# ----------------------------------------------------------------------------
# Header — market status + live index waves
# ----------------------------------------------------------------------------
now_ist = datetime.now(IST)
open_now = is_market_open()

left, right = st.columns([3, 2])
with left:
    st.markdown("## 📈 NSE Intraday Assistant")
    st.caption(f"Feed: **{feed_info['source_label']}**")
with right:
    if open_now:
        st.success(f"🟢 Market OPEN · {now_ist:%H:%M:%S} IST", icon="🕒")
    else:
        st.info(f"🌙 Market CLOSED · {now_ist:%H:%M} IST · opens 9:15 AM IST "
                f"(Mon–Fri). Replay mode lets you practice meanwhile.", icon="🕒")

# Live scrolling tape — TradingView streams this itself (the 'waves')
tape = [(INDICES["NIFTY50"]["tv"], "NIFTY 50"), (INDICES["BANKNIFTY"]["tv"], "BANK NIFTY")]
tape += [(to_tradingview(s), s) for s in cfg["watchlist"][:8]]
tv_widget.ticker_tape(tape)


# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_live, tab_journal, tab_learn = st.tabs(["📊 Live Dashboard", "📓 Trade Journal", "📚 Learn"])

with tab_live:

    @st.fragment(run_every="4s")
    def market_context():
        n50 = engine.index_trend.get("NIFTY50")
        bnf = engine.index_trend.get("BANKNIFTY")
        n50_px = engine.aggregators["NIFTY50"].last_price
        bnf_px = engine.aggregators["BANKNIFTY"].last_price
        chips = trend_chip("NIFTY 50", n50) + trend_chip("BANK NIFTY", bnf)
        px_txt = ""
        if n50_px:
            px_txt += f'<span class="ctx-chip">NIFTY <b>{n50_px:,.1f}</b></span>'
        if bnf_px:
            px_txt += f'<span class="ctx-chip">BANKNIFTY <b>{bnf_px:,.1f}</b></span>'
        st.markdown("##### 🧭 Market context")
        st.markdown(chips + px_txt, unsafe_allow_html=True)
        st.caption("Trend = 20-EMA slope + price position on 5-min candles. Trades "
                   "aligned with the index trend succeed more often than fights against it.")
    market_context()

    col_watch, col_detail = st.columns([1, 2], gap="medium")

    with col_watch:
        st.markdown("##### 👀 Watchlist")
        if "selected" not in st.session_state:
            st.session_state.selected = cfg["watchlist"][0]

        @st.fragment(run_every="4s")
        def watchlist_panel():
            for sym in cfg["watchlist"]:
                snap = engine.snapshots.get(sym) or engine.compute_snapshot(sym)
                agg = engine.aggregators[sym]
                px = agg.last_price
                conviction = snap.conviction if snap else "NO SETUP"
                direction = snap.direction if snap else 0
                c1, c2 = st.columns([1, 1], vertical_alignment="center")
                with c1:
                    if st.button(f"{sym}", key=f"btn_{sym}", use_container_width=True):
                        st.session_state.selected = sym
                        st.rerun()
                with c2:
                    px_txt = f"₹{px:,.1f}" if px else "—"
                    st.markdown(f'<div style="text-align:right;line-height:1.3">'
                                f'<span class="wl-px">{px_txt}</span><br>'
                                f'{badge(conviction, direction)}</div>',
                                unsafe_allow_html=True)
        watchlist_panel()

    with col_detail:
        sym = st.session_state.get("selected", cfg["watchlist"][0])
        st.markdown(f"##### 📉 {sym} — live chart (TradingView, streams on its own)")
        tv_widget.advanced_chart(to_tradingview(sym), height=440)
        if mode == "replay":
            st.caption("⚠️ Note: the chart above is TradingView's REAL market chart. In "
                       "replay mode the signal panels below run on the practice session, "
                       "so chart and signals won't match. In live/delayed mode they align.")

        @st.fragment(run_every="4s")
        def detail_panel():
            snap = engine.snapshots.get(sym) or engine.compute_snapshot(sym)
            if not snap:
                st.info("Waiting for first data for this symbol…")
                return
            g = build_guidance(snap, capital=capital, risk_pct=risk_pct)

            st.markdown(f"""
            <div class="guide-card">
              <div class="guide-headline">{g['headline']}</div>
              <div style="margin-bottom:8px">{badge(snap.conviction, snap.direction)}
                <span style="color:#64748b;font-size:0.8rem"> · signal agreement strength,
                not a win-rate · {snap.ts:%H:%M} IST · ₹{snap.price:,.2f}</span></div>
              <div class="guide-action">{g['action']}</div>
              {''.join(f'<div class="guide-caveat">⚠️ {c}</div>' for c in g['caveats'])}
            </div>""", unsafe_allow_html=True)

            st.markdown("**Why — the 5 signals** "
                        f"(🟢 {snap.bull_count} bullish · 🔴 {snap.bear_count} bearish)")
            for line in g["reasoning"]:
                st.markdown(f'<div class="reason-line">{line}</div>', unsafe_allow_html=True)
            extra = " · ".join(x for x in (g["mtf"], g["market"]) if x)
            if extra:
                st.markdown(f'<div class="reason-line">🧭 {extra}</div>', unsafe_allow_html=True)

            plan = g["risk_plan"]
            if plan:
                st.markdown("**🛡️ Risk plan (common-practice illustration)**")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Entry ~", f"₹{plan.entry:,.2f}")
                m2.metric("Stop-loss", f"₹{plan.stop_loss:,.2f}",
                          help=GLOSSARY["Stop-loss"] + " " + plan.notes)
                m3.metric("Target (2:1)", f"₹{plan.target:,.2f}")
                m4.metric("Qty", f"{plan.suggested_qty}",
                          help=f"Risks ₹{plan.capital_at_risk:,.0f} "
                               f"({plan.capital_at_risk_pct}% of capital) if the stop is hit.")
            journal.resolve_pending(lambda s, t: price_at(engine, s, t))
        detail_panel()

with tab_journal:
    st.markdown("#### 📓 Trade Journal — every HIGH-conviction signal, scored honestly")
    st.caption("Each signal is logged the moment it fires, then scored against what price "
               "actually did 30 and 60 minutes later. 'Favorable' = moved >0.15% in the "
               "signal's direction; 'adverse' = against. This is how we find out together "
               "whether the system earns trust — or doesn't.")

    @st.fragment(run_every="10s")
    def journal_panel():
        perf = journal.performance_summary()
        if perf.get("resolved", 0) > 0:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Resolved signals", perf["resolved"])
            c2.metric("Favorable", f"{perf['favorable']} ({perf['favorable_rate']}%)")
            c3.metric("Adverse", perf["adverse"])
            c4.metric("Flat", perf["flat"])
            c5.metric("Avg signed move @60m", f"{perf['avg_signed_move_60m_pct']}%")
            st.caption("PAST outcomes on this data feed only — not predictive.")
        rows = journal.all_signals(200)
        if rows:
            df = pd.DataFrame(rows)
            df["dir"] = df["direction"].map({1: "▲ LONG", -1: "▼ SHORT"})
            show = df[["ts", "symbol", "dir", "conviction", "price", "stop_loss",
                       "target", "move_30m_pct", "move_60m_pct", "outcome", "source"]]
            st.dataframe(show, use_container_width=True, height=380)
            with st.expander("🔍 Full reasoning for the latest signal"):
                import json as _json
                st.write(f"**{df.iloc[0]['symbol']}** @ {df.iloc[0]['ts']}")
                for line in _json.loads(df.iloc[0]["reasoning"]):
                    st.markdown(f"- {line}")
        else:
            st.info("No HIGH-conviction signals logged yet. They'll appear here "
                    "automatically the moment one fires.")
    journal_panel()

with tab_learn:
    st.markdown("#### 📚 Plain-language glossary")
    st.caption("Every term the dashboard uses, explained like a mentor would.")
    for term, explanation in GLOSSARY.items():
        with st.expander(f"**{term}**"):
            st.write(explanation)
    st.markdown("#### 🧪 Backtesting")
    st.write("Run `python scripts/fetch_history.py` to download real intraday history, "
             "then `python scripts/run_backtest.py` for an honest walk-forward test. "
             "Results are out-of-sample only — the parameters never see the data "
             "they're judged on.")

st.markdown(f'<div class="disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)
