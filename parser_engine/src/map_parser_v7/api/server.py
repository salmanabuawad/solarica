from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from map_parser_v7.core.engine import ParserEngine

app = FastAPI(title="map-parser-v7")
engine = ParserEngine()


class RunRequest(BaseModel):
    files: list[str]
    force_ocr: bool = False


class StepRequest(BaseModel):
    step_id: str
    files: list[str]
    resolve_dependencies: bool = True
    force_ocr: bool = False


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/run")
def run(req: RunRequest):
    return engine.run_full(req.files, force_ocr=req.force_ocr)


@app.post("/step")
def step(req: StepRequest):
    return engine.run_step(req.step_id, req.files, resolve_dependencies=req.resolve_dependencies, force_ocr=req.force_ocr)


@app.get("/progress/{job_id}")
def progress(job_id: str):
    return engine.get_progress(job_id)
