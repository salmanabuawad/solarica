from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.schemas import SessionCreateRequest, SessionMetadataUpdate, SessionState


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[UUID, SessionState] = {}

    def create(self, req: SessionCreateRequest) -> SessionState:
        session = SessionState(
            site_name=req.site_name,
            part_name=req.part_name,
            module_part_number=req.module_part_number,
            operator=req.operator,
            notes=req.notes,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: UUID) -> SessionState:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Unknown session_id: {session_id}")
        return session

    def update(self, session_id: UUID, req: SessionMetadataUpdate) -> SessionState:
        session = self.get(session_id)
        for field in ("site_name", "part_name", "module_part_number", "operator", "notes"):
            value = getattr(req, field)
            if value is not None:
                setattr(session, field, value)
        session.updated_at = datetime.utcnow()
        return session

    def record_result(self, session_id: UUID, result_id: str) -> SessionState:
        session = self.get(session_id)
        session.measurement_count += 1
        session.last_result_id = result_id
        session.status = "measured"
        session.updated_at = datetime.utcnow()
        return session
