from pydantic import BaseModel
from typing import Optional

class SiteCreate(BaseModel):
    site_code: str
    site_name: str
    country: Optional[str] = None
    region: Optional[str] = None

class ProjectCreate(BaseModel):
    site_id: int
    project_code: str
    project_name: str
    dc_capacity_mwp: Optional[float] = None
    ac_capacity_mw: Optional[float] = None
