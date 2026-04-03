"""
Audit log endpoint — admin-only view of all system actions.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_roles
from app.repositories import audit_repo

router = APIRouter()


@router.get("")
def list_audit_log(
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    return [e.to_dict() for e in audit_repo.list_recent(db, limit=limit)]
