from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_roles, any_authenticated
from app.repositories import task_repo, audit_repo
from app.schemas.task import (
    MaintenanceTaskCreate, MaintenanceTaskRead,
    TaskMessageCreate, TaskApprovalAction, TaskTestResultCreate,
)

router = APIRouter()


@router.post("", response_model=MaintenanceTaskRead)
def create_task(
    payload: MaintenanceTaskCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager", "technician")),
):
    task = task_repo.create_task(db, **payload.model_dump())
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="create_task", entity_type="task", entity_id=task.id,
                          detail=f"Task: {task.title}")
    db.commit()
    return task.to_dict()


@router.get("", response_model=list[MaintenanceTaskRead])
def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)):
    return [t.to_dict() for t in task_repo.list_tasks(db, project_id=project_id)]


@router.get("/{task_id}", response_model=MaintenanceTaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = task_repo.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task.to_dict()


@router.post("/{task_id}/messages", response_model=MaintenanceTaskRead)
def add_message(
    task_id: int,
    payload: TaskMessageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(any_authenticated()),
):
    task = task_repo.add_message(db, task_id, **payload.model_dump())
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    db.commit()
    return task.to_dict()


@router.post("/{task_id}/approve", response_model=MaintenanceTaskRead)
def approve(
    task_id: int,
    payload: TaskApprovalAction,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "manager")),
):
    task = task_repo.approve_task(
        db, task_id,
        approver_name=payload.approver_name,
        approved=payload.approved,
        decision_note=payload.decision_note,
    )
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="approve_task", entity_type="task", entity_id=task_id,
                          detail=f"Decision: {'approved' if payload.approved else 'rejected'}")
    db.commit()
    return task.to_dict()


@router.post("/{task_id}/test-results", response_model=MaintenanceTaskRead)
def add_test_result(
    task_id: int,
    payload: TaskTestResultCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(any_authenticated()),
):
    task = task_repo.add_test_result(db, task_id, **payload.model_dump())
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    db.commit()
    return task.to_dict()
