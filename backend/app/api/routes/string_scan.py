"""
POST /api/projects/{id}/scan-strings
  Accepts one or more uploaded PDF files (multipart/form-data) OR a file_id
  referencing an already-uploaded project file.
  Returns a full string extraction preview: strings, gaps, duplicates, anomalies,
  site metadata and capacity.

GET /api/projects/{id}/scan-stream?file_ids=id1,id2
  Server-Sent Events stream — runs the full pipeline (parse → topology sync →
  string sync → analytics save) and emits a progress event after each stage.
  Uses map_parser_v7.ParserEngine when available, falls back to the legacy
  pdf_string_extractor otherwise.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.parsers.design.pdf_string_extractor import (
    build_site_design_preview,
    build_site_design_preview_multi,
    _extract_text_from_pdf,
    detect_string_pattern_candidates,
)
from app.parsers.design.dxf_parser import (
    extract_detection_text_from_dxf,
    extract_detection_text_from_dxf_path,
    extract_text_from_dxf,
    extract_text_from_dxf_path,
    parse_dxf,
    parse_dxf_path,
)
from app.repositories import project_repo
from app.services.topology_validation import TopologyValidationService
from app.services.map_reconciliation import MapReconciliationService
from app.services.event_bus import EventBus

# ── ParserEngine (map_parser_v7) ─────────────────────────────────────────────
# Installed via:  pip install -e /opt/solarica/parser_engine
# Falls back to legacy pdf_string_extractor when not available.
_PE_AVAILABLE = False
try:
    from map_parser_v7.core.engine import ParserEngine as _ParserEngine
    from map_parser_v7.steps.registry import STEPS as _PE_STEPS
    from map_parser_v7.utils.text_patterns import _detect_level as _pe_detect_level
    from map_parser_v7.utils.text_patterns import sort_key as _pe_sort_key
    _PE_AVAILABLE = True
except ImportError:
    pass

router = APIRouter()
_DETECT_CACHE_TTL_SECONDS = 15 * 60
_DETECT_CACHE_LOCK = threading.Lock()
_DETECT_CACHE: dict[str, dict[str, Any]] = {}

UPLOAD_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "uploads", "projects"
)
# backend/ — subprocess cwd so `import app` works (same as uvicorn working directory).
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _project_dir(project_id: int) -> str:
    return os.path.join(UPLOAD_ROOT, str(project_id))


def _read_meta(project_id: int) -> list:
    import json
    p = os.path.join(_project_dir(project_id), ".meta")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return json.load(f)


async def _collect_scan_file_pairs(
    project_id: int,
    files: Optional[List[UploadFile]],
    file_ids: Optional[str],
) -> list[tuple[bytes, str]]:
    file_pairs: list[tuple[bytes, str]] = []
    allowed = {".pdf", ".dxf"}

    if file_ids:
        meta = _read_meta(project_id)
        for fid in [x.strip() for x in file_ids.split(",") if x.strip()]:
            record = next((r for r in meta if r["id"] == fid), None)
            if not record:
                raise HTTPException(status_code=404, detail=f"File '{fid}' not found in project {project_id}")
            ext = os.path.splitext(record["save_name"])[1].lower()
            if ext not in allowed:
                raise HTTPException(status_code=400, detail=f"Only PDF/DXF files can be scanned. '{record['original_name']}' is {ext.upper()}.")
            path = os.path.join(_project_dir(project_id), record["save_name"])
            if not os.path.exists(path):
                raise HTTPException(status_code=404, detail=f"File missing from disk: {record['original_name']}")
            with open(path, "rb") as f:
                file_pairs.append((f.read(), record["original_name"]))

    if files:
        for upload in files:
            ext = os.path.splitext(upload.filename or "")[1].lower()
            if ext not in allowed:
                raise HTTPException(status_code=400, detail=f"Only PDF/DXF files can be scanned. '{upload.filename}' is {ext.upper()}.")
            content = await upload.read()
            file_pairs.append((content, upload.filename or "upload.pdf"))

    if not file_pairs:
        raise HTTPException(status_code=400, detail="No files provided. Supply 'files' (multipart) or 'file_ids' (form field).")

    return file_pairs


def _collect_project_file_pairs(project_id: int, file_ids: str) -> list[tuple[bytes, str]]:
    file_pairs: list[tuple[bytes, str]] = []
    allowed = {".pdf", ".dxf"}
    meta = _read_meta(project_id)
    for fid in [x.strip() for x in file_ids.split(",") if x.strip()]:
        record = next((r for r in meta if r["id"] == fid), None)
        if not record:
            raise HTTPException(status_code=404, detail=f"File '{fid}' not found in project {project_id}")
        ext = os.path.splitext(record["save_name"])[1].lower()
        if ext not in allowed:
            raise HTTPException(status_code=400, detail=f"Only PDF/DXF files can be scanned. '{record['original_name']}' is {ext.upper()}.")
        path = os.path.join(_project_dir(project_id), record["save_name"])
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"File missing from disk: {record['original_name']}")
        with open(path, "rb") as f:
            file_pairs.append((f.read(), record["original_name"]))
    if not file_pairs:
        raise HTTPException(status_code=400, detail="No files found for the given file_ids.")
    return file_pairs


def _collect_project_file_records(project_id: int, file_ids: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    allowed = {".pdf", ".dxf"}
    meta = _read_meta(project_id)
    for fid in [x.strip() for x in file_ids.split(",") if x.strip()]:
        record = next((r for r in meta if r["id"] == fid), None)
        if not record:
            raise HTTPException(status_code=404, detail=f"File '{fid}' not found in project {project_id}")
        ext = os.path.splitext(record["save_name"])[1].lower()
        if ext not in allowed:
            raise HTTPException(status_code=400, detail=f"Only PDF/DXF files can be scanned. '{record['original_name']}' is {ext.upper()}.")
        path = os.path.join(_project_dir(project_id), record["save_name"])
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"File missing from disk: {record['original_name']}")
        records.append({"filename": record["original_name"], "path": path, "ext": ext})
    if not records:
        raise HTTPException(status_code=400, detail="No files found for the given file_ids.")
    return records


def _pattern_options_for_project(db: Session, project_id: int) -> tuple[list[dict[str, Any]], str | None]:
    saved_pattern_name: str | None = None
    if project_id > 0:
        project = project_repo.get_project(db, project_id)
        saved_pattern_name = project.string_pattern if project else None
        patterns = project_repo.get_active_string_patterns(db, project_id)
    else:
        patterns = [
            {
                "id": None,
                "pattern_name": item["pattern_name"],
                "pattern_regex": item["pattern_regex"],
                "source": "default",
            }
            for item in project_repo.DEFAULT_STRING_PATTERNS
        ]
    return patterns, saved_pattern_name


def _extract_scan_text(file_pairs: list[tuple[bytes, str]]) -> str:
    parts: list[str] = []
    for content, filename in file_pairs:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            parts.append(_extract_text_from_pdf(content))
        elif ext == ".dxf":
            parts.append(extract_text_from_dxf(content))
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    return "\n".join(part for part in parts if part)


def _prune_detect_cache() -> None:
    cutoff = time.time() - _DETECT_CACHE_TTL_SECONDS
    with _DETECT_CACHE_LOCK:
        expired = [key for key, item in _DETECT_CACHE.items() if item.get("created_at", 0) < cutoff]
        for key in expired:
            _DETECT_CACHE.pop(key, None)


def _prepare_scan_entries(file_pairs: list[tuple[bytes, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for content, filename in file_pairs:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            text = _extract_text_from_pdf(content)
        elif ext == ".dxf":
            text = extract_text_from_dxf(content)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        entries.append({"filename": filename, "content": content, "text": text, "text_is_partial": False})
    return entries


def _prepare_detect_entries(file_pairs: list[tuple[bytes, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for content, filename in file_pairs:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            text = _extract_text_from_pdf(content)
        elif ext == ".dxf":
            text = extract_detection_text_from_dxf(content)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        entries.append({
            "filename": filename,
            "content": content,
            "text": text,
            "text_is_partial": ext == ".dxf",
        })
    return entries


def _prepare_scan_entries_from_records(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for record in records:
        ext = record["ext"]
        if ext == ".pdf":
            with open(record["path"], "rb") as f:
                content = f.read()
            text = _extract_text_from_pdf(content)
            entries.append({
                "filename": record["filename"],
                "path": record["path"],
                "content": content,
                "text": text,
                "text_is_partial": False,
            })
        elif ext == ".dxf":
            text = extract_text_from_dxf_path(record["path"])
            entries.append({
                "filename": record["filename"],
                "path": record["path"],
                "text": text,
                "text_is_partial": False,
            })
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    return entries


def _prepare_detect_entries_from_records(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for record in records:
        ext = record["ext"]
        if ext == ".pdf":
            with open(record["path"], "rb") as f:
                content = f.read()
            text = _extract_text_from_pdf(content)
            entries.append({
                "filename": record["filename"],
                "path": record["path"],
                "text": text,
                "text_is_partial": False,
            })
        elif ext == ".dxf":
            text = extract_detection_text_from_dxf_path(record["path"])
            entries.append({
                "filename": record["filename"],
                "path": record["path"],
                "text": text,
                "text_is_partial": True,
            })
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    return entries


def _hydrate_scan_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("content") is not None:
            hydrated.append(entry)
            continue
        path = entry.get("path")
        if not path:
            hydrated.append(entry)
            continue
        ext = os.path.splitext(entry.get("filename", ""))[1].lower()
        if ext == ".dxf":
            hydrated.append(entry)
            continue
        with open(path, "rb") as f:
            content = f.read()
        hydrated.append({**entry, "content": content})
    return hydrated


def _parse_dxf_entry(
    entry: dict[str, Any],
    approved_pattern_name: str | None = None,
    approved_pattern_regex: str | None = None,
) -> dict[str, Any]:
    extracted_text = None if entry.get("text_is_partial") else entry.get("text")
    path = entry.get("path")
    if path:
        # Isolate heavy/stability-sensitive DXF parsing from the API worker.
        script = """
