from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
JSON_DIR = DATA_DIR / "json"

for folder in (DATA_DIR, RAW_DIR, JSON_DIR):
    folder.mkdir(parents=True, exist_ok=True)

ADAPTER_MODE = os.getenv("PVPM_ADAPTER", "simulator").strip().lower()
HOST = os.getenv("PVPM_HOST", "127.0.0.1")
PORT = int(os.getenv("PVPM_PORT", "8765"))
