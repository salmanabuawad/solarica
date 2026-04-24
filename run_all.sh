#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
python -m venv .venv || true
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 &
B=$!

cd "$ROOT/frontend"
npm install
npm run dev &
F=$!

trap 'kill $B $F || true' EXIT INT TERM
wait $F
