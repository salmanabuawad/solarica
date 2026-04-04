"""
Minimal label scan API — ported from repo `parser_engine/backend/app/main.py` (as-is behavior).

POST /scan accepts a file; body is decoded as UTF-8 with errors ignored (same as standalone stub).
For PDF/DXF binary, use the main project string-scan endpoints instead.
"""
from fastapi import APIRouter, UploadFile

from app.parsers.design.final_engine import run

router = APIRouter()


@router.post("/scan")
async def scan(file: UploadFile):
    content = await file.read()
    text = content.decode(errors="ignore")
    return run(text)
