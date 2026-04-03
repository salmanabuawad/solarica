"""
Field testing routes — Megger, Isolation, Continuity, IV Curve, etc.

GET  /api/projects/{id}/tests              — list all test records for a project
POST /api/projects/{id}/tests              — record a new test result
GET  /api/projects/{id}/tests/types        — list all test type definitions
GET  /api/projects/{id}/tests/commissioning-ready — commissioning check
DELETE /api/projects/{id}/tests/{record_id}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.repositories import test_repo

router = APIRouter()


class TestRecordCreate(BaseModel):
    test_code:       str              # "megger" | "isolation" | "continuity" | ...
    entity_type:     str              # "string" | "inverter" | "section" | "array"
    entity_ref:      Optional[str] = None   # e.g. "S.1.2.3"
    result_status:   str              # "pass" | "fail" | "inconclusive"
    measured_values: Optional[dict] = None  # {"resistance_mohm": 450, "test_voltage_v": 1000}
    test_date:       Optional[str] = None   # ISO date "2026-04-02"
    notes:           Optional[str] = None
    recorded_by:     Optional[str] = None


@router.get("/{project_id}/tests/types")
def get_test_types(project_id: int, db: Session = Depends(get_db)):
    return [
        {
            "id":          tt.id,
            "test_code":   tt.test_code,
            "test_name":   tt.test_name,
            "unit":        tt.unit,
            "description": tt.description,
        }
        for tt in test_repo.list_test_types(db)
    ]


@router.get("/{project_id}/tests/commissioning-ready")
def check_commissioning(project_id: int, db: Session = Depends(get_db)):
    return test_repo.commissioning_ready(db, project_id)


@router.get("/{project_id}/tests")
def list_tests(
    project_id: int,
    test_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    records = test_repo.list_records(db, project_id, test_code=test_code)
    return [r.to_dict() for r in records]


@router.post("/{project_id}/tests")
def create_test(
    project_id: int,
    payload: TestRecordCreate,
    db: Session = Depends(get_db),
):
    try:
        rec = test_repo.create_record(
            db,
            project_id=project_id,
            test_code=payload.test_code,
            entity_type=payload.entity_type,
            entity_ref=payload.entity_ref,
            result_status=payload.result_status,
            measured_values=payload.measured_values,
            test_date=payload.test_date,
            notes=payload.notes,
            recorded_by=payload.recorded_by,
        )
        db.commit()
        return rec.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{project_id}/tests/{record_id}")
def delete_test(project_id: int, record_id: int, db: Session = Depends(get_db)):
    ok = test_repo.delete_record(db, record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Test record not found")
    db.commit()
    return {"ok": True}
