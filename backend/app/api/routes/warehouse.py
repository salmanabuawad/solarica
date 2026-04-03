"""
Warehouse management — create warehouses, receive stock, view stock levels.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_roles, any_authenticated
from app.repositories import inventory_repo, audit_repo

router = APIRouter()


class WarehouseCreate(BaseModel):
    name: str
    location: str | None = None
    manager_name: str | None = None
    project_id: int | None = None


class StockReceive(BaseModel):
    material_id: int
    quantity: float


@router.get("")
def list_warehouses(db: Session = Depends(get_db)):
    return [w.to_dict() for w in inventory_repo.list_warehouses(db)]


@router.post("")
def create_warehouse(
    payload: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse")),
):
    wh = inventory_repo.create_warehouse(
        db,
        name=payload.name,
        project_id=payload.project_id,
        location=payload.location,
        manager_name=payload.manager_name,
    )
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="create_warehouse", entity_type="warehouse", entity_id=wh.id)
    db.commit()
    return wh.to_dict()


@router.get("/{warehouse_id}/stock")
def get_stock(warehouse_id: int, db: Session = Depends(get_db)):
    wh = inventory_repo.get_warehouse(db, warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return [s.to_dict() for s in inventory_repo.get_stock_for_warehouse(db, warehouse_id)]


@router.post("/{warehouse_id}/receive")
def receive_stock(
    warehouse_id: int,
    payload: StockReceive,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse")),
):
    wh = inventory_repo.get_warehouse(db, warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    stock = inventory_repo.receive_stock(db, warehouse_id, payload.material_id, payload.quantity)
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="receive_stock", entity_type="warehouse", entity_id=warehouse_id,
                          detail=f"material_id={payload.material_id} qty={payload.quantity}")
    db.commit()
    return stock.to_dict()


class WarehouseUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    manager_name: str | None = None
    project_id: int | None = None


@router.patch("/{warehouse_id}")
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "warehouse")),
):
    wh = inventory_repo.get_warehouse(db, warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    for k, v in updates.items():
        setattr(wh, k, v)
    db.commit()
    return wh.to_dict()


@router.delete("/{warehouse_id}")
def delete_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    wh = inventory_repo.get_warehouse(db, warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    db.delete(wh)
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="delete_warehouse", entity_type="warehouse", entity_id=warehouse_id)
    db.commit()
    return {"deleted": True}


@router.get("/{warehouse_id}/transactions")
def get_warehouse_transactions(warehouse_id: int, db: Session = Depends(get_db)):
    from app.models.inventory import MaterialIssueTransaction
    txns = (db.query(MaterialIssueTransaction)
            .filter(MaterialIssueTransaction.warehouse_id == warehouse_id)
            .order_by(MaterialIssueTransaction.issued_at.desc())
            .all())
    return [t.to_dict() for t in txns]
