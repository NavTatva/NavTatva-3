#!/usr/bin/env bash
# ==============================================================================
# NavTatva · TideTrace - macOS Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x ".venv/bin/python" ]; then
    echo "[ERROR] Python environment missing in .venv."
    echo "Running Setup_mac first..."
    bash "$SCRIPT_DIR/Setup_mac"
    if [ ! -x ".venv/bin/python" ]; then
        echo "[ERROR] Setup failed. See errors above."
        exit 1
    fi
fi

# Configuration flags
export TIDETRACE_OFFLINE="${TIDETRACE_OFFLINE:-0}"
export TIDETRACE_OPEN_METEO_LIVE="${TIDETRACE_OPEN_METEO_LIVE:-1}"
export AISSTREAM_API_KEY="${AISSTREAM_API_KEY:-12a28c6c53e8526cfe02f279f3d9fbee137576d9}"

echo "============================================================"
echo " Starting TideTrace on http://127.0.0.1:8000"
echo " Press Ctrl+C in this terminal to stop."
echo "============================================================"

# Automatically open browser after 1 second
(sleep 1 && (open "http://127.0.0.1:8000" 2>/dev/null || true)) &

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
