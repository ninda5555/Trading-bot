"""Beginner guidance layer — turns a SignalSnapshot into mentor-style,
plain-English 'what should I do right now?' text, always paired with the
reasoning and a stop-loss idea. Never a bare BUY/SELL.
"""
from __future__ import annotations

from typing import Optional

from .risk import RiskPlan, build_risk_plan
from .signals import SignalSnapshot

GLOSSARY = {
    "VWAP": "Volume-Weighted Average Price — the average price paid today, weighted by volume. "
            "Think of it as the day's 'fair price'. Above VWAP = buyers winning; below = sellers winning.",
    "ORB": "Opening Range Breakout — the high/low of the first 15 minutes (9:15–9:30). "
           "Price escaping that range with volume often sets the day's direction.",
    "RSI": "Relative Strength Index (0–100) — a momentum speedometer. Above 60 = strong buying "
           "momentum, below 40 = strong selling momentum, 40–60 = nothing decisive.",
    "MACD": "Moving Average Convergence Divergence — compares a fast and slow average of price. "
            "Positive & rising = short-term trend up; negative & falling = down.",
    "Stop-loss": "A pre-decided exit price that caps your loss if the trade goes against you. "
                 "Deciding it BEFORE entering is what separates trading from gambling.",
    "ATR": "Average True Range — how far the stock typically moves per candle. Stops placed "
           "less than ~1.5 ATR away get hit by normal noise.",
    "Conviction": "How many of the 5 signals agree in one direction, confirmed by the 15-minute "
                  "trend. It measures signal AGREEMENT, not probability of profit.",
    "Position size": "How many shares to trade so that if your stop-loss is hit, you lose only "
                     "a fixed small % (1–2%) of your capital.",
}


def _direction_word(d: int) -> str:
    return "bullish (upward)" if d > 0 else "bearish (downward)" if d < 0 else "neutral"


def build_guidance(snap: SignalSnapshot, capital: float = 100000.0,
                   risk_pct: float = 1.0) -> dict:
    """Returns {'headline', 'action', 'reasoning': [..], 'risk_plan', 'caveats': [..]}"""
    reasoning = [f"{'🟢' if v.vote > 0 else '🔴' if v.vote < 0 else '⚪'} {v.name}: {v.detail}"
                 for v in snap.votes]
    caveats = []
    risk_plan: Optional[RiskPlan] = None

    if snap.warming_up:
        caveats.append("Signals are still warming up — some indicators need ~20 closed "
                       "5-minute candles (about 100 minutes into the session) to be reliable.")

    mtf_txt = ("15-min trend agrees — the bigger picture supports this."
               if snap.mtf_agrees else
               "15-min trend does NOT confirm — this could be short-term noise."
               if snap.direction != 0 else "")
    market_txt = ""
    if snap.market_aligned is True:
        market_txt = "Aligned with the overall market (NIFTY50 index is moving the same way)."
    elif snap.market_aligned is False:
        market_txt = ("AGAINST the market trend — the index is moving the other way. "
                      "Counter-trend trades fail more often; extra caution warranted.")

    agree_txt = f"{snap.agreeing}/5 signals agree"

    if snap.conviction == "HIGH":
        side = "long (buy)" if snap.direction > 0 else "short (sell)"
        headline = f"{'📈' if snap.direction > 0 else '📉'} HIGH conviction {_direction_word(snap.direction)} setup"
        action = (f"{agree_txt} in the {_direction_word(snap.direction)} direction and the 15-minute "
                  f"trend confirms. {market_txt} If you were considering a {side} position, this is "
                  f"the kind of alignment intraday traders look for. The risk panel below shows a "
                  f"common way to size it and where a stop-loss could go. Never enter without "
                  f"deciding your exit first.")
    elif snap.conviction == "MEDIUM":
        headline = f"🟡 MEDIUM conviction — {_direction_word(snap.direction)} lean, not confirmed"
        action = (f"{agree_txt} {_direction_word(snap.direction)}, but confirmation is incomplete. "
                  f"{mtf_txt} {market_txt} A patient approach: wait for the next 5-minute candle to "
                  f"close and see if a 4th signal joins, rather than jumping in early. "
                  f"Half-confirmed setups are where beginners lose money.")
    elif snap.conviction == "LOW":
        headline = "⚪ LOW conviction — weak lean, no real setup"
        action = (f"Only {agree_txt}. {mtf_txt} This is noise territory. The professional move is "
                  f"to do nothing and wait. Not trading IS a position — cash never hits a stop-loss.")
    else:
        headline = "⚪ NO SETUP — signals are mixed"
        action = ("The signals disagree with each other right now. No edge, no trade. "
                  "Watch and wait for alignment; it usually comes once or twice a day.")

    if snap.direction != 0 and snap.atr5 and snap.conviction in ("HIGH", "MEDIUM"):
        structure = snap.orb_low if snap.direction > 0 else snap.orb_high
        risk_plan = build_risk_plan(entry=snap.price, atr=snap.atr5,
                                    direction=snap.direction, capital=capital,
                                    risk_pct=risk_pct, structure_level=structure)
        if risk_plan.suggested_qty == 0:
            caveats.append("Suggested quantity is 0 — the stop distance is too wide for your "
                           "capital at this risk %. Skipping is the disciplined answer.")
    if snap.market_aligned is False:
        caveats.append("Setup is against the index trend — many intraday traders skip these entirely.")
    if snap.conviction in ("HIGH", "MEDIUM") and snap.mtf_agrees is False:
        caveats.append("The 15-minute chart disagrees with the 5-minute signal.")

    return {"headline": headline, "action": action, "reasoning": reasoning,
            "mtf": mtf_txt, "market": market_txt, "risk_plan": risk_plan,
            "caveats": caveats}
