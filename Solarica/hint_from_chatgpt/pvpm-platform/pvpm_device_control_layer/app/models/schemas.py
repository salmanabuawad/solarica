from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "pvpm-device-control-layer"
    version: str = "0.1.0"


class DeviceInfo(BaseModel):
    connected: bool
    transport: str
    port: Optional[str] = None
    vendor: Optional[str] = None
    device_model: Optional[str] = None
    serial_number: Optional[str] = None
    detail: Optional[str] = None


class SessionCreateRequest(BaseModel):
    site_name: Optional[str] = None
    part_name: Optional[str] = None
    module_part_number: Optional[str] = None
    operator: Optional[str] = None
    notes: Optional[str] = None


class SessionMetadataUpdate(BaseModel):
    site_name: Optional[str] = None
    part_name: Optional[str] = None
    module_part_number: Optional[str] = None
    operator: Optional[str] = None
    notes: Optional[str] = None


class SessionState(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "created"
    site_name: Optional[str] = None
    part_name: Optional[str] = None
    module_part_number: Optional[str] = None
    operator: Optional[str] = None
    notes: Optional[str] = None
    measurement_count: int = 0
    last_result_id: Optional[str] = None


class MeasureResponse(BaseModel):
    accepted: bool = True
    session_id: UUID
    result_id: str
    status: str


class MeasurementResult(BaseModel):
    result_id: str
    session_id: UUID
    measured_at: datetime
    source: str
    metadata_applied_to_device: bool
    metadata: dict[str, Any]
    metrics: dict[str, Any]
    curve: list[dict[str, float]]
    raw_file_path: str
    json_file_path: str
