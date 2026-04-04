"""
API routes for the device inventory repository.
Prefix: /api/device-inventory
"""
from __future__ import annotations

from typing import List, Optional

import csv
import io

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
import app.repositories.device_repo as repo

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SiteCreate(BaseModel):
    site_name: str
    country: Optional[str] = None
    region: Optional[str] = None
    source_notes: Optional[str] = None


class DeviceCreate(BaseModel):
    site_id: int
    area: Optional[str] = None
    category: str
    manufacturer: Optional[str] = None
    model_raw: Optional[str] = None
    model_normalized: Optional[str] = None
    quantity: Optional[int] = None
    unit: str = "ea"
    is_exact_model_confirmed: bool = False
    role: Optional[str] = None
    source_notes: Optional[str] = None


class DeviceUpdate(BaseModel):
    area: Optional[str] = None
    manufacturer: Optional[str] = None
    model_raw: Optional[str] = None
    model_normalized: Optional[str] = None
    quantity: Optional[int] = None
    is_exact_model_confirmed: Optional[bool] = None
    role: Optional[str] = None
    source_notes: Optional[str] = None


class SpecUpsert(BaseModel):
    spec_key: str
    spec_value: str
    source_note: Optional[str] = None


class CVECreate(BaseModel):
    manufacturer: Optional[str] = None
    product_scope: str
    cve_id: Optional[str] = None
    title: str
    severity: Optional[str] = None
    affected_versions: Optional[str] = None
    fixed_versions: Optional[str] = None
    advisory_source: Optional[str] = None
    applicability: str = "unknown"
    notes: Optional[str] = None


class LinkCreate(BaseModel):
    vuln_id: int
    relationship_type: str = "direct"


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

@router.get("/sites")
def list_sites(db: Session = Depends(get_db)):
    sites = repo.list_sites(db)
    return [s.to_dict() for s in sites]


@router.post("/sites", status_code=201)
def create_site(payload: SiteCreate, db: Session = Depends(get_db)):
    site = repo.create_site(db, **payload.model_dump())
    return site.to_dict()


