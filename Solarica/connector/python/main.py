"""
Solarica Python Connector – entry point.

Run:
    uvicorn main:app --host 127.0.0.1 --port 8765

Or package with PyInstaller:
    pyinstaller solarica_connector.spec
"""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.driver_factory import get_driver
from app.export import export_csv, export_json
from app.repository import get_measurement, list_measurements
from app.schemas import (
    ConnectRequest,
    DeviceStatus,
    HealthResponse,
    ImportStartResult,
    ImportStatus,
    MeasurementsResponse,
    PortsResponse,
    SyncUploadResult,
)
from app.services import (
    get_import_status,
    seed_from_driver,
    start_watcher,
    stop_watcher,
    upload_unsynced,
)

CONNECTOR_VERSION = "1.0.0"

app = FastAPI(
    title="Solarica Connector",
    version=CONNECTOR_VERSION,
    description=(
        "Local connector service for PVPM 1540X measurement acquisition. "
        "Exposes a REST API consumed by the Solarica web app. "
        "Both Python and .NET connectors implement the same contract."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health / detection
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, version=CONNECTOR_VERSION, runtime="python")


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------


@app.get("/api/device/status", response_model=DeviceStatus)
def device_status() -> DeviceStatus:
    return DeviceStatus(**get_driver().detect())


@app.get("/api/device/ports", response_model=PortsResponse)
def device_ports() -> PortsResponse:
    return PortsResponse(items=get_driver().list_ports())


@app.post("/api/device/connect", response_model=DeviceStatus)
def device_connect(payload: ConnectRequest) -> DeviceStatus:
    return DeviceStatus(**get_driver().connect(payload.port))


@app.post("/api/device/disconnect")
def device_disconnect() -> dict:
    get_driver().disconnect()
    return {"ok": True}


@app.get("/api/device/files")
def device_files() -> dict:
    """List measurement files available in the current watch folder."""
    driver = get_driver()
    items = driver.list_files() if hasattr(driver, "list_files") else []
    return {"items": items}


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@app.post("/api/import/start", response_model=ImportStartResult)
def import_start(background_tasks: BackgroundTasks) -> ImportStartResult:
    """Start an import in the background and return immediately.

    Poll /api/import/status to track progress (state: running → completed).
    """
    from app.services import _import_lock  # noqa: PLC0415
    if _import_lock.locked():
        # Already running — return last count
        prev = int(__import__("app.services", fromlist=["get_sync_state"])
                   .get_sync_state("last_imported_count", "0") or 0)
        return ImportStartResult(ok=True, imported=prev)
    background_tasks.add_task(_run_import_bg)
    return ImportStartResult(ok=True, imported=0)


def _run_import_bg() -> None:
    try:
        seed_from_driver()
    except Exception:
        pass


@app.get("/api/import/status", response_model=ImportStatus)
def import_status() -> ImportStatus:
    return ImportStatus(**get_import_status())


@app.post("/api/import/watch/start")
def import_watch_start() -> dict:
    """Start background file watcher — auto-imports new files as they appear."""
    started = start_watcher()
    return {"ok": True, "started": started, "watching": True}


@app.post("/api/import/watch/stop")
def import_watch_stop() -> dict:
    """Stop the background file watcher."""
    stopped = stop_watcher()
    return {"ok": True, "stopped": stopped, "watching": False}


@app.post("/api/device/launch-pvpm")
def launch_pvpm() -> dict:
    """Launch the PVPMdisp transfer software to pull data from the device."""
    import subprocess, sys
    from pathlib import Path
    candidates = [
        Path(r"C:\Program Files (x86)\PVPMdisp\PVPMdisp.exe"),
        Path(r"C:\Program Files\PVPMdisp\PVPMdisp.exe"),
    ]
    for exe in candidates:
        if exe.exists():
            subprocess.Popen([str(exe)], shell=False)
            return {"ok": True, "launched": str(exe)}
    return {"ok": False, "error": "PVPMdisp.exe not found"}


# ---------------------------------------------------------------------------
# Measurements (local cache)
# ---------------------------------------------------------------------------


@app.get("/api/measurements", response_model=MeasurementsResponse)
def measurements_list() -> MeasurementsResponse:
    return MeasurementsResponse(items=list_measurements())


@app.get("/api/measurements/{measurement_id}")
def measurement_detail(measurement_id: str) -> dict:
    item = get_measurement(measurement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return item


# ---------------------------------------------------------------------------
# Sync to cloud backend
# ---------------------------------------------------------------------------


@app.post("/api/sync/upload", response_model=SyncUploadResult)
def sync_upload() -> SyncUploadResult:
    result = upload_unsynced()
    return SyncUploadResult(**result)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@app.get("/api/export/csv")
def export_csv_endpoint() -> Response:
    data = export_csv()
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=measurements.csv"},
    )


@app.get("/api/export/json")
def export_json_endpoint() -> Response:
    data = export_json()
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=measurements.json"},
    )


# ---------------------------------------------------------------------------
# CLI entry point (for PyInstaller exe)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.connector_port,
        log_level=settings.log_level.lower(),
    )
