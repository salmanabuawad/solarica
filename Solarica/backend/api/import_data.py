"""Data import API endpoints."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from config import settings
from parsers import parse_import_file
from services.measurement_import import insert_measurement_payload

router = APIRouter()


class ImportResult(BaseModel):
    success: bool
    measurement_id: Optional[int] = None
    message: str
    duplicate: bool = False
    errors: list[str] = []


class IVPointPayload(BaseModel):
    voltage: float
    current: float


class MeasurementPayload(BaseModel):
    measured_at: Optional[datetime] = None
    device_serial: Optional[str] = None
    sensor_serial: Optional[str] = None
    irradiance_sensor_serial: Optional[str] = None
    customer: Optional[str] = None
    module_type: Optional[str] = None
    remarks: Optional[str] = None
    ppk: Optional[float] = None
    rs: Optional[float] = None
    rp: Optional[float] = None
    voc: Optional[float] = None
    isc: Optional[float] = None
    vpmax: Optional[float] = None
    ipmax: Optional[float] = None
    pmax: Optional[float] = None
    fill_factor: Optional[float] = None
    ff: Optional[float] = None
    eeff: Optional[float] = None
    tmod: Optional[float] = None
    tcell: Optional[float] = None
    source_file: Optional[str] = None
    device_record_id: Optional[str] = None
    sync_source: Optional[str] = None
    iv_curve: list[IVPointPayload] = Field(default_factory=list)


class MeasurementBatchRequest(BaseModel):
    measurements: list[MeasurementPayload]
    allow_duplicates: bool = False


class ImportBatchResult(BaseModel):
    success: bool
    total: int
    imported: int
    duplicates: int
    failed: int
    results: list[ImportResult]


def _result_from_dict(data: dict[str, Any]) -> ImportResult:
    return ImportResult(**data)


def _do_import(content: bytes, filename: str, suffix: str, site_id: Optional[int] = None) -> ImportResult:
    """Blocking import logic - run in thread pool."""
    result = parse_import_file(content, filename=filename, format_hint=suffix)
    if not result:
        return ImportResult(
            success=False,
            message="No valid measurement data found in file",
            errors=["Parser returned empty result"],
        )

    return _result_from_dict(
        insert_measurement_payload(result, source_file_override=filename, site_id=site_id)
    )


@router.post("/upload", response_model=ImportResult)
async def upload_file(file: UploadFile = File(...), site_id: Optional[int] = Form(None)):
    """
    Upload and import a PVPM export file.
    Supports: .xls, .xlsx, .csv, .txt (ASCII export from PVPM.disp)
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xls", ".xlsx", ".csv", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Use .xls, .xlsx, .csv, or .txt (PVPM ASCII export)",
        )

    content = await file.read()
    try:
        result = parse_import_file(content, filename=file.filename or "upload", format_hint=suffix)
    except Exception as e:
        return ImportResult(success=False, message=str(e), errors=[str(e)])

    if not result:
        return ImportResult(
            success=False,
            message="No valid measurement data found in file",
            errors=["Parser returned empty result"],
        )

    # Run blocking DB work in thread pool to avoid hanging the event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _do_import(content, file.filename or "upload", suffix, site_id),
    )


@router.post("/measurement", response_model=ImportResult)
async def import_measurement(payload: MeasurementPayload):
    """Import a single structured measurement payload."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _result_from_dict(insert_measurement_payload(payload)),
    )


@router.post("/batch", response_model=ImportBatchResult)
async def import_measurement_batch(request: MeasurementBatchRequest):
    """Import a batch of structured measurement payloads."""
    loop = asyncio.get_event_loop()

    def _run_batch() -> ImportBatchResult:
        results = [
            _result_from_dict(
                insert_measurement_payload(
                    payload,
                    allow_duplicates=request.allow_duplicates,
                )
            )
            for payload in request.measurements
        ]
        imported = sum(1 for item in results if item.success and not item.duplicate)
        duplicates = sum(1 for item in results if item.duplicate)
        failed = sum(1 for item in results if not item.success)
        return ImportBatchResult(
            success=failed == 0,
            total=len(results),
            imported=imported,
            duplicates=duplicates,
            failed=failed,
            results=results,
        )

    return await loop.run_in_executor(None, _run_batch)


@router.get("/folder")
async def get_import_folder_info():
    """Get the configured import folder path (for file watcher / manual drops)."""
    return {
        "import_folder": str(Path(settings.import_folder).resolve()),
        "watch_enabled": settings.watch_import_folder,
    }
