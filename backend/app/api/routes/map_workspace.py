from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project, String as ProjectString, DesignValidationRun
from app.models.task import MaintenanceTask
from app.models.topology import MapZone, ProjectInverter
from app.models.map_workspace import MapLayer, MapObject, MapObjectLink
from app.api.routes.project_files import _read_meta

router = APIRouter()


LAYER_SPECS = [
    ("blocks", "topology", 10, {"stroke": "#1d4ed8", "fill": "rgba(29,78,216,0.08)"}),
    ("zones", "topology", 20, {"stroke": "#0f766e", "fill": "rgba(15,118,110,0.08)"}),
    ("rows", "structural", 30, {"stroke": "#334155"}),
    ("assets", "structural", 40, {"fill": "#2563eb"}),
    ("electrical", "electrical", 50, {"fill": "#7c3aed"}),
    ("storage", "storage", 60, {"fill": "#059669"}),
    ("workflow", "workflow", 70, {"fill": "#f59e0b"}),
    ("qc", "qa", 80, {"fill": "#ef4444"}),
]


def _infer_topology(project: Project, file_names: list[str]) -> str:
    t = (project.project_type or "").lower()
    names = " ".join(file_names).lower()
    if "fpv" in names or "floating" in t or "fpv" in t:
        return "floating_pv"
    if "roof" in t:
        return "rooftop"
    if "fixed" in t:
        return "ground_fixed_tilt"
    return "ground_tracker"


def _infer_energy_system(project: Project, file_names: list[str]) -> str:
    combined = f"{project.name} {project.description or ''} {' '.join(file_names)}".lower()
    if any(k in combined for k in ["bess", "battery", "storage", "mvs", "pcs"]):
        return "pv_plus_storage"
    return "pv_only"


def _status_color(status: str | None) -> str:
    s = (status or "").lower()
    if s in {"completed", "closed", "passed", "verified"}:
        return "#16a34a"
    if s in {"in_progress", "running", "pending"}:
        return "#f59e0b"
    if s in {"failed", "error", "blocked"}:
        return "#ef4444"
    return "#64748b"


def _get_or_create_layers(project_id: int, db: Session) -> dict[str, MapLayer]:
    existing = {l.name: l for l in db.query(MapLayer).filter(MapLayer.project_id == project_id).all()}
    changed = False
    for idx, (name, layer_type, z, style) in enumerate(LAYER_SPECS):
        if name not in existing:
            layer = MapLayer(
                project_id=project_id,
                name=name,
                layer_type=layer_type,
                is_visible_default=True,
                z_index=z,
                style_json=style,
            )
            db.add(layer)
            db.flush()
            existing[name] = layer
            changed = True
    if changed:
        db.commit()
    return existing


def _upsert_object(db: Session, project_id: int, uid: str, **kwargs: Any) -> MapObject:
    obj = db.query(MapObject).filter(MapObject.project_id == project_id, MapObject.object_uid == uid).first()
    if obj is None:
        obj = MapObject(project_id=project_id, object_uid=uid, **kwargs)
        db.add(obj)
        db.flush()
    else:
        for k, v in kwargs.items():
            setattr(obj, k, v)
    return obj


