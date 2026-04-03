from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_password, verify_password


def get_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id).all()


def create_user(db: Session, *, username: str, password: str, display_name: str, role: str) -> User:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        display_name=display_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_by_username(db, username)
    if user and verify_password(password, user.hashed_password):
        return user
    return None


def seed_default_users(db: Session) -> None:
    defaults = [
        ("admin",     "admin123",     "System Admin",      "admin"),
        ("manager",   "manager123",   "Site Manager",      "manager"),
        ("tech",      "tech123",      "Field Technician",  "technician"),
        ("warehouse", "warehouse123", "Warehouse Staff",   "warehouse"),
        ("owner",     "owner123",     "Project Owner",     "owner"),
    ]
    for username, password, display_name, role in defaults:
        if not get_by_username(db, username):
            create_user(db, username=username, password=password, display_name=display_name, role=role)
