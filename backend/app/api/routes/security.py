from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.schemas.security import DeviceCreate, SecurityScanRequest
from app.services.security_service import security_service

router = APIRouter()


@router.post("/devices")
def register_device(payload: DeviceCreate):
    return security_service.register_device(payload)


@router.get("/devices")
def list_devices(project_id: Optional[str] = Query(None)):
    return security_service.list_devices(project_id)


@router.get("/devices/{device_id}")
def get_device(device_id: str):
    device = security_service.get_device(device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    return device


@router.post("/scan")
def run_security_scan(payload: SecurityScanRequest):
    return security_service.run_security_scan(payload)


@router.get("/vulnerabilities")
def list_vulnerabilities(
    project_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    return security_service.list_vulnerabilities(project_id, severity, status)


@router.patch("/vulnerabilities/{vuln_id}/status")
def update_vulnerability_status(
    vuln_id: str,
    new_status: str = Query(...),
    notes: Optional[str] = Query(None),
):
    result = security_service.update_vulnerability_status(vuln_id, new_status, notes)
    if not result:
        raise HTTPException(404, "Vulnerability not found")
    return result


@router.get("/dashboard")
def get_security_dashboard(project_id: Optional[str] = Query(None)):
    return security_service.get_dashboard(project_id)


# ── Firmware Intelligence ──────────────────────────────────────

@router.post("/firmware/check")
def check_firmware_updates(project_id: Optional[str] = Query(None)):
    """Check all devices against known CVE database and generate firmware alerts."""
    return security_service.check_firmware_updates(project_id)


@router.get("/firmware/alerts")
def get_firmware_alerts(project_id: Optional[str] = Query(None)):
    """Get all firmware vulnerability alerts."""
    return security_service.get_firmware_alerts(project_id)


@router.get("/firmware/summary")
def get_firmware_summary(project_id: Optional[str] = Query(None)):
    """Get firmware intelligence summary including manufacturer breakdown."""
    return security_service.get_firmware_summary(project_id)


@router.get("/firmware/remediation-tasks")
def get_remediation_tasks(project_id: Optional[str] = Query(None)):
    """Get auto-generated remediation tasks for firmware vulnerabilities."""
    return security_service.get_remediation_tasks(project_id)
