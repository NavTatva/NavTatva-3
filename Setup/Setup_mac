#!/usr/bin/env bash
# ==============================================================================
# NavTatva · TideTrace - macOS Environment Setup
# ==============================================================================
set -euo pipefail

# Navigate to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "============================================================"
echo " NavTatva · TideTrace - macOS Automated Setup"
echo "============================================================"
echo "Project root: $ROOT_DIR"
echo ""

# 1. Check Python installation
echo "[1/5] Checking Python 3..."
if command -v python3 &>/dev/null; then
    PY_BIN="python3"
elif command -v python &>/dev/null; then
    PY_BIN="python"
else
    echo "[ERROR] Python 3 is not installed or not in PATH."
    echo "Please install Python 3.11 or newer (e.g. from https://www.python.org or brew install python)."
    exit 1
fi

PY_VER=$($PY_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Found Python $PY_VER ($PY_BIN)"

# 2. Setup Virtual Environment
echo ""
echo "[2/5] Setting up virtual environment in .venv..."
if [ ! -d ".venv" ]; then
    echo "Creating new virtual environment..."
    $PY_BIN -m venv .venv
else
    echo "Virtual environment .venv already exists."
fi

VENV_PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
    echo "[ERROR] Virtual environment python missing at $VENV_PY"
    exit 1
fi

# 3. Upgrade pip and install dependencies
echo ""
echo "[3/5] Installing project dependencies..."
"$VENV_PY" -m pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "Installing requirements.txt..."
    "$VENV_PY" -m pip install --no-user -r requirements.txt reportlab rasterio pytest httpx
fi

# Install PyTorch CPU and segmentation-models-pytorch
echo "Installing PyTorch and segmentation-models-pytorch..."
"$VENV_PY" -m pip install --no-user torch torchvision segmentation-models-pytorch

# 4. Configure AISStream API Key
echo ""
echo "[4/5] Configuring AISStream API key..."
KEY_DIR="$HOME/.config/navtatva"
KEY_FILE="$KEY_DIR/aisstream.key"
DEFAULT_KEY="12a28c6c53e8526cfe02f279f3d9fbee137576d9"

mkdir -p "$KEY_DIR"
if [ ! -f "$KEY_FILE" ] || [ ! -s "$KEY_FILE" ]; then
    echo -n "$DEFAULT_KEY" > "$KEY_FILE"
    chmod 600 "$KEY_FILE" 2>/dev/null || true
    echo "API key saved to $KEY_FILE"
else
    echo "Existing key file found at $KEY_FILE"
fi

# 5. Verify Environment
echo ""
echo "[5/5] Verifying environment and ML model checkpoint..."
"$VENV_PY" -c "
import app.main
from app.ml import infer
model = infer.get_model()
print('✓ App modules loaded successfully')
print('✓ U-Net model ready:', model is not None)
"

echo ""
echo "============================================================"
echo " Setup completed successfully!"
echo " To run the project on Mac, run:"
echo "   ./Setup/run_mac"
echo " or double-click Setup/run_mac.command"
echo "============================================================"
