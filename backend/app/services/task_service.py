from fastapi import HTTPException
from app.schemas.task import MaintenanceTaskCreate, TaskMessageCreate, TaskApprovalAction, TaskTestResultCreate

# Seed demo tasks linked to seed projects
_SEED = [
    {"id": 1,  "project_id": 1, "site_name": "Alentejo North",   "description": None, "title": "Install inverter cabinets block A",  "task_type": "installation",   "asset_type": "inverter",  "asset_ref": "INV-A1",  "priority": "high",     "status": "in_progress", "assigned_to": "tech",    "requires_approval": True,  "requires_test_result": True,  "messages": [], "approvals": [], "test_results": []},
    {"id": 2,  "project_id": 1, "site_name": "Alentejo North",   "description": None, "title": "Cable tray routing rows 1-10",       "task_type": "installation",   "asset_type": "cable",     "asset_ref": "CT-R1",   "priority": "medium",   "status": "open",        "assigned_to": "tech",    "requires_approval": False, "requires_test_result": False, "messages": [], "approvals": [], "test_results": []},
    {"id": 3,  "project_id": 1, "site_name": "Alentejo North",   "description": None, "title": "IV curve measurement batch 1",       "task_type": "measurement",    "asset_type": "string",    "asset_ref": "S.1.1",   "priority": "high",     "status": "open",        "assigned_to": "tech",    "requires_approval": False, "requires_test_result": True,  "messages": [], "approvals": [], "test_results": []},
    {"id": 4,  "project_id": 2, "site_name": "Porto Industrial", "description": None, "title": "Rooftop structural inspection",      "task_type": "inspection",     "asset_type": "structure", "asset_ref": "ROOF-01", "priority": "critical", "status": "in_progress", "assigned_to": "manager", "requires_approval": True,  "requires_test_result": False, "messages": [], "approvals": [], "test_results": []},
    {"id": 5,  "project_id": 2, "site_name": "Porto Industrial", "description": None, "title": "Grid connection commissioning test", "task_type": "commissioning",  "asset_type": "grid",      "asset_ref": "GC-01",   "priority": "critical", "status": "open",        "assigned_to": "tech",    "requires_approval": True,  "requires_test_result": True,  "messages": [], "approvals": [], "test_results": []},
    {"id": 6,  "project_id": 3, "site_name": "Évora Rural",      "description": None, "title": "Battery storage wiring check",      "task_type": "inspection",     "asset_type": "battery",   "asset_ref": "BAT-01",  "priority": "high",     "status": "open",        "assigned_to": "tech",    "requires_approval": False, "requires_test_result": True,  "messages": [], "approvals": [], "test_results": []},
    {"id": 7,  "project_id": 3, "site_name": "Évora Rural",      "description": None, "title": "Load flow testing",                 "task_type": "testing",        "asset_type": "inverter",  "asset_ref": "INV-01",  "priority": "high",     "status": "in_progress", "assigned_to": "tech",    "requires_approval": True,  "requires_test_result": True,  "messages": [], "approvals": [], "test_results": []},
    {"id": 8,  "project_id": 4, "site_name": "Lisbon Central",   "description": None, "title": "Structural canopy approval",        "task_type": "approval",       "asset_type": "structure", "asset_ref": "CAN-01",  "priority": "medium",   "status": "open",        "assigned_to": "manager", "requires_approval": True,  "requires_test_result": False, "messages": [], "approvals": [], "test_results": []},
    {"id": 9,  "project_id": 5, "site_name": "Beja Fields",      "description": None, "title": "Design file validation",            "task_type": "validation",     "asset_type": "design",    "asset_ref": "DES-01",  "priority": "high",     "status": "open",        "assigned_to": "manager", "requires_approval": True,  "requires_test_result": False, "messages": [], "approvals": [], "test_results": []},
    {"id": 10, "project_id": 5, "site_name": "Beja Fields",      "description": None, "title": "Shade analysis review",             "task_type": "analysis",       "asset_type": "design",    "asset_ref": "SHA-01",  "priority": "medium",   "status": "open",        "assigned_to": "tech",    "requires_approval": False, "requires_test_result": False, "messages": [], "approvals": [], "test_results": []},
]


class TaskService:
    def __init__(self):
        self._items = [dict(s) for s in _SEED]
        self._id = len(_SEED) + 1

    def _find(self, task_id: int):
        item = next((x for x in self._items if x["id"] == task_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return item

    def create(self, payload: MaintenanceTaskCreate):
        item = payload.model_dump()
        item.update({"id": self._id, "status": "open", "messages": [], "approvals": [], "test_results": []})
        self._items.append(item)
        self._id += 1
        return item

    def list_all(self):
        return self._items

    def get(self, task_id: int):
        return self._find(task_id)

    def add_message(self, task_id: int, payload: TaskMessageCreate):
        item = self._find(task_id)
        item["messages"].append(payload.model_dump())
        return item

    def approve(self, task_id: int, payload: TaskApprovalAction):
        item = self._find(task_id)
        item["approvals"].append({
            "approver_name": payload.approver_name,
            "decision_note": payload.decision_note,
            "status": "approved" if payload.approved else "rejected",
        })
        item["status"] = "approved" if payload.approved else "rejected"
        return item

    def add_test_result(self, task_id: int, payload: TaskTestResultCreate):
        item = self._find(task_id)
        item["test_results"].append(payload.model_dump())
        return item