@router.get("/sites/{site_id}")
def get_site(site_id: int, db: Session = Depends(get_db)):
    site = repo.get_site(db, site_id)
    if not site:
        raise HTTPException(404, "Site not found")
    return site.to_dict()


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@router.get("/devices")
def list_devices(
    site_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    devices = repo.list_devices(db, site_id=site_id, category=category, manufacturer=manufacturer)
    return [d.to_dict(include_specs=True, include_vulns=True) for d in devices]


@router.post("/devices", status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    # Verify site exists
    site = repo.get_site(db, payload.site_id)
    if not site:
        raise HTTPException(404, "Site not found")
    device = repo.create_device(db, **payload.model_dump())
    return device.to_dict(include_specs=True, include_vulns=True)


@router.get("/devices/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = repo.get_device(db, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    return device.to_dict(include_specs=True, include_vulns=True)


@router.patch("/devices/{device_id}")
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = repo.update_device(db, device_id, **payload.model_dump(exclude_none=True))
    if not device:
        raise HTTPException(404, "Device not found")
    return device.to_dict(include_specs=True, include_vulns=True)


@router.delete("/devices/bulk", status_code=200)
def delete_devices_bulk(ids: List[int] = Body(..., embed=True), db: Session = Depends(get_db)):
    """Delete multiple devices by ID list."""
    if not ids:
        raise HTTPException(400, "No device IDs provided")
    deleted = repo.delete_devices_bulk(db, ids)
    return {"deleted": deleted}


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    if not repo.delete_device(db, device_id):
        raise HTTPException(404, "Device not found")


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

@router.get("/devices/{device_id}/specs")
def list_specs(device_id: int, db: Session = Depends(get_db)):
    device = repo.get_device(db, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    return [s.to_dict() for s in repo.list_specs(db, device_id)]


@router.put("/devices/{device_id}/specs")
def upsert_spec(device_id: int, payload: SpecUpsert, db: Session = Depends(get_db)):
    device = repo.get_device(db, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    spec = repo.upsert_spec(db, device_id, payload.spec_key, payload.spec_value, payload.source_note)
    return spec.to_dict()


# ---------------------------------------------------------------------------
# CVEs
# ---------------------------------------------------------------------------

@router.get("/cves")
def list_cves(
    manufacturer: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    cves = repo.list_cves(db, manufacturer=manufacturer, severity=severity)
    return [c.to_dict() for c in cves]


@router.post("/cves", status_code=201)
def create_cve(payload: CVECreate, db: Session = Depends(get_db)):
    # Check for duplicate CVE code
    if payload.cve_id:
        existing = repo.get_cve_by_code(db, payload.cve_id)
        if existing:
            raise HTTPException(409, f"{payload.cve_id} already exists")
    cve = repo.create_cve(db, **payload.model_dump())
    return cve.to_dict()


@router.get("/cves/{cve_id}")
def get_cve(cve_id: int, db: Session = Depends(get_db)):
    cve = repo.get_cve(db, cve_id)
    if not cve:
        raise HTTPException(404, "CVE not found")
    return cve.to_dict()


# ---------------------------------------------------------------------------
# Device ↔ CVE links
# ---------------------------------------------------------------------------

@router.post("/devices/{device_id}/cves", status_code=201)
def link_cve(device_id: int, payload: LinkCreate, db: Session = Depends(get_db)):
    device = repo.get_device(db, device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    cve = repo.get_cve(db, payload.vuln_id)
    if not cve:
        raise HTTPException(404, "CVE not found")
    lnk = repo.link_device_to_cve(db, device_id, payload.vuln_id, payload.relationship_type)
    return lnk.to_dict()


@router.delete("/devices/{device_id}/cves/{vuln_id}", status_code=204)
def unlink_cve(device_id: int, vuln_id: int, db: Session = Depends(get_db)):
    if not repo.unlink_device_from_cve(db, device_id, vuln_id):
        raise HTTPException(404, "Link not found")


# ---------------------------------------------------------------------------
# Summary / stats
# ---------------------------------------------------------------------------

@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """High-level stats for the device inventory."""
    from sqlalchemy import func
    from app.models.device_repo import DeviceInventory, DeviceCVE, DeviceSite

    site_count = db.query(func.count(DeviceSite.id)).scalar()
    device_count = db.query(func.count(DeviceInventory.id)).scalar()
    total_units = db.query(func.sum(DeviceInventory.quantity)).scalar() or 0
    cve_count = db.query(func.count(DeviceCVE.id)).scalar()

    severity_counts = {}
    for sev in ("Critical", "High", "Medium", "Low"):
        cnt = db.query(func.count(DeviceCVE.id)).filter(DeviceCVE.severity == sev).scalar()
        severity_counts[sev.lower()] = cnt

    categories = (
        db.query(DeviceInventory.category, func.count(DeviceInventory.id))
        .group_by(DeviceInventory.category)
        .all()
    )

    return {
        "site_count": site_count,
        "device_type_count": device_count,
        "total_units": int(total_units),
        "cve_count": cve_count,
        "severity_breakdown": severity_counts,
        "categories": {cat: cnt for cat, cnt in categories},
    }


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

@router.get("/devices/export/csv")
def export_devices_csv(
    site_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Download all device inventory rows as a CSV file."""
    devices = repo.list_devices(db, site_id=site_id, category=category)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "site_name", "area", "category", "manufacturer", "model_raw",
        "model_normalized", "quantity", "unit", "role",
        "is_exact_model_confirmed", "vuln_count", "source_notes",
    ])
    for d in devices:
        row = d.to_dict(include_specs=False, include_vulns=False)
        writer.writerow([
            row.get("site_name", ""),
            row.get("area", ""),
            row.get("category", ""),
            row.get("manufacturer", ""),
            row.get("model_raw", ""),
            row.get("model_normalized", ""),
            row.get("quantity", ""),
            row.get("unit", "ea"),
            row.get("role", ""),
            "1" if row.get("is_exact_model_confirmed") else "0",
            row.get("vuln_count", 0),
            row.get("source_notes", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=device_inventory.csv"},
    )


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

@router.post("/devices/import/csv")
async def import_devices_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Bulk-import devices from a CSV file.
    Required columns: site_name, category
    Optional: area, manufacturer, model_raw, model_normalized, quantity, unit, role, source_notes
    """
    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    created = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        site_name = (row.get("site_name") or "").strip()
        category  = (row.get("category") or "").strip()
        if not site_name or not category:
            errors.append(f"Row {i}: site_name and category are required")
            continue
        # Find or create site
        from app.models.device_repo import DeviceSite
        site = db.query(DeviceSite).filter(DeviceSite.site_name == site_name).first()
        if not site:
            site = repo.create_site(db, site_name=site_name)
        qty_raw = (row.get("quantity") or "").strip()
        qty = int(qty_raw) if qty_raw.lstrip("-").isdigit() else None
        confirmed_raw = (row.get("is_exact_model_confirmed") or "0").strip()
        confirmed = confirmed_raw in ("1", "true", "True", "yes", "Yes")
        try:
            repo.create_device(
                db,
                site_id=site.id,
                area=(row.get("area") or "").strip() or None,
                category=category,
                manufacturer=(row.get("manufacturer") or "").strip() or None,
                model_raw=(row.get("model_raw") or "").strip() or None,
                model_normalized=(row.get("model_normalized") or "").strip() or None,
                quantity=qty,
                unit=(row.get("unit") or "ea").strip() or "ea",
                is_exact_model_confirmed=confirmed,
                role=(row.get("role") or "").strip() or None,
                source_notes=(row.get("source_notes") or "").strip() or None,
            )
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {i}: {exc}")
    return {"created": created, "errors": errors}


# ---------------------------------------------------------------------------
# Admin: re-seed from repository.json
# ---------------------------------------------------------------------------

@router.post("/seed")
def seed_repository(db: Session = Depends(get_db)):
    """Re-run the seed from device_repo/device_repository/repository.json."""
    result = repo.seed_from_repository_json(db)
    return result
