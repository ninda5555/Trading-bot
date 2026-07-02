"""Load config.yaml — the single place credentials and settings live."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
EXAMPLE_PATH = PROJECT_ROOT / "config.yaml.example"

DEFAULTS = {
    "fyers": {"app_id": "", "secret_key": "", "redirect_url": "https://127.0.0.1",
              "totp_secret": "", "pin": ""},
    "risk": {"capital": 100000, "risk_per_trade_pct": 1.0, "daily_loss_limit_pct": 3.0},
    "feed": {"mode": "replay"},
    "watchlist": ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
                  "SBIN", "TATAMOTORS", "AXISBANK"],
}


def load_config() -> dict:
    """Read config.yaml, falling back to safe defaults so the dashboard
    still runs in replay/delayed mode before Fyers credentials exist."""
    cfg = {k: (dict(v) if isinstance(v, dict) else list(v)) for k, v in DEFAULTS.items()}
    path = CONFIG_PATH if CONFIG_PATH.exists() else None
    if path is None and EXAMPLE_PATH.exists():
        path = EXAMPLE_PATH  # placeholder values; fine for replay/delayed modes
    if path:
        with open(path) as f:
            user_cfg = yaml.safe_load(f) or {}
        for key, val in user_cfg.items():
            if isinstance(val, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(val)
            else:
                cfg[key] = val
    # Environment variables override the file (useful for servers/CI)
    env_app = os.environ.get("FYERS_APP_ID")
    env_secret = os.environ.get("FYERS_SECRET_KEY")
    if env_app:
        cfg["fyers"]["app_id"] = env_app
    if env_secret:
        cfg["fyers"]["secret_key"] = env_secret
    return cfg


def has_fyers_credentials(cfg: dict | None = None) -> bool:
    cfg = cfg or load_config()
    app_id = cfg["fyers"].get("app_id", "")
    secret = cfg["fyers"].get("secret_key", "")
    return bool(app_id and secret and "YOUR_" not in app_id and "YOUR_" not in secret)
