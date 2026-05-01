"""EPL endpoints.

This module owns pre-construction validation and reconstruction APIs.  The
first production endpoint added here is the BHK / SolarEdge string-optimizer
model:

    physical rows → electrical zones → strings → optimizers → modules

The endpoint intentionally works from uploaded project PDFs rather than a
hard-coded fixture, so it can be reused for similar agro-PV / SolarEdge sites.
"""
from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import PROJECTS_ROOT
from app.services import db_store
from .string_optimizer_parser import (
    build_string_optimizer_model_from_pdfs,
    write_string_optimizer_csvs,
)

router = APIRouter()

# Cache expensive PDF text extraction by project + PDF mtimes.
_STRING_OPT_CACHE: dict[tuple[str, str], dict] = {}


@router.get("/status")
def epl_status() -> dict:
    return {"module": "epl", "phase": "execution_planning_layer", "status": "ready"}


def _project_pdf_paths(project_uuid: str) -> list[str]:
    files = db_store.list_project_files(project_uuid)
    return sorted(
        f["storage_path"]
        for f in files
        if str(f.get("storage_path", "")).lower().endswith(".pdf")
    )


def _cache_key(project_uuid: str, pdf_paths: list[str]) -> tuple[str, str]:
    try:
        mtimes = ",".join(str(int(os.path.getmtime(p))) for p in pdf_paths)
    except Exception:
        mtimes = str(int(time.time()))
    return project_uuid, mtimes


def _build_model(project_id: str) -> dict:
    project_uuid = db_store.get_project_uuid(project_id)
    if not project_uuid:
        raise HTTPException(status_code=404, detail="Project not found")

    pdf_paths = _project_pdf_paths(project_uuid)
    if not pdf_paths:
        raise HTTPException(status_code=400, detail="No uploaded PDF files found for this project")

    key = _cache_key(project_uuid, pdf_paths)
    cached = _STRING_OPT_CACHE.get(key)
    if cached is not None:
        return cached

    model = build_string_optimizer_model_from_pdfs(pdf_paths)
    _STRING_OPT_CACHE[key] = model
    return model


@router.get("/projects/{project_id}/string-optimizer-model")
def get_string_optimizer_model(
    project_id: str,
    include_optimizers: bool = Query(False, description="Return all optimizer rows; false keeps response light."),
) -> dict:
    """Return the EPL strings/optimizers model for the current project.

    By default the response omits the 6,336 optimizer records because the
    frontend usually needs only summary, physical rows, zones and strings.
    Use `?include_optimizers=true` for full data.
    """
    model = dict(_build_model(project_id))
    if not include_optimizers:
        model["optimizers"] = []
        model["optimizers_omitted"] = True
    return model


@router.get("/projects/{project_id}/string-optimizer-export")
def export_string_optimizer_model(project_id: str) -> FileResponse:
    """Generate CSV/JSON exports and return a zip file.

    The zip contains:
      - string_optimizer_model.json
      - physical_rows.csv
      - string_zones.csv
      - strings.csv
      - optimizers.csv
      - validation_issues.csv
    """
    model = _build_model(project_id)

    out_dir = PROJECTS_ROOT / project_id / "epl_exports" / "strings_optimizers"
    paths = write_string_optimizer_csvs(model, out_dir)

    zip_path = PROJECTS_ROOT / project_id / "epl_exports" / "strings_optimizers.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths.values():
            pp = Path(p)
            if pp.exists():
                z.write(pp, pp.name)

    return FileResponse(
        str(zip_path),
        filename=f"{project_id}_strings_optimizers.zip",
        media_type="application/zip",
    )
