"""
Task file attachments — upload, list, download evidence files.
Stores files under uploads/tasks/{task_id}/
Accepts: PDF, DXF, PNG, JPG, JPEG
"""
import os
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import any_authenticated
from app.repositories import audit_repo

router = APIRouter()

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "uploads", "tasks")
ALLOWED_EXT = {".pdf", ".dxf", ".png", ".jpg", ".jpeg"}
MAX_SIZE_MB = 50


def _task_dir(task_id: int) -> str:
    d = os.path.join(UPLOAD_ROOT, str(task_id))
    os.makedirs(d, exist_ok=True)
    return d


@router.get("/{task_id}/attachments")
def list_attachments(task_id: int, db: Session = Depends(get_db)):
    from app.models.task import TaskAttachment
    items = db.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).all()
    return [a.to_dict() for a in items]


@router.post("/{task_id}/attachments")
async def upload_attachments(
    task_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(any_authenticated()),
):
    from app.models.task import MaintenanceTask, TaskAttachment
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    results = []
    for upload in files:
        _, ext = os.path.splitext(upload.filename or "")
        ext = ext.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

        content = await upload.read()
        if len(content) / (1024 * 1024) > MAX_SIZE_MB:
            raise HTTPException(status_code=400, detail=f"File exceeds {MAX_SIZE_MB} MB limit")

        file_id = str(uuid.uuid4())
        save_name = f"{file_id}{ext}"
        save_path = os.path.join(_task_dir(task_id), save_name)
        with open(save_path, "wb") as f:
            f.write(content)

        att = TaskAttachment(
            task_id=task_id,
            file_type=ext.lstrip(".").upper(),
            file_name=upload.filename or save_name,
            file_path=save_path,
            uploaded_by=current_user.get("username"),
        )
        db.add(att)
        db.flush()
        results.append(att.to_dict())

    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="upload_attachments", entity_type="task", entity_id=task_id,
                          detail=f"Uploaded {len(results)} file(s)")
    db.commit()
    return results


@router.get("/{task_id}/attachments/{att_id}/download")
def download_attachment(task_id: int, att_id: int, db: Session = Depends(get_db)):
    from app.models.task import TaskAttachment
    att = db.query(TaskAttachment).filter(
        TaskAttachment.id == att_id, TaskAttachment.task_id == task_id
    ).first()
    if not att or not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(att.file_path, filename=att.file_name)


@router.delete("/{task_id}/attachments/{att_id}")
def delete_attachment(
    task_id: int,
    att_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(any_authenticated()),
):
    from app.models.task import TaskAttachment
    att = db.query(TaskAttachment).filter(
        TaskAttachment.id == att_id, TaskAttachment.task_id == task_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if os.path.exists(att.file_path):
        os.remove(att.file_path)
    db.delete(att)
    db.commit()
    return {"ok": True}
