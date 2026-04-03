from pydantic import BaseModel

class ProjectCreate(BaseModel):
    name: str
    customer_name: str | None = None
    customer_id: int | None = None
    site_name: str
    project_type: str
    description: str | None = None

class ProjectPhaseUpdate(BaseModel):
    phase: str

class ProjectActiveUpdate(BaseModel):
    is_active: bool

class ProjectRead(BaseModel):
    id: int
    name: str
    customer_name: str | None = None
    customer_id: int | None = None
    company_id: int | None = None
    company_name: str | None = None
    site_name: str
    project_type: str
    phase: str
    progress_percent: float
    description: str | None = None
    is_active: bool = True
    string_pattern: str | None = None
    created_at: str | None = None
    class Config:
        from_attributes = True

class ValidationIssueRead(BaseModel):
    severity: str
    asset_type: str | None = None
    asset_ref: str | None = None
    issue_type: str
    message: str

class ValidationRunRead(BaseModel):
    status: str
    issues: list[ValidationIssueRead]
