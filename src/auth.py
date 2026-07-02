"""Fyers OAuth + daily token lifecycle, built for SEBI's retail-algo framework.

How Fyers auth works (and why it must run daily):
  1. You open a Fyers login URL in a browser and log in with your ID + 2FA
     (TOTP/PIN — SEBI mandates two-factor authentication for API access).
  2. Fyers redirects to your registered redirect URL (https://127.0.0.1) with
     an `auth_code` in the query string.
  3. We exchange that auth_code for an access_token.
  4. Access tokens EXPIRE DAILY (~6 AM IST cutover) — SEBI requires daily
     re-authentication, so this is by design, not a bug. Run
     `python scripts/daily_auth.py` each morning before 9:15.

SEBI April-2026 retail algo framework notes (decision-support today, but this
module is built so order placement could be added compliantly later):
  * Static IP whitelisting: configured on the Fyers MyAPI dashboard per app —
    add your fixed IP there. This code works unchanged; the broker enforces it.
  * Mandatory 2FA: the TOTP flow below covers it.
  * Daily re-auth: enforced by token expiry + this module's refresh flow.
  * Order APIs are deliberately NOT wired up in this version.

Tokens are cached in .tokens/ (gitignored), never in the repo.
"""
from __future__ import annotations

import json
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import pytz

from .config import load_config, PROJECT_ROOT, has_fyers_credentials

IST = pytz.timezone("Asia/Kolkata")
TOKEN_DIR = PROJECT_ROOT / ".tokens"
TOKEN_FILE = TOKEN_DIR / "fyers_token.json"


class FyersAuthError(RuntimeError):
    pass


def _fyers_session(cfg: dict):
    from fyers_apiv3 import fyersModel
    f = cfg["fyers"]
    return fyersModel.SessionModel(
        client_id=f["app_id"],
        secret_key=f["secret_key"],
        redirect_uri=f["redirect_url"],
        response_type="code",
        grant_type="authorization_code",
    )


def get_login_url(cfg: Optional[dict] = None) -> str:
    cfg = cfg or load_config()
    if not has_fyers_credentials(cfg):
        raise FyersAuthError("Fyers app_id/secret_key not set in config.yaml yet.")
    return _fyers_session(cfg).generate_authcode()


def extract_auth_code(redirected_url: str) -> str:
    """User pastes the full https://127.0.0.1/?...auth_code=XXX url after login."""
    qs = parse_qs(urlparse(redirected_url.strip()).query)
    code = qs.get("auth_code", [None])[0]
    if not code:
        raise FyersAuthError("No auth_code found in that URL. Paste the FULL "
                             "address bar contents after Fyers redirects you.")
    return code


def exchange_code_for_token(auth_code: str, cfg: Optional[dict] = None) -> str:
    cfg = cfg or load_config()
    session = _fyers_session(cfg)
    session.set_token(auth_code)
    resp = session.generate_token()
    if not resp or "access_token" not in resp:
        raise FyersAuthError(f"Token exchange failed: {resp}")
    token = resp["access_token"]
    _save_token(token)
    return token


def _save_token(token: str):
    TOKEN_DIR.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({
        "access_token": token,
        "created_at": datetime.now(IST).isoformat(),
        "trading_day": datetime.now(IST).strftime("%Y-%m-%d"),
    }))
    TOKEN_FILE.chmod(0o600)  # owner-only read: it's a credential


def load_cached_token() -> Optional[str]:
    """Return today's token if we have one; Fyers tokens die daily (~6 AM IST)."""
    if not TOKEN_FILE.exists():
        return None
    data = json.loads(TOKEN_FILE.read_text())
    created = datetime.fromisoformat(data["created_at"])
    now = datetime.now(IST)
    same_day = created.astimezone(IST).date() == now.date()
    before_cutover = created.astimezone(IST).hour >= 6 or now.hour < 6
    if same_day and before_cutover:
        return data["access_token"]
    return None


def totp_now(cfg: Optional[dict] = None) -> Optional[str]:
    """Current 6-digit TOTP code if a secret is configured (2FA helper)."""
    cfg = cfg or load_config()
    secret = cfg["fyers"].get("totp_secret", "")
    if not secret:
        return None
    import pyotp
    return pyotp.TOTP(secret).now()


def interactive_login(open_browser: bool = True) -> str:
    """The morning ritual: prints/opens login URL, prompts for redirect URL,
    exchanges + caches the token. Used by scripts/daily_auth.py."""
    cfg = load_config()
    cached = load_cached_token()
    if cached:
        print("✅ Already have a valid token for today's session.")
        return cached
    url = get_login_url(cfg)
    print("\n1. Open this URL and log in to Fyers (2FA required):\n")
    print(f"   {url}\n")
    code_hint = totp_now(cfg)
    if code_hint:
        print(f"   Your current TOTP code: {code_hint}\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    print("2. After login, the browser lands on https://127.0.0.1/?... "
          "(page may show an error — that's fine, the code is in the URL).")
    redirected = input("3. Paste the FULL redirected URL here: ")
    token = exchange_code_for_token(extract_auth_code(redirected), cfg)
    print("✅ Access token obtained and cached for today.")
    return token


def get_fyers_client():
    """Authenticated REST client (quotes/history). Raises if no token today."""
    from fyers_apiv3 import fyersModel
    cfg = load_config()
    token = load_cached_token()
    if not token:
        raise FyersAuthError("No valid token for today. Run: python scripts/daily_auth.py")
    return fyersModel.FyersModel(client_id=cfg["fyers"]["app_id"], token=token,
                                 is_async=False, log_path=str(TOKEN_DIR))
