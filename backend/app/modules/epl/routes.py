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
from app.epl_engine.features import feature_payload, merge_enabled_features
from app.epl_engine.parsers.deepsearch_parser import (
    build_deepsearch_model,
    prepare_map_data,
    write_deepsearch_exports,
)
from app.services import db_store
from .map_source import attach_map_source_image_url
from .string_optimizer_parser import (
    build_string_optimizer_model_from_pdfs,
    write_string_optimizer_csvs,
)

router = APIRouter()
project_router = APIRouter()

# Cache expensive PDF text extraction by project + PDF mtimes.
_STRING_OPT_CACHE: dict[tuple[str, str], dict] = {}
_DEEPSEARCH_CACHE: dict[tuple[str, str], dict] = {}


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


def _project_epl_input_paths(project_uuid: str) -> list[str]:
    files = db_store.list_project_files(project_uuid)
    return sorted(
        f["storage_path"]
        for f in files
        if str(f.get("storage_path", "")).lower().endswith((".pdf", ".zip"))
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
    model = attach_map_source_image_url(project_id, project_uuid, model)
    _STRING_OPT_CACHE[key] = model
    return model


def _build_deepsearch(project_id: str) -> dict:
    project_uuid = db_store.get_project_uuid(project_id)
    if not project_uuid:
        raise HTTPException(status_code=404, detail="Project not found")

    input_paths = _project_epl_input_paths(project_uuid)
    if not input_paths:
        raise HTTPException(status_code=400, detail="No uploaded PDF or ZIP files found for this project")

    key = _cache_key(project_uuid, input_paths)
    cached = _DEEPSEARCH_CACHE.get(key)
    if cached is not None:
        return cached

    meta = db_store.get_project_metadata(project_uuid)
    summary = meta.get("summary") or {}
    project_type = summary.get("project_type") or summary.get("site_profile") or "unknown"
    enabled_features = summary.get("enabled_features") or None
    work_dir = PROJECTS_ROOT / project_id / "epl_deepsearch" / "work"
    model = build_deepsearch_model(
        input_paths,
        work_dir=work_dir,
        default_project_folder=project_id,
        enabled_features=merge_enabled_features(project_type, enabled_features),
    )
    _DEEPSEARCH_CACHE[key] = model
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


@project_router.get("/projects/{project_id}/features")
def get_project_features(project_id: str) -> dict:
    project_uuid = db_store.get_project_uuid(project_id)
    if not project_uuid:
        raise HTTPException(status_code=404, detail="Project not found")
    meta = db_store.get_project_metadata(project_uuid)
    summary = meta.get("summary") or {}
    project_type = summary.get("project_type") or summary.get("site_profile") or "unknown"
    enabled_features = summary.get("enabled_features") or None
    payload = feature_payload(project_type, enabled_features)
    try:
        model = _build_deepsearch(project_id)
        payload["project_type_guess_by_folder"] = model.get("project_folders") or {}
    except Exception:
        payload["project_type_guess_by_folder"] = {}
    return payload


@project_router.get("/projects/{project_id}/epl/model")
def get_epl_model(
    project_id: str,
    include_raw_text: bool = Query(False, description="Include raw text per document. This can be large."),
) -> dict:
    model = dict(_build_deepsearch(project_id))
    if not include_raw_text:
        model.pop("raw_text", None)
        model["raw_text_omitted"] = True
    return model


@project_router.get("/projects/{project_id}/epl/map-data")
def get_epl_map_data(
    project_id: str,
    project_folder: str | None = Query(None, description="Optional folder/site candidate to return."),
) -> dict:
    model = _build_deepsearch(project_id)
    return prepare_map_data(model, project_folder=project_folder)


@project_router.get("/projects/{project_id}/epl/export")
def export_epl_model(project_id: str) -> FileResponse:
    model = _build_deepsearch(project_id)
    out_dir = PROJECTS_ROOT / project_id / "epl_exports" / "deepsearch"
    paths = write_deepsearch_exports(model, out_dir)

    zip_path = PROJECTS_ROOT / project_id / "epl_exports" / "epl_deepsearch.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths.values():
            pp = Path(p)
            if pp.exists() and pp.is_file():
                z.write(pp, pp.relative_to(out_dir))

    return FileResponse(
        str(zip_path),
        filename=f"{project_id}_epl_deepsearch.zip",
        media_type="application/zip",
    )