import json
import sys
from app.parsers.design.dxf_parser import parse_dxf_path

path = sys.argv[1]
filename = sys.argv[2]
pattern_name = None if sys.argv[3] == "__NONE__" else sys.argv[3]
pattern_regex = None if sys.argv[4] == "__NONE__" else sys.argv[4]

result = parse_dxf_path(
    path,
    filename,
    approved_pattern_name=pattern_name,
    approved_pattern_regex=pattern_regex,
    extracted_text=None,
)
print(json.dumps(result))
"""
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                path,
                entry["filename"],
                approved_pattern_name or "__NONE__",
                approved_pattern_regex or "__NONE__",
            ],
            capture_output=True,
            text=True,
            cwd=_BACKEND_ROOT,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(stderr or f"DXF parser subprocess failed with exit code {completed.returncode}")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DXF parser subprocess returned invalid JSON") from exc

    return parse_dxf(
        entry["content"],
        entry["filename"],
        approved_pattern_regex=approved_pattern_regex,
        approved_pattern_name=approved_pattern_name,
        extracted_text=extracted_text,
    )


def _cache_detect_entries(project_id: int, file_ids: str | None, entries: list[dict[str, Any]]) -> str:
    _prune_detect_cache()
    token = uuid.uuid4().hex
    with _DETECT_CACHE_LOCK:
        _DETECT_CACHE[token] = {
            "created_at": time.time(),
            "project_id": project_id,
            "file_ids": file_ids,
            "entries": entries,
        }
    return token


def _consume_detect_entries(project_id: int, detect_token: str | None) -> list[dict[str, Any]] | None:
    if not detect_token:
        return None
    _prune_detect_cache()
    with _DETECT_CACHE_LOCK:
        cached = _DETECT_CACHE.pop(detect_token, None)
    if not cached:
        return None
    if cached.get("project_id") != project_id:
        return None
    return cached.get("entries")


# ---------------------------------------------------------------------------
# Scan from uploaded bytes (multipart — one or more files)
# ---------------------------------------------------------------------------

@router.post("/{project_id}/scan-strings")
async def scan_strings(
    project_id: int,
    files: Optional[List[UploadFile]] = File(default=None),
    file_ids: Optional[str] = Form(default=None),   # comma-separated IDs of already-uploaded files
    approved_pattern_name: Optional[str] = Form(default=None),
    approved_pattern_regex: Optional[str] = Form(default=None),
    detect_token: Optional[str] = Form(default=None),
):
    """
    Scan one or more design PDFs and return extracted string data,
    site metadata, capacity info, gaps and anomalies.

    Two modes:
    • Upload files directly (multipart files=[...])
    • Reference already-uploaded project files by file_id (form field file_ids="id1,id2")
    """
    cached_entries = _consume_detect_entries(project_id, detect_token)
    if cached_entries is not None:
        scan_entries = _hydrate_scan_entries(cached_entries)
    else:
        file_pairs = await _collect_scan_file_pairs(project_id, files, file_ids)
        scan_entries = _prepare_scan_entries(file_pairs)

    try:
        if len(scan_entries) == 1:
            entry = scan_entries[0]
            fname = entry["filename"]
            ext = os.path.splitext(fname)[1].lower()
            if ext == ".dxf":
                result = _parse_dxf_entry(
                    entry,
                    approved_pattern_name=approved_pattern_name,
                    approved_pattern_regex=approved_pattern_regex,
                )
            else:
                content = entry["content"]
                result = build_site_design_preview(
                    content,
                    fname,
                    approved_pattern_regex=approved_pattern_regex,
                    approved_pattern_name=approved_pattern_name,
                    extracted_text=entry["text"],
                )
        else:
            # Mixed multi-file: split by type
            pdfs = [(entry["content"], entry["filename"]) for entry in scan_entries if os.path.splitext(entry["filename"])[1].lower() == ".pdf"]
            pdf_texts = [entry["text"] for entry in scan_entries if os.path.splitext(entry["filename"])[1].lower() == ".pdf"]
            dxfs = [entry for entry in scan_entries if os.path.splitext(entry["filename"])[1].lower() == ".dxf"]
            results_list = []
            if pdfs:
                results_list.append(
                    build_site_design_preview_multi(
                        pdfs,
                        approved_pattern_regex=approved_pattern_regex,
                        approved_pattern_name=approved_pattern_name,
                        extracted_texts=pdf_texts,
                    )
                )
            for entry in dxfs:
                results_list.append(
                    _parse_dxf_entry(
                        entry,
                        approved_pattern_name=approved_pattern_name,
                        approved_pattern_regex=approved_pattern_regex,
                    )
                )
            if len(results_list) == 1:
                result = results_list[0]
            else:
                # Merge: take first as base, aggregate strings/entities
                result = results_list[0]
                for r in results_list[1:]:
                    result["valid_count"] += r.get("valid_count", 0)
                    result["invalid_count"] += r.get("invalid_count", 0)
                    result["inverters"] = result.get("inverters", []) + r.get("inverters", [])
                    result["ac_assets"] = result.get("ac_assets", []) + r.get("ac_assets", [])
                    result["batteries"] = result.get("batteries", []) + r.get("batteries", [])
                    result["validation_findings"] = result.get("validation_findings", []) + r.get("validation_findings", [])
                    result["output_validation_findings"] = result.get("output_validation_findings", []) + r.get("output_validation_findings", [])
                    # Merge mppt_groups: first non-empty wins
                    if not result.get("mppt_groups") and r.get("mppt_groups"):
                        result["mppt_groups"] = r["mppt_groups"]
                    # page_count: sum across files
                    if r.get("page_count") is not None:
                        result["page_count"] = (result.get("page_count") or 0) + r["page_count"]
                    # Propagate new scalar fields if not yet present
                    for _field in ("coordinates", "building_area_ha", "fenced_area_ha",
                                   "fence_length_m", "system_license", "storage_capacity_mwh"):
                        if result.get(_field) is None and r.get(_field) is not None:
                            result[_field] = r[_field]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Run topology validation
    try:
        bus = EventBus()
        topo_findings = TopologyValidationService().validate(result, project_id=project_id, bus=bus)
        recon = MapReconciliationService().reconcile(result, bus=bus)
        result["topology_findings"] = topo_findings
        result["reconciliation"] = recon
        result["events"] = bus.events()
    except Exception:
        result["topology_findings"] = []
        result["reconciliation"] = {}
        result["events"] = []

    return JSONResponse(content=result)


@router.post("/{project_id}/detect-string-pattern")
async def detect_string_pattern(
    project_id: int,
    files: Optional[List[UploadFile]] = File(default=None),
    file_ids: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    patterns, saved_pattern_name = _pattern_options_for_project(db, project_id)

    try:
        if file_ids and not files:
            records = _collect_project_file_records(project_id, file_ids)
            file_pairs = None
            file_count = len(records)
        else:
            records = None
            file_pairs = await _collect_scan_file_pairs(project_id, files, file_ids)
            file_count = len(file_pairs)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    def _detect_work() -> dict[str, Any]:
        if records is not None:
            scan_entries = _prepare_detect_entries_from_records(records)
        elif file_pairs is not None:
            scan_entries = _prepare_detect_entries(file_pairs)
        else:
            raise HTTPException(
                status_code=500,
                detail="detect-string-pattern: no file inputs after collect",
            )
        text = "\n".join(entry["text"] for entry in scan_entries if entry.get("text"))
        detect_token = _cache_detect_entries(project_id, file_ids, scan_entries)
        detection = detect_string_pattern_candidates(
            text,
            patterns,
            preferred_pattern_name=saved_pattern_name,
        )
        return {
            **detection,
            "saved_pattern_name": saved_pattern_name,
            "file_count": file_count,
            "detect_token": detect_token,
        }

    try:
        return await asyncio.to_thread(_detect_work)
    except re.error as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid string pattern regex in project configuration: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# ParserEngine output → legacy result-dict adapter
# ---------------------------------------------------------------------------

def _pe_ctx_to_result(ctx: dict) -> dict:
    """
    Convert a finished ParserEngine context into the `result` dict format
    expected by the DB sync steps (topology sync, string sync, analytics save).
    """
    strings_data  = ctx.get("strings", {})
    valid_strings = strings_data.get("valid_strings", [])
    invalid_strings = strings_data.get("invalid_strings", [])
    by_inverter   = strings_data.get("by_inverter", {})
    md            = ctx.get("project_metadata", {})
    batteries_ctx = ctx.get("batteries", {})
    install       = md.get("installation", {})
    tracking      = install.get("tracking", {})
    level         = ctx.get("string_level", 3)
    naming        = ctx.get("naming_patterns", {})
    str_pattern   = naming.get("strings", {}).get("detected_pattern")

    # Build string_rows -------------------------------------------------------
    string_rows: list[dict] = []
    for inv_key, info in by_inverter.items():
        for s in info.get("strings", []):
            string_rows.append({
                "is_valid": True,
                "string_code": s,
                "raw_value": s,
                "inverter_key": inv_key,
                "invalid_reason": None,
            })
    for s in invalid_strings:
        string_rows.append({
            "is_valid": False,
            "string_code": None,
            "raw_value": s,
            "inverter_key": None,
            "invalid_reason": "Invalid naming pattern",
        })

    # Build inverters list ----------------------------------------------------
    inverters_list: list[dict] = []
    for inv_key in sorted(by_inverter.keys(), key=_pe_sort_key if _PE_AVAILABLE else lambda x: x):
        inverters_list.append({
            "raw_name": inv_key,
            "normalized_name": inv_key,
            "strings_count": by_inverter[inv_key].get("count", len(by_inverter[inv_key].get("strings", []))),
            "pattern": str_pattern,
        })

    # Build missing / duplicate / outlier analytics ---------------------------
    str_val = ctx.get("string_validation", {})
    missing_raw = str_val.get("missing_by_inverter", [])
    missing_by_inv: dict[str, list[int]] = {
        item["inverter"]: item["missing_strings"] for item in missing_raw
    }

    dup_by_inv: dict[str, list[int]] = {}
    for s in strings_data.get("duplicates", []):
        parts = s.split(".")
        try:
            if level == 4 and len(parts) >= 5:
                key = f"{parts[1]}.{parts[2]}.{parts[3]}"
                idx = int(parts[4])
            else:
                key = f"{parts[1]}.{parts[2]}"
                idx = int(parts[3])
            dup_by_inv.setdefault(key, []).append(idx)
        except (IndexError, ValueError):
            pass

    # Scalar metadata ---------------------------------------------------------
    declared_kwp = md.get("declared_dc_power_kwp")
    plant_mw = round(declared_kwp / 1000, 4) if declared_kwp else None
    coords = md.get("coordinates")  # {"lat": ..., "lon": ...} or None
    module_wattages = md.get("module_wattages") or []

    design_val = ctx.get("design_validation", {})

    return {
        "valid_count":   len(valid_strings),
        "invalid_count": len(invalid_strings),
        "string_rows":   string_rows,
        "inverters":     inverters_list,
        "inverter_count_detected": len(inverters_list),
        # site metadata
        "site_name":           md.get("site_name"),
        "country":             md.get("country"),
        "region":              md.get("region"),
        "coordinates":         coords,
        "latitude":            coords["lat"] if coords else None,
        "longitude":           coords["lon"] if coords else None,
        "plant_capacity_mw":   plant_mw,
        "system_rating_kwp":   declared_kwp,
        "module_count":        md.get("declared_modules"),
        "modules_per_string":  md.get("declared_modules_per_string"),
        "module_power_wp":     module_wattages[0] if module_wattages else None,
        "tracker_enabled":     tracking.get("enabled", False),
        "tracker_rotation_deg": None,
        "azimuth_deg":         None,
        # batteries
        "battery_capacity_mwh": batteries_ctx.get("storage_capacity_mwh"),
        "has_battery":          batteries_ctx.get("has_battery", False),
        # analytics
        "missing_strings_by_inverter":          missing_by_inv,
        "duplicate_string_numbers_by_inverter": dup_by_inv,
        "outlier_strings_by_inverter":          {},
        # validation
        "validation_findings":        design_val.get("flags", []),
        "output_validation_findings": [],
        "topology_findings":          [],
        "reconciliation":             {},
        "events":                     [],
        "ac_assets":                  [{"label": item} for item in ctx.get("ac_equipment", {}).get("items", [])],
        "batteries":                  [] if not batteries_ctx.get("has_battery") else [{"label": "BESS"}],
        "mppt_groups":                [],
        "suffix_string_issues":       [],
        "mppt_validation_issues":     [],
        "page_count":                 len(ctx.get("extracted", {}).get("pages", [])) or None,
        "inverter_models":            [md.get("inverter_model")] if md.get("inverter_model") else [],
        "source_document":            ctx.get("files", [""])[0].split("/")[-1].split("\\")[-1],
        "design_validation":          design_val,
    }


# ParserEngine step → (UI step number, pct when running, label)
_PE_STEP_MAP: dict[str, tuple[int, int, str]] = {
    "load_files":            (1,  5,  "Loading files"),
    "extract_text":          (1,  15, "Extracting text"),
    "extract_metadata":      (2,  22, "Reading site metadata"),
    "classify_installation": (2,  25, "Classifying installation"),
    "detect_patterns":       (2,  28, "Detecting naming patterns"),
    "extract_inverters":     (3,  35, "Mapping inverters"),
    "extract_strings":       (3,  45, "Extracting strings"),
    "extract_mppts":         (3,  50, "Extracting MPPTs"),
    "extract_ac_equipment":  (3,  52, "Reading AC equipment"),
    "extract_batteries":     (3,  55, "Reading storage"),
    "extract_simple_layout": (3,  58, "Building site layout"),
    "assign_profiles":       (4,  62, "Assigning inverter profiles"),
    "validate_strings":      (4,  68, "Validating strings"),
    "validate_output":       (4,  72, "Validating output"),
    "build_report":          (4,  78, "Building report"),
}


# ---------------------------------------------------------------------------
# SSE streaming scan endpoint
# GET /projects/{project_id}/scan-stream?file_ids=id1,id2
#
# Streams progress events as the pipeline runs:
#   step 1 – parse PDF / DXF
#   step 2 – extract strings & inverters  (done immediately after step 1)
#   step 3 – sync topology inverters to DB
#   step 4 – sync design strings to DB
#   step 5 – save analytics & finalise
#   complete – sends compact result + analytics blob
# ---------------------------------------------------------------------------

@router.get("/{project_id}/scan-stream")
def scan_stream(
    project_id: int,
    file_ids: str = Query(..., description="Comma-separated uploaded file IDs"),
    approved_pattern_name: str | None = Query(default=None),
    approved_pattern_regex: str | None = Query(default=None),
    detect_token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """SSE endpoint: runs the full scan pipeline and emits per-step progress."""

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def _sse_comment(comment: str = "keepalive") -> str:
        return f": {comment}\n\n"

    def generate():
        try:
            # ── Step 1: load files from disk & parse ──────────────────────
            yield _sse({"step": 1, "state": "running", "pct": 5,
                        "label": "Parsing design file"})

            cached_entries = _consume_detect_entries(project_id, detect_token)
            if cached_entries is not None:
                scan_entries = _hydrate_scan_entries(cached_entries)
            else:
                try:
                    records = _collect_project_file_records(project_id, file_ids)
                    scan_entries = _prepare_scan_entries_from_records(records)
                except HTTPException as exc:
                    yield _sse({"type": "error", "error": exc.detail})
                    return
                except (ValueError, RuntimeError) as exc:
                    yield _sse({"type": "error", "error": str(exc)})
                    return

            if not scan_entries:
                yield _sse({"type": "error", "error": "No files found for the given file_ids."})
                return

            # Persist the approved pattern before the destructive sync begins.
            if approved_pattern_name:
                try:
                    project = project_repo.get_project(db, project_id)
                    if project:
                        project.string_pattern = approved_pattern_name
                        db.commit()
                except Exception as exc:
                    db.rollback()
                    yield _sse({"type": "error", "step": 1, "error": f"Could not save approved pattern: {exc}"})
                    return

            # ── Parse: use legacy parser for PDF (reliable 672-string path).
            # ParserEngine shallow-merges step results via ctx.update(), which
            # causes later steps (e.g. validate_strings) to overwrite by_inverter
            # with partial data. We keep the engine wiring for DXF-only jobs.
            _use_engine = (approved_pattern_regex is None) and _PE_AVAILABLE and all(
                os.path.splitext(entry["filename"])[1].lower() != ".pdf" for entry in scan_entries
            )
            if _use_engine:
                # Write files to temp paths so ParserEngine can read them
                tmp_files: list[str] = []
                tmp_handles = []
                try:
                    for entry in scan_entries:
                        fname = entry["filename"]
                        ext = os.path.splitext(fname)[1].lower()
                        path = entry.get("path")
                        if path:
                            tmp_files.append(path)
                            continue
                        tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                        tf.write(entry["content"])
                        tf.flush()
                        tf.close()
                        tmp_files.append(tf.name)
                        tmp_handles.append(tf.name)
                except Exception as exc:
                    yield _sse({"type": "error", "step": 1, "error": f"Temp file error: {exc}"})
                    return

                engine = _ParserEngine()
                ctx: dict = {"files": tmp_files, "job_id": "sse"}
                try:
                    for step_def in _PE_STEPS:
                        sid = step_def["id"]
                        ui_step, pct, label = _PE_STEP_MAP.get(sid, (1, 10, step_def["title"]))
                        yield _sse({"step": ui_step, "state": "running", "pct": pct, "label": label})
                        step_fn = getattr(engine, f"step_{sid}", None)
                        if step_fn is None:
                            continue
                        step_result = step_fn(ctx)
                        if isinstance(step_result, dict):
                            ctx.update(step_result)
                except Exception as exc:
                    yield _sse({"type": "error", "step": 1, "error": f"Parser engine error: {exc}"})
                    return
                finally:
                    for p in tmp_handles:
                        try:
                            os.unlink(p)
                        except OSError:
                            pass

                result = _pe_ctx_to_result(ctx)
            else:
                # Keep the SSE connection alive while long PDF parsing runs
                # so reverse proxies do not abort the chunked response.
                parse_state: dict = {"done": False, "result": None, "error": None}

                def _run_legacy_parse() -> None:
                    try:
                        if len(scan_entries) == 1:
                            entry = scan_entries[0]
                            fname = entry["filename"]
                            ext = os.path.splitext(fname)[1].lower()
                            if ext == ".dxf":
                                parse_state["result"] = _parse_dxf_entry(
                                    entry,
                                    approved_pattern_name=approved_pattern_name,
                                    approved_pattern_regex=approved_pattern_regex,
                                )
                            else:
                                parse_state["result"] = build_site_design_preview(
                                    entry["content"],
                                    fname,
                                    approved_pattern_regex=approved_pattern_regex,
                                    approved_pattern_name=approved_pattern_name,
                                    extracted_text=entry["text"],
                                )
                        else:
                            pdf_entries = [entry for entry in scan_entries if os.path.splitext(entry["filename"])[1].lower() == ".pdf"]
                            pdfs = [(entry["content"], entry["filename"]) for entry in pdf_entries]
                            pdf_texts = [entry["text"] for entry in pdf_entries]
                            dxfs = [entry for entry in scan_entries if os.path.splitext(entry["filename"])[1].lower() == ".dxf"]
                            results_list: list[dict] = []
                            if pdfs:
                                results_list.append(build_site_design_preview_multi(
                                    pdfs,
                                    approved_pattern_regex=approved_pattern_regex,
                                    approved_pattern_name=approved_pattern_name,
                                    extracted_texts=pdf_texts,
                                ))
                            for entry in dxfs:
                                results_list.append(
                                    _parse_dxf_entry(
                                        entry,
                                        approved_pattern_name=approved_pattern_name,
                                        approved_pattern_regex=approved_pattern_regex,
                                    )
                                )
                            if not results_list:
                                raise ValueError("No parseable files found.")
                            merged = results_list[0]
                            for r in results_list[1:]:
                                merged["valid_count"] += r.get("valid_count", 0)
                                merged["invalid_count"] += r.get("invalid_count", 0)
                                merged["inverters"] = merged.get("inverters", []) + r.get("inverters", [])
                                merged["ac_assets"] = merged.get("ac_assets", []) + r.get("ac_assets", [])
                                merged["batteries"] = merged.get("batteries", []) + r.get("batteries", [])
                                merged["validation_findings"] = merged.get("validation_findings", []) + r.get("validation_findings", [])
                                merged["output_validation_findings"] = merged.get("output_validation_findings", []) + r.get("output_validation_findings", [])
                            parse_state["result"] = merged
                    except Exception as exc:
                        parse_state["error"] = exc
                    finally:
                        parse_state["done"] = True

                parse_thread = threading.Thread(target=_run_legacy_parse, daemon=True)
                parse_thread.start()
                last_keepalive = time.monotonic()
                while not parse_state["done"]:
                    now = time.monotonic()
                    if now - last_keepalive >= 10:
                        yield _sse_comment()
                        last_keepalive = now
                    time.sleep(0.5)
                parse_thread.join()

                if parse_state["error"] is not None:
                    exc = parse_state["error"]
                    if isinstance(exc, (ValueError, RuntimeError)):
                        yield _sse({"type": "error", "step": 1, "error": str(exc)})
                    else:
                        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
                        yield _sse({"type": "error", "step": 1, "error": f"Unexpected parse error: {exc}"})
                    return

                result = parse_state["result"]
                if not isinstance(result, dict):
                    yield _sse({"type": "error", "step": 1, "error": "Parser returned an invalid response."})
                    return

            # Topology validation (fast, non-DB)
            try:
                bus = EventBus()
                topo_findings = TopologyValidationService().validate(result, project_id=project_id, bus=bus)
                recon = MapReconciliationService().reconcile(result, bus=bus)
                result["topology_findings"] = topo_findings
                result["reconciliation"] = recon
                result["events"] = bus.events()
            except Exception:
                result.setdefault("topology_findings", [])
                result.setdefault("reconciliation", {})
                result.setdefault("events", [])

            yield _sse({"step": 1, "state": "done", "pct": 25, "label": "Parsing design file"})
            yield _sse({"step": 2, "state": "done", "pct": 30, "label": "Extracting strings & inverters"})

            # ── Step 3: sync topology inverters ───────────────────────────
            yield _sse({"step": 3, "state": "running", "pct": 35, "label": "Syncing topology"})
            try:
                from app.models.topology import ProjectInverter
                db.query(ProjectInverter).filter(ProjectInverter.project_id == project_id).delete()
                for inv in result.get("inverters", []):
                    parts = inv["raw_name"].split(".")
                    obj = ProjectInverter(
                        project_id=project_id,
                        inverter_label=inv["raw_name"],
                        section_no=int(parts[0]) if len(parts) >= 2 else None,
                        block_no=int(parts[1]) if len(parts) >= 2 else None,
                        detected_string_count=inv.get("strings_count", 0),
                        detection_pattern=inv.get("pattern"),
                        is_inferred=inv.get("pattern") in ("inferred", "gap_fill"),
                    )
                    db.add(obj)
                db.commit()
            except Exception as exc:
                db.rollback()
                yield _sse({"type": "error", "step": 3, "error": str(exc)})
                return
            yield _sse({"step": 3, "state": "done", "pct": 60, "label": "Syncing topology"})

            # ── Step 4: sync design strings ───────────────────────────────
            yield _sse({"step": 4, "state": "running", "pct": 65, "label": "Syncing design strings"})
            try:
                from app.models.project import Inverter, String as ProjectString
                db.query(ProjectString).filter(ProjectString.project_id == project_id).delete()
                db.query(Inverter).filter(Inverter.project_id == project_id).delete()
                db.flush()
                inv_map: dict[str, object] = {}
                for inv in result.get("inverters", []):
                    obj = Inverter(
                        project_id=project_id,
                        inverter_no=inv.get("raw_name") or inv.get("normalized_name", ""),
                        metadata_json={"pattern": inv.get("pattern"),
                                       "strings_count": inv.get("strings_count", 0)},
                    )
                    db.add(obj)
                    db.flush()
                    inv_map[obj.inverter_no] = obj
                for row in result.get("string_rows", []):
                    if not row.get("is_valid") or not row.get("string_code"):
                        continue
                    inv_key = row.get("inverter_key")
                    inv_obj = inv_map.get(inv_key) if inv_key else None
                    db.add(ProjectString(
                        project_id=project_id,
                        inverter_id=inv_obj.id if inv_obj else None,
                        string_no=row["string_code"],
                        status="planned",
                    ))
                db.commit()
            except Exception as exc:
                db.rollback()
                yield _sse({"type": "error", "step": 4, "error": str(exc)})
                return
            yield _sse({"step": 4, "state": "done", "pct": 85, "label": "Syncing design strings"})

            # ── Step 5: save analytics ────────────────────────────────────
            yield _sse({"step": 5, "state": "running", "pct": 90, "label": "Refreshing project data"})
            string_rows = result.get("string_rows", [])
            invalid_rows_compact = [
                {
                    "string_code": r.get("string_code"),
                    "raw_value": r.get("raw_value"),
                    "inverter_key": r.get("inverter_key"),
                    "invalid_reason": r.get("invalid_reason"),
                }
                for r in string_rows if not r.get("is_valid")
            ]
            invalid_ab_labels = result.get("invalid_ab_labels", []) or []
            all_invalid_rows: list[dict] = []
            seen_invalid_keys: set[tuple[object, object, object, object]] = set()
            for row in invalid_rows_compact:
                key = (
                    row.get("string_code"),
                    row.get("raw_value"),
                    row.get("inverter_key"),
                    row.get("invalid_reason"),
                )
                if key in seen_invalid_keys:
                    continue
                seen_invalid_keys.add(key)
                all_invalid_rows.append(row)
            inverters_list = result.get("inverters", [])
            analytics: dict = {
                "pattern": inverters_list[0].get("pattern") if inverters_list else None,
                "approved_pattern_name": approved_pattern_name,
                "approved_pattern_regex": approved_pattern_regex,
                "valid_count": result.get("valid_count", 0),
                "invalid_count": len(all_invalid_rows) + len(invalid_ab_labels),
                "invalid_rows": all_invalid_rows,
                "missing_strings_by_inverter": result.get("missing_strings_by_inverter", {}),
                "duplicate_string_numbers_by_inverter": result.get("duplicate_string_numbers_by_inverter", {}),
                "outlier_strings_by_inverter": result.get("outlier_strings_by_inverter", {}),
                "design_metadata": {
                    "project_name": result.get("project_name"),
                    "site_code": result.get("site_code"),
                    "site_name": result.get("site_name"),
                    "source_document": result.get("source_document"),
                    "country": result.get("country"),
                    "region": result.get("region"),
                    "coordinates": result.get("coordinates"),
                    "latitude": result.get("latitude"),
                    "longitude": result.get("longitude"),
                    "plant_capacity_mw": result.get("plant_capacity_mw"),
                    "system_rating_kwp": result.get("system_rating_kwp"),
                    "module_type": result.get("module_type"),
                    "module_count": result.get("module_count"),
                    "module_power_wp": result.get("module_power_wp"),
                    "modules_per_string": result.get("modules_per_string"),
                    "total_strings_doc": result.get("total_strings_doc"),
                    "tracker_enabled": result.get("tracker_enabled", False),
                    "tracker_rotation_deg": result.get("tracker_rotation_deg"),
                    "azimuth_deg": result.get("azimuth_deg"),
                    "battery_capacity_mwh": result.get("battery_capacity_mwh"),
                    "battery_type": result.get("battery_type"),
                    "storage_capacity_mwh": result.get("storage_capacity_mwh"),
                    "bess_inv": result.get("bess_inv"),
                    "building_area_ha": result.get("building_area_ha"),
                    "fenced_area_ha": result.get("fenced_area_ha"),
                    "fence_length_m": result.get("fence_length_m"),
                    "system_license": result.get("system_license"),
                    "inverter_models": result.get("inverter_models", []),
                    "inverter_count_detected": result.get("inverter_count_detected", 0),
                    "page_count": result.get("page_count"),
                    "validation_findings": result.get("validation_findings", []),
                    "output_validation_findings": result.get("output_validation_findings", []),
                    "invalid_ab_labels": invalid_ab_labels,
                    "suffix_string_issues": result.get("suffix_string_issues", []),
                    "mppt_validation_issues": result.get("mppt_validation_issues", []),
                },
            }
            try:
                from app.models.project import Project as ProjectModel
                proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                if proj:
                    proj.scan_analytics_json = analytics
                    db.commit()
            except Exception as exc:
                db.rollback()
                yield _sse({"type": "error", "step": 5, "error": str(exc)})
                return
            yield _sse({"step": 5, "state": "done", "pct": 98, "label": "Refreshing project data"})

            # ── Complete: send compact result (no large arrays) ────────────
            compact = {k: v for k, v in result.items()
                       if k not in ("string_rows", "page_texts", "strings", "gaps", "anomalies")}
            yield _sse({"type": "complete", "pct": 100, "result": compact, "analytics": analytics})
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            yield _sse({"type": "error", "error": f"Unexpected scan stream error: {exc}"})
            return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx response buffering
            "Connection":       "keep-alive",
        },
    )
