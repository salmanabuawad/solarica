"""
Repository for the solar equipment catalog.

Bulk import uses raw PostgreSQL COPY for performance (607K+ spec rows).
All search/query functions work on the already-loaded catalog.
"""
from __future__ import annotations

import csv
import io
import os
import logging
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from app.models.solar_catalog import (
    CatalogDataSource, CatalogCategory, CatalogManufacturer,
    CatalogDevice, CatalogSpec, CatalogVulnerability, CatalogVulnMatch,
)

logger = logging.getLogger(__name__)

# Path to solar_db_dump_real folder (relative to this file: ../../../../device_repo/...)
_DUMP_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",                    # /opt/solarica/
    "device_repo", "device_repository", "solar_db_dump_real",
))


# ---------------------------------------------------------------------------
# Catalog status / stats
# ---------------------------------------------------------------------------

def get_catalog_stats(db: Session) -> dict:
    device_count = db.query(func.count(CatalogDevice.id)).scalar() or 0
    spec_count = db.query(func.count(CatalogSpec.id)).scalar() or 0
    mfr_count = db.query(func.count(CatalogManufacturer.id)).scalar() or 0
    vuln_count = db.query(func.count(CatalogVulnerability.id)).scalar() or 0

    by_category = (
        db.query(CatalogCategory.category_code, func.count(CatalogDevice.id))
        .join(CatalogDevice, CatalogDevice.category_id == CatalogCategory.id, isouter=True)
        .group_by(CatalogCategory.category_code)
        .all()
    )

    return {
        "loaded": device_count > 0,
        "device_count": device_count,
        "spec_count": spec_count,
        "manufacturer_count": mfr_count,
        "vulnerability_count": vuln_count,
        "by_category": {row[0]: row[1] for row in by_category},
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_devices(
    db: Session,
    q: Optional[str] = None,
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
    technology: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
) -> tuple[list[CatalogDevice], int]:
    """
    Full-text-style search. Returns (rows, total_count).
    """
    query = (
        db.query(CatalogDevice)
        .join(CatalogDevice.category)
        .join(CatalogDevice.manufacturer)
        .join(CatalogDevice.source)
    )

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            CatalogDevice.model_name.ilike(pattern)
            | CatalogManufacturer.manufacturer_name.ilike(pattern)
            | CatalogDevice.description.ilike(pattern)
        )
    if category:
        query = query.filter(CatalogCategory.category_code == category)
    if manufacturer:
        query = query.filter(CatalogManufacturer.manufacturer_name.ilike(f"%{manufacturer}%"))
    if technology:
        query = query.filter(CatalogDevice.technology.ilike(f"%{technology}%"))

    total = query.count()

    _sort_map = {
        "manufacturer_name": CatalogManufacturer.manufacturer_name,
        "model_name":        CatalogDevice.model_name,
        "brand_name":        CatalogDevice.brand_name,
        "category_name":     CatalogCategory.category_code,
        "technology":        CatalogDevice.technology,
        "source_code":       CatalogDataSource.source_code,
    }
    sort_col = _sort_map.get(sort_by or "manufacturer_name", CatalogManufacturer.manufacturer_name)
    order_expr = sort_col.desc() if sort_dir == "desc" else sort_col.asc()
    secondary = CatalogDevice.model_name.asc() if sort_by and sort_by != "model_name" else CatalogManufacturer.manufacturer_name.asc()

    rows = (
        query
        .order_by(order_expr, secondary)
        .limit(limit)
        .offset(offset)
        .all()
    )
    return rows, total


def get_device(db: Session, device_id: int) -> Optional[CatalogDevice]:
    return (
        db.query(CatalogDevice)
        .options(
            joinedload(CatalogDevice.category),
            joinedload(CatalogDevice.manufacturer),
            joinedload(CatalogDevice.source),
            joinedload(CatalogDevice.specs),
        )
        .filter(CatalogDevice.id == device_id)
        .first()
    )


