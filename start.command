#!/bin/zsh
set -eu
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment missing. See LOCAL_SETUP.md.'
  exit 1
fi
# Enable historical AIS downloads for real preset scenes; set to 1 for offline use.
export TIDETRACE_OFFLINE="${TIDETRACE_OFFLINE:-0}"
export TIDETRACE_OPEN_METEO_LIVE="${TIDETRACE_OPEN_METEO_LIVE:-1}"
print 'TideTrace: http://127.0.0.1:8000 — press Ctrl+C to stop.'
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
