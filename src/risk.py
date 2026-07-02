"""Risk engine: position sizing, ATR stop-loss ideas, daily loss limit.

Everything here is an educational suggestion based on common risk-management
practice (fixed-fractional sizing, ATR stops). It is NOT financial advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DISCLAIMER = ("Educational suggestions based on common risk practices "
              "(1-2% fixed-fractional sizing, ATR-based stops). "
              "Not financial advice. Markets can and do gap through stop-losses.")


@dataclass
class RiskPlan:
    entry: float
    stop_loss: float
    target: float
    risk_per_share: float
    suggested_qty: int
    capital_at_risk: float
    capital_at_risk_pct: float
    notes: str


def atr_stop(entry: float, atr: float, direction: int, multiplier: float = 1.5,
             structure_level: Optional[float] = None) -> float:
    """Stop = entry -/+ 1.5*ATR, but never tighter than the structure level
    (e.g. opening-range low for a long) when one exists."""
    raw = entry - direction * multiplier * atr
    if structure_level is not None:
        pad = 0.1 * atr  # small buffer past the level so a retest doesn't stop you out
        if direction > 0:
            raw = min(raw, structure_level - pad)
        else:
            raw = max(raw, structure_level + pad)
    return round(raw, 2)


def position_size(capital: float, risk_pct: float, entry: float,
                  stop_loss: float) -> tuple[int, float]:
    """Fixed-fractional sizing: risk at most risk_pct% of capital on the trade.
    qty = (capital * risk%) / (per-share risk)."""
    per_share = abs(entry - stop_loss)
    if per_share <= 0:
        return 0, 0.0
    rupees_at_risk = capital * risk_pct / 100.0
    qty = int(rupees_at_risk // per_share)
    # can't buy more than capital allows (cash/delivery basis; ignores leverage)
    max_affordable = int(capital // entry) if entry > 0 else 0
    qty = min(qty, max_affordable)
    return max(qty, 0), per_share


def build_risk_plan(entry: float, atr: float, direction: int, capital: float,
                    risk_pct: float, structure_level: Optional[float] = None,
                    reward_multiple: float = 2.0) -> RiskPlan:
    stop = atr_stop(entry, atr, direction, structure_level=structure_level)
    per_share = abs(entry - stop)
    qty, _ = position_size(capital, risk_pct, entry, stop)
    target = round(entry + direction * reward_multiple * per_share, 2)
    at_risk = qty * per_share
    notes = (f"Stop is 1.5x ATR (₹{atr:.2f}) away"
             + (f", snapped beyond the structure level ₹{structure_level:,.2f}"
                if structure_level is not None else "")
             + f". Target shown at {reward_multiple:g}:1 reward-to-risk.")
    return RiskPlan(entry=round(entry, 2), stop_loss=stop, target=target,
                    risk_per_share=round(per_share, 2), suggested_qty=qty,
                    capital_at_risk=round(at_risk, 2),
                    capital_at_risk_pct=round(at_risk / capital * 100, 2) if capital else 0.0,
                    notes=notes)


@dataclass
class DayRiskTracker:
    """Tracks hypothetical running P&L for the day against the loss limit."""
    capital: float
    daily_loss_limit_pct: float = 3.0
    realized_pnl: float = 0.0

    def record(self, pnl: float):
        self.realized_pnl += pnl

    @property
    def limit_rupees(self) -> float:
        return self.capital * self.daily_loss_limit_pct / 100.0

    @property
    def breached(self) -> bool:
        return self.realized_pnl <= -self.limit_rupees

    @property
    def warning(self) -> Optional[str]:
        if self.breached:
            return (f"DAILY LOSS LIMIT HIT: hypothetical losses ₹{-self.realized_pnl:,.0f} "
                    f"have reached {self.daily_loss_limit_pct:g}% of capital. Common practice: "
                    "STOP trading for the day. Tomorrow is another session.")
        if self.realized_pnl <= -0.75 * self.limit_rupees:
            return (f"Caution: hypothetical losses ₹{-self.realized_pnl:,.0f} are at 75% of "
                    f"your {self.daily_loss_limit_pct:g}% daily loss limit. Consider slowing down.")
        return None
