from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.dependencies import get_adapter, get_controller, get_session_manager, get_storage_service
from app.models.schemas import (
    DeviceInfo,
    HealthResponse,
    MeasureResponse,
    SessionCreateRequest,
    SessionMetadataUpdate,
    SessionState,
)

router = APIRouter(prefix="/api", tags=["pvpm"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/device", response_model=DeviceInfo)
def device() -> DeviceInfo:
    return get_adapter().detect_device()


@router.post("/session", response_model=SessionState)
def create_session(req: SessionCreateRequest) -> SessionState:
    return get_session_manager().create(req)


@router.get("/session/{session_id}", response_model=SessionState)
def get_session(session_id: UUID) -> SessionState:
    try:
        return get_session_manager().get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/session/{session_id}/metadata", response_model=SessionState)
def update_session(session_id: UUID, req: SessionMetadataUpdate) -> SessionState:
    try:
        return get_session_manager().update(session_id, req)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/session/{session_id}/measure", response_model=MeasureResponse)
def measure(session_id: UUID) -> MeasureResponse:
    try:
        result = get_controller().measure(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return MeasureResponse(
        accepted=True,
        session_id=result.session_id,
        result_id=result.result_id,
        status="completed",
    )


@router.get("/session/{session_id}/result")
def session_result(session_id: UUID):
    try:
        session = get_session_manager().get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "session_id": str(session.session_id),
        "last_result_id": session.last_result_id,
        "measurement_count": session.measurement_count,
        "status": session.status,
    }


@router.get("/results")
def list_results():
    return get_storage_service().list_results()
