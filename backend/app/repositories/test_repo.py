"""Repository for TestType and TestRecord."""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.testing import TestType, TestRecord

# ── Default test types ───────────────────────────────────────────────────────

DEFAULT_TEST_TYPES = [
    {"test_code": "continuity",  "test_name": "Continuity Test",         "unit": "Ω",   "description": "Verifies electrical continuity of string cables"},
    {"test_code": "polarity",    "test_name": "Polarity Check",           "unit": None,  "description": "Confirms correct DC polarity before connection"},
    {"test_code": "megger",      "test_name": "Megger (Insulation)",      "unit": "MΩ",  "description": "Insulation resistance test — DC 1000V applied between live and earth"},
    {"test_code": "isolation",   "test_name": "DC Isolation Test",        "unit": "MΩ",  "description": "DC isolation resistance between array and earth per IEC 62446"},
    {"test_code": "iv_curve",    "test_name": "IV Curve (PVPM)",          "unit": "W",   "description": "Current-voltage characteristic sweep from PVPM 1540X"},
    {"test_code": "earth_fault", "test_name": "Earth Fault / Leakage",    "unit": "mA",  "description": "Leakage current to earth under operating conditions"},
    {"test_code": "voc_check",   "test_name": "Open-Circuit Voltage",     "unit": "V",   "description": "String Voc verification against STC design value"},
    {"test_code": "isc_check",   "test_name": "Short-Circuit Current",    "unit": "A",   "description": "String Isc verification against STC design value"},
]


def seed_test_types(db: Session) -> None:
    if db.query(TestType).count() > 0:
        return
    for tt in DEFAULT_TEST_TYPES:
        db.add(TestType(**tt))
    db.flush()


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_records(db: Session, project_id: int, test_code: str | None = None) -> list[TestRecord]:
    q = db.query(TestRecord).filter(TestRecord.project_id == project_id)
    if test_code:
        tt = db.query(TestType).filter(TestType.test_code == test_code).first()
        if tt:
            q = q.filter(TestRecord.test_type_id == tt.id)
    return q.order_by(TestRecord.created_at.desc()).all()


def create_record(
    db: Session,
    project_id: int,
    test_code: str,
    entity_type: str,
    entity_ref: str | None,
    result_status: str,
    measured_values: dict | None,
    test_date: str | None,
    notes: str | None,
    recorded_by: str | None,
) -> TestRecord:
    tt = db.query(TestType).filter(TestType.test_code == test_code).first()
    if not tt:
        raise ValueError(f"Unknown test_code: {test_code!r}")
    rec = TestRecord(
        project_id=project_id,
        test_type_id=tt.id,
        entity_type=entity_type,
        entity_ref=entity_ref,
        result_status=result_status,
        measured_values=measured_values,
        test_date=test_date,
        notes=notes,
        recorded_by=recorded_by,
    )
    db.add(rec)
    db.flush()
    db.refresh(rec)
    return rec


def get_record(db: Session, record_id: int) -> TestRecord | None:
    return db.query(TestRecord).filter(TestRecord.id == record_id).first()


def delete_record(db: Session, record_id: int) -> bool:
    rec = db.query(TestRecord).filter(TestRecord.id == record_id).first()
    if not rec:
        return False
    db.delete(rec)
    db.flush()
    return True


def list_test_types(db: Session) -> list[TestType]:
    return db.query(TestType).order_by(TestType.id).all()


def commissioning_ready(db: Session, project_id: int) -> dict:
    """Check whether all required pre-energization tests have at least one 'pass' record."""
    required = ["continuity", "polarity", "megger", "iv_curve"]
    passed = set()
    records = db.query(TestRecord).filter(
        TestRecord.project_id == project_id,
        TestRecord.result_status == "pass",
    ).all()
    for r in records:
        if r.test_type and r.test_type.test_code in required:
            passed.add(r.test_type.test_code)
    missing = [c for c in required if c not in passed]
    return {
        "ready": len(missing) == 0,
        "passed": sorted(passed),
        "missing": missing,
        "required": required,
    }
