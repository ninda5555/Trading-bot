@echo off
title NSE Intraday Assistant
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem Find a COMPATIBLE Python (3.10 - 3.12).
rem Very new Pythons (3.13 / 3.14) cannot run the Fyers library yet
rem because it needs an older component with no package for them.
rem ---------------------------------------------------------------
set "PY="
for %%V in (3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "pass" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; raise SystemExit(0 if sys.version_info[:2] <= (3,12) and sys.version_info[:2] >= (3,9) else 1)" >nul 2>nul && set "PY=python"
)

if not defined PY (
  echo.
  echo  This app needs Python 3.12 ^(a very new Python like 3.14 is TOO new
  echo  for the Fyers stock-broker library - not your fault!^).
  echo.
  echo  One-time fix, takes 3 minutes:
  echo    1. Open this link in your browser:
  echo       https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
  echo    2. Run the downloaded installer and click "Install Now"
  echo       ^(you can keep your other Python - they live side by side^)
  echo    3. When it finishes, double-click this file again.
  echo.
  pause
  exit /b 1
)

echo Using Python: %PY%
echo Checking the app's parts are installed - the FIRST run can take a few minutes...
%PY% -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
  echo.
  echo  Something went wrong while downloading the app's parts.
  echo  1. Check your internet connection and double-click this file again.
  echo  2. If it keeps failing, take a photo of this window and ask for help.
  echo.
  pause
  exit /b 1
)

echo.
echo Starting your dashboard - your browser will open by itself in a moment.
echo (Keep this black window open while you use the dashboard. Close it to stop.)
echo.
%PY% -m streamlit run dashboard\app.py
pause
