"""
Minimal label scan API — text-only stub (same response shape as the old final_engine).

POST /scan decodes the body as UTF-8 with errors ignored. For PDF/DXF use string-scan.
"""
from fastapi import APIRouter, UploadFile

from app.parsers.design.unified_scan_adapter import plain_text_stub_scan

router = APIRouter()


@router.post("/scan")
async def scan(file: UploadFile):
    content = await file.read()
    text = content.decode(errors="ignore")
    return plain_text_stub_scan(text)
