"""
Topology API routes — manage map zones and query stored topology.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.topology import MapZone, ProjectInverter, ProjectMPPT

router = APIRouter()


# ── Map Zones ────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/topology/zones")
def list_zones(project_id: int, db: Session = Depends(get_db)):
    zones = db.query(MapZone).filter(MapZone.project_id == project_id).all()
    return [z.to_dict() for z in zones]


@router.post("/projects/{project_id}/topology/zones")
def create_zone(project_id: int, payload: dict, db: Session = Depends(get_db)):
    zone = MapZone(
        project_id=project_id,
        zone_label=payload["zone_label"],
        color_code=payload.get("color_code"),
        inverter_label=payload.get("inverter_label"),
        geometry_ref=payload.get("geometry_ref"),
        notes=payload.get("notes"),
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone.to_dict()


@router.delete("/projects/{project_id}/topology/zones/{zone_id}")
def delete_zone(project_id: int, zone_id: int, db: Session = Depends(get_db)):
    zone = db.query(MapZone).filter(MapZone.id == zone_id, MapZone.project_id == project_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(zone)
    db.commit()
    return {"ok": True}


# ── Inverter Topology ────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/topology/inverters")
def list_inverters(project_id: int, db: Session = Depends(get_db)):
    inverters = db.query(ProjectInverter).filter(ProjectInverter.project_id == project_id).all()
    return [i.to_dict() for i in inverters]


@router.post("/projects/{project_id}/topology/inverters/sync")
def sync_inverters(project_id: int, payload: dict, db: Session = Depends(get_db)):
    """Sync inverter topology from scan result (upsert by label)."""
    inverters_data = payload.get("inverters", [])
    # Delete existing and re-insert
    db.query(ProjectInverter).filter(ProjectInverter.project_id == project_id).delete()
    for inv in inverters_data:
        parts = inv["raw_name"].split(".")
        obj = ProjectInverter(
            project_id=project_id,
            inverter_label=inv["raw_name"],
            section_no=int(parts[0]) if len(parts) >= 2 else None,
            block_no=int(parts[1]) if len(parts) >= 2 else None,
            detected_string_count=inv.get("strings_count", 0),
            detection_pattern=inv.get("pattern"),
            is_inferred=inv.get("pattern") in ("inferred", "gap_fill"),
        )
        db.add(obj)
    db.commit()
    return {"synced": len(inverters_data)}


@router.patch("/projects/{project_id}/topology/inverters/{label}")
def update_inverter(project_id: int, label: str, payload: dict, db: Session = Depends(get_db)):
    inv = db.query(ProjectInverter).filter(
        ProjectInverter.project_id == project_id,
        ProjectInverter.inverter_label == label,
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Inverter not found")
    for field in ("icb_zone", "color_group", "expected_string_count"):
        if field in payload:
            setattr(inv, field, payload[field])
    db.commit()
    db.refresh(inv)
    return inv.to_dict()
