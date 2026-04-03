from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.task import MaintenanceTask, TaskMessage, TaskApproval, TaskTestResult


def list_tasks(db: Session, project_id: int | None = None) -> list[MaintenanceTask]:
    q = db.query(MaintenanceTask)
    if project_id is not None:
        q = q.filter(MaintenanceTask.project_id == project_id)
    return q.order_by(MaintenanceTask.id).all()


def get_task(db: Session, task_id: int) -> MaintenanceTask | None:
    return db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()


def create_task(db: Session, **kwargs) -> MaintenanceTask:
    task = MaintenanceTask(**kwargs, status="open")
    db.add(task)
    db.flush()
    return task


def add_message(db: Session, task_id: int, *, author_name: str, message_type: str = "text",
                message_text: str | None = None) -> MaintenanceTask | None:
    task = get_task(db, task_id)
    if not task:
        return None
    msg = TaskMessage(task_id=task_id, author_name=author_name, message_type=message_type, message_text=message_text)
    db.add(msg)
    db.flush()
    db.refresh(task)
    return task


def approve_task(db: Session, task_id: int, *, approver_name: str, approved: bool,
                 decision_note: str | None = None) -> MaintenanceTask | None:
    task = get_task(db, task_id)
    if not task:
        return None
    approval = TaskApproval(
        task_id=task_id,
        approver_name=approver_name,
        status="approved" if approved else "rejected",
        decision_note=decision_note,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(approval)
    task.status = "approved" if approved else "rejected"
    db.flush()
    db.refresh(task)
    return task


def add_test_result(db: Session, task_id: int, *, test_type: str, title: str,
                    status: str = "informational", summary: str | None = None,
                    raw_result_json: dict | None = None) -> MaintenanceTask | None:
    task = get_task(db, task_id)
    if not task:
        return None
    tr = TaskTestResult(
        task_id=task_id,
        test_type=test_type,
        title=title,
        status=status,
        summary=summary,
        raw_result_json=raw_result_json,
    )
    db.add(tr)
    db.flush()
    db.refresh(task)
    return task


def seed_tasks(db: Session) -> None:
    from app.repositories.project_repo import list_projects
    if db.query(MaintenanceTask).count() > 0:
        return
    projects = list_projects(db)
    if not projects:
        return
    pid = {p.name: p.id for p in projects}
    seeds = [
        {"project_id": pid.get("Solar Farm Alpha", 1),  "site_name": "Alentejo North",   "title": "Install inverter cabinets block A",  "task_type": "installation",  "asset_type": "inverter",  "asset_ref": "INV-A1",  "priority": "high",     "assigned_to": "tech",    "requires_approval": True,  "requires_test_result": True},
        {"project_id": pid.get("Solar Farm Alpha", 1),  "site_name": "Alentejo North",   "title": "Cable tray routing rows 1-10",       "task_type": "installation",  "asset_type": "cable",     "asset_ref": "CT-R1",   "priority": "medium",   "assigned_to": "tech",    "requires_approval": False, "requires_test_result": False},
        {"project_id": pid.get("Solar Farm Alpha", 1),  "site_name": "Alentejo North",   "title": "IV curve measurement batch 1",       "task_type": "measurement",   "asset_type": "string",    "asset_ref": "S.1.1",   "priority": "high",     "assigned_to": "tech",    "requires_approval": False, "requires_test_result": True},
        {"project_id": pid.get("Rooftop Porto B2B", 2), "site_name": "Porto Industrial", "title": "Rooftop structural inspection",      "task_type": "inspection",    "asset_type": "structure", "asset_ref": "ROOF-01", "priority": "critical", "assigned_to": "manager", "requires_approval": True,  "requires_test_result": False},
        {"project_id": pid.get("Rooftop Porto B2B", 2), "site_name": "Porto Industrial", "title": "Grid connection commissioning test", "task_type": "commissioning", "asset_type": "grid",      "asset_ref": "GC-01",   "priority": "critical", "assigned_to": "tech",    "requires_approval": True,  "requires_test_result": True},
        {"project_id": pid.get("Rural Mini-Grid", 3),   "site_name": "Évora Rural",      "title": "Battery storage wiring check",      "task_type": "inspection",    "asset_type": "battery",   "asset_ref": "BAT-01",  "priority": "high",     "assigned_to": "tech",    "requires_approval": False, "requires_test_result": True},
        {"project_id": pid.get("Agrivoltaic Demo", 5),  "site_name": "Beja Fields",      "title": "Design file validation",            "task_type": "validation",    "asset_type": "design",    "asset_ref": "DES-01",  "priority": "high",     "assigned_to": "manager", "requires_approval": True,  "requires_test_result": False},
    ]
    for s in seeds:
        db.add(MaintenanceTask(**s, status="open"))
    db.flush()
