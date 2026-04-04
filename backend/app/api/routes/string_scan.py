"""
POST /api/projects/{id}/scan-strings
  Accepts one or more uploaded PDF/DXF files (multipart/form-data) OR file_ids
  referencing already-uploaded project files.
  Returns a full string extraction preview via the unified PDF/DXF parser.

GET /api/projects/{id}/scan-stream?file_ids=id1,id2
  Server-Sent Events stream — same pipeline (legacy / optional clients).

POST /api/projects/{id}/scan-run  JSON body { file_ids, ... }
  Same pipeline; returns one JSON response (preferred behind proxies — no chunked SSE).
"""
import asyncio
import json
import os
import re
import sys
import tempfile
import threading
import time
import traceback
import uuid
from typing import Any, Iterator, List, Optional

from pydantic import BaseModel

from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db

from app.parsers.design.unified_layout_parser import extract_joined_text, run_full
from app.parsers.design.unified_scan_adapter import (
    adapt_unified_report_to_legacy_scan_result,
    detect_string_pattern_candidates,
)
from app.repositories import project_repo
from app.services.topology_validation import TopologyValidationService
from app.services.map_reconciliation import MapReconciliationService
from app.services.event_bus import EventBus

router = APIRouter()
_DETECT_CACHE_TTL_SECONDS = 15 * 60
_DETECT_CACHE_LOCK = threading.Lock()
_DETECT_CACHE: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Background-job store — backed by /tmp files so all uvicorn workers share state
# ---------------------------------------------------------------------------
_JOB_TTL_SECONDS = 30 * 60      # keep finished job files 30 min
_JOB_DIR = tempfile.gettempdir()
_JOB_PREFIX = "solarica_scan_"
_PHASE_PREFIX = "solarica_phase_"


def _job_path(job_id: str) -> str:
    return os.path.join(_JOB_DIR, f"{_JOB_PREFIX}{job_id}.json")


# ── Phase-file helpers ────────────────────────────────────────────────────────

def _phase_dir(job_id: str) -> str:
    return os.path.join(_JOB_DIR, f"{_PHASE_PREFIX}{job_id}")


def _phase_path(job_id: str, phase: int) -> str:
    return os.path.join(_phase_dir(job_id), f"phase{phase}.json")


def _save_phase(job_id: str, phase: int, data: Any) -> None:
    """Atomically write phase output to its JSON file."""
    d = _phase_dir(job_id)
    os.makedirs(d, exist_ok=True)
    p = _phase_path(job_id, phase)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, p)


def _load_phase(job_id: str, phase: int) -> Any:
    with open(_phase_path(job_id, phase), encoding="utf-8") as f:
        return json.load(f)


def _cleanup_phase_dir(job_id: str) -> None:
    import shutil
    d = _phase_dir(job_id)
    try:
        shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def _make_job(project_id: int) -> tuple[str, dict]:
    job_id = uuid.uuid4().hex
    job: dict[str, Any] = {
        "state": "running",   # running | done | error
        "pct": 0,
        "label": "Starting…",
        "error": None,
        "scan_summary": None,
        "project_id": project_id,
        "created_at": time.time(),
    }
    _write_job(job_id, job)
    _prune_jobs()
    return job_id, job


def _write_job(job_id: str, job: dict) -> None:
    """Atomically write job state to /tmp — safe for multi-worker access."""
    path = _job_path(job_id)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(job, f)
    os.replace(tmp, path)          # atomic on POSIX


def _read_job(job_id: str) -> dict | None:
    try:
        with open(_job_path(job_id)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _prune_jobs() -> None:
    cutoff = time.time() - _JOB_TTL_SECONDS
    try:
        for name in os.listdir(_JOB_DIR):
            if not name.startswith(_JOB_PREFIX):
                continue
            p = os.path.join(_JOB_DIR, name)
            try:
                if os.path.getmtime(p) < cutoff:
                    os.unlink(p)
            except OSError:
                pass
    except OSError:
        pass


def _job_update(job_id: str, **kwargs) -> None:
    """Read-modify-write job file.  job_id is the key, not the dict."""
    job = _read_job(job_id) or {}
    job.update(kwargs)
    _write_job(job_id, job)

UPLOAD_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "uploads", "projects"
)
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


