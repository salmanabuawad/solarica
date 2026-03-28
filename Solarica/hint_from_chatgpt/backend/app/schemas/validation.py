from pydantic import BaseModel
from typing import Dict, Any, Optional

class ValidationRuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    category: str
    scope: str
    severity: str
    is_active: bool = True
    engine_type: str
    message_template: Optional[str] = None
    description: Optional[str] = None
    parameters: Dict[str, Any] = {}

class ValidationIssueOut(BaseModel):
    id: int
    rule_code: str
    severity: str
    entity_type: str
    entity_key: str
    issue_message: str
