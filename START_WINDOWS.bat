@echo off
title LogiSentinel - Predictive Logistics
cd /d "%~dp0"
echo.
echo  ==========================================================
echo    LogiSentinel - starting up
echo  ==========================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo  [!] Python was not found on this computer.
  echo      Install Python 3.10 or newer from https://www.python.org/downloads/
  echo      IMPORTANT: tick "Add Python to PATH" during installation, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  First run: creating a private Python environment...
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)

if not exist ".venv\installed.flag" (
  echo  First run: installing packages. This needs internet once and takes 2-5 minutes...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
  if errorlevel 1 goto fail
  echo ok> ".venv\installed.flag"
)

echo  Starting the server. Your browser will open automatically.
echo  Keep this window open while you use the app. Close it to stop.
echo.
".venv\Scripts\python.exe" run.py
pause
exit /b 0

:fail
echo.
echo  [!] Setup failed. Check your internet connection and try again.
echo      If it still fails, delete the .venv folder and run this file again.
pause
exit /b 1