def list_manufacturers(
    db: Session,
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = (
        db.query(
            CatalogManufacturer.manufacturer_name,
            func.count(CatalogDevice.id).label("device_count"),
        )
        .join(CatalogDevice, CatalogDevice.manufacturer_id == CatalogManufacturer.id, isouter=True)
    )
    if q:
        query = query.filter(CatalogManufacturer.manufacturer_name.ilike(f"%{q}%"))
    if category:
        query = (
            query
            .join(CatalogCategory, CatalogCategory.id == CatalogDevice.category_id, isouter=True)
            .filter(CatalogCategory.category_code == category)
        )
    rows = (
        query
        .group_by(CatalogManufacturer.manufacturer_name)
        .order_by(CatalogManufacturer.manufacturer_name)
        .limit(limit)
        .all()
    )
    return [{"manufacturer_name": r[0], "device_count": r[1]} for r in rows]


def list_categories(db: Session) -> list[CatalogCategory]:
    return db.query(CatalogCategory).order_by(CatalogCategory.category_name).all()


def list_vulnerabilities(db: Session) -> list[CatalogVulnerability]:
    return (
        db.query(CatalogVulnerability)
        .options(joinedload(CatalogVulnerability.matches))
        .order_by(CatalogVulnerability.published_date.desc())
        .all()
    )


def get_device_vulnerabilities(db: Session, device_id: int) -> list[dict]:
    """
    Find CVEs that match this device via manufacturer ILIKE + model ILIKE patterns.
    Mirrors the vw_device_vulnerabilities SQL view.
    """
    device = get_device(db, device_id)
    if not device:
        return []

    mfr_name = device.manufacturer.manufacturer_name if device.manufacturer else ""
    model_name = device.model_name

    matches_q = db.query(CatalogVulnMatch).options(joinedload(CatalogVulnMatch.vulnerability)).all()

    results = []
    for match in matches_q:
        mfr_pat = (match.manufacturer_pattern or "").replace("%", "")
        model_pat = (match.model_pattern or "").replace("%", "")
        if mfr_pat.lower() in mfr_name.lower() and model_pat.lower() in model_name.lower():
            v = match.vulnerability
            results.append({
                **v.to_dict(),
                "match_notes": match.notes,
            })

    return results


# ---------------------------------------------------------------------------
# Bulk import from CSV files
# ---------------------------------------------------------------------------

def _csv_path(filename: str) -> str:
    return os.path.join(_DUMP_DIR, filename)


def _read_csv(filename: str) -> list[dict]:
    path = _csv_path(filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_optional_str(val: str) -> Optional[str]:
    return val.strip() if val and val.strip() else None


def _parse_optional_float(val: str) -> Optional[float]:
    try:
        return float(val) if val and val.strip() else None
    except ValueError:
        return None


def _parse_optional_bool(val: str) -> Optional[bool]:
    if val and val.strip().lower() in ("true", "1", "t"):
        return True
    if val and val.strip().lower() in ("false", "0", "f"):
        return False
    return None


def _parse_optional_date(val: str):
    from datetime import date
    if not val or not val.strip():
        return None
    try:
        return date.fromisoformat(val.strip())
    except ValueError:
        return None


def import_catalog_from_csv(db: Session) -> dict:
    """
    Load solar_db_dump_real CSV files into the catalog tables.
    Idempotent: skips if data already loaded (checks device count).
    Uses batch inserts for performance with 607K+ spec rows.
    """
    existing = db.query(func.count(CatalogDevice.id)).scalar() or 0
    if existing > 0:
        return {"status": "skipped", "reason": f"catalog already loaded ({existing} devices)"}

    if not os.path.exists(_DUMP_DIR):
        return {"status": "error", "reason": f"solar_db_dump_real not found at {_DUMP_DIR}"}

    logger.info("Loading solar catalog from CSV files in %s", _DUMP_DIR)
    counts: dict[str, int] = {}

    # ── Sources ───────────────────────────────────────────────────
    source_map: dict[int, int] = {}  # csv source_id → db id
    for row in _read_csv("sources.csv"):
        src = CatalogDataSource(
            id=int(row["source_id"]),
            source_code=row["source_code"],
            name=row["name"],
            publisher=_parse_optional_str(row.get("publisher", "")),
            source_url=_parse_optional_str(row.get("source_url", "")),
            retrieved_on=_parse_optional_date(row.get("retrieved_on", "")),
            release_date=_parse_optional_date(row.get("release_date", "")),
            notes=_parse_optional_str(row.get("notes", "")),
        )
        db.merge(src)
    db.flush()
    counts["sources"] = db.query(func.count(CatalogDataSource.id)).scalar()

    # ── Categories ────────────────────────────────────────────────
    for row in _read_csv("asset_categories.csv"):
        cat = CatalogCategory(
            id=int(row["category_id"]),
            category_code=row["category_code"],
            category_name=row["category_name"],
        )
        db.merge(cat)
    db.flush()
    counts["categories"] = db.query(func.count(CatalogCategory.id)).scalar()

    # ── Manufacturers ─────────────────────────────────────────────
    for row in _read_csv("manufacturers.csv"):
        mfr = CatalogManufacturer(
            id=int(row["manufacturer_id"]),
            manufacturer_name=row["manufacturer_name"],
        )
        db.merge(mfr)
    db.flush()
    counts["manufacturers"] = db.query(func.count(CatalogManufacturer.id)).scalar()

    # ── Devices (28K rows — batch in groups of 500) ───────────────
    device_rows = _read_csv("device_models.csv")
    BATCH = 500
    for i in range(0, len(device_rows), BATCH):
        batch = device_rows[i : i + BATCH]
        for row in batch:
            dev = CatalogDevice(
                id=int(row["device_id"]),
                category_id=int(row["category_id"]),
                source_id=int(row["source_id"]),
                manufacturer_id=int(row["manufacturer_id"]),
                model_name=row["model_name"],
                brand_name=_parse_optional_str(row.get("brand_name", "")),
                technology=_parse_optional_str(row.get("technology", "")),
                description=_parse_optional_str(row.get("description", "")),
                source_release_date=_parse_optional_date(row.get("source_release_date", "")),
                source_last_update=_parse_optional_date(row.get("source_last_update", "")),
                is_hybrid=_parse_optional_bool(row.get("is_hybrid", "")),
            )
            db.merge(dev)
        db.flush()
        logger.info("Devices: %d / %d loaded", min(i + BATCH, len(device_rows)), len(device_rows))

    counts["devices"] = len(device_rows)

    # ── Specs (607K rows — batch in groups of 2000) ───────────────
    spec_rows = _read_csv("device_specs.csv")
    SPEC_BATCH = 2000
    for i in range(0, len(spec_rows), SPEC_BATCH):
        batch = spec_rows[i : i + SPEC_BATCH]
        for row in batch:
            spec = CatalogSpec(
                id=int(row["spec_id"]),
                device_id=int(row["device_id"]),
                spec_group=row["spec_group"],
                spec_key=row["spec_key"],
                spec_value_text=_parse_optional_str(row.get("spec_value_text", "")),
                spec_value_num=_parse_optional_float(row.get("spec_value_num", "")),
                unit=_parse_optional_str(row.get("unit", "")),
            )
            db.merge(spec)
        db.flush()
        if i % 20000 == 0:
            logger.info("Specs: %d / %d loaded", min(i + SPEC_BATCH, len(spec_rows)), len(spec_rows))

    counts["specs"] = len(spec_rows)

    # ── Vulnerabilities ───────────────────────────────────────────
    for row in _read_csv("vulnerabilities.csv"):
        vuln = CatalogVulnerability(
            id=int(row["vulnerability_id"]),
            cve_id=_parse_optional_str(row.get("cve_id", "")),
            advisory_id=_parse_optional_str(row.get("advisory_id", "")),
            source_name=_parse_optional_str(row.get("source_name", "")),
            title=row["title"],
            severity=_parse_optional_str(row.get("severity", "")),
            cvss_v3=_parse_optional_float(row.get("cvss_v3", "")),
            published_date=_parse_optional_date(row.get("published_date", "")),
            description=_parse_optional_str(row.get("description", "")),
            affected_product=_parse_optional_str(row.get("affected_product", "")),
        )
        db.merge(vuln)
    db.flush()
    counts["vulnerabilities"] = db.query(func.count(CatalogVulnerability.id)).scalar()

    # ── Vulnerability matches ──────────────────────────────────────
    for row in _read_csv("vulnerability_matches.csv"):
        match = CatalogVulnMatch(
            id=int(row["match_id"]),
            vulnerability_id=int(row["vulnerability_id"]),
            manufacturer_pattern=_parse_optional_str(row.get("manufacturer_pattern", "")),
            model_pattern=_parse_optional_str(row.get("model_pattern", "")),
            notes=_parse_optional_str(row.get("notes", "")),
        )
        db.merge(match)
    db.flush()
    counts["vuln_matches"] = db.query(func.count(CatalogVulnMatch.id)).scalar()

    db.commit()
    logger.info("Solar catalog import complete: %s", counts)
    return {"status": "ok", "counts": counts}
