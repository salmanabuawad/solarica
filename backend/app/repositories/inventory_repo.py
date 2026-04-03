from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.inventory import (
    Material, Warehouse, WarehouseStock,
    MaterialIssueTransaction, MaterialIssueItem, InventoryVarianceFlag
)


# ── Materials ────────────────────────────────────────────────────────────────

def list_materials(db: Session) -> list[Material]:
    return db.query(Material).order_by(Material.id).all()


def get_material(db: Session, material_id: int) -> Material | None:
    return db.query(Material).filter(Material.id == material_id).first()


def create_material(db: Session, **kwargs) -> Material:
    m = Material(**kwargs)
    db.add(m)
    db.flush()
    return m


# ── Warehouses ───────────────────────────────────────────────────────────────

def list_warehouses(db: Session) -> list[Warehouse]:
    return db.query(Warehouse).order_by(Warehouse.id).all()


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    return db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()


def create_warehouse(db: Session, *, name: str, project_id: int | None = None,
                     location: str | None = None, manager_name: str | None = None) -> Warehouse:
    wh = Warehouse(name=name, project_id=project_id, location=location, manager_name=manager_name)
    db.add(wh)
    db.flush()
    return wh


def receive_stock(db: Session, warehouse_id: int, material_id: int, quantity: float) -> WarehouseStock:
    stock = (db.query(WarehouseStock)
             .filter(WarehouseStock.warehouse_id == warehouse_id, WarehouseStock.material_id == material_id)
             .first())
    if stock:
        stock.quantity_available = float(stock.quantity_available) + quantity
        stock.last_updated = datetime.now(timezone.utc)
    else:
        stock = WarehouseStock(warehouse_id=warehouse_id, material_id=material_id, quantity_available=quantity)
        db.add(stock)
    db.flush()
    return stock


def get_stock_for_warehouse(db: Session, warehouse_id: int) -> list[WarehouseStock]:
    return (db.query(WarehouseStock)
            .filter(WarehouseStock.warehouse_id == warehouse_id)
            .all())


# ── Issue Transactions ───────────────────────────────────────────────────────

def list_issues(db: Session, project_id: int | None = None) -> list[MaterialIssueTransaction]:
    q = db.query(MaterialIssueTransaction)
    if project_id is not None:
        q = q.filter(MaterialIssueTransaction.project_id == project_id)
    return q.order_by(MaterialIssueTransaction.id.desc()).all()


def get_issue(db: Session, issue_id: int) -> MaterialIssueTransaction | None:
    return db.query(MaterialIssueTransaction).filter(MaterialIssueTransaction.id == issue_id).first()


def create_issue(db: Session, *, project_id: int, warehouse_id: int, issued_to_user: str | None = None,
                 issued_by_user: str | None = None, site_name: str | None = None,
                 asset_type: str | None = None, asset_ref: str | None = None,
                 expected_usage_days: int = 30, notes: str | None = None,
                 items: list[dict] | None = None) -> MaterialIssueTransaction:
    txn = MaterialIssueTransaction(
        project_id=project_id,
        warehouse_id=warehouse_id,
        issued_to_user=issued_to_user,
        issued_by_user=issued_by_user,
        site_name=site_name,
        asset_type=asset_type,
        asset_ref=asset_ref,
        expected_usage_by_date=datetime.now(timezone.utc) + timedelta(days=expected_usage_days),
        notes=notes,
        status="issued",
    )
    db.add(txn)
    db.flush()

    for it in (items or []):
        mat = get_material(db, it.get("material_id") or 0)
        issue_item = MaterialIssueItem(
            transaction_id=txn.id,
            material_id=it.get("material_id") or mat.id if mat else 0,
            quantity_issued=it.get("quantity_issued", 0),
            unit=it.get("unit"),
        )
        db.add(issue_item)

    db.flush()
    db.refresh(txn)
    return txn


