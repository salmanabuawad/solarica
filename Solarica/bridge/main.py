"""Local bridge service for PVPM sync on Windows."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from parsers import parse_import_file  # noqa: E402

BRIDGE_PORT = 8765
SAMPLE_FILE = PROJECT_ROOT / "Sample_output" / "sample_measurement_2026-05.csv"

app = FastAPI(title="IVCurve Bridge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SyncRequest(BaseModel):
    sample_mode: bool = True


class JobState(BaseModel):
    job_id: str
    status: str
    message: str
    measurements: list[dict[str, Any]] = Field(default_factory=list)
    imported_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None


JOBS: dict[str, JobState] = {}
LAST_SYNC_AT: str | None = None
SEEN_RECORD_KEYS: set[str] = set()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _measurement_key(measurement: dict[str, Any]) -> str:
    return "|".join(
        str(measurement.get(field) or "")
        for field in ("device_serial", "measured_at", "voc", "isc", "pmax")
    )


def _load_saved_measurements() -> list[dict[str, Any]]:
    if not SAMPLE_FILE.exists():
        raise FileNotFoundError(f"Sample file not found: {SAMPLE_FILE}")

    parsed = parse_import_file(
        SAMPLE_FILE.read_bytes(),
        filename=SAMPLE_FILE.name,
        format_hint=SAMPLE_FILE.suffix,
    )
    if not parsed:
        raise ValueError("No measurement data could be parsed from the bridge sample file")

    parsed["source_file"] = SAMPLE_FILE.name
    parsed["sync_source"] = "windows-bridge"
    parsed["device_record_id"] = _measurement_key(parsed)
    return [parsed]


async def _run_sync_job(job_id: str, sample_mode: bool) -> None:
    global LAST_SYNC_AT

    job = JOBS[job_id]
    job.status = "running"
    job.message = "Connecting to PVPM bridge source."
    await asyncio.sleep(1)

    try:
        measurements = _load_saved_measurements() if sample_mode else []
        fresh_measurements: list[dict[str, Any]] = []
        duplicates = 0
        for measurement in measurements:
            record_key = _measurement_key(measurement)
            if record_key in SEEN_RECORD_KEYS:
                duplicates += 1
                continue
            SEEN_RECORD_KEYS.add(record_key)
            fresh_measurements.append(measurement)

        job.measurements = fresh_measurements
        job.duplicate_count = duplicates
        job.imported_count = len(fresh_measurements)
        job.status = "completed"
        job.message = (
            "Prepared measurements from sample bridge mode."
            if sample_mode
            else "Bridge completed without any device records."
        )
        job.completed_at = _now_iso()
        LAST_SYNC_AT = job.completed_at
    except Exception as exc:
        job.status = "failed"
        job.failed_count = 1
        job.message = str(exc)
        job.completed_at = _now_iso()


@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "status": "online",
        "bridge_version": "0.1.0",
        "device_connected": True,
        "device_mode": "sample-transfer",
        "requires_transfer_mode": True,
        "sample_mode": True,
        "last_sync_at": LAST_SYNC_AT,
        "message": "Bridge stub is online. Replace sample mode with the real PVPM Windows transfer path on the bridge host.",
    }


@app.post("/sync")
async def start_sync(request: SyncRequest) -> dict[str, str]:
    job_id = uuid4().hex[:12]
    JOBS[job_id] = JobState(
        job_id=job_id,
        status="queued",
        message="Sync queued.",
        started_at=_now_iso(),
    )
    asyncio.create_task(_run_sync_job(job_id, request.sample_mode))
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Bridge sync started.",
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Bridge job not found")
    return job.model_dump()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ivcurve-bridge"}
