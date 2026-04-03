"""
API routes for the solar equipment catalog.
Prefix: /api/solar-catalog

Endpoints:
  GET  /status              — catalog load status + stats
  POST /import              — trigger CSV import (admin, runs in background thread)
  GET  /categories          — list all 7 categories
  GET  /manufacturers       — searchable manufacturer list
  GET  /devices             — search devices (q, category, manufacturer, technology)
  GET  /devices/{id}        — device detail with specs
  GET  /devices/{id}/vulns  — CVEs matching this device
  GET  /vulnerabilities     — all catalog CVEs
"""
from __future__ import annotations

import csv
import io
import threading
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, BackgroundTasks, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
import app.repositories.solar_catalog_repo as repo

router = APIRouter()
logger = logging.getLogger(__name__)

# Track whether an import is in progress
_import_lock = threading.Lock()
_import_status: dict = {"running": False, "last_result": None}


# ---------------------------------------------------------------------------
# Status & import
# ---------------------------------------------------------------------------

@router.get("/status")
def catalog_status(db: Session = Depends(get_db)):
    stats = repo.get_catalog_stats(db)
    return {
        **stats,
        "import_running": _import_status["running"],
        "last_import_result": _import_status["last_result"],
    }


def _run_import():
    """Background thread: load CSVs into catalog tables."""
    global _import_status
    _import_status["running"] = True
    db = SessionLocal()
    try:
        result = repo.import_catalog_from_csv(db)
        _import_status["last_result"] = result
        logger.info("Solar catalog import finished: %s", result)
    except Exception as e:
        logger.error("Solar catalog import error: %s", e)
        _import_status["last_result"] = {"status": "error", "reason": str(e)}
    finally:
        db.close()
        _import_status["running"] = False


@router.post("/import")
def trigger_import():
    """
    Trigger a background import of the solar_db_dump_real CSV files.
    Returns immediately; poll /status to track progress.
    Idempotent — skips if catalog already loaded.
    """
    if _import_status["running"]:
        return {"status": "already_running"}
    t = threading.Thread(target=_run_import, daemon=True)
    t.start()
    return {"status": "started"}


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    cats = repo.list_categories(db)
    return [c.to_dict() for c in cats]


@router.get("/manufacturers")
def list_manufacturers(
    q: Optional[str] = Query(None, description="Search by name"),
    category: Optional[str] = Query(None, description="Filter by category_code"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    return repo.list_manufacturers(db, q=q, category=category, limit=limit)


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@router.get("/devices")
def search_devices(
    q: Optional[str] = Query(None, description="Search model name, manufacturer, description"),
    category: Optional[str] = Query(None, description="category_code filter"),
    manufacturer: Optional[str] = Query(None, description="Manufacturer name filter"),
    technology: Optional[str] = Query(None, description="Technology filter (e.g. Mono-c-Si)"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    sort_by: Optional[str] = Query(None, description="Column to sort by"),
    sort_dir: str = Query("asc", description="asc or desc"),
    db: Session = Depends(get_db),
):
    rows, total = repo.search_devices(
        db, q=q, category=category, manufacturer=manufacturer,
        technology=technology, limit=limit, offset=offset,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [d.to_dict() for d in rows],
    }


@router.get("/devices/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = repo.get_device(db, device_id)
    if not device:
        raise HTTPException(404, "Device not found in catalog")
    return device.to_dict(include_specs=True)


@router.get("/devices/{device_id}/vulns")
def get_device_vulns(device_id: int, db: Session = Depends(get_db)):
    device = repo.get_device(db, device_id)
    if not device:
        raise HTTPException(404, "Device not found in catalog")
    return repo.get_device_vulnerabilities(db, device_id)


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

@router.get("/devices/export/csv")
def export_catalog_csv(
    q:            Optional[str] = Query(None),
    category:     Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    technology:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Stream all matching catalog devices as CSV (respects active filters)."""
    rows, _ = repo.search_devices(
        db, q=q, category=category, manufacturer=manufacturer,
        technology=technology, limit=100_000, offset=0,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "manufacturer_name", "model_name", "brand_name", "category_code",
        "category_name", "technology", "source_code", "is_hybrid", "description",
    ])
    for d in rows:
        row = d.to_dict()
        writer.writerow([
            row.get("manufacturer_name", ""),
            row.get("model_name", ""),
            row.get("brand_name", ""),
            row.get("category_code", ""),
            row.get("category_name", ""),
            row.get("technology", ""),
            row.get("source_code", ""),
            "1" if row.get("is_hybrid") is True else ("0" if row.get("is_hybrid") is False else ""),
            row.get("description", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=solar_catalog.csv"},
    )


# ---------------------------------------------------------------------------
# CSV Import (custom / user-added devices)
# ---------------------------------------------------------------------------

@router.post("/devices/import/csv")
async def import_catalog_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Add custom devices to the catalog from a CSV file.
    Required columns: manufacturer_name, model_name, category_code
    Optional: brand_name, technology, description, source_code, is_hybrid
    """
    from app.models.solar_catalog import (
        CatalogManufacturer, CatalogCategory, CatalogDataSource, CatalogDevice,
    )
    content = await file.read()
    text    = content.decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(text))

    # Resolve / create a "custom" data source once
    source = db.query(CatalogDataSource).filter(CatalogDataSource.source_code == "custom").first()
    if not source:
        source = CatalogDataSource(source_code="custom", source_name="Custom Import", source_url=None)
        db.add(source)
        db.flush()

    created = 0
    errors  = []
    for i, row in enumerate(reader, start=2):
        mfr_name  = (row.get("manufacturer_name") or "").strip()
        model     = (row.get("model_name")         or "").strip()
        cat_code  = (row.get("category_code")      or "").strip()
        if not mfr_name or not model or not cat_code:
            errors.append(f"Row {i}: manufacturer_name, model_name, category_code are required")
            continue

        # Category must exist
        cat = db.query(CatalogCategory).filter(CatalogCategory.category_code == cat_code).first()
        if not cat:
            errors.append(f"Row {i}: unknown category_code '{cat_code}'")
            continue

        # Find or create manufacturer
        mfr = db.query(CatalogManufacturer).filter(
            CatalogManufacturer.manufacturer_name.ilike(mfr_name)
        ).first()
        if not mfr:
            mfr = CatalogManufacturer(manufacturer_name=mfr_name)
            db.add(mfr)
            db.flush()

        is_hybrid_raw = (row.get("is_hybrid") or "").strip().lower()
        is_hybrid = True if is_hybrid_raw in ("1","true","yes") else (False if is_hybrid_raw in ("0","false","no") else None)

        try:
            device = CatalogDevice(
                category_id=cat.id,
                source_id=source.id,
                manufacturer_id=mfr.id,
                model_name=model,
                brand_name=(row.get("brand_name") or "").strip() or None,
                technology=(row.get("technology") or "").strip() or None,
                description=(row.get("description") or "").strip() or None,
                is_hybrid=is_hybrid,
            )
            db.add(device)
            db.flush()
            created += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            errors.append(f"Row {i}: {exc}")

    db.commit()
    return {"created": created, "errors": errors}


# ---------------------------------------------------------------------------
# Vulnerabilities
# ---------------------------------------------------------------------------

@router.get("/vulnerabilities")
def list_vulnerabilities(db: Session = Depends(get_db)):
    vulns = repo.list_vulnerabilities(db)
    result = []
    for v in vulns:
        d = v.to_dict()
        d["matches"] = [m.to_dict() for m in v.matches]
        result.append(d)
    return result
