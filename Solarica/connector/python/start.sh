#!/usr/bin/env bash
set -e

if [ ! -d venv ]; then
    echo "ERROR: Virtual environment not found. Run ./install.sh first."
    exit 1
fi

source venv/bin/activate
echo "Starting Solarica Python Connector on http://127.0.0.1:8765 ..."
uvicorn main:app --host 127.0.0.1 --port 8765
