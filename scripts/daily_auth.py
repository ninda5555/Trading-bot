#!/usr/bin/env python3
"""Morning ritual: refresh the Fyers access token before market open.

Run this each trading day before 9:15 AM IST:
    python scripts/daily_auth.py

Why daily? Fyers tokens expire every day and SEBI's retail-algo framework
requires daily re-authentication with 2FA. Automate the *reminder*, not the
credential: set a 8:45 AM alarm, run this, paste the redirect URL, done in
~20 seconds (faster if totp_secret is set in config.yaml).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import interactive_login, FyersAuthError  # noqa: E402

if __name__ == "__main__":
    try:
        interactive_login()
    except FyersAuthError as e:
        print(f"❌ {e}")
        sys.exit(1)
