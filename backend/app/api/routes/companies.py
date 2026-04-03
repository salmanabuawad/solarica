from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import company_repo

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    code: str | None = None
    country: str | None = None
    contact_email: str | None = None

class CustomerCreate(BaseModel):
    company_id: int
    name: str
    code: str | None = None
    contact_email: str | None = None
    notes: str | None = None

class CustomerUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    contact_email: str | None = None
    notes: str | None = None


# ── Company routes ───────────────────────────────────────────────

@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    return [c.to_dict() for c in company_repo.list_companies(db)]


@router.post("/companies")
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    obj = company_repo.create_company(
        db, name=payload.name, code=payload.code,
        country=payload.country, contact_email=payload.contact_email,
    )
    db.commit()
    db.refresh(obj)
    return obj.to_dict()


@router.get("/companies/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db)):
    obj = company_repo.get_company(db, company_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Company not found")
    return obj.to_dict()


@router.patch("/companies/{company_id}")
def update_company(company_id: int, payload: CompanyCreate, db: Session = Depends(get_db)):
    obj = company_repo.update_company(
        db, company_id,
        name=payload.name, code=payload.code,
        country=payload.country, contact_email=payload.contact_email,
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Company not found")
    db.commit()
    return obj.to_dict()


@router.delete("/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    if not company_repo.delete_company(db, company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    db.commit()
    return {"ok": True}


# ── Customer routes ──────────────────────────────────────────────

@router.get("/customers")
def list_customers(company_id: int | None = None, db: Session = Depends(get_db)):
    return [c.to_dict() for c in company_repo.list_customers(db, company_id)]


@router.post("/customers")
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    obj = company_repo.create_customer(
        db, company_id=payload.company_id, name=payload.name,
        code=payload.code, contact_email=payload.contact_email, notes=payload.notes,
    )
    db.commit()
    db.refresh(obj)
    return obj.to_dict()


@router.get("/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    obj = company_repo.get_customer(db, customer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")
    return obj.to_dict()


@router.patch("/customers/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)):
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    obj = company_repo.update_customer(db, customer_id, **fields)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.commit()
    return obj.to_dict()


@router.delete("/customers/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    if not company_repo.delete_customer(db, customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")
    db.commit()
    return {"ok": True}
