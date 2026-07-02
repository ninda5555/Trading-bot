"""Trade journal: every HIGH-conviction signal is logged with its reasoning,
then scored against what price ACTUALLY did 30 and 60 minutes later.

This is the accountability layer. If the system's high-conviction calls don't
hold up here over weeks, you'll see it in plain numbers — no hiding.
Storage: SQLite at data/journal.db (gitignored).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytz

from .config import PROJECT_ROOT
from .signals import SignalSnapshot

IST = pytz.timezone("Asia/Kolkata")
DB_PATH = PROJECT_ROOT / "data" / "journal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction INTEGER NOT NULL,        -- +1 long, -1 short
    conviction TEXT NOT NULL,
    price REAL NOT NULL,
    agreeing INTEGER,
    mtf_agrees INTEGER,
    market_aligned INTEGER,
    reasoning TEXT,                    -- JSON list of signal details
    stop_loss REAL,
    target REAL,
    source TEXT DEFAULT 'live',        -- live / delayed / replay-sim
    price_30m REAL,
    price_60m REAL,
    move_30m_pct REAL,
    move_60m_pct REAL,
    outcome TEXT                       -- favorable / adverse / flat / pending
);
"""


class TradeJournal:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def log_signal(self, snap: SignalSnapshot, stop_loss: Optional[float] = None,
                   target: Optional[float] = None, source: str = "live") -> int:
        reasoning = json.dumps([f"{v.name}: {v.detail}" for v in snap.votes])
        cur = self._conn.execute(
            """INSERT INTO signals (ts, symbol, direction, conviction, price,
               agreeing, mtf_agrees, market_aligned, reasoning, stop_loss,
               target, source, outcome)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'pending')""",
            (snap.ts.isoformat(), snap.symbol, snap.direction, snap.conviction,
             snap.price, snap.agreeing, int(snap.mtf_agrees),
             None if snap.market_aligned is None else int(snap.market_aligned),
             reasoning, stop_loss, target, source))
        self._conn.commit()
        return cur.lastrowid

    def already_logged_recently(self, symbol: str, direction: int,
                                within_minutes: int = 30) -> bool:
        """Debounce: don't re-log the same setup every 5 minutes."""
        row = self._conn.execute(
            "SELECT ts FROM signals WHERE symbol=? AND direction=? "
            "ORDER BY id DESC LIMIT 1", (symbol, direction)).fetchone()
        if not row:
            return False
        last = datetime.fromisoformat(row[0])
        now = datetime.now(IST)
        if last.tzinfo is None:
            last = IST.localize(last)
        return (now - last) < timedelta(minutes=within_minutes)

    def record_outcome(self, signal_id: int, price_30m: Optional[float],
                       price_60m: Optional[float]):
        row = self._conn.execute(
            "SELECT price, direction FROM signals WHERE id=?", (signal_id,)).fetchone()
        if not row:
            return
        entry, direction = row
        m30 = round((price_30m - entry) / entry * 100, 3) if price_30m else None
        m60 = round((price_60m - entry) / entry * 100, 3) if price_60m else None
        judge = m60 if m60 is not None else m30
        if judge is None:
            outcome = "pending"
        else:
            signed = judge * direction   # positive = moved in signal's favor
            outcome = "favorable" if signed > 0.15 else \
                      "adverse" if signed < -0.15 else "flat"
        self._conn.execute(
            """UPDATE signals SET price_30m=?, price_60m=?, move_30m_pct=?,
               move_60m_pct=?, outcome=? WHERE id=?""",
            (price_30m, price_60m, m30, m60, outcome, signal_id))
        self._conn.commit()

    def pending_signals(self) -> list[dict]:
        cur = self._conn.execute(
            "SELECT id, ts, symbol, direction, price FROM signals "
            "WHERE outcome='pending' ORDER BY ts")
        return [dict(zip(("id", "ts", "symbol", "direction", "price"), r))
                for r in cur.fetchall()]

    def all_signals(self, limit: int = 500) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?",
                                 (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def resolve_pending(self, price_at):
        """Score pending signals once 30/60 minutes of data exist past them.
        price_at(symbol, ts) -> closing price of the 1-min candle at/after ts,
        or None if that time hasn't been reached yet."""
        for sig in self.pending_signals():
            ts = datetime.fromisoformat(sig["ts"])
            p30 = price_at(sig["symbol"], ts + timedelta(minutes=30))
            p60 = price_at(sig["symbol"], ts + timedelta(minutes=60))
            if p60 is not None or p30 is not None:
                # only finalize when the 60m mark exists (or session ended)
                if p60 is not None:
                    self.record_outcome(sig["id"], p30, p60)

    def performance_summary(self) -> dict:
        """Honest aggregate stats over resolved signals."""
        rows = self._conn.execute(
            """SELECT direction, move_30m_pct, move_60m_pct, outcome FROM signals
               WHERE outcome != 'pending'""").fetchall()
        n = len(rows)
        if n == 0:
            return {"resolved": 0}
        fav = sum(1 for r in rows if r[3] == "favorable")
        adv = sum(1 for r in rows if r[3] == "adverse")
        flat = n - fav - adv
        signed_60 = [r[0] * r[2] for r in rows if r[2] is not None]
        avg_move = sum(signed_60) / len(signed_60) if signed_60 else 0.0
        return {"resolved": n, "favorable": fav, "adverse": adv, "flat": flat,
                "favorable_rate": round(fav / n * 100, 1),
                "avg_signed_move_60m_pct": round(avg_move, 3)}
