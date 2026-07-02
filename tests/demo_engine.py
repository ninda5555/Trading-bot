#!/usr/bin/env python3
"""End-to-end engine demo: plays a full simulated NSE session through the
event-driven pipeline (1m candles -> 5m/15m rollup -> signals -> conviction ->
guidance -> risk plan -> journal) and prints what fired.

Run: python tests/demo_engine.py [seed]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.feeds import ReplayFeed
from src.guidance import build_guidance
from src.journal import TradeJournal
from src.replay import build_session
from src.signals import SignalEngine

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
WATCH = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN"]

session, regimes = build_session(WATCH, seed=seed)
print("=== SIMULATED SESSION (practice data, not real market) ===")
for s, r in regimes.items():
    print(f"  {s:<10} regime: {r}")
print()

high_events = []
engine = SignalEngine(WATCH)
journal = TradeJournal(Path(__file__).parent / "demo_journal.db")


def on_snap(snap):
    if snap.conviction in ("HIGH", "MEDIUM") and snap.direction != 0:
        high_events.append(snap)
        if snap.conviction == "HIGH" and not journal.already_logged_recently(
                snap.symbol, snap.direction, within_minutes=30):
            journal.log_signal(snap, source="replay-sim")


engine.on_snapshot = on_snap
ReplayFeed(engine, session, speed=0).start()  # full day, event-driven, instant

print(f"=== {len(high_events)} MEDIUM/HIGH conviction snapshots fired during the day ===\n")
shown = set()
for snap in high_events:
    key = (snap.symbol, snap.direction, snap.conviction)
    if key in shown:
        continue
    shown.add(key)
    g = build_guidance(snap, capital=100000, risk_pct=1.0)
    print(f"--- {snap.symbol} @ {snap.ts:%H:%M} IST · ₹{snap.price:,.2f} "
          f"· {snap.conviction} ({snap.agreeing}/5 agree) ---")
    print(f"  {g['headline']}")
    for line in g["reasoning"]:
        print(f"    {line}")
    if g["mtf"]:
        print(f"    🧭 {g['mtf']}")
    if g["market"]:
        print(f"    🧭 {g['market']}")
    print(f"  WHAT TO DO: {g['action'][:220]}...")
    if g["risk_plan"]:
        p = g["risk_plan"]
        print(f"  RISK PLAN: entry ₹{p.entry:,.2f} | stop ₹{p.stop_loss:,.2f} | "
              f"target ₹{p.target:,.2f} | qty {p.suggested_qty} "
              f"(risks ₹{p.capital_at_risk:,.0f} = {p.capital_at_risk_pct}% of ₹1L)")
    for c in g["caveats"]:
        print(f"  ⚠️  {c}")
    print()

# resolve journal outcomes against the same session (what happened 30/60m later)
def price_at(symbol, ts):
    for c in engine.aggregators[symbol].s1.candles:
        if c.ts >= ts:
            return c.close
    return None

journal.resolve_pending(price_at)
print("=== JOURNAL (HIGH-conviction only, outcomes checked 30/60 min later) ===")
for row in journal.all_signals(20):
    print(f"  #{row['id']} {row['ts'][11:16]} {row['symbol']:<10} "
          f"{'LONG ' if row['direction'] > 0 else 'SHORT'} @₹{row['price']:,.2f} "
          f"-> 30m: {row['move_30m_pct'] if row['move_30m_pct'] is not None else '—'}% "
          f"60m: {row['move_60m_pct'] if row['move_60m_pct'] is not None else '—'}% "
          f"[{row['outcome']}]")
print("\n" + str(journal.performance_summary()))
