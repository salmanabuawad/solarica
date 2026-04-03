from sqlalchemy.orm import Session
from app.models.company import Company, Customer


# ── Companies ────────────────────────────────────────────────────

def list_companies(db: Session) -> list[Company]:
    return db.query(Company).order_by(Company.name).all()


def get_company(db: Session, company_id: int) -> Company | None:
    return db.query(Company).filter(Company.id == company_id).first()


def create_company(db: Session, *, name: str, code: str | None = None,
                   country: str | None = None, contact_email: str | None = None) -> Company:
    obj = Company(name=name, code=code, country=country, contact_email=contact_email)
    db.add(obj)
    db.flush()
    return obj


def update_company(db: Session, company_id: int, **fields) -> Company | None:
    obj = get_company(db, company_id)
    if not obj:
        return None
    for k, v in fields.items():
        setattr(obj, k, v)
    db.flush()
    return obj


def delete_company(db: Session, company_id: int) -> bool:
    obj = get_company(db, company_id)
    if not obj:
        return False
    db.delete(obj)
    db.flush()
    return True


# ── Customers ────────────────────────────────────────────────────

def list_customers(db: Session, company_id: int | None = None) -> list[Customer]:
    q = db.query(Customer)
    if company_id is not None:
        q = q.filter(Customer.company_id == company_id)
    return q.order_by(Customer.name).all()


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.query(Customer).filter(Customer.id == customer_id).first()


def create_customer(db: Session, *, company_id: int, name: str, code: str | None = None,
                    contact_email: str | None = None, notes: str | None = None) -> Customer:
    obj = Customer(company_id=company_id, name=name, code=code,
                   contact_email=contact_email, notes=notes)
    db.add(obj)
    db.flush()
    return obj


def update_customer(db: Session, customer_id: int, **fields) -> Customer | None:
    obj = get_customer(db, customer_id)
    if not obj:
        return None
    for k, v in fields.items():
        setattr(obj, k, v)
    db.flush()
    return obj


def delete_customer(db: Session, customer_id: int) -> bool:
    obj = get_customer(db, customer_id)
    if not obj:
        return False
    db.delete(obj)
    db.flush()
    return True
