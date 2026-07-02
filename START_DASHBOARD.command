#!/usr/bin/env bash
# Mac/Linux launcher — double-click me (on Mac) or run: bash START_DASHBOARD.command
cd "$(dirname "$0")"

# Find a COMPATIBLE Python (3.9 - 3.12). Very new Pythons (3.13/3.14) can't
# run the Fyers library yet (it pins an older aiohttp with no wheels for them).
PY=""
for cand in python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if (3,9) <= sys.version_info[:2] <= (3,12) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo ""
  echo " This app needs Python 3.12 (very new Pythons like 3.14 are TOO new"
  echo " for the Fyers stock-broker library — not your fault!)."
  echo ""
  echo " One-time fix: install Python 3.12 from"
  echo "   https://www.python.org/downloads/release/python-31210/"
  echo " then double-click this file again."
  echo ""
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Using Python: $PY"
echo "Checking the app's parts are installed — the FIRST run can take a few minutes..."
if ! "$PY" -m pip install -r requirements.txt --quiet --disable-pip-version-check; then
  echo ""
  echo " Something went wrong while downloading the app's parts."
  echo " Check your internet connection and run this again; if it keeps"
  echo " failing, copy the message above and ask for help."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
echo "Starting your dashboard — your browser will open by itself in a moment."
echo "(Keep this window open while you use the dashboard. Close it to stop.)"
echo ""
"$PY" -m streamlit run dashboard/app.py
