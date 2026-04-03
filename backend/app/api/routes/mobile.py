from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.mobile import MobileHomeResponse

router = APIRouter()

@router.get("/home/{role}", response_model=MobileHomeResponse)
def mobile_home(role: str, db: Session = Depends(get_db)):
    role = role.lower()
    cards = {
        "technician": ["My Tasks", "My Projects", "Daily Report", "Upload Evidence", "Materials"],
        "manager":    ["Dashboard", "Approvals", "Alerts", "Tasks", "Inventory"],
        "warehouse":  ["Issue Material", "Receive Return", "Open Transactions", "Low Stock Alerts"],
        "owner":      ["Approvals", "Reports", "Progress Summary"],
        "admin":      ["System Status", "Projects", "Users", "Integrations"],
    }.get(role, ["Home"])
    return {"role": role, "cards": cards}


@router.get("/summary/{role}")
def mobile_summary(role: str, db: Session = Depends(get_db)):
    """Return real counts for the mobile home dashboard."""
    from app.models.task import MaintenanceTask
    from app.models.inventory import MaterialIssueTransaction, InventoryVarianceFlag, Material, WarehouseStock
    from app.models.project import Project

    summary: dict = {}
    try:
        summary["open_tasks"]        = db.query(MaintenanceTask).filter(MaintenanceTask.status.in_(["open", "in_progress"])).count()
        summary["pending_approvals"] = db.query(MaintenanceTask).filter(MaintenanceTask.status == "pending_approval").count()
        summary["active_projects"]   = db.query(Project).filter(Project.is_active == True).count()
        summary["open_flags"]        = db.query(InventoryVarianceFlag).filter(InventoryVarianceFlag.status == "open").count()
        summary["open_issues"]       = db.query(MaterialIssueTransaction).filter(MaterialIssueTransaction.status == "issued").count()

        # Low stock count
        low_stock = 0
        for mat in db.query(Material).all():
            total = sum(
                float(s.quantity_available)
                for s in db.query(WarehouseStock).filter(WarehouseStock.material_id == mat.id).all()
            )
            if total < float(mat.min_threshold):
                low_stock += 1
        summary["low_stock_items"] = low_stock
    except Exception:
        pass
    return summary
