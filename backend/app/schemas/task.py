from pydantic import BaseModel

class MaintenanceTaskCreate(BaseModel):
    project_id: int
    site_name: str | None = None
    asset_type: str
    asset_ref: str | None = None
    title: str
    description: str | None = None
    task_type: str = "maintenance"
    priority: str = "medium"
    assigned_to: str | None = None
    requires_approval: bool = False
    requires_test_result: bool = False

class TaskMessageCreate(BaseModel):
    author_name: str
    message_type: str = "text"
    message_text: str | None = None

class TaskApprovalAction(BaseModel):
    approver_name: str
    decision_note: str | None = None
    approved: bool = True

class TaskTestResultCreate(BaseModel):
    test_type: str
    title: str
    status: str = "informational"
    summary: str | None = None
    raw_result_json: dict | None = None

class MaintenanceTaskRead(MaintenanceTaskCreate):
    id: int
    status: str
    messages: list[dict] = []
    approvals: list[dict] = []
    test_results: list[dict] = []
