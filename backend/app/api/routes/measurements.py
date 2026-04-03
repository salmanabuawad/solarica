import io
import zipfile
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import measurement_repo
from app.parsers.pvpm.parser_v5 import parse_sui_bytes

router = APIRouter()

MAX_FILES = 500
MAX_MB    = 200

ZIP_MAGIC = b"PK\x03\x04"
SUI_MAGIC = b"UIKenn"


def _is_zip(data: bytes) -> bool:
    return data[:4] == ZIP_MAGIC


def _is_sui(data: bytes) -> bool:
    return data[:6] == SUI_MAGIC


def _parse_and_save(raw: bytes, filename: str, db: Session, project_id: int | None = None) -> dict:
    parsed = parse_sui_bytes(raw, filename)
    m = measurement_repo.create_measurement(
        db,
        source_file_name=filename,
        payload_json=parsed,
        project_id=project_id,
    )
    return {"id": m.id, "file_name": filename, "ok": True}


def _extract_sui_from_zip(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    results: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # include all files that look like SUI (by name OR by content)
        for name in sorted(zf.namelist()):
            if name.endswith("/"):          # skip directory entries
                continue
            if "__MACOSX" in name:         # skip macOS metadata
                continue
            raw = zf.read(name)
            # Accept if named .sui OR starts with UIKenn magic
            if name.lower().endswith(".sui") or _is_sui(raw):
                results.append((name, raw))
    if not results:
        raise ValueError("No .SUI files found inside the ZIP archive.")
    return results


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
def list_measurements(
    project_id: Optional[int] = None,
    string_label: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return [m.to_dict() for m in measurement_repo.list_measurements(
        db, project_id=project_id, string_label=string_label, limit=limit, offset=offset
    )]


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{measurement_id}")
def get_measurement(measurement_id: int, db: Session = Depends(get_db)):
    m = measurement_repo.get_measurement(db, measurement_id)
    if not m:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return m.to_dict()


# ── Batch upload ──────────────────────────────────────────────────────────────

@router.post("/upload-sui")
async def upload_sui(
    files: Optional[List[UploadFile]] = File(default=None),
    project_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Accept one or more .SUI files and/or .ZIP archives.
    Detection is by file content (magic bytes), not just extension.
    Optionally associate all imported measurements with a project_id.
    Returns {imported, failed, results[], errors[]}.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    sui_pairs: list[tuple[str, bytes]] = []
    errors:    list[dict] = []

    for upload in files:
        raw  = await upload.read()
        name = upload.filename or "upload.sui"

        if len(raw) == 0:
            errors.append({"file": name, "error": "Empty file."})
            continue

        size_mb = len(raw) / (1024 * 1024)
        if size_mb > MAX_MB:
            errors.append({"file": name, "error": f"File too large ({size_mb:.1f} MB, max {MAX_MB} MB)."})
            continue

        # Detect by content first, then fall back to extension
        if _is_zip(raw):
            try:
                sui_pairs.extend(_extract_sui_from_zip(raw))
            except (zipfile.BadZipFile, ValueError) as exc:
                errors.append({"file": name, "error": str(exc)})
        elif _is_sui(raw):
            sui_pairs.append((name, raw))
        else:
            # Try by extension as last resort
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext == "sui":
                sui_pairs.append((name, raw))
            elif ext == "zip":
                try:
                    sui_pairs.extend(_extract_sui_from_zip(raw))
                except Exception as exc:
                    errors.append({"file": name, "error": str(exc)})
            else:
                # Try parsing anyway — parser will raise ValueError if not SUI
                sui_pairs.append((name, raw))

    if not sui_pairs and not errors:
        raise HTTPException(status_code=400, detail="No files could be processed.")

    if len(sui_pairs) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files ({len(sui_pairs)}). Max {MAX_FILES} per batch.")

    results: list[dict] = []
    for filename, raw in sui_pairs:
        try:
            results.append(_parse_and_save(raw, filename, db, project_id=project_id))
        except Exception as exc:
            errors.append({"file": filename, "error": str(exc)})

    linked = 0
    if results and project_id is not None:
        try:
            linked = measurement_repo.auto_link_to_project_strings(db, project_id)
        except Exception:
            pass

    if results:
        db.commit()

    response = {
        "imported": len(results),
        "failed":   len(errors),
        "results":  results,
        "errors":   errors,
    }
    if project_id is not None:
        response["strings_linked"] = linked

    return response
