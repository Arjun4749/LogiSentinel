#!/usr/bin/env bash
# LogiSentinel one-click start for macOS / Linux.  Run:  bash start_mac_linux.sh
set -e
cd "$(dirname "$0")"
echo "=========================================================="
echo "  LogiSentinel - starting up"
echo "=========================================================="
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[!] Python 3.10+ is not installed. Get it from https://www.python.org/downloads/"
  exit 1
fi
if [ ! -x ".venv/bin/python" ]; then
  echo "First run: creating a private Python environment..."
  "$PY" -m venv .venv || { echo "[!] Could not create venv. On Ubuntu run: sudo apt install python3-venv"; exit 1; }
fi
if [ ! -f ".venv/installed.flag" ]; then
  echo "First run: installing packages (needs internet once, 2-5 minutes)..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r backend/requirements.txt
  echo ok > .venv/installed.flag
fi
echo "Starting the server. Your browser will open automatically. Press CTRL+C to stop."
exec .venv/bin/python run.py
