from pydantic import BaseModel

class MaterialCreate(BaseModel):
    name: str
    category: str | None = None
    unit: str
    sku: str | None = None
    min_threshold: float = 0
    unit_cost: float | None = None

class MaterialIssueItem(BaseModel):
    material_name: str
    quantity_issued: float
    quantity_returned: float = 0
    quantity_consumed: float = 0
    quantity_missing: float = 0
    unit: str | None = None

class MaterialIssueCreate(BaseModel):
    project_id: int
    warehouse_name: str
    issued_to_user: str
    issued_by_user: str
    site_name: str | None = None
    asset_type: str | None = None
    asset_ref: str | None = None
    expected_usage_days: int = 7
    notes: str | None = None
    items: list[MaterialIssueItem]

class MaterialIssueRead(MaterialIssueCreate):
    id: int
    status: str
    red_flags: list[dict] = []
