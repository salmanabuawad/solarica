"""Site details and site strings API endpoints."""

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from database import get_db_connection
from services.site_design_import import (
    build_site_design_preview_multi,
    import_site_design_pdf_multi,
)

router = APIRouter()


class SiteSummaryResponse(BaseModel):
    id: int
    site_code: str
    site_name: str
    layout_name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    module_type: Optional[str] = None
    module_count: Optional[int] = None
    plant_capacity_mw: Optional[float] = None
    string_count: int


class SiteDetailResponse(SiteSummaryResponse):
    source_document: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None


class SiteStringResponse(BaseModel):
    id: int
    string_code: str
    section_no: int
    block_no: int
    string_no: int


class SiteDesignImportResponse(BaseModel):
    success: bool
    site_id: int
    site_code: str
    site_name: str
    source_document: str
    string_count: int
    message: str


class SiteDesignPreviewRow(BaseModel):
    row_id: int
    raw_value: str
    string_code: Optional[str] = None
    section_no: Optional[int] = None
    block_no: Optional[int] = None
    string_no: Optional[int] = None
    is_valid: bool
    invalid_reason: Optional[str] = None


class SiteDesignPreviewMetadata(BaseModel):
    project: str
    location: Optional[str] = None
    total_modules: Optional[int] = None


class SiteDesignPreviewResponse(BaseModel):
    metadata: SiteDesignPreviewMetadata
    site_code: str
    site_name: str
    layout_name: str
    source_document: str
    country: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    plant_capacity_mw: Optional[float] = None
    module_type: Optional[str] = None
    module_count: Optional[int] = None
    notes: str
    strings: dict[str, list[str]]
    anomalies: dict[str, list[str]]
    gaps: dict[str, list[str]]
    duplicates: list[str]
    valid_count: int
    invalid_count: int
    has_errors: bool
    string_rows: list[SiteDesignPreviewRow]


@router.post("/preview-design-pdf", response_model=SiteDesignPreviewResponse)
async def preview_design_pdf(
    files: list[UploadFile] = File(...),
    regions: Optional[str] = Form(None),
):
    """Preview and validate one or more site design PDFs before import."""
    for f in files:
        if Path(f.filename or "").suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF design documents are supported")

    regions_list: list | None = None
    if regions:
        try:
            regions_list = json.loads(regions)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid regions JSON")

    file_data = [(await f.read(), f.filename or "design.pdf") for f in files]
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: build_site_design_preview_multi(file_data, regions=regions_list),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SiteDesignPreviewResponse(**result)


@router.post("/import-design-pdf", response_model=SiteDesignImportResponse)
async def import_design_pdf(
    files: list[UploadFile] = File(...),
    regions: Optional[str] = Form(None),
):
    """Parse one or more site design PDFs and create/update the site + string list."""
    for f in files:
        if Path(f.filename or "").suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF design documents are supported")

    regions_list: list | None = None
    if regions:
        try:
            regions_list = json.loads(regions)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid regions JSON")

    file_data = [(await f.read(), f.filename or "design.pdf") for f in files]
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: import_site_design_pdf_multi(file_data, regions=regions_list),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SiteDesignImportResponse(**result)


@router.get("", response_model=list[SiteSummaryResponse])
async def list_sites(conn=Depends(get_db_connection)):
    """List all sites with basic metadata and string counts."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.site_code, s.site_name, s.layout_name, s.country, s.region,
                   s.module_type, s.module_count, s.plant_capacity_mw,
                   COUNT(ss.id) AS string_count
            FROM site_details s
            LEFT JOIN site_strings ss ON ss.site_id = s.id
            GROUP BY s.id, s.site_code, s.site_name, s.layout_name, s.country, s.region,
                     s.module_type, s.module_count, s.plant_capacity_mw
            ORDER BY s.site_code
            """
        )
        rows = cur.fetchall()

    return [
        SiteSummaryResponse(
            id=row[0],
            site_code=row[1],
            site_name=row[2],
            layout_name=row[3],
            country=row[4],
            region=row[5],
            module_type=row[6],
            module_count=row[7],
            plant_capacity_mw=row[8],
            string_count=row[9] or 0,
        )
        for row in rows
    ]


@router.get("/{site_id}", response_model=SiteDetailResponse)
async def get_site(site_id: int, conn=Depends(get_db_connection)):
    """Get one site's details."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.site_code, s.site_name, s.layout_name, s.country, s.region,
                   s.module_type, s.module_count, s.plant_capacity_mw, s.source_document,
                   s.latitude, s.longitude, s.notes,
                   COUNT(ss.id) AS string_count
            FROM site_details s
            LEFT JOIN site_strings ss ON ss.site_id = s.id
            WHERE s.id = %s
            GROUP BY s.id, s.site_code, s.site_name, s.layout_name, s.country, s.region,
                     s.module_type, s.module_count, s.plant_capacity_mw, s.source_document,
                     s.latitude, s.longitude, s.notes
            """,
            (site_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Site not found")

    return SiteDetailResponse(
        id=row[0],
        site_code=row[1],
        site_name=row[2],
        layout_name=row[3],
        country=row[4],
        region=row[5],
        module_type=row[6],
        module_count=row[7],
        plant_capacity_mw=row[8],
        source_document=row[9],
        latitude=row[10],
        longitude=row[11],
        notes=row[12],
        string_count=row[13] or 0,
    )


@router.get("/{site_id}/strings", response_model=list[SiteStringResponse])
async def list_site_strings(
    site_id: int,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    conn=Depends(get_db_connection),
):
    """List strings for a site with optional search."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM site_details WHERE id = %s", (site_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Site not found")

        if search:
            like_value = f"%{search}%"
            cur.execute(
                """
                SELECT id, string_code, section_no, block_no, string_no
                FROM site_strings
                WHERE site_id = %s AND string_code LIKE %s
                ORDER BY section_no, block_no, string_no
                LIMIT %s OFFSET %s
                """,
                (site_id, like_value, limit, skip),
            )
        else:
            cur.execute(
                """
                SELECT id, string_code, section_no, block_no, string_no
                FROM site_strings
                WHERE site_id = %s
                ORDER BY section_no, block_no, string_no
                LIMIT %s OFFSET %s
                """,
                (site_id, limit, skip),
            )
        rows = cur.fetchall()

    return [
        SiteStringResponse(
            id=row[0],
            string_code=row[1],
            section_no=row[2],
            block_no=row[3],
            string_no=row[4],
        )
        for row in rows
    ]
