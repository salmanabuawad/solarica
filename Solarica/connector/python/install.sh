#!/usr/bin/env bash
set -e

echo "============================================================"
echo " Solarica Python Connector - Linux / macOS Installer"
echo "============================================================"
echo

# Check Python 3.11+
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.11+ from https://python.org"
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python $PYVER detected"

echo
echo "[1/4] Creating virtual environment..."
python3 -m venv venv

echo "[2/4] Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt

echo "[3/4] Creating data and watch folders..."
mkdir -p data import_watch

echo "[4/4] Creating .env configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  .env created from .env.example — edit it before running."
else
    echo "  .env already exists, skipping."
fi

chmod +x start.sh

echo
echo "============================================================"
echo " Installation complete!"
echo
echo " Next steps:"
echo "   1. Edit .env — set PVPM_DRIVER=vendor_export"
echo "   2. Set WATCH_FOLDER to the PVPM export directory"
echo "   3. Run: ./start.sh"
echo "============================================================"
