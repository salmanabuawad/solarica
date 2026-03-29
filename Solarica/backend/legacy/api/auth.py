"""Auth endpoints: login, me, register (bootstrap), and manager-controlled user creation."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth_deps import RequireGlobalRole, get_current_user
from auth_utils import create_access_token, hash_password, verify_password
from config import settings
from database import get_connection, get_db_connection

router = APIRouter()

_use_sqlite = settings.database_url.strip().lower().startswith("sqlite")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str


class CreateUserRequest(BaseModel):
    full_name: str
    email: str
    password: str
    global_role: Optional[str] = None  # e.g. "manager"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_user(cur, full_name: str, email: str, password_hash: str) -> int:
    """Insert a user row and return the new user id (works for PG and SQLite)."""
    if _use_sqlite:
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)",
            (full_name, email, password_hash),
        )
        return cur.lastrowid
    else:
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (full_name, email, password_hash),
        )
        return cur.fetchone()[0]


def _assign_global_role(cur, user_id: int, role_code: str) -> None:
    cur.execute("SELECT id FROM roles WHERE role_code = %s", (role_code,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "INSERT INTO user_global_roles (user_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING"
            if not _use_sqlite
            else "INSERT OR IGNORE INTO user_global_roles (user_id, role_id) VALUES (%s, %s)",
            (user_id, row[0]),
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login")
def login(body: LoginRequest, conn=Depends(get_db_connection)):
    """Return a JWT access token for valid credentials."""
    username = body.username.lower().strip()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, password_hash, is_active FROM users WHERE email = %s",
            (username,),
        )
        row = cur.fetchone()

    if not row or not bool(row[2]) or not verify_password(body.password, row[1]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid username or password")

    return {"access_token": create_access_token(row[0]), "token_type": "bearer"}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user with their roles."""
    return user


@router.post("/register", status_code=201)
def register(body: RegisterRequest, conn=Depends(get_db_connection)):
    """
    Bootstrap endpoint — creates the first user (manager) if no users exist.
    Returns 403 once the platform has at least one user; use POST /auth/users instead.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]

    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform already has users. Ask a manager to create your account.",
        )

    email = body.email.lower().strip()
    with conn.cursor() as cur:
        user_id = _insert_user(cur, body.full_name.strip(), email, hash_password(body.password))
        # First user always gets the manager role
        _assign_global_role(cur, user_id, "manager")
    conn.commit()

    return {"id": user_id, "email": email, "message": "Admin account created. Please log in."}


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    manager: dict = Depends(RequireGlobalRole("manager")),
    conn=Depends(get_db_connection),
):
    """Manager-only: create a new user and optionally assign a global role."""
    email = body.email.lower().strip()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")

        user_id = _insert_user(cur, body.full_name.strip(), email, hash_password(body.password))
        if body.global_role:
            _assign_global_role(cur, user_id, body.global_role)
    conn.commit()

    return {"id": user_id, "email": email}


@router.get("/users")
def list_users(
    _manager: dict = Depends(RequireGlobalRole("manager")),
    conn=Depends(get_db_connection),
):
    """Manager-only: list all users with their global roles."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.full_name, u.email, u.is_active, r.role_code
            FROM users u
            LEFT JOIN user_global_roles ugr ON ugr.user_id = u.id
            LEFT JOIN roles r ON r.id = ugr.role_id
            ORDER BY u.id
            """
        )
        rows = cur.fetchall()

    # Aggregate roles per user
    users: dict[int, dict] = {}
    for row in rows:
        uid = row[0]
        if uid not in users:
            users[uid] = {
                "id": uid,
                "full_name": row[1],
                "email": row[2],
                "is_active": bool(row[3]),
                "global_roles": [],
            }
        if row[4]:
            users[uid]["global_roles"].append(row[4])

    return {"items": list(users.values())}
