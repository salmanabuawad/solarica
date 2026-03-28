from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import JSON_DIR, RAW_DIR


class StorageService:
    def save_measurement(self, session_id: UUID, payload: dict[str, Any]) -> tuple[str, str]:
        measured_at = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        result_id = f"{session_id}_{measured_at}"

        raw_path = RAW_DIR / f"{result_id}.sui"
        json_path = JSON_DIR / f"{result_id}.json"

        raw_bytes = payload.pop("raw_bytes", b"")
        raw_path.write_bytes(raw_bytes)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return str(raw_path), str(json_path)

    def list_results(self) -> list[dict[str, Any]]:
        results = []
        for path in sorted(JSON_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                results.append(data)
            except Exception:
                continue
        return results
