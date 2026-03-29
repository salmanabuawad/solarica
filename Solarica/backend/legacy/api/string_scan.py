"""String scan API endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from auth_deps import get_current_user
from database import get_db_connection
from services.string_scan import (
    get_all_patterns,
    get_active_pattern,
    set_active_pattern,
    fast_detect_pattern,
    classify_all_tokens,
    build_scan_result,
    save_scan_run,
)
from services.site_design_import import _extract_text_from_pdf, _preprocess_text

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────

class PatternResponse(BaseModel):
    id: int
    pattern_code: str
    pattern_name: str
    match_regex: str
    parse_regex: str
    example_value: Optional[str] = None
    level_count: int
    levels: list[str]
    no_leading_zero: bool
    max_digits_per_level: int
    is_active: bool


class ActivePatternResponse(BaseModel):
    site_id: int
    pattern: PatternResponse


class SetPatternRequest(BaseModel):
    pattern_id: int


class ScanRectangle(BaseModel):
    section_code: str = ""
    x_pct: float
    y_pct: float
    w_pct: float
    h_pct: float


# ── Pattern routes ─────────────────────────────────────────────────────────

@router.get("/string-patterns", response_model=list[PatternResponse])
async def list_patterns(conn=Depends(get_db_connection)):
    try:
        return get_all_patterns(conn)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sites/{site_id}/string-pattern", response_model=ActivePatternResponse)
async def get_site_pattern(site_id: int, conn=Depends(get_db_connection)):
    pattern = get_active_pattern(site_id, conn)
    if not pattern:
        # Fall back to S4_LEVEL pattern rather than 404
        patterns = get_all_patterns(conn)
        pattern = next((p for p in patterns if p["pattern_code"] == "S4_LEVEL"), None) or (patterns[0] if patterns else None)
    if not pattern:
        raise HTTPException(status_code=404, detail="No string patterns configured in database")
    return ActivePatternResponse(site_id=site_id, pattern=PatternResponse(**pattern))


@router.put("/sites/{site_id}/string-pattern", response_model=ActivePatternResponse)
async def set_site_pattern(
    site_id: int,
    body: SetPatternRequest,
    conn=Depends(get_db_connection),
    _user=Depends(get_current_user),
):
    try:
        pattern = set_active_pattern(site_id, body.pattern_id, conn)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return ActivePatternResponse(site_id=site_id, pattern=PatternResponse(**pattern))


# ── Scan routes ────────────────────────────────────────────────────────────

def _parse_regions(regions_json: Optional[str]) -> list[dict]:
    """Parse regions JSON string. Accepts normalized (0-1) or percentage (0-100) coords."""
    if not regions_json:
        return []
    try:
        rects = json.loads(regions_json)
    except Exception:
        return []
    result = []
    for r in rects:
        # Support both normalized (0-1) and percentage (0-100) formats
        x = float(r.get("x_pct", r.get("x", 0)))
        y = float(r.get("y_pct", r.get("y", 0)))
        w = float(r.get("w_pct", r.get("w", 1)))
        h = float(r.get("h_pct", r.get("h", 1)))
        # Normalise to 0-1 if values look like percentages
        if x > 1 or y > 1 or w > 1 or h > 1:
            x, y, w, h = x / 100, y / 100, w / 100, h / 100
        result.append({"x": x, "y": y, "w": w, "h": h})
    return result


@router.post("/sites/{site_id}/scan-strings/prepare")
async def prepare_scan(
    site_id: int,
    files: list[UploadFile] = File(...),
    regions: Optional[str] = Form(None),
    conn=Depends(get_db_connection),
    _user=Depends(get_current_user),
):
    """Fast-detect the string pattern from the uploaded PDF(s)."""
    regions_list = _parse_regions(regions)

    pattern = get_active_pattern(site_id, conn)
    configured_code = pattern["pattern_code"] if pattern else "S_DOT_3"
    all_patterns = get_all_patterns(conn)

    loop = asyncio.get_event_loop()
    try:
        parts = []
        for f in files:
            content = await f.read()
            part = await loop.run_in_executor(
                None, lambda c=content: _extract_text_from_pdf(c, regions_list or None)
            )
            parts.append(part)
        text = "\n".join(parts)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    fd = fast_detect_pattern(text, all_patterns, configured_code)
    return {"site_id": site_id, "fast_detect": fd}


@router.post("/sites/{site_id}/scan-strings")
async def scan_strings(
    site_id: int,
    files: list[UploadFile] = File(...),
    regions: Optional[str] = Form(None),
    save_run: bool = Form(True),
    compare_to_design: bool = Form(True),
    conn=Depends(get_db_connection),
    _user=Depends(get_current_user),
):
    """Full string scan: classify tokens, compare to design, generate issues."""
    regions_list = _parse_regions(regions)

    pattern = get_active_pattern(site_id, conn)
    all_patterns = get_all_patterns(conn)

    # Fall back to auto-detected pattern if none configured
    loop = asyncio.get_event_loop()
    try:
        parts = []
        for f in files:
            content = await f.read()
            part = await loop.run_in_executor(
                None, lambda c=content: _extract_text_from_pdf(c, regions_list or None)
            )
            parts.append(part)
        text = "\n".join(parts)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    configured_code = pattern["pattern_code"] if pattern else "S_DOT_3"
    fd = fast_detect_pattern(text, all_patterns, configured_code)

    # Use detected pattern if confidence is high and no manual pattern set
    if not pattern or fd["confidence"] > 0.8:
        active_code = fd["detected_pattern_code"]
    else:
        active_code = configured_code

    active_pattern = next((p for p in all_patterns if p["pattern_code"] == active_code), None)
    if not active_pattern:
        active_pattern = all_patterns[0] if all_patterns else None
    if not active_pattern:
        raise HTTPException(status_code=500, detail="No string patterns configured in DB")

    classified = classify_all_tokens(text, active_pattern)
    result = build_scan_result(classified, active_pattern, site_id, fd, conn, compare_to_design=compare_to_design)

    if save_run:
        try:
            run_id = save_scan_run(site_id, active_pattern, fd, result, conn)
            result["run_id"] = run_id
        except Exception:
            result["run_id"] = 0

    return result