def _materialize_scan_paths(entries: list[dict[str, Any]]) -> tuple[list[Path], list[Path]]:
    paths: list[Path] = []
    cleanup: list[Path] = []
    for entry in entries:
        existing = entry.get("path")
        if existing:
            paths.append(Path(existing))
            continue
        content = entry.get("content")
        if content is None:
            raise ValueError(f"No path or content for entry: {entry.get('filename')}")
        ext = os.path.splitext(entry.get("filename", ""))[1].lower() or ".pdf"
        tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tf.write(content)
        tf.close()
        p = Path(tf.name)
        paths.append(p)
        cleanup.append(p)
    return paths, cleanup


def _entry_unified_text(entry: dict[str, Any]) -> str:
    p = entry.get("path")
    if p:
        return extract_joined_text(Path(p))
    content = entry.get("content")
    if content is None:
        return ""
    ext = os.path.splitext(entry.get("filename", ""))[1].lower() or ".pdf"
    tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tf.write(content)
    tf.close()
    try:
        return extract_joined_text(Path(tf.name))
    finally:
        try:
            os.unlink(tf.name)
        except OSError:
            pass


def _run_unified_scan(
    entries: list[dict[str, Any]],
    *,
    approved_pattern_name: str | None,
    approved_pattern_regex: str | None,
) -> dict[str, Any]:
    paths, cleanup = _materialize_scan_paths(entries)
    try:
        report = run_full(paths)
        primary = entries[0].get("filename") or "design"
        return adapt_unified_report_to_legacy_scan_result(
            report,
            source_document=primary,
            approved_pattern_name=approved_pattern_name,
            approved_pattern_regex=approved_pattern_regex,
        )
    finally:
        for p in cleanup:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


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
        if ext not in (".pdf", ".dxf"):
            raise ValueError(f"Unsupported file type: {ext}")
        entry = {"filename": filename, "content": content, "text": "", "text_is_partial": False}
        entry["text"] = _entry_unified_text(entry)
        entries.append(entry)
    return entries