def _bootstrap_workspace(project_id: int, db: Session) -> dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_records = _read_meta(project_id)
    active_files = [f for f in file_records if f.get("is_active", True)]
    active_file_names = [f.get("original_name", "") for f in active_files]
    topology = _infer_topology(project, active_file_names)
    energy_system = _infer_energy_system(project, active_file_names)

    layers = _get_or_create_layers(project_id, db)

    invs = db.query(ProjectInverter).filter(ProjectInverter.project_id == project_id).order_by(ProjectInverter.inverter_label).all()
    strings = db.query(ProjectString).filter(ProjectString.project_id == project_id).order_by(ProjectString.id).all()
    zones = db.query(MapZone).filter(MapZone.project_id == project_id).order_by(MapZone.id).all()
    tasks = db.query(MaintenanceTask).filter(MaintenanceTask.project_id == project_id).order_by(MaintenanceTask.id.desc()).all()
    validation_runs = db.query(DesignValidationRun).filter(DesignValidationRun.project_id == project_id).order_by(DesignValidationRun.id.desc()).all()

    # block object
    _upsert_object(
        db,
        project_id,
        uid=f"project-{project_id}-block",
        layer_id=layers["blocks"].id,
        object_type="project_boundary",
        subtype=topology,
        label=project.name,
        geometry_type="polygon",
        geometry_json={"x": 20, "y": 20, "width": 860, "height": 500},
        properties_json={
            "site_name": project.site_name,
            "topology": topology,
            "energy_system": energy_system,
            "project_type": project.project_type,
        },
        source_ref="project"
    )

    # zone objects
    if zones:
        zone_cols = max(1, math.ceil(math.sqrt(len(zones))))
        zone_w = 180
        zone_h = 90
        for idx, zone in enumerate(zones):
            col = idx % zone_cols
            row = idx // zone_cols
            _upsert_object(
                db,
                project_id,
                uid=f"zone-{zone.id}",
                layer_id=layers["zones"].id,
                object_type="zone",
                subtype="map_zone",
                label=zone.zone_label,
                geometry_type="polygon",
                geometry_json={"x": 40 + col * 200, "y": 50 + row * 110, "width": zone_w, "height": zone_h},
                properties_json={"color_code": zone.color_code, "inverter_label": zone.inverter_label, "notes": zone.notes},
                source_ref="topology.map_zones",
            )
    else:
        # fallback pseudo-zones by topology
        zone_count = 4 if topology == "ground_tracker" else 3
        for idx in range(zone_count):
            label = f"Zone {idx+1}"
            _upsert_object(
                db,
                project_id,
                uid=f"autozone-{idx+1}",
                layer_id=layers["zones"].id,
                object_type="zone",
                subtype="generated_zone",
                label=label,
                geometry_type="polygon",
                geometry_json={"x": 50 + (idx % 2) * 250, "y": 60 + (idx // 2) * 130, "width": 220, "height": 100},
                properties_json={"generated": True},
                source_ref="bootstrap",
            )

    # row / structural objects
    row_count = max(6, min(18, math.ceil(max(len(strings), 1) / 20)))
    if topology == "floating_pv":
        row_prefix = "Float"
        row_object_type = "float_row"
    elif topology == "rooftop":
        row_prefix = "Roof"
        row_object_type = "roof_band"
    else:
        row_prefix = "Row"
        row_object_type = "tracker_row"

    for idx in range(row_count):
        _upsert_object(
            db,
            project_id,
            uid=f"row-{idx+1}",
            layer_id=layers["rows"].id,
            object_type=row_object_type,
            subtype=topology,
            label=f"{row_prefix} {idx+1}",
            geometry_type="line",
            geometry_json={"x1": 60, "y1": 90 + idx * 24, "x2": 840, "y2": 90 + idx * 24},
            properties_json={"generated": True, "index": idx + 1},
            source_ref="bootstrap",
        )

    # electrical / inverter objects
    inv_cols = 4
    for idx, inv in enumerate(invs[:32]):
        col = idx % inv_cols
        row = idx // inv_cols
        layer_name = "electrical"
        subtype = "inverter"
        if energy_system == "pv_plus_storage" and idx < 4 and any(k in " ".join(active_file_names).lower() for k in ["mvs", "bess", "battery"]):
            subtype = "station"
        obj = _upsert_object(
            db,
            project_id,
            uid=f"inverter-{inv.id}",
            layer_id=layers[layer_name].id,
            object_type="electrical_node",
            subtype=subtype,
            label=inv.inverter_label,
            geometry_type="point",
            geometry_json={"cx": 120 + col * 170, "cy": 400 + row * 42},
            properties_json={
                "section_no": inv.section_no,
                "block_no": inv.block_no,
                "icb_zone": inv.icb_zone,
                "expected_string_count": inv.expected_string_count,
                "detected_string_count": inv.detected_string_count,
            },
            source_ref="topology.project_inverters",
        )
        # basic task linking for first matching task
        task = next((t for t in tasks if (t.asset_ref or "") == inv.inverter_label or inv.inverter_label in (t.title or "")), None)
        if task and not db.query(MapObjectLink).filter(MapObjectLink.object_id == obj.id, MapObjectLink.task_id == task.id).first():
            db.add(MapObjectLink(object_id=obj.id, task_id=task.id, link_type="task", note=task.status))

    # storage objects
    if energy_system == "pv_plus_storage":
        storage_count = 6 if topology == "floating_pv" else 4
        for idx in range(storage_count):
            _upsert_object(
                db,
                project_id,
                uid=f"storage-{idx+1}",
                layer_id=layers["storage"].id,
                object_type="storage_unit",
                subtype="battery_container",
                label=f"BESS {idx+1}",
                geometry_type="polygon",
                geometry_json={"x": 650, "y": 70 + idx * 52, "width": 160, "height": 32},
                properties_json={"generated": True},
                source_ref="bootstrap",
            )

    # workflow objects from tasks
    for idx, task in enumerate(tasks[:16]):
        _upsert_object(
            db,
            project_id,
            uid=f"task-{task.id}",
            layer_id=layers["workflow"].id,
            object_type="workflow_item",
            subtype=task.status,
            label=task.title,
            geometry_type="point",
            geometry_json={"cx": 120 + (idx % 4) * 170, "cy": 540 + (idx // 4) * 34},
            properties_json={"status": task.status, "priority": task.priority, "assigned_to": task.assigned_to},
            source_ref="tasks",
        )

    # qc summary objects from latest validation run issues
    latest = validation_runs[0] if validation_runs else None
    if latest and latest.issues:
        severities = defaultdict(int)
        for issue in latest.issues:
            severities[issue.severity] += 1
        x = 650
        order = ["error", "warning", "info"]
        for idx, sev in enumerate(order):
            count = severities.get(sev, 0)
            if count == 0:
                continue
            _upsert_object(
                db,
                project_id,
                uid=f"qc-{sev}",
                layer_id=layers["qc"].id,
                object_type="qc_group",
                subtype=sev,
                label=f"{sev.title()} · {count}",
                geometry_type="point",
                geometry_json={"cx": x, "cy": 420 + idx * 38},
                properties_json={"count": count, "status": sev},
                source_ref="validation",
            )

    db.commit()

    layer_list = db.query(MapLayer).filter(MapLayer.project_id == project_id).order_by(MapLayer.z_index, MapLayer.id).all()
    object_list = db.query(MapObject).filter(MapObject.project_id == project_id).order_by(MapObject.id).all()

    metrics = {
        "active_files": len(active_files),
        "zones": len(zones),
        "inverters": len(invs),
        "strings": len(strings),
        "tasks": len(tasks),
        "open_tasks": len([t for t in tasks if (t.status or '').lower() in {'open', 'in_progress'}]),
        "validation_issues": len(latest.issues) if latest else 0,
        "storage_units": len([o for o in object_list if o.object_type == 'storage_unit']),
    }

    return {
        "project": project.to_dict(),
        "topology": topology,
        "energy_system": energy_system,
        "layers": [l.to_dict() for l in layer_list],
        "objects": [o.to_dict() for o in object_list],
        "metrics": metrics,
        "inspector": {
            "summary": f"{metrics['inverters']} inverters · {metrics['strings']} strings · {metrics['tasks']} tasks",
            "source_files": [f.get('original_name') for f in active_files][:8],
        },
    }


@router.post("/projects/{project_id}/map/bootstrap")
def bootstrap_map(project_id: int, payload: dict | None = None, db: Session = Depends(get_db)):
    force = bool((payload or {}).get("force"))
    if force:
        db.query(MapObjectLink).filter(MapObjectLink.object_id.in_(db.query(MapObject.id).filter(MapObject.project_id == project_id))).delete(synchronize_session=False)
        db.query(MapObject).filter(MapObject.project_id == project_id).delete(synchronize_session=False)
        db.query(MapLayer).filter(MapLayer.project_id == project_id).delete(synchronize_session=False)
        db.commit()
    return _bootstrap_workspace(project_id, db)


@router.get("/projects/{project_id}/map/workspace")
def get_map_workspace(project_id: int, db: Session = Depends(get_db)):
    has_layers = db.query(MapLayer).filter(MapLayer.project_id == project_id).first()
    if not has_layers:
        return _bootstrap_workspace(project_id, db)

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    files = [f.get("original_name", "") for f in _read_meta(project_id) if f.get("is_active", True)]
    topology = _infer_topology(project, files)
    energy_system = _infer_energy_system(project, files)
    layers = db.query(MapLayer).filter(MapLayer.project_id == project_id).order_by(MapLayer.z_index, MapLayer.id).all()
    objects = db.query(MapObject).filter(MapObject.project_id == project_id).order_by(MapObject.id).all()
    tasks = db.query(MaintenanceTask).filter(MaintenanceTask.project_id == project_id).all()
    validations = db.query(DesignValidationRun).filter(DesignValidationRun.project_id == project_id).all()
    return {
        "project": project.to_dict(),
        "topology": topology,
        "energy_system": energy_system,
        "layers": [l.to_dict() for l in layers],
        "objects": [o.to_dict() for o in objects],
        "metrics": {
            "active_files": len(files),
            "objects": len(objects),
            "tasks": len(tasks),
            "open_tasks": len([t for t in tasks if (t.status or '').lower() in {'open', 'in_progress'}]),
            "validation_runs": len(validations),
        },
        "inspector": {"summary": f"{len(objects)} mapped objects"},
    }


@router.get("/projects/{project_id}/map/layers")
def list_layers(project_id: int, db: Session = Depends(get_db)):
    return [l.to_dict() for l in db.query(MapLayer).filter(MapLayer.project_id == project_id).order_by(MapLayer.z_index, MapLayer.id).all()]


@router.get("/projects/{project_id}/map/objects")
def list_objects(project_id: int, db: Session = Depends(get_db)):
    return [o.to_dict() for o in db.query(MapObject).filter(MapObject.project_id == project_id).order_by(MapObject.id).all()]


@router.post("/projects/{project_id}/map/objects")
def create_object(project_id: int, payload: dict, db: Session = Depends(get_db)):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    obj = MapObject(
        project_id=project_id,
        layer_id=payload.get("layer_id"),
        object_uid=payload.get("object_uid") or f"manual-{project_id}-{os.urandom(4).hex()}",
        object_type=payload.get("object_type", "manual_object"),
        subtype=payload.get("subtype"),
        label=payload.get("label"),
        geometry_type=payload.get("geometry_type", "point"),
        geometry_json=payload.get("geometry") or payload.get("geometry_json") or {},
        properties_json=payload.get("properties") or payload.get("properties_json") or {},
        parent_id=payload.get("parent_id"),
        source_ref=payload.get("source_ref", "manual"),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj.to_dict()


@router.patch("/map/objects/{object_id}")
def update_object(object_id: int, payload: dict, db: Session = Depends(get_db)):
    obj = db.query(MapObject).filter(MapObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Map object not found")
    for field, source_key in [("label", "label"), ("subtype", "subtype"), ("geometry_type", "geometry_type"), ("parent_id", "parent_id"), ("source_ref", "source_ref")]:
        if source_key in payload:
            setattr(obj, field, payload[source_key])
    if "layer_id" in payload:
        obj.layer_id = payload["layer_id"]
    if "geometry" in payload or "geometry_json" in payload:
        obj.geometry_json = payload.get("geometry") or payload.get("geometry_json")
    if "properties" in payload or "properties_json" in payload:
        obj.properties_json = payload.get("properties") or payload.get("properties_json")
    db.commit()
    db.refresh(obj)
    return obj.to_dict()


@router.post("/map/objects/{object_id}/link")
def link_object(object_id: int, payload: dict, db: Session = Depends(get_db)):
    obj = db.query(MapObject).filter(MapObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Map object not found")
    link = MapObjectLink(
        object_id=object_id,
        asset_id=payload.get("asset_id"),
        task_id=payload.get("task_id"),
        qc_id=payload.get("qc_id"),
        link_type=payload.get("link_type"),
        note=payload.get("note"),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link.to_dict()
