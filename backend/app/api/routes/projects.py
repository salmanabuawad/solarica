from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.permissions import require_roles, any_authenticated
from app.repositories import project_repo, audit_repo
from app.schemas.project import ProjectCreate, ProjectRead, ProjectPhaseUpdate, ProjectActiveUpdate, ValidationRunRead

router = APIRouter()


def _naming_pattern_to_dict(pattern) -> dict:
    return {
        "id": pattern.id,
        "project_id": pattern.project_id,
        "asset_type": pattern.asset_type,
        "pattern_name": pattern.pattern_name,
        "pattern_regex": pattern.pattern_regex,
        "is_active": pattern.is_active,
        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
    }


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    proj = project_repo.create_project(
        db,
        name=payload.name,
        customer_name=payload.customer_name,
        customer_id=payload.customer_id,
        site_name=payload.site_name,
        project_type=payload.project_type,
        description=payload.description,
    )
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="create_project", entity_type="project", entity_id=proj.id,
                          detail=f"Created project: {proj.name}")
    db.commit()
    return proj.to_dict()


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return [p.to_dict() for p in project_repo.list_projects(db)]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)):
    proj = project_repo.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj.to_dict()


@router.get("/{project_id}/naming-patterns")
def list_naming_patterns(
    project_id: int,
    asset_type: str | None = None,
    db: Session = Depends(get_db),
):
    if project_repo.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    project_repo.ensure_default_string_patterns(db, project_id)
    return [
        _naming_pattern_to_dict(p)
        for p in project_repo.list_naming_patterns(db, project_id, asset_type=asset_type)
    ]


