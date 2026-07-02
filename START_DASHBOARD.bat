@echo off
title NSE Intraday Assistant
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python is not installed on this computer yet. One-time fix:
  echo.
  echo    1. Open  https://www.python.org/downloads/  in your browser
  echo    2. Click the big yellow Download button and run the installer
  echo    3. IMPORTANT: tick the box "Add Python to PATH" on the first screen
  echo    4. When it finishes, double-click this file again
  echo.
  pause
  exit /b 1
)

echo Checking the app's parts are installed - the FIRST run can take a few minutes...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo.
echo Starting your dashboard - your browser will open by itself in a moment.
echo (Keep this black window open while you use the dashboard. Close it to stop.)
echo.
python -m streamlit run dashboard\app.py
pause
