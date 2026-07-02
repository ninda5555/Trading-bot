#!/usr/bin/env bash
# Mac/Linux launcher — double-click me (on Mac) or run: bash START_DASHBOARD.command
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo " Python is not installed on this computer yet. One-time fix:"
  echo "   1. Open https://www.python.org/downloads/ and install Python 3"
  echo "   2. Then double-click this file again"
  echo ""
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Checking the app's parts are installed — the FIRST run can take a few minutes..."
python3 -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo ""
echo "Starting your dashboard — your browser will open by itself in a moment."
echo "(Keep this window open while you use the dashboard. Close it to stop.)"
echo ""
python3 -m streamlit run dashboard/app.py