@router.post("/{project_id}/naming-patterns")
def create_naming_pattern(
    project_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    if project_repo.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    asset_type = str(payload.get("asset_type", "")).strip() or "string"
    pattern_name = str(payload.get("pattern_name", "")).strip()
    pattern_regex = str(payload.get("pattern_regex", "")).strip()
    if not pattern_name or not pattern_regex:
        raise HTTPException(status_code=400, detail="pattern_name and pattern_regex are required")
    pattern = project_repo.create_naming_pattern(
        db,
        project_id=project_id,
        asset_type=asset_type,
        pattern_name=pattern_name,
        pattern_regex=pattern_regex,
        is_active=bool(payload.get("is_active", True)),
    )
    audit_repo.log_action(
        db,
        actor_username=current_user["username"],
        actor_role=current_user["role"],
        action="create_naming_pattern",
        entity_type="project",
        entity_id=project_id,
        detail=f"{asset_type}: {pattern_name}",
    )
    db.commit()
    return _naming_pattern_to_dict(pattern)


@router.patch("/{project_id}/naming-patterns/{pattern_id}")
def update_naming_pattern(
    project_id: int,
    pattern_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    pattern = project_repo.update_naming_pattern(
        db,
        project_id,
        pattern_id,
        pattern_name=(str(payload["pattern_name"]).strip() if "pattern_name" in payload else None),
        pattern_regex=(str(payload["pattern_regex"]).strip() if "pattern_regex" in payload else None),
        is_active=payload.get("is_active") if "is_active" in payload else None,
    )
    if not pattern:
        raise HTTPException(status_code=404, detail="Naming pattern not found")
    audit_repo.log_action(
        db,
        actor_username=current_user["username"],
        actor_role=current_user["role"],
        action="update_naming_pattern",
        entity_type="project",
        entity_id=project_id,
        detail=f"{pattern.asset_type}: {pattern.pattern_name}",
    )
    db.commit()
    return _naming_pattern_to_dict(pattern)


@router.delete("/{project_id}/naming-patterns/{pattern_id}")
def delete_naming_pattern(
    project_id: int,
    pattern_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    pattern = project_repo.delete_naming_pattern(db, project_id, pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Naming pattern not found")
    audit_repo.log_action(
        db,
        actor_username=current_user["username"],
        actor_role=current_user["role"],
        action="delete_naming_pattern",
        entity_type="project",
        entity_id=project_id,
        detail=f"{pattern.asset_type}: {pattern.pattern_name}",
    )
    db.commit()
    return {"ok": True}


@router.get("/{project_id}/strings")
def list_project_strings(project_id: int, db: Session = Depends(get_db)):
    """DC strings stored for the project (design model)."""
    from app.models.project import String as ProjectString

    if project_repo.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    rows = (
        db.query(ProjectString)
        .options(joinedload(ProjectString.inverter))
        .filter(ProjectString.project_id == project_id)
        .order_by(ProjectString.id)
        .all()
    )
    out: list[dict] = []
    for s in rows:
        inv_no = s.inverter.inverter_no if s.inverter else None
        out.append({
            "id": s.id,
            "project_id": s.project_id,
            "string_no": s.string_no,
            "status": s.status,
            "inverter_id": s.inverter_id,
            "inverter_no": inv_no,
        })
    return out


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    name = project_repo.delete_project(db, project_id)
    if name is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="delete_project", entity_type="project", entity_id=project_id,
                          detail=f"Deleted project: {name}")
    db.commit()
    return {"ok": True}


@router.patch("/{project_id}/active", response_model=ProjectRead)
def set_project_active(
    project_id: int,
    payload: ProjectActiveUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    proj = project_repo.set_project_active(db, project_id, payload.is_active)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    audit_repo.log_action(
        db,
        actor_username=current_user["username"],
        actor_role=current_user["role"],
        action="set_project_active",
        entity_type="project",
        entity_id=project_id,
        detail=f"is_active={payload.is_active}",
    )
    db.commit()
    return proj.to_dict()


@router.post("/{project_id}/phase", response_model=ProjectRead)
def update_phase(
    project_id: int,
    payload: ProjectPhaseUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    proj = project_repo.update_phase(db, project_id, payload.phase)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="update_phase", entity_type="project", entity_id=project_id,
                          detail=f"Phase → {payload.phase}")
    db.commit()
    return proj.to_dict()


@router.post("/{project_id}/strings/sync")
def sync_strings_from_scan(project_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Bulk-upsert Inverter + String rows from a string-scan result.
    Clears existing design-model rows for this project then re-inserts.
    Expected payload: { inverters: [...], string_rows: [...] }
    """
    from app.models.project import Inverter, String as ProjectString

    if project_repo.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Clear existing
    db.query(ProjectString).filter(ProjectString.project_id == project_id).delete()
    db.query(Inverter).filter(Inverter.project_id == project_id).delete()
    db.flush()

    # Insert inverters
    inv_map: dict[str, Inverter] = {}
    for inv in payload.get("inverters", []):
        obj = Inverter(
            project_id=project_id,
            inverter_no=inv.get("raw_name") or inv.get("normalized_name", ""),
            metadata_json={"pattern": inv.get("pattern"), "strings_count": inv.get("strings_count", 0)},
        )
        db.add(obj)
        db.flush()
        inv_map[obj.inverter_no] = obj

    # Insert strings from valid rows
    inserted = 0
    for row in payload.get("string_rows", []):
        if not row.get("is_valid") or not row.get("string_code"):
            continue
        inv_key = row.get("inverter_key")
        inv_obj = inv_map.get(inv_key) if inv_key else None
        s = ProjectString(
            project_id=project_id,
            inverter_id=inv_obj.id if inv_obj else None,
            string_no=row["string_code"],
            status="planned",
        )
        db.add(s)
        inserted += 1

    db.commit()

    analytics = payload.get("analytics")
    if analytics:
        from app.models.project import Project as ProjectModel
        proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if proj:
            proj.scan_analytics_json = analytics
            db.commit()

    return {"inverters_synced": len(inv_map), "strings_synced": inserted}


@router.patch("/{project_id}/string-pattern", response_model=ProjectRead)
def update_string_pattern(
    project_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    """Set / override the string naming pattern for a project (e.g. 'S.N.N.N')."""
    from app.models.project import Project as ProjectModel
    proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    pattern = payload.get("string_pattern", "")
    proj.string_pattern = pattern.strip() or None
    audit_repo.log_action(
        db,
        actor_username=current_user["username"],
        actor_role=current_user["role"],
        action="update_string_pattern",
        entity_type="project",
        entity_id=project_id,
        detail=f"string_pattern → {proj.string_pattern!r}",
    )
    db.commit()
    db.refresh(proj)
    return proj.to_dict()


@router.get("/{project_id}/scan-analytics")
def get_scan_analytics(project_id: int, db: Session = Depends(get_db)):
    """Return the last stored scan analytics for a project."""
    from app.models.project import Project as ProjectModel
    proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj.scan_analytics_json or {}


@router.post("/{project_id}/compare-design-output")
def compare_design_output(project_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Compare the stored design topology (from DB) against an operational output structure.

    Payload: { "output": { "inverters": [{"id": "1.1", "strings": ["S.1.1.1", ...]}, ...] } }
    Returns: { "status": "match"|"mismatch", "missing_inverters": [], "extra_inverters": [],
               "string_mismatches": [{"inverter": "1.1", "missing_strings": [], "extra_strings": []}] }
    """
    from app.models.project import Inverter, String as ProjectString

    # Load design topology from DB
    design_inverters = db.query(Inverter).filter(
        Inverter.project_id == project_id
    ).all()
    design_strings = db.query(ProjectString).filter(
        ProjectString.project_id == project_id
    ).all()

    if not design_inverters:
        raise HTTPException(status_code=404, detail="No design topology found. Run a string scan first.")

    # Build design maps
    design_inv_labels = {inv.inverter_no for inv in design_inverters}
    design_strings_by_inv: dict = {}
    for s in design_strings:
        inv_obj = s.inverter
        inv_no = inv_obj.inverter_no if inv_obj else None
        if inv_no:
            design_strings_by_inv.setdefault(inv_no, set()).add(s.string_no)

    # Parse output structure
    output_data = payload.get("output", {})
    output_inverters = output_data.get("inverters", [])
    output_inv_labels = {inv.get("id", "") for inv in output_inverters}
    output_strings_by_inv = {
        inv.get("id", ""): set(inv.get("strings", []))
        for inv in output_inverters
    }

    # Compare
    missing_inverters = sorted(design_inv_labels - output_inv_labels)
    extra_inverters = sorted(output_inv_labels - design_inv_labels)

    string_mismatches = []
    for inv_label in sorted(design_inv_labels & output_inv_labels):
        design_strs = design_strings_by_inv.get(inv_label, set())
        output_strs = output_strings_by_inv.get(inv_label, set())
        missing = sorted(design_strs - output_strs)
        extra = sorted(output_strs - design_strs)
        if missing or extra:
            string_mismatches.append({
                "inverter": inv_label,
                "missing_strings": list(missing),
                "extra_strings": list(extra),
            })

    status = "match" if not missing_inverters and not extra_inverters and not string_mismatches else "mismatch"

    return {
        "status": status,
        "design_inverter_count": len(design_inv_labels),
        "output_inverter_count": len(output_inv_labels),
        "missing_inverters": missing_inverters,
        "extra_inverters": extra_inverters,
        "string_mismatches": string_mismatches,
    }


@router.post("/{project_id}/validate-design", response_model=ValidationRunRead)
def validate_design(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(any_authenticated()),
):
    result = project_repo.validate_design(
        db, project_id,
        actor_username=current_user.get("username", "system"),
        actor_role=current_user.get("role", "system"),
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="validate_design", entity_type="project", entity_id=project_id,
                          detail=f"Validation: {result['status']}")
    db.commit()
    return result