def run_red_flags(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    created = []
    overdue = (db.query(MaterialIssueTransaction)
               .filter(MaterialIssueTransaction.status == "issued",
                       MaterialIssueTransaction.expected_usage_by_date < now)
               .all())
    for txn in overdue:
        total_consumed = sum(float(i.quantity_consumed) for i in txn.items)
        if total_consumed <= 0:
            for item in txn.items:
                flag = InventoryVarianceFlag(
                    transaction_id=txn.id,
                    material_id=item.material_id,
                    expected_quantity=float(item.quantity_issued),
                    actual_quantity=0,
                    variance_quantity=float(item.quantity_issued),
                    severity="high",
                    reason="Material issued but no consumption reflected within expected usage window.",
                    status="open",
                )
                db.add(flag)
                created.append({"issue_id": txn.id})
            txn.status = "flagged"
    db.flush()
    return {"created_flags": created}


def update_material(db: Session, material_id: int, **kwargs) -> Material | None:
    m = get_material(db, material_id)
    if not m:
        return None
    for k, v in kwargs.items():
        if hasattr(m, k):
            setattr(m, k, v)
    db.flush()
    return m


def delete_material(db: Session, material_id: int) -> bool:
    m = get_material(db, material_id)
    if not m:
        return False
    db.delete(m)
    db.flush()
    return True


def list_flags(db: Session, status: str | None = None, project_id: int | None = None) -> list:
    q = db.query(InventoryVarianceFlag)
    if status:
        q = q.filter(InventoryVarianceFlag.status == status)
    if project_id:
        q = q.join(MaterialIssueTransaction, InventoryVarianceFlag.transaction_id == MaterialIssueTransaction.id).filter(MaterialIssueTransaction.project_id == project_id)
    return q.order_by(InventoryVarianceFlag.created_at.desc()).all()


def resolve_flag(db: Session, flag_id: int, reviewer: str) -> InventoryVarianceFlag | None:
    from datetime import datetime, timezone
    flag = db.query(InventoryVarianceFlag).filter(InventoryVarianceFlag.id == flag_id).first()
    if not flag:
        return None
    flag.status = "resolved"
    flag.reviewed_by = reviewer
    flag.resolved_at = datetime.now(timezone.utc)
    db.flush()
    return flag


def update_issue_consumption(db: Session, issue_id: int, items: list[dict]) -> MaterialIssueTransaction | None:
    txn = get_issue(db, issue_id)
    if not txn:
        return None
    for item_data in items:
        material_id = item_data.get("material_id")
        issue_item = next((i for i in txn.items if i.material_id == material_id), None)
        if issue_item:
            if "quantity_consumed" in item_data:
                issue_item.quantity_consumed = item_data["quantity_consumed"]
            if "quantity_returned" in item_data:
                issue_item.quantity_returned = item_data["quantity_returned"]
            if "quantity_missing" in item_data:
                issue_item.quantity_missing = item_data["quantity_missing"]
    # If all items accounted for, mark as consumed
    all_done = all(
        float(i.quantity_consumed) + float(i.quantity_returned) + float(i.quantity_missing) >= float(i.quantity_issued)
        for i in txn.items
    )
    if all_done and txn.status == "issued":
        txn.status = "consumed"
    db.flush()
    db.refresh(txn)
    return txn


def get_low_stock(db: Session) -> list[dict]:
    """Return materials that are below min_threshold in any warehouse."""
    results = []
    for material in list_materials(db):
        total_available = sum(
            float(s.quantity_available)
            for s in db.query(WarehouseStock).filter(WarehouseStock.material_id == material.id).all()
        )
        if total_available < float(material.min_threshold):
            results.append({
                "material_id": material.id,
                "material_name": material.name,
                "category": material.category,
                "unit": material.unit,
                "total_available": total_available,
                "min_threshold": float(material.min_threshold),
                "deficit": float(material.min_threshold) - total_available,
            })
    return results


# ── Seed data ────────────────────────────────────────────────────────────────

def seed_inventory(db: Session) -> None:
    if db.query(Material).count() > 0:
        return
    seeds = [
        {"name": "PV Module 400W",       "category": "module",     "unit": "pcs", "sku": "MOD-400W",   "min_threshold": 50,  "unit_cost": 180.00},
        {"name": "String Inverter 25kW", "category": "inverter",   "unit": "pcs", "sku": "INV-25KW",   "min_threshold": 2,   "unit_cost": 3200.00},
        {"name": "DC Cable 6mm²",        "category": "cable",      "unit": "m",   "sku": "CBL-DC6",    "min_threshold": 200, "unit_cost": 1.40},
        {"name": "AC Cable 16mm²",       "category": "cable",      "unit": "m",   "sku": "CBL-AC16",   "min_threshold": 100, "unit_cost": 3.20},
        {"name": "Mounting Rail 4.4m",   "category": "mounting",   "unit": "pcs", "sku": "MNT-RAIL44", "min_threshold": 20,  "unit_cost": 22.50},
        {"name": "DC Combiner Box 8-in", "category": "electrical", "unit": "pcs", "sku": "COM-DC8",    "min_threshold": 5,   "unit_cost": 420.00},
        {"name": "Earthing Cable 16mm²", "category": "cable",      "unit": "m",   "sku": "CBL-GND16",  "min_threshold": 50,  "unit_cost": 2.10},
        {"name": "MC4 Connector pair",   "category": "connector",  "unit": "pcs", "sku": "CON-MC4",    "min_threshold": 100, "unit_cost": 1.20},
    ]
    for s in seeds:
        db.add(Material(**s))
    db.flush()

    # Seed a default warehouse
    if db.query(Warehouse).count() == 0:
        wh = Warehouse(name="Main Warehouse", location="Site Office", manager_name="warehouse")
        db.add(wh)
        db.flush()
