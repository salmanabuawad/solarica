"""
Project file upload/download/delete/replace/toggle.
Stores files under  uploads/projects/{project_id}/
Accepts: .pdf  .dxf
"""
import os, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "uploads", "projects")
ALLOWED_EXT = {".pdf", ".dxf"}
MAX_SIZE_MB = 50


def _project_dir(project_id: int) -> str:
    d = os.path.join(UPLOAD_ROOT, str(project_id))
    os.makedirs(d, exist_ok=True)
    return d


def _meta_path(project_id: int) -> str:
    return os.path.join(_project_dir(project_id), ".meta")


def _read_meta(project_id: int) -> list:
    p = _meta_path(project_id)
    if not os.path.exists(p):
        return []
    import json
    with open(p) as f:
        return json.load(f)


def _write_meta(project_id: int, records: list):
    import json
    with open(_meta_path(project_id), "w") as f:
        json.dump(records, f, indent=2)


def _backfill(record: dict) -> dict:
    """Ensure older records have the is_active field."""
    record.setdefault("is_active", True)
    return record


# ── List ─────────────────────────────────────────────────────────

@router.get("/{project_id}/files")
def list_files(project_id: int):
    return [_backfill(r) for r in _read_meta(project_id)]


# ── Upload ───────────────────────────────────────────────────────

@router.post("/{project_id}/files")
async def upload_files(project_id: int, files: List[UploadFile] = File(...)):
    meta = _read_meta(project_id)
    results = []

    for upload in files:
        _, ext = os.path.splitext(upload.filename or "")
        ext = ext.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400,
                detail=f"File '{upload.filename}' is not allowed. Only PDF and DXF files are accepted.")

        content = await upload.read()
        if len(content) / (1024 * 1024) > MAX_SIZE_MB:
            raise HTTPException(status_code=400,
                detail=f"File '{upload.filename}' exceeds the {MAX_SIZE_MB} MB limit.")

        file_id   = str(uuid.uuid4())
        save_name = f"{file_id}{ext}"
        with open(os.path.join(_project_dir(project_id), save_name), "wb") as f:
            f.write(content)

        record = {
            "id":            file_id,
            "original_name": upload.filename,
            "file_type":     ext.lstrip(".").upper(),
            "size_bytes":    len(content),
            "uploaded_at":   datetime.now(timezone.utc).isoformat(),
            "save_name":     save_name,
            "is_active":     True,
        }
        meta.append(record)
        results.append(record)

    _write_meta(project_id, meta)
    return results


# ── Download ─────────────────────────────────────────────────────

@router.get("/{project_id}/files/{file_id}/download")
def download_file(project_id: int, file_id: str):
    meta = _read_meta(project_id)
    record = next((r for r in meta if r["id"] == file_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    path = os.path.join(_project_dir(project_id), record["save_name"])
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File missing from disk")
    return FileResponse(path, filename=record["original_name"])


# ── Replace (PUT) ─────────────────────────────────────────────────
# Keeps the same file ID; overwrites the stored file and updates metadata.

@router.put("/{project_id}/files/{file_id}")
async def replace_file(project_id: int, file_id: str, file: UploadFile = File(...)):
    meta = _read_meta(project_id)
    record = next((r for r in meta if r["id"] == file_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Only PDF and DXF files are accepted.")

    content = await file.read()
    if len(content) / (1024 * 1024) > MAX_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File exceeds the {MAX_SIZE_MB} MB limit.")

    # Remove old physical file
    old_path = os.path.join(_project_dir(project_id), record["save_name"])
    if os.path.exists(old_path):
        os.remove(old_path)

    # Write new file (same id, possibly different extension)
    new_save = f"{file_id}{ext}"
    with open(os.path.join(_project_dir(project_id), new_save), "wb") as f:
        f.write(content)

    record.update({
        "original_name": file.filename,
        "file_type":     ext.lstrip(".").upper(),
        "size_bytes":    len(content),
        "uploaded_at":   datetime.now(timezone.utc).isoformat(),
        "save_name":     new_save,
    })
    record.setdefault("is_active", True)

    _write_meta(project_id, meta)
    return record


# ── Update metadata (PATCH) ───────────────────────────────────────
# Supports: is_active (bool), original_name (str)

class FileUpdate(BaseModel):
    is_active:     Optional[bool] = None
    original_name: Optional[str]  = None


@router.patch("/{project_id}/files/{file_id}")
def update_file(project_id: int, file_id: str, payload: FileUpdate):
    meta = _read_meta(project_id)
    record = next((r for r in meta if r["id"] == file_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    if payload.is_active is not None:
        record["is_active"] = payload.is_active
    if payload.original_name is not None and payload.original_name.strip():
        record["original_name"] = payload.original_name.strip()

    _write_meta(project_id, meta)
    return _backfill(record)


# ── Delete ───────────────────────────────────────────────────────

@router.delete("/{project_id}/files/{file_id}")
def delete_file(project_id: int, file_id: str):
    meta = _read_meta(project_id)
    record = next((r for r in meta if r["id"] == file_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    path = os.path.join(_project_dir(project_id), record["save_name"])
    if os.path.exists(path):
        os.remove(path)
    _write_meta(project_id, [r for r in meta if r["id"] != file_id])
    return {"ok": True}
