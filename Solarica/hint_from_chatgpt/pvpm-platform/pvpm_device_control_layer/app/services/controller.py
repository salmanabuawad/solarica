from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.adapters.base import PVPMAdapter
from app.models.schemas import MeasurementResult
from app.services.session_manager import SessionManager
from app.services.storage import StorageService


class DeviceController:
    def __init__(self, adapter: PVPMAdapter, sessions: SessionManager, storage: StorageService) -> None:
        self.adapter = adapter
        self.sessions = sessions
        self.storage = storage

    def measure(self, session_id: UUID) -> MeasurementResult:
        session = self.sessions.get(session_id)

        self.adapter.open()
        try:
            applied = self.adapter.apply_metadata(
                session.site_name,
                session.part_name,
                session.module_part_number,
            )
            self.adapter.trigger_measurement()
            payload = self.adapter.fetch_result()
        finally:
            self.adapter.close()

        payload["session"] = {
            "session_id": str(session.session_id),
            "site_name": session.site_name,
            "part_name": session.part_name,
            "module_part_number": session.module_part_number,
            "operator": session.operator,
            "notes": session.notes,
        }
        payload["metadata_applied_to_device"] = bool(applied)

        raw_path, json_path = self.storage.save_measurement(session.session_id, payload.copy())
        result_id = json_path.split("/")[-1].replace(".json", "")
        self.sessions.record_result(session.session_id, result_id)

        return MeasurementResult(
            result_id=result_id,
            session_id=session.session_id,
            measured_at=datetime.fromisoformat(payload["measured_at"]),
            source=self.adapter.__class__.__name__,
            metadata_applied_to_device=bool(applied),
            metadata=payload.get("metadata", {}),
            metrics=payload.get("metrics", {}),
            curve=payload.get("curve", []),
            raw_file_path=raw_path,
            json_file_path=json_path,
        )
