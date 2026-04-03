from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.permissions import require_roles, any_authenticated
from app.repositories import inventory_repo, audit_repo
from app.schemas.inventory import MaterialCreate, MaterialIssueCreate, MaterialIssueRead

router = APIRouter()


class MaterialUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    sku: str | None = None
    min_threshold: float | None = None
    unit_cost: float | None = None


class ConsumeItem(BaseModel):
    material_id: int
    quantity_consumed: float = 0
    quantity_returned: float = 0
    quantity_missing: float = 0


class ResolveFlag(BaseModel):
    reviewer: str


@router.post("/materials")
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse")),
):
    mat = inventory_repo.create_material(db, **payload.model_dump())
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="create_material", entity_type="material", entity_id=mat.id)
    db.commit()
    return mat.to_dict()


@router.get("/materials")
def list_materials(db: Session = Depends(get_db)):
    return [m.to_dict() for m in inventory_repo.list_materials(db)]


@router.patch("/materials/{material_id}")
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse")),
):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    mat = inventory_repo.update_material(db, material_id, **updates)
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="update_material", entity_type="material", entity_id=material_id)
    db.commit()
    return mat.to_dict()


@router.delete("/materials/{material_id}")
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    ok = inventory_repo.delete_material(db, material_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Material not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="delete_material", entity_type="material", entity_id=material_id)
    db.commit()
    return {"deleted": True}


@router.post("/issue", response_model=MaterialIssueRead)
def issue_material(
    payload: MaterialIssueCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse")),
):
    # Resolve material by ID or by name
    items = []
    for item in payload.items:
        mat = None
        if hasattr(item, 'material_id') and item.material_id:
            mat = inventory_repo.get_material(db, item.material_id)
        if not mat and item.material_name:
            all_mats = inventory_repo.list_materials(db)
            mat = next((m for m in all_mats if m.name.lower() == item.material_name.lower()), None)
        if mat:
            items.append({
                "material_id": mat.id,
                "quantity_issued": item.quantity_issued,
                "unit": item.unit or mat.unit,
            })

    # Resolve warehouse by name or create default
    warehouses = inventory_repo.list_warehouses(db)
    wh = next((w for w in warehouses if w.name.lower() == (payload.warehouse_name or "").lower()), None)
    if not wh:
        wh = inventory_repo.create_warehouse(db, name=payload.warehouse_name or "Default Warehouse")

    txn = inventory_repo.create_issue(
        db,
        project_id=payload.project_id,
        warehouse_id=wh.id,
        issued_to_user=payload.issued_to_user,
        issued_by_user=payload.issued_by_user,
        site_name=payload.site_name,
        asset_type=payload.asset_type,
        asset_ref=payload.asset_ref,
        expected_usage_days=payload.expected_usage_days,
        notes=payload.notes,
        items=items,
    )
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="issue_material", entity_type="issue", entity_id=txn.id)
    db.commit()
    return txn.to_dict()


@router.get("/issues")
def list_issues(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    issues = inventory_repo.list_issues(db, project_id=project_id)
    if status:
        issues = [i for i in issues if i.status == status]
    return [t.to_dict() for t in issues]


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    txn = inventory_repo.get_issue(db, issue_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Issue not found")
    return txn.to_dict()


@router.patch("/issues/{issue_id}/consume")
def record_consumption(
    issue_id: int,
    items: list[ConsumeItem],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse", "technician")),
):
    txn = inventory_repo.update_issue_consumption(db, issue_id, [i.model_dump() for i in items])
    if not txn:
        raise HTTPException(status_code=404, detail="Issue not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="record_consumption", entity_type="issue", entity_id=issue_id)
    db.commit()
    return txn.to_dict()


@router.get("/flags")
def list_flags(
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    flags = inventory_repo.list_flags(db, status=status, project_id=project_id)
    return [f.to_dict() for f in flags]


@router.patch("/flags/{flag_id}/resolve")
def resolve_flag(
    flag_id: int,
    payload: ResolveFlag,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    flag = inventory_repo.resolve_flag(db, flag_id, reviewer=payload.reviewer or current_user["username"])
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="resolve_flag", entity_type="flag", entity_id=flag_id)
    db.commit()
    return flag.to_dict()


@router.get("/stock/low")
def get_low_stock(db: Session = Depends(get_db)):
    return inventory_repo.get_low_stock(db)


@router.post("/run-red-flags")
def run_red_flags(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    result = inventory_repo.run_red_flags(db)
    db.commit()
    return result