def _prepare_detect_entries(file_pairs: list[tuple[bytes, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for content, filename in file_pairs:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".pdf", ".dxf"):
            raise ValueError(f"Unsupported file type: {ext}")
        entry = {"filename": filename, "content": content, "text": "", "text_is_partial": False}
        entry["text"] = _entry_unified_text(entry)
        entries.append(entry)
    return entries


def _prepare_scan_entries_from_records(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for record in records:
        ext = record["ext"]
        if ext == ".pdf":
            with open(record["path"], "rb") as f:
                content = f.read()
            entry = {
                "filename": record["filename"],
                "path": record["path"],
                "content": content,
                "text": "",
                "text_is_partial": False,
            }
        elif ext == ".dxf":
            entry = {
                "filename": record["filename"],
                "path": record["path"],
                "text": "",
                "text_is_partial": False,
            }
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        entry["text"] = _entry_unified_text(entry)
        entries.append(entry)
    return entries


def _prepare_detect_entries_from_records(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    return _prepare_scan_entries_from_records(records)


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
        result = _run_unified_scan(
            scan_entries,
            approved_pattern_name=approved_pattern_name,
            approved_pattern_regex=approved_pattern_regex,
        )
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
# Polling-based detect endpoints (wizard uses these to avoid long HTTP waits)
# ---------------------------------------------------------------------------

class DetectStartBody(BaseModel):
    """Multipart fields are not JSON, so this endpoint uses Form params."""
    pass  # handled via Form parameters directly


@router.post("/{project_id}/detect-start")
async def detect_start(
    project_id: int,
    files: Optional[List[UploadFile]] = File(default=None),
    file_ids: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Start a background pattern-detection job and return a job_id immediately.
    Poll GET /{project_id}/detect-status/{job_id} for progress and result.
    """
    patterns, saved_pattern_name = _pattern_options_for_project(db, project_id)

    # Collect file bytes now (in the async request handler, before the thread)
    try:
        if file_ids and not files:
            records = _collect_project_file_records(project_id, file_ids)
            file_pairs: list[tuple[bytes, str]] | None = None
            file_count = len(records)
        else:
            records = None
            file_pairs = await _collect_scan_file_pairs(project_id, files, file_ids)
            file_count = len(file_pairs)
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job_id, _job = _make_job(project_id)
    _job_update(job_id, label="Detecting pattern…", pct=5)

    def _bg() -> None:
        try:
            if records is not None:
                scan_entries = _prepare_detect_entries_from_records(records)
            else:
                scan_entries = _prepare_detect_entries(file_pairs or [])
            text = "\n".join(entry["text"] for entry in scan_entries if entry.get("text"))
            detect_token = _cache_detect_entries(project_id, file_ids, scan_entries)
            detection = detect_string_pattern_candidates(
                text, patterns, preferred_pattern_name=saved_pattern_name,
            )
            result = {
                **detection,
                "saved_pattern_name": saved_pattern_name,
                "file_count": file_count,
                "detect_token": detect_token,
            }
            _job_update(job_id, state="done", pct=100, label="Done", scan_summary=result)
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            _job_update(job_id, state="error", error=str(exc))

    threading.Thread(target=_bg, daemon=True).start()
    return {"job_id": job_id}


@router.get("/{project_id}/detect-status/{job_id}")
def detect_status(project_id: int, job_id: str) -> dict:
    """Poll detect-job progress.  When state=='done', scan_summary contains the detection result."""
    job = _read_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Detect job not found (may have expired).")
    if job.get("project_id") != project_id:
        raise HTTPException(status_code=403, detail="Job does not belong to this project.")
    return {k: v for k, v in job.items() if k not in ("created_at", "project_id")}


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
#   complete – analytics + small scan_summary (no full parse result blob)
# ---------------------------------------------------------------------------


def _scan_pipeline_events(
    db: Session,
    project_id: int,
    file_ids: str,
    approved_pattern_name: str | None,
    approved_pattern_regex: str | None,
    detect_token: str | None,
) -> Iterator[dict]:
    try:
        # ── Step 1: load files from disk & parse ──────────────────────
        yield {"step": 1, "state": "running", "pct": 5,
               "label": "Parsing design file"}

        cached_entries = _consume_detect_entries(project_id, detect_token)
        if cached_entries is not None:
            # Cached entries already contain 'path'; no need to hydrate content —
            # _run_unified_scan → run_full reads the file directly from path.
            scan_entries = cached_entries
        else:
            try:
                records = _collect_project_file_records(project_id, file_ids)
                # Build minimal entries with just the file path.  run_full will
                # open the PDF/DXF once inside the parse thread; we deliberately
                # skip _prepare_scan_entries_from_records here because that
                # function calls _entry_unified_text which opens the file with
                # pdfplumber a second time, doubling parse time on large PDFs.
                scan_entries = [
                    {"filename": r["filename"], "path": r["path"], "ext": r["ext"]}
                    for r in records
                ]
            except HTTPException as exc:
                yield {"type": "error", "error": exc.detail}
                return
            except (ValueError, RuntimeError) as exc:
                yield {"type": "error", "error": str(exc)}
                return

        if not scan_entries:
            yield {"type": "error", "error": "No files found for the given file_ids."}
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
                yield {"type": "error", "step": 1, "error": f"Could not save approved pattern: {exc}"}
                return

        # Unified PDF/DXF parse (may be slow — keep SSE alive for proxies).
        parse_state: dict = {"done": False, "result": None, "error": None}

        def _run_unified_parse_thread() -> None:
            try:
                parse_state["result"] = _run_unified_scan(
                    scan_entries,
                    approved_pattern_name=approved_pattern_name,
                    approved_pattern_regex=approved_pattern_regex,
                )
            except Exception as exc:
                parse_state["error"] = exc
            finally:
                parse_state["done"] = True

        parse_thread = threading.Thread(target=_run_unified_parse_thread, daemon=True)
        parse_thread.start()
        last_keepalive = time.monotonic()
        while not parse_state["done"]:
            now = time.monotonic()
            if now - last_keepalive >= 10:
                yield {"_keepalive": True}
                last_keepalive = now
            time.sleep(0.5)
        parse_thread.join()

        if parse_state["error"] is not None:
            exc = parse_state["error"]
            if isinstance(exc, (ValueError, RuntimeError)):
                yield {"type": "error", "step": 1, "error": str(exc)}
            else:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
                yield {"type": "error", "step": 1, "error": f"Unexpected parse error: {exc}"}
            return

        result = parse_state["result"]
        if not isinstance(result, dict):
            yield {"type": "error", "step": 1, "error": "Parser returned an invalid response."}
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

        yield {"step": 1, "state": "done", "pct": 25, "label": "Parsing design file"}
        yield {"step": 2, "state": "done", "pct": 30, "label": "Extracting strings & inverters"}

        # ── Step 3: sync topology inverters ───────────────────────────
        yield {"step": 3, "state": "running", "pct": 35, "label": "Syncing topology"}
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
            yield {"type": "error", "step": 3, "error": str(exc)}
            return
        yield {"step": 3, "state": "done", "pct": 60, "label": "Syncing topology"}

        # ── Step 4: sync design strings ───────────────────────────────
        yield {"step": 4, "state": "running", "pct": 65, "label": "Syncing design strings"}
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
            yield {"type": "error", "step": 4, "error": str(exc)}
            return
        yield {"step": 4, "state": "done", "pct": 85, "label": "Syncing design strings"}

        # ── Step 5: save analytics ────────────────────────────────────
        yield {"step": 5, "state": "running", "pct": 90, "label": "Refreshing project data"}
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
                yield {"type": "synced", "kind": "scan_analytics"}
        except Exception as exc:
            db.rollback()
            yield {"type": "error", "step": 5, "error": str(exc)}
            return
        yield {"step": 5, "state": "done", "pct": 98, "label": "Refreshing project data"}

        yield {
            "type": "complete",
            "pct": 100,
            "scan_summary": {
                "valid_count": analytics.get("valid_count", 0),
                "invalid_count": analytics.get("invalid_count", 0),
                "inverter_count_detected": result.get("inverter_count_detected", 0),
            },
        }
    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        yield {"type": "error", "error": f"Unexpected scan stream error: {exc}"}
        return


# ---------------------------------------------------------------------------
# Background-job worker  (drives the polling-based scan API)
# ---------------------------------------------------------------------------

def _run_scan_job(
    job_id: str,
    project_id: int,
    file_ids: str,
    approved_pattern_name: str | None,
    approved_pattern_regex: str | None,
    detect_token: str | None,
    *,
    entries_override: list[dict[str, Any]] | None = None,
    temp_paths: list[str] | None = None,
) -> None:
    """
    5-phase scan pipeline.  Each phase writes its output to a JSON file in
    /tmp/solarica_phase_{job_id}/ before proceeding to the next phase.
    This keeps peak memory low — PDF objects from Phase 1 are freed before
    Phase 2 starts — and gives a clear checkpoint if anything fails.

    Phase 1  (5→30%)   Extract text items from PDF/DXF files
    Phase 2  (30→55%)  Parse site pattern, strings, per-inverter stats
    Phase 3  (55→68%)  Adapt to legacy format + topology validation
    Phase 4  (68→85%)  DB sync: topology inverters + design strings  [skipped if project_id==0]
    Phase 5  (85→100%) Save analytics to project record              [skipped if project_id==0]

    When project_id==0 (wizard mode), Phases 4 & 5 are skipped and the full
    parsed result is returned as scan_summary so the wizard can pre-fill its form.
    """
    from app.parsers.design.unified_layout_parser import (
        extract_items_from_file, run_full_from_items,
        items_to_json, items_from_json,
    )
    from app.parsers.design.unified_scan_adapter import adapt_unified_report_to_legacy_scan_result

    db = SessionLocal()
    try:
        # ── Resolve file entries ──────────────────────────────────────────────
        if entries_override is not None:
            entries = entries_override
        else:
            cached_entries = _consume_detect_entries(project_id, detect_token)
            if cached_entries is not None:
                entries = cached_entries
            else:
                try:
                    records = _collect_project_file_records(project_id, file_ids)
                    entries = [{"filename": r["filename"], "path": r["path"], "ext": r["ext"]}
                               for r in records]
                except (HTTPException, ValueError, RuntimeError) as exc:
                    _job_update(job_id, state="error",
                                error=getattr(exc, "detail", None) or str(exc))
                    return

        # Only persist the pattern when we have a real project
        if approved_pattern_name and project_id > 0:
            try:
                proj = project_repo.get_project(db, project_id)
                if proj:
                    proj.string_pattern = approved_pattern_name
                    db.commit()
            except Exception:
                db.rollback()

        # ── Phase 1: Extract text items ───────────────────────────────────────
        _job_update(job_id, pct=5, label="Extracting text from design files")
        try:
            all_items: list[Any] = []
            source_doc = entries[0].get("filename", "design") if entries else "design"
            for entry in entries:
                path = entry.get("path")
                if path:
                    raw = extract_items_from_file(Path(path))
                else:
                    content = entry.get("content")
                    if not content:
                        continue
                    ext = os.path.splitext(entry.get("filename", ""))[1].lower() or ".pdf"
                    tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    tf.write(content); tf.close()
                    try:
                        raw = extract_items_from_file(Path(tf.name))
                    finally:
                        try: os.unlink(tf.name)
                        except OSError: pass
                all_items.extend(raw)
            _save_phase(job_id, 1, {"items": items_to_json(all_items), "source_doc": source_doc})
            # Explicitly free the large list before Phase 2
            all_items = []   # type: ignore[assignment]
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            _job_update(job_id, state="error", error=f"Phase 1 (text extraction) failed: {exc}")
            return
        _job_update(job_id, pct=30, label="Parsing strings and inverters")

        # ── Phase 2: Parse + analyze ──────────────────────────────────────────
        try:
            p1 = _load_phase(job_id, 1)
            items_loaded = items_from_json(p1["items"])
            report = run_full_from_items(items_loaded)
            _save_phase(job_id, 2, report)
            items_loaded = []   # type: ignore[assignment]
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            _job_update(job_id, state="error", error=f"Phase 2 (string parsing) failed: {exc}")
            return
        _job_update(job_id, pct=55, label="Validating design topology")

        # ── Phase 3: Adapt + validate ─────────────────────────────────────────
        try:
            p2 = _load_phase(job_id, 2)
            source_doc = _load_phase(job_id, 1).get("source_doc", "design")
            result = adapt_unified_report_to_legacy_scan_result(
                p2,
                source_document=source_doc,
                approved_pattern_name=approved_pattern_name,
                approved_pattern_regex=approved_pattern_regex,
            )
            try:
                from app.services.event_bus import EventBus
                from app.services.topology_validation import TopologyValidationService
                from app.services.map_reconciliation import MapReconciliationService
                bus = EventBus()
                result["topology_findings"] = TopologyValidationService().validate(
                    result, project_id=project_id, bus=bus)
                result["reconciliation"] = MapReconciliationService().reconcile(result, bus=bus)
                result["events"] = bus.events()
            except Exception:
                result.setdefault("topology_findings", [])
                result.setdefault("reconciliation", {})
                result.setdefault("events", [])
            _save_phase(job_id, 3, result)
        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            _job_update(job_id, state="error", error=f"Phase 3 (validation) failed: {exc}")
            return
        _job_update(job_id, pct=68, label="Syncing topology to database")

        # ── Wizard / preview mode: skip DB phases, return full result ─────────
        if project_id == 0:
            result = _load_phase(job_id, 3)
            _job_update(job_id, state="done", pct=100, label="Done", scan_summary=result)
            return

        # ── Phase 4: DB sync ──────────────────────────────────────────────────
        try:
            result = _load_phase(job_id, 3)
            from app.models.topology import ProjectInverter
            db.query(ProjectInverter).filter(ProjectInverter.project_id == project_id).delete()
            for inv in result.get("inverters", []):
                parts = inv["raw_name"].split(".")
                db.add(ProjectInverter(
                    project_id=project_id,
                    inverter_label=inv["raw_name"],
                    section_no=int(parts[0]) if len(parts) >= 2 else None,
                    block_no=int(parts[1]) if len(parts) >= 2 else None,
                    detected_string_count=inv.get("strings_count", 0),
                    detection_pattern=inv.get("pattern"),
                    is_inferred=inv.get("pattern") in ("inferred", "gap_fill"),
                ))
            db.commit()
            _job_update(job_id, pct=75, label="Syncing design strings")

            from app.models.project import Inverter, String as ProjectString
            db.query(ProjectString).filter(ProjectString.project_id == project_id).delete()
            db.query(Inverter).filter(Inverter.project_id == project_id).delete()
            db.flush()
            inv_map: dict[str, Any] = {}
            for inv in result.get("inverters", []):
                obj = Inverter(
                    project_id=project_id,
                    inverter_no=inv.get("raw_name") or inv.get("normalized_name", ""),
                    metadata_json={"pattern": inv.get("pattern"),
                                   "strings_count": inv.get("strings_count", 0)},
                )
                db.add(obj); db.flush()
                inv_map[obj.inverter_no] = obj
            for row in result.get("string_rows", []):
                if not row.get("is_valid") or not row.get("string_code"):
                    continue
                inv_obj = inv_map.get(row.get("inverter_key") or "")
                db.add(ProjectString(
                    project_id=project_id,
                    inverter_id=inv_obj.id if inv_obj else None,
                    string_no=row["string_code"],
                    status="planned",
                ))
            db.commit()
        except Exception as exc:
            db.rollback()
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            _job_update(job_id, state="error", error=f"Phase 4 (DB sync) failed: {exc}")
            return
        _job_update(job_id, pct=85, label="Saving analytics")

        # ── Phase 5: Analytics save ───────────────────────────────────────────
        try:
            result = _load_phase(job_id, 3)
            string_rows = result.get("string_rows", [])
            invalid_rows = [
                {"string_code": r.get("string_code"), "raw_value": r.get("raw_value"),
                 "inverter_key": r.get("inverter_key"), "invalid_reason": r.get("invalid_reason")}
                for r in string_rows if not r.get("is_valid")
            ]
            # dedup
            seen: set[tuple] = set()
            deduped: list[dict] = []
            for row in invalid_rows:
                k = (row.get("string_code"), row.get("raw_value"),
                     row.get("inverter_key"), row.get("invalid_reason"))
                if k not in seen:
                    seen.add(k); deduped.append(row)
            inverters_list = result.get("inverters", [])
            analytics: dict = {
                "pattern": inverters_list[0].get("pattern") if inverters_list else None,
                "approved_pattern_name": approved_pattern_name,
                "approved_pattern_regex": approved_pattern_regex,
                "valid_count": result.get("valid_count", 0),
                "invalid_count": len(deduped) + len(result.get("invalid_ab_labels", [])),
                "invalid_rows": deduped,
                "missing_strings_by_inverter": result.get("missing_strings_by_inverter", {}),
                "duplicate_string_numbers_by_inverter": result.get("duplicate_string_numbers_by_inverter", {}),
                "outlier_strings_by_inverter": result.get("outlier_strings_by_inverter", {}),
                # Detected BOS / site devices from the design file
                "detected_devices": result.get("devices", []),
                "device_summary": result.get("device_summary", {}),
                "design_metadata": {
                    k: result.get(k) for k in (
                        "project_name", "site_code", "site_name", "source_document",
                        "country", "region", "coordinates", "latitude", "longitude",
                        "plant_capacity_mw", "system_rating_kwp", "module_type",
                        "module_count", "module_power_wp", "modules_per_string",
                        "total_strings_doc", "tracker_enabled", "tracker_rotation_deg",
                        "azimuth_deg", "battery_capacity_mwh", "battery_type",
                        "storage_capacity_mwh", "bess_inv", "building_area_ha",
                        "fenced_area_ha", "fence_length_m", "system_license",
                        "inverter_models", "inverter_count_detected", "page_count",
                        "validation_findings", "output_validation_findings",
                        "invalid_ab_labels", "suffix_string_issues", "mppt_validation_issues",
                    )
                },
            }
            from app.models.project import Project as ProjectModel
            proj = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if proj:
                proj.scan_analytics_json = analytics
                db.commit()
        except Exception as exc:
            db.rollback()
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            _job_update(job_id, state="error", error=f"Phase 5 (analytics) failed: {exc}")
            return

        scan_summary = {
            "valid_count": analytics.get("valid_count", 0),
            "invalid_count": analytics.get("invalid_count", 0),
            "inverter_count_detected": result.get("inverter_count_detected", 0),
        }
        _job_update(job_id, state="done", pct=100, label="Done", scan_summary=scan_summary)

    except Exception as exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        _job_update(job_id, state="error", error=f"Unexpected scan error: {exc}")
    finally:
        db.close()
        _cleanup_phase_dir(job_id)
        # Clean up temp files written for wizard/preview uploads
        if temp_paths:
            for p in temp_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass


class ScanStartBody(BaseModel):
    """JSON body for POST /scan-start (legacy / backwards-compat)."""
    file_ids: str
    approved_pattern_name: str | None = None
    approved_pattern_regex: str | None = None
    detect_token: str | None = None


@router.post("/{project_id}/scan-start")
async def scan_start(
    project_id: int,
    request: Request,
    files: Optional[List[UploadFile]] = File(default=None),
    file_ids: Optional[str] = Form(default=None),
    approved_pattern_name: Optional[str] = Form(default=None),
    approved_pattern_regex: Optional[str] = Form(default=None),
    detect_token: Optional[str] = Form(default=None),
) -> dict:
    """
    Start a background scan job and return a job_id immediately.

    Accepts **multipart/form-data** (preferred): supply either ``files``
    (direct upload, wizard mode) or ``file_ids`` (comma-separated IDs of
    already-uploaded project files).

    Also accepts **application/json** body for backwards-compatibility::

        {"file_ids": "id1,id2", "approved_pattern_name": "...", ...}

    Poll GET /{project_id}/scan-status/{job_id} for progress.
    When project_id==0 (wizard preview), DB sync is skipped and the full
    parsed result is returned as scan_summary so the form can be pre-filled.
    """
    # ── JSON body fallback (backwards-compat with old frontend) ──────────────
    ct = request.headers.get("content-type", "")
    if "application/json" in ct and not file_ids:
        try:
            body = await request.json()
            file_ids = body.get("file_ids") or file_ids
            approved_pattern_name = body.get("approved_pattern_name") or approved_pattern_name
            approved_pattern_regex = body.get("approved_pattern_regex") or approved_pattern_regex
            detect_token = body.get("detect_token") or detect_token
        except Exception:
            pass

    # Save uploaded files to temp paths now (before the background thread starts)
    temp_paths: list[str] = []
    entries_override: list[dict[str, Any]] | None = None

    if files:
        for upload in files:
            ext = os.path.splitext(upload.filename or "")[1].lower() or ".pdf"
            if ext not in (".pdf", ".dxf"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Only PDF/DXF files can be scanned. '{upload.filename}' is {ext.upper()}.",
                )
            content = await upload.read()
            tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tf.write(content)
            tf.close()
            temp_paths.append(tf.name)
        entries_override = [
            {"filename": upload.filename or os.path.basename(p), "path": p,
             "ext": os.path.splitext(p)[1].lower()}
            for upload, p in zip(files, temp_paths)
        ]

    if not entries_override and not file_ids:
        # No files and no file_ids — also check detect_token cache
        if not detect_token:
            raise HTTPException(
                status_code=400,
                detail="Supply 'files' (multipart upload) or 'file_ids' (form field).",
            )

    job_id, _job = _make_job(project_id)
    t = threading.Thread(
        target=_run_scan_job,
        args=(job_id, project_id, file_ids or "", approved_pattern_name,
              approved_pattern_regex, detect_token),
        kwargs={"entries_override": entries_override, "temp_paths": temp_paths or None},
        daemon=True,
    )
    t.start()
    return {"job_id": job_id}


@router.get("/{project_id}/scan-status/{job_id}")
def scan_status(project_id: int, job_id: str) -> dict:
    """
    Poll scan progress.  Returns one of::

        {"state": "running", "pct": 45, "label": "Syncing design strings"}
        {"state": "done",    "pct": 100, "scan_summary": {...}}
        {"state": "error",   "error": "..."}

    Job state is stored in /tmp — visible to all uvicorn worker processes.
    """
    job = _read_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found (may have expired).")
    if job.get("project_id") != project_id:
        raise HTTPException(status_code=403, detail="Job does not belong to this project.")
    return {k: v for k, v in job.items() if k not in ("created_at", "project_id")}


class ScanRunBody(BaseModel):
    """JSON body for POST /scan-run (non-streaming; avoids chunked proxy bugs)."""

    file_ids: str
    approved_pattern_name: str | None = None
    approved_pattern_regex: str | None = None
    detect_token: str | None = None


def _scan_error_detail(ev: dict) -> str:
    err = ev.get("error")
    if err is None:
        return "Scan failed"
    if isinstance(err, list):
        return json.dumps(err, default=str)
    return str(err)


@router.post("/{project_id}/scan-run")
def scan_run(project_id: int, body: ScanRunBody) -> dict:
    """Run the same pipeline as scan-stream; returns one JSON body (no SSE/chunked stream)."""
    db = SessionLocal()
    try:
        last_ev: dict | None = None
        for ev in _scan_pipeline_events(
            db,
            project_id,
            body.file_ids,
            body.approved_pattern_name,
            body.approved_pattern_regex,
            body.detect_token,
        ):
            last_ev = ev
            if ev.get("type") == "error":
                raise HTTPException(status_code=422, detail=_scan_error_detail(ev))
        if last_ev and last_ev.get("type") == "complete":
            return {"ok": True, "scan_summary": last_ev.get("scan_summary") or {}}
        raise HTTPException(status_code=500, detail="Scan finished without a complete result")
    finally:
        db.close()


@router.get("/{project_id}/scan-stream")
def scan_stream(
    project_id: int,
    file_ids: str = Query(..., description="Comma-separated uploaded file IDs"),
    approved_pattern_name: str | None = Query(default=None),
    approved_pattern_regex: str | None = Query(default=None),
    detect_token: str | None = Query(default=None),
):
    """SSE endpoint: runs the full scan pipeline and emits per-step progress."""

    def _sse(payload: dict) -> str:
        try:
            body = json.dumps(payload, default=str, allow_nan=False)
        except (TypeError, ValueError) as exc:
            body = json.dumps(
                {"type": "error", "error": f"sse_encode_failed: {exc}"},
                default=str,
                allow_nan=False,
            )
        # CRLF line endings — some stacks only delimit SSE on \r\n\r\n; LF-only breaks clients.
        return f"data: {body}\r\n\r\n"

    def _sse_comment(comment: str = "keepalive") -> str:
        return f": {comment}\r\n\r\n"

    def generate():
        db = SessionLocal()
        try:
            for ev in _scan_pipeline_events(
                db,
                project_id,
                file_ids,
                approved_pattern_name,
                approved_pattern_regex,
                detect_token,
            ):
                if ev.get("_keepalive"):
                    yield _sse_comment()
                else:
                    yield _sse(ev)
        finally:
            db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
