"""
Repository functions for the device inventory (device_repo).
Handles DeviceSite, DeviceInventory, DeviceSpec, DeviceCVE, DeviceVulnLink.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.device_repo import (
    DeviceSite, DeviceInventory, DeviceSpec, DeviceCVE, DeviceVulnLink
)


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

def list_sites(db: Session) -> list[DeviceSite]:
    return (
        db.query(DeviceSite)
        .options(joinedload(DeviceSite.devices))
        .order_by(DeviceSite.site_name)
        .all()
    )


def get_site(db: Session, site_id: int) -> Optional[DeviceSite]:
    return (
        db.query(DeviceSite)
        .options(joinedload(DeviceSite.devices))
        .filter(DeviceSite.id == site_id)
        .first()
    )


def create_site(db: Session, site_name: str, country: str = None,
                region: str = None, source_notes: str = None) -> DeviceSite:
    site = DeviceSite(
        site_name=site_name,
        country=country,
        region=region,
        source_notes=source_notes,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def list_devices(
    db: Session,
    site_id: Optional[int] = None,
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
) -> list[DeviceInventory]:
    q = (
        db.query(DeviceInventory)
        .options(
            joinedload(DeviceInventory.site),
            joinedload(DeviceInventory.specs),
            joinedload(DeviceInventory.vuln_links).joinedload(DeviceVulnLink.vuln),
        )
    )
    if site_id:
        q = q.filter(DeviceInventory.site_id == site_id)
    if category:
        q = q.filter(DeviceInventory.category == category)
    if manufacturer:
        q = q.filter(DeviceInventory.manufacturer.ilike(f"%{manufacturer}%"))
    return q.order_by(DeviceInventory.site_id, DeviceInventory.id).all()


def get_device(db: Session, device_id: int) -> Optional[DeviceInventory]:
    return (
        db.query(DeviceInventory)
        .options(
            joinedload(DeviceInventory.site),
            joinedload(DeviceInventory.specs),
            joinedload(DeviceInventory.vuln_links).joinedload(DeviceVulnLink.vuln),
        )
        .filter(DeviceInventory.id == device_id)
        .first()
    )


def create_device(db: Session, **kwargs) -> DeviceInventory:
    device = DeviceInventory(**kwargs)
    db.add(device)
    db.commit()
    db.refresh(device)
    return get_device(db, device.id)


def update_device(db: Session, device_id: int, **kwargs) -> Optional[DeviceInventory]:
    device = db.query(DeviceInventory).filter(DeviceInventory.id == device_id).first()
    if not device:
        return None
    for k, v in kwargs.items():
        if hasattr(device, k) and v is not None:
            setattr(device, k, v)
    db.commit()
    return get_device(db, device_id)


def delete_device(db: Session, device_id: int) -> bool:
    device = db.query(DeviceInventory).filter(DeviceInventory.id == device_id).first()
    if not device:
        return False
    db.delete(device)
    db.commit()
    return True


def delete_devices_bulk(db: Session, device_ids: list[int]) -> int:
    """Delete multiple devices by ID. Returns count of deleted rows."""
    count = db.query(DeviceInventory).filter(DeviceInventory.id.in_(device_ids)).delete(synchronize_session="fetch")
    db.commit()
    return count


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

def list_specs(db: Session, device_id: int) -> list[DeviceSpec]:
    return (
        db.query(DeviceSpec)
        .filter(DeviceSpec.device_id == device_id)
        .order_by(DeviceSpec.spec_key)
        .all()
    )


def upsert_spec(db: Session, device_id: int, spec_key: str,
                spec_value: str, source_note: str = None) -> DeviceSpec:
    spec = (
        db.query(DeviceSpec)
        .filter(DeviceSpec.device_id == device_id, DeviceSpec.spec_key == spec_key)
        .first()
    )
    if spec:
        spec.spec_value = spec_value
        if source_note:
            spec.source_note = source_note
    else:
        spec = DeviceSpec(
            device_id=device_id,
            spec_key=spec_key,
            spec_value=spec_value,
            source_note=source_note,
        )
        db.add(spec)
    db.commit()
    db.refresh(spec)
    return spec


# ---------------------------------------------------------------------------
# CVEs
# ---------------------------------------------------------------------------

def list_cves(
    db: Session,
    manufacturer: Optional[str] = None,
    severity: Optional[str] = None,
) -> list[DeviceCVE]:
    q = db.query(DeviceCVE).options(joinedload(DeviceCVE.device_links))
    if manufacturer:
        q = q.filter(DeviceCVE.manufacturer.ilike(f"%{manufacturer}%"))
    if severity:
        q = q.filter(DeviceCVE.severity.ilike(severity))
    return q.order_by(DeviceCVE.severity, DeviceCVE.cve_id).all()


def get_cve(db: Session, cve_id: int) -> Optional[DeviceCVE]:
    return (
        db.query(DeviceCVE)
        .options(joinedload(DeviceCVE.device_links).joinedload(DeviceVulnLink.device))
        .filter(DeviceCVE.id == cve_id)
        .first()
    )


def get_cve_by_code(db: Session, cve_code: str) -> Optional[DeviceCVE]:
    return db.query(DeviceCVE).filter(DeviceCVE.cve_id == cve_code).first()


def create_cve(db: Session, **kwargs) -> DeviceCVE:
    cve = DeviceCVE(**kwargs)
    db.add(cve)
    db.commit()
    db.refresh(cve)
    return cve


# ---------------------------------------------------------------------------
# Device ↔ CVE links
# ---------------------------------------------------------------------------

def link_device_to_cve(
    db: Session,
    device_id: int,
    vuln_id: int,
    relationship_type: str = "direct",
) -> DeviceVulnLink:
    existing = (
        db.query(DeviceVulnLink)
        .filter(DeviceVulnLink.device_id == device_id, DeviceVulnLink.vuln_id == vuln_id)
        .first()
    )
    if existing:
        return existing
    lnk = DeviceVulnLink(device_id=device_id, vuln_id=vuln_id, relationship_type=relationship_type)
    db.add(lnk)
    db.commit()
    db.refresh(lnk)
    return lnk


def unlink_device_from_cve(db: Session, device_id: int, vuln_id: int) -> bool:
    lnk = (
        db.query(DeviceVulnLink)
        .filter(DeviceVulnLink.device_id == device_id, DeviceVulnLink.vuln_id == vuln_id)
        .first()
    )
    if not lnk:
        return False
    db.delete(lnk)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Seed from repository.json
# ---------------------------------------------------------------------------

_REPO_JSON = os.path.join(
    os.path.dirname(__file__),          # repositories/
    "..", "..", "..",                    # /opt/solarica/
    "device_repo", "device_repository", "repository.json",
)


def seed_from_repository_json(db: Session) -> dict:
    """
    Load device_repo/device_repository/repository.json into the DB.
    Idempotent — skips records that already exist.
    """
    json_path = os.path.normpath(_REPO_JSON)
    if not os.path.exists(json_path):
        return {"status": "skipped", "reason": "repository.json not found", "path": json_path}

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    site_map: dict[int, int] = {}   # original site_id → DB id
    device_map: dict[int, int] = {} # original device_id → DB id
    vuln_map: dict[int, int] = {}   # original vuln_id → DB id

    sites_added = 0
    devices_added = 0
    specs_added = 0
    vulns_added = 0
    links_added = 0

    # ── Sites ────────────────────────────────────────────────────
    for s in data.get("sites", []):
        existing = db.query(DeviceSite).filter(DeviceSite.site_name == s["site_name"]).first()
        if existing:
            site_map[s["site_id"]] = existing.id
        else:
            site = DeviceSite(
                site_name=s["site_name"],
                country=s.get("country"),
                region=s.get("region"),
                source_notes=s.get("source_notes"),
            )
            db.add(site)
            db.flush()
            site_map[s["site_id"]] = site.id
            sites_added += 1

    db.flush()

    # ── Devices ──────────────────────────────────────────────────
    for d in data.get("devices", []):
        db_site_id = site_map.get(d["site_id"])
        if db_site_id is None:
            continue

        existing = (
            db.query(DeviceInventory)
            .filter(
                DeviceInventory.site_id == db_site_id,
                DeviceInventory.model_normalized == d.get("model_normalized"),
                DeviceInventory.category == d["category"],
            )
            .first()
        )
        if existing:
            device_map[d["device_id"]] = existing.id
        else:
            dev = DeviceInventory(
                site_id=db_site_id,
                area=d.get("area"),
                category=d["category"],
                manufacturer=d.get("manufacturer"),
                model_raw=d.get("model_raw"),
                model_normalized=d.get("model_normalized"),
                quantity=d.get("quantity"),
                unit=d.get("unit", "ea"),
                is_exact_model_confirmed=bool(d.get("is_exact_model_confirmed", 0)),
                role=d.get("role"),
                source_notes=d.get("source_notes"),
            )
            db.add(dev)
            db.flush()
            device_map[d["device_id"]] = dev.id
            devices_added += 1

    db.flush()

    # ── Specs ────────────────────────────────────────────────────
    for sp in data.get("device_specs", []):
        db_device_id = device_map.get(sp["device_id"])
        if db_device_id is None:
            continue
        existing = (
            db.query(DeviceSpec)
            .filter(DeviceSpec.device_id == db_device_id, DeviceSpec.spec_key == sp["spec_key"])
            .first()
        )
        if not existing:
            db.add(DeviceSpec(
                device_id=db_device_id,
                spec_key=sp["spec_key"],
                spec_value=sp["spec_value"],
                source_note=sp.get("source_note"),
            ))
            specs_added += 1

    db.flush()

    # ── Vulnerabilities ──────────────────────────────────────────
    for v in data.get("vulnerabilities", []):
        existing = db.query(DeviceCVE).filter(DeviceCVE.cve_id == v.get("cve_id")).first()
        if existing:
            vuln_map[v["vuln_id"]] = existing.id
        else:
            cve = DeviceCVE(
                manufacturer=v.get("manufacturer"),
                product_scope=v["product_scope"],
                cve_id=v.get("cve_id"),
                title=v["title"],
                severity=v.get("severity"),
                affected_versions=v.get("affected_versions"),
                fixed_versions=v.get("fixed_versions"),
                advisory_source=v.get("advisory_source"),
                applicability=v.get("applicability", "unknown"),
                notes=v.get("notes"),
            )
            db.add(cve)
            db.flush()
            vuln_map[v["vuln_id"]] = cve.id
            vulns_added += 1

    db.flush()

    # ── Device–CVE links (auto-link by manufacturer) ─────────────
    # Link each CVE to devices from matching manufacturer
    all_cves = db.query(DeviceCVE).all()
    all_devs = db.query(DeviceInventory).all()

    for cve in all_cves:
        if not cve.manufacturer:
            continue
        for dev in all_devs:
            if dev.manufacturer and dev.manufacturer.lower() == cve.manufacturer.lower():
                existing_lnk = (
                    db.query(DeviceVulnLink)
                    .filter(DeviceVulnLink.device_id == dev.id, DeviceVulnLink.vuln_id == cve.id)
                    .first()
                )
                if not existing_lnk:
                    applicability = cve.applicability or "unknown"
                    rel_type = (
                        "direct" if applicability == "direct_if_firmware_matches"
                        else "adjacent" if "adjacent" in applicability
                        else "indirect"
                    )
                    db.add(DeviceVulnLink(
                        device_id=dev.id,
                        vuln_id=cve.id,
                        relationship_type=rel_type,
                    ))
                    links_added += 1

    db.commit()

    return {
        "status": "ok",
        "sites_added": sites_added,
        "devices_added": devices_added,
        "specs_added": specs_added,
        "vulns_added": vulns_added,
        "links_added": links_added,
    }
