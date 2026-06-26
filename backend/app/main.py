"""
Solarica Parsing Engine API.

All project data (blocks, trackers, piers, pier statuses, metadata, uploaded files)
is stored in Postgres. The parser still writes JSON artifacts to disk for debug,
but all API reads/writes go through the DB.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import PROJECTS_ROOT
from app.image_utils import shrink_image_to_max
from app.services import db_store

app = FastAPI(title="Solarica Parsing Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth -----------------------------------------------------------------
#
# Minimal admin-only auth: a single seeded user (username/password from env,
# defaults admin/admin123) signed with HMAC-SHA256. Tokens are valid for 7
# days, no refresh flow. Everything under /api/* except /api/auth/login
# requires a Bearer token. Static /projects/* and /health stay public.

AUTH_SECRET = os.environ.get("AUTH_SECRET") or secrets.token_hex(32)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")
TOKEN_TTL_SECONDS = 7 * 24 * 3600


# --- Password hashing (salted SHA-256) --------------------------------

def _hash_pw(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${h}"


def _verify_pw(plain: str, stored: str) -> bool:
    if not stored:
        return False
    if "$" not in stored:
        return hmac.compare_digest(plain, stored)
    salt, h = stored.split("$", 1)
    expected = hashlib.sha256(f"{salt}{plain}".encode()).hexdigest()
    return hmac.compare_digest(expected, h)


# --- Users table ------------------------------------------------------

ACTIVE_USER_ROLES = {"admin", "editor", "viewer", "electric"}

USERS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT,
  role          TEXT NOT NULL DEFAULT 'viewer',
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

USER_PROJECT_ACCESS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_project_access (
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, project_id)
);
"""

# Audit log of successful logins — who signed in, from which IP, and when. Used
# to gauge how many distinct users/IPs are actually using the system over time.
LOGIN_EVENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS login_events (
  id         SERIAL PRIMARY KEY,
  username   TEXT NOT NULL,
  role       TEXT,
  ip         TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_login_events_created_at ON login_events (created_at DESC);
"""


def _ensure_users_schema() -> None:
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(USERS_SCHEMA_SQL)
        cur.execute(USER_PROJECT_ACCESS_SCHEMA_SQL)
        cur.execute(LOGIN_EVENTS_SCHEMA_SQL)
        # Seed the configured admin if no user exists (first-boot bootstrap).
        cur.execute("SELECT COUNT(*) AS n FROM users")
        row = cur.fetchone()
        n = (row["n"] if isinstance(row, dict) else row[0]) if row else 0
        if n == 0:
            cur.execute(
                "INSERT INTO users (username, password_hash, display_name, role) VALUES (%s, %s, %s, %s)",
                (ADMIN_USER, _hash_pw(ADMIN_PASS), "Administrator", "admin"),
            )
        conn.commit()


@app.on_event("startup")
def _startup_users() -> None:
    try:
        _ensure_users_schema()
    except Exception as exc:  # noqa: BLE001
        print(f"[users] schema ensure failed: {exc}")


def _db_user_row(username: str) -> Optional[dict]:
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, display_name, role, is_active FROM users WHERE username = %s",
            (username,),
        )
        return cur.fetchone()


def _project_access_ids(username: str) -> set[str]:
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.project_id
            FROM user_project_access upa
            JOIN users u ON u.id = upa.user_id
            JOIN projects p ON p.id = upa.project_id
            WHERE u.username = %s
            """,
            (username,),
        )
        return {str(r["project_id"]) for r in cur.fetchall()}


def _can_access_project(auth_data: dict, project_id: str) -> bool:
    role = auth_data.get("role")
    if role == "admin":
        return True
    ids = _project_access_ids(str(auth_data.get("username") or ""))
    if ids:
        # Explicit per-project grants → scoped to exactly those projects
        # (e.g. a viewer assigned only to BHK sees only BHK).
        return project_id in ids
    # No grants: a viewer is global read-only (writes are blocked in the auth
    # middleware); editor/electric require an explicit project grant.
    return role == "viewer"


def _sign_token(user: str, role: str = "viewer") -> str:
    ts = int(time.time())
    payload = f"{user}|{role}|{ts}"
    sig = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def _verify_token(token: str) -> Optional[dict]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.rsplit("|", 3)
        if len(parts) == 4:
            user, role, ts_str, sig = parts
        else:
            # Legacy 2-field token: user|ts|sig, role defaulted to admin.
            user, ts_str, sig = decoded.rsplit("|", 2)
            role = "admin"
        payload = f"{user}|{role}|{ts_str}" if len(parts) == 4 else f"{user}|{ts_str}"
        expected = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        ts = int(ts_str)
        if time.time() - ts > TOKEN_TTL_SECONDS:
            return None
        return {"username": user, "role": role, "issued_at": ts}
    except Exception:
        return None


_PUBLIC_API_PATHS = {"/api/auth/login"}
# Write methods are blocked for read-only ("viewer") users at the middleware
# layer, so the whole API is read-only for them regardless of which endpoint.
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if path.startswith("/api/") and path not in _PUBLIC_API_PATHS:
        auth = request.headers.get("authorization", "")
        data = _verify_token(auth[7:]) if auth.startswith("Bearer ") else None
        if not data:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        if request.method in _WRITE_METHODS and data.get("role") == "viewer":
            return JSONResponse({"detail": "Read-only user — changes are not allowed."}, status_code=403)
        project_match = re.match(r"^/api/(?:epl/|security/)?projects/([^/]+)", path)
        if project_match:
            project_id = unquote(project_match.group(1))
            if not _can_access_project(data, project_id):
                return JSONResponse({"detail": "Project access denied"}, status_code=403)
    return await call_next(request)


def _require_admin(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    data = _verify_token(auth[7:]) if auth.startswith("Bearer ") else None
    if not data:
        raise HTTPException(401, "Not authenticated")
    if data.get("role") != "admin":
        raise HTTPException(403, "Admin role required")
    return data


# --- Login audit log --------------------------------------------------

def _client_ip(request: Request) -> str:
    # Behind nginx the socket peer is 127.0.0.1, so prefer the proxy headers
    # (X-Forwarded-For lists "client, proxy1, ..." — the first hop is the user).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return request.client.host if request.client else ""


def _record_login(username: str, role: str, request: Request) -> None:
    try:
        ua = (request.headers.get("user-agent") or "")[:500]
        with db_store.get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO login_events (username, role, ip, user_agent) VALUES (%s, %s, %s, %s)",
                (username, role, _client_ip(request), ua),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — logging must never break login
        print(f"[login_log] record failed: {exc}")


@app.post("/api/auth/login")
async def api_login(request: Request, creds: dict = Body(...)):
    username = str(creds.get("username") or "")
    password = str(creds.get("password") or "")
    # Try DB first
    row = _db_user_row(username)
    if row and row.get("is_active") and _verify_pw(password, row.get("password_hash") or ""):
        role = row.get("role") or "viewer"
        _record_login(username, role, request)
        return {
            "access_token": _sign_token(username, role),
            "token_type": "bearer",
            "user": {"username": username, "role": role, "display_name": row.get("display_name")},
        }
    # Env-var fallback (only if no such user in DB)
    if not row and username == ADMIN_USER and password == ADMIN_PASS:
        _record_login(username, "admin", request)
        return {
            "access_token": _sign_token(username, "admin"),
            "token_type": "bearer",
            "user": {"username": username, "role": "admin"},
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/auth/me")
async def api_me(request: Request):
    auth = request.headers.get("authorization", "")
    data = _verify_token(auth[7:]) if auth.startswith("Bearer ") else None
    if not data:
        raise HTTPException(401, "Not authenticated")
    return data


@app.get("/api/login-log")
def api_login_log(request: Request, limit: int = 200):
    """Admin-only: recent successful logins + an interest summary (distinct
    users / IPs, both overall and in the last 7 days)."""
    _require_admin(request)
    limit = max(1, min(int(limit or 200), 2000))

    def _n(d: dict, k: str) -> int:
        try:
            return int(d.get(k) or 0)
        except Exception:
            return 0

    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT username) AS users, "
            "COUNT(DISTINCT ip) AS ips FROM login_events"
        )
        summ = cur.fetchone() or {}
        cur.execute(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT username) AS users, "
            "COUNT(DISTINCT ip) AS ips FROM login_events "
            "WHERE created_at >= NOW() - INTERVAL '7 days'"
        )
        last7 = cur.fetchone() or {}
        cur.execute(
            "SELECT username, role, ip, user_agent, created_at FROM login_events "
            "ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        events = []
        for r in cur.fetchall():
            d = dict(r)
            if d.get("created_at") is not None:
                d["created_at"] = d["created_at"].isoformat()
            events.append(d)

    return {
        "summary": {
            "total_logins": _n(summ, "total"),
            "distinct_users": _n(summ, "users"),
            "distinct_ips": _n(summ, "ips"),
            "last7_logins": _n(last7, "total"),
            "last7_users": _n(last7, "users"),
            "last7_ips": _n(last7, "ips"),
        },
        "events": events,
    }


# --- Users CRUD (admin only) -----------------------------------------

@app.get("/api/users")
def api_list_users(request: Request):
    _require_admin(request)
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, display_name, role, is_active, created_at FROM users ORDER BY id"
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("created_at") is not None:
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


@app.post("/api/users")
def api_create_user(request: Request, body: dict = Body(...)):
    _require_admin(request)
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    display_name = body.get("display_name") or None
    role = str(body.get("role") or "viewer")
    if not username or not password:
        raise HTTPException(400, "username and password are required")
    if role not in ACTIVE_USER_ROLES:
        raise HTTPException(400, "role must be admin, editor, viewer, or electric")
    with db_store.get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash, display_name, role) VALUES (%s, %s, %s, %s) RETURNING id",
                (username, _hash_pw(password), display_name, role),
            )
        except Exception as exc:
            if "duplicate key" in str(exc).lower():
                raise HTTPException(409, f"User '{username}' already exists")
            raise
        new_id = cur.fetchone()["id"]
        conn.commit()
        return {"id": new_id, "username": username, "display_name": display_name, "role": role, "is_active": True}


@app.put("/api/users/{user_id}")
def api_update_user(user_id: int, request: Request, body: dict = Body(...)):
    _require_admin(request)
    fields = []
    params: list = []
    if "display_name" in body:
        fields.append("display_name = %s"); params.append(body.get("display_name"))
    if "role" in body:
        role = str(body.get("role") or "")
        if role not in ACTIVE_USER_ROLES:
            raise HTTPException(400, "role must be admin, editor, viewer, or electric")
        fields.append("role = %s"); params.append(role)
    if "is_active" in body:
        fields.append("is_active = %s"); params.append(bool(body.get("is_active")))
    if "password" in body and body.get("password"):
        fields.append("password_hash = %s"); params.append(_hash_pw(str(body["password"])))
    if not fields:
        raise HTTPException(400, "Nothing to update")
    fields.append("updated_at = NOW()")
    params.append(user_id)
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", params)
        conn.commit()
        return {"updated": cur.rowcount}


@app.delete("/api/users/{user_id}")
def api_delete_user(user_id: int, request: Request):
    me = _require_admin(request)
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row and row["username"] == me["username"]:
            raise HTTPException(400, "You cannot delete your own account")
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return {"deleted": cur.rowcount}


# --- Field configurations -------------------------------------------------
#
# Reusable per-grid column preferences (visibility, pinning, order, custom
# label, width). Mirrors the buildingsmanager `field_configurations` table
# pattern but scoped down to what we need for the parser app's grids.

FIELD_CONFIG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS field_configurations (
  grid_name     text NOT NULL,
  field_name    text NOT NULL,
  display_name  text,
  visible       boolean NOT NULL DEFAULT true,
  pin_side      text,
  column_order  integer,
  width         integer,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (grid_name, field_name)
);
CREATE INDEX IF NOT EXISTS idx_field_configurations_grid_name
  ON field_configurations(grid_name);
"""


# Seed default configuration for each named grid the admin might want to
# tune. Safe to re-run — inserts only when a (grid_name, field_name) row
# is missing.
FIELD_CONFIG_SEEDS: dict[str, list[dict]] = {
    "piers-list": [
        # Widths derived from a one-time scan of actual pier data
        # (max(LENGTH) per field) using width = chars*7 + 30 px (left
        # padding 12 + right padding 12 + sort-icon room 6).  Pier
        # checkbox column lives outside this config (it's the special
        # __select column locked-pinned to the absolute left).
        {"field_name": "pier_code",          "display_name": "Pier",          "column_order": 1,  "visible": True,                       "width": 84},
        {"field_name": "tracker_code",       "display_name": "Tracker",       "column_order": 2,  "visible": True,                       "width": 72},
        {"field_name": "row_num",            "display_name": "Row",           "column_order": 3,  "visible": True,                       "width": 52},
        {"field_name": "pier_type",          "display_name": "Type",          "column_order": 4,  "visible": True,                       "width": 64},
        {"field_name": "structure_code",     "display_name": "Struct.",       "column_order": 5,  "visible": True,                       "width": 72},
        {"field_name": "slope_band",         "display_name": "Slope",         "column_order": 6,  "visible": True,                       "width": 64},
        {"field_name": "tracker_type_code",  "display_name": "Tracker Type",  "column_order": 7,  "visible": True,                       "width": 130},
        {"field_name": "status",             "display_name": "Status",        "column_order": 8,  "visible": True,  "pin_side": "right", "width": 92},
        {"field_name": "block_code",         "display_name": "Block",         "column_order": 9,  "visible": False,                      "width": 58},
        {"field_name": "row_type",           "display_name": "Row Type",      "column_order": 10, "visible": False,                      "width": 76},
    ],
    "strings-list": [
        {"field_name": "string",      "display_name": "String",  "column_order": 1, "visible": True, "pin_side": "left"},
        {"field_name": "status",      "display_name": "Status",  "column_order": 2, "visible": True},
        {"field_name": "comment",     "display_name": "Comment", "column_order": 3, "visible": True},
        {"field_name": "images",      "display_name": "Images",  "column_order": 4, "visible": True},
        {"field_name": "row",         "display_name": "Row",     "column_order": 5, "visible": True},
        {"field_name": "voltage",     "display_name": "Voltage", "column_order": 6, "visible": True},
        {"field_name": "string_type", "display_name": "Type",    "column_order": 7, "visible": True},
    ],
    "devices-bom": [
        {"field_name": "part_no",      "display_name": "Part No",    "column_order": 1, "visible": True},
        {"field_name": "device_type",  "display_name": "Device Type","column_order": 2, "visible": True},
        {"field_name": "name",         "display_name": "Name",       "column_order": 3, "visible": True},
        {"field_name": "qty",          "display_name": "Qty",        "column_order": 4, "visible": True},
        {"field_name": "module_count", "display_name": "Modules",    "column_order": 5, "visible": True},
        {"field_name": "pier_count",   "display_name": "Piers",      "column_order": 6, "visible": True},
    ],
    "devices-pier-specs": [
        {"field_name": "pier_type",      "display_name": "Type",      "column_order": 1, "visible": True},
        {"field_name": "pier_type_full", "display_name": "Full Name", "column_order": 2, "visible": True},
        {"field_name": "zone",           "display_name": "Zone",      "column_order": 3, "visible": True},
        {"field_name": "size",           "display_name": "Size",      "column_order": 4, "visible": True},
        {"field_name": "part_no",        "display_name": "Part No",   "column_order": 5, "visible": True},
    ],
}


def _ensure_field_config_schema() -> None:
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(FIELD_CONFIG_SCHEMA_SQL)
        # Seed defaults that aren't yet in the table.
        for grid_name, rows in FIELD_CONFIG_SEEDS.items():
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO field_configurations
                        (grid_name, field_name, display_name, visible, pin_side, column_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (grid_name, field_name) DO NOTHING
                    """,
                    (
                        grid_name,
                        row["field_name"],
                        row.get("display_name"),
                        row.get("visible", True),
                        row.get("pin_side"),
                        row.get("column_order"),
                    ),
                )
        conn.commit()


@app.on_event("startup")
def _startup_field_configs() -> None:
    try:
        _ensure_field_config_schema()
    except Exception as exc:  # noqa: BLE001
        # Startup must not crash if the DB isn't reachable; log and carry on.
        print(f"[field_configurations] schema ensure failed: {exc}")


@app.get("/api/field-configs")
def api_list_field_configs(grid_name: Optional[str] = None):
    with db_store.get_conn() as conn, conn.cursor() as cur:
        if grid_name:
            cur.execute(
                """
                SELECT grid_name, field_name, display_name, visible, pin_side, column_order, width
                FROM field_configurations
                WHERE grid_name = %s
                ORDER BY COALESCE(column_order, 999), field_name
                """,
                (grid_name,),
            )
        else:
            cur.execute(
                """
                SELECT grid_name, field_name, display_name, visible, pin_side, column_order, width
                FROM field_configurations
                ORDER BY grid_name, COALESCE(column_order, 999), field_name
                """
            )
        return [dict(r) for r in cur.fetchall()]


@app.put("/api/field-configs")
def api_upsert_field_configs(rows: list[dict] = Body(...)):
    """Bulk upsert. Each row: {grid_name, field_name, display_name?, visible?,
    pin_side?, column_order?, width?}."""
    if not isinstance(rows, list):
        raise HTTPException(400, "Body must be an array of field config rows")
    updated = 0
    with db_store.get_conn() as conn, conn.cursor() as cur:
        for r in rows:
            grid = r.get("grid_name")
            field = r.get("field_name")
            if not grid or not field:
                continue
            cur.execute(
                """
                INSERT INTO field_configurations
                    (grid_name, field_name, display_name, visible, pin_side, column_order, width)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (grid_name, field_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    visible      = EXCLUDED.visible,
                    pin_side     = EXCLUDED.pin_side,
                    column_order = EXCLUDED.column_order,
                    width        = EXCLUDED.width,
                    updated_at   = now()
                """,
                (
                    grid, field,
                    r.get("display_name"),
                    bool(r.get("visible", True)),
                    r.get("pin_side") or None,
                    r.get("column_order"),
                    r.get("width"),
                ),
            )
            updated += 1
        conn.commit()
    return {"updated": updated}


@app.delete("/api/field-configs/{grid_name}/{field_name}")
def api_delete_field_config(grid_name: str, field_name: str):
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM field_configurations WHERE grid_name = %s AND field_name = %s",
            (grid_name, field_name),
        )
        conn.commit()
        return {"deleted": cur.rowcount}

PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/projects", StaticFiles(directory=str(PROJECTS_ROOT)), name="projects")


# --- Lifecycle phase modules -----------------------------------------
# Each module owns its slice of the product lifecycle and exposes its
# own REST surface under /api/<module>. Today only `security` carries
# real logic (DCCB + inverter extraction); the others are scaffolded
# and return a `/status` stub until their phase lands.
from app.modules.security.routes  import router as security_router   # noqa: E402
from app.modules.epl.routes       import router as epl_router, project_router as epl_project_router  # noqa: E402

app.include_router(security_router,  prefix="/api/security",  tags=["security"])
app.include_router(epl_router,       prefix="/api/epl",       tags=["epl"])
app.include_router(epl_project_router, prefix="/api",          tags=["epl"])


# --- Constants ------------------------------------------------------------

VALID_STATUSES = {"New", "In Progress", "Implemented", "Approved", "Rejected", "Fixed"}

PLANT_INFO_DEFAULTS = {
    "total_output_mw": None,
    "total_strings": None,
    "total_modules": None,
    "modules_per_string": None,
    "module_capacity_w": None,
    "module_length_m": None,
    "module_width_m": None,
    "pitch_m": None,
    "inverters": None,
    "dccb": None,
    "string_groups": None,
    "devices": None,
    "dc_zones": None,
    "ac_zones": None,
    "transformers": None,
    "storage_zones": None,
    "batteries": None,
    "pcs": None,
    "storage_capacity_mwh": None,
    "camera_zones": None,
    "cameras": None,
    "network_devices": None,
    "site_id": None,
    "project_number": None,
    "nextracker_model": None,
    "lat_long": None,
    "snow_load": None,
    "wind_load": None,
    "issue_date": None,
    "expected_trackers": None,
    "expected_piers": None,
    "expected_modules_from_bom": None,
    "tolerance_ratio": 0.05,
    "notes": "",
}

ELECTRICAL_KEYS = (
    "total_output_mw", "total_strings", "total_modules", "modules_per_string",
    "module_capacity_w", "module_length_m", "module_width_m", "pitch_m",
    "inverters", "dccb", "string_groups", "devices",
    "dc_zones", "ac_zones", "transformers",
    "storage_zones", "batteries", "pcs", "storage_capacity_mwh",
    "camera_zones", "cameras", "network_devices",
    "site_id", "project_number", "nextracker_model", "lat_long",
    "snow_load", "wind_load", "issue_date",
    "expected_trackers", "expected_piers", "expected_modules_from_bom",
    "tracker_matrix", "bill_of_materials",
    "pier_type_specs", "pier_spacing_m",
)

# File upload kinds allowed
FILE_KINDS = {"construction_pdf", "ramming_pdf", "overlay_image", "block_mapping", "other"}


# --- Health ---------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True}


# --- Helpers --------------------------------------------------------------

def _require_project_uuid(project_id: str) -> str:
    u = db_store.get_project_uuid(project_id)
    if not u:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return u


def _compute_row_stats(trackers: list) -> dict:
    rows = [str(t.get("row", "")) for t in trackers if t.get("row")]
    unique = set(rows)
    numeric = [int(r) for r in rows if r.isdigit()]
    return {
        "row_count": len(unique),
        "mean_row_num": round(sum(numeric) / len(numeric), 1) if numeric else None,
    }


def _load_plant_info(project_uuid: str) -> dict:
    """Merge defaults ← extracted electrical (summary.electrical) ← user plant_info overrides."""
    meta = db_store.get_project_metadata(project_uuid)
    base = dict(PLANT_INFO_DEFAULTS)
    elec = (meta.get("summary") or {}).get("electrical") or {}
    for key in ELECTRICAL_KEYS:
        if elec.get(key) is not None:
            base[key] = elec[key]
    user = meta.get("plant_info") or {}
    for key, value in user.items():
        if value is not None and value != "":
            base[key] = value
    return base


def _project_upload_dir(project_id: str) -> Path:
    d = PROJECTS_ROOT / project_id / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _latest_files_by_kind(files: list[dict]) -> dict:
    """Return the newest uploaded file for each kind.

    db_store.list_project_files returns newest first, so setdefault keeps
    the file the user uploaded most recently when a kind has several rows.
    """
    by_kind = {}
    for f in files:
        by_kind.setdefault(f.get("kind"), f)
    return by_kind


def _build_epl_document_summary(files: list[dict], detected_profile: str | None = None) -> dict | None:
    """Build a no-ramming summary from uploaded electrical/layout PDFs.

    BHK/agro-PV drawing sets may have no structural ramming sheet at all, but
    the EPL string/optimizer parser can still validate the document package.
    Return None when the uploaded PDFs do not contain those signals.
    """
    pdf_paths = [
        f["storage_path"]
        for f in files
        if str(f.get("storage_path", "")).lower().endswith(".pdf")
    ]
    if not pdf_paths:
        return None

    from app.modules.epl.string_optimizer_parser import build_string_optimizer_model_from_pdfs

    so_model = build_string_optimizer_model_from_pdfs(pdf_paths)
    so_summary = so_model.get("summary") or {}
    if not (so_summary.get("strings") or so_summary.get("optimizers")):
        return None

    metadata = so_model.get("metadata") or {}
    electrical = {
        "total_strings": metadata.get("expected_strings"),
        "total_modules": metadata.get("expected_modules"),
        "modules_per_string": metadata.get("modules_per_string"),
        "string_groups": so_summary.get("string_zones"),
        "devices": (
            f"{metadata.get('expected_optimizers')} optimizers"
            if metadata.get("expected_optimizers") is not None
            else None
        ),
    }
    electrical = {k: v for k, v in electrical.items() if v is not None}
    physical_row_count = so_summary.get("physical_rows") or so_summary.get("rows_with_work") or 0
    zone_count = so_summary.get("string_zones") or 0

    return {
        "site_profile": detected_profile or "ground_pier",
        "document_profile": "agro_pv_epl",
        "detected_site_profile": detected_profile,
        "parse_scope": "electrical_only",
        "extraction_method": "document_epl",
        "block_count": 0,
        "tracker_count": 0,
        "pier_count": 0,
        "row_count": physical_row_count,
        "physical_row_count": physical_row_count,
        "zone_count": zone_count,
        "uploaded_pdf_count": len(pdf_paths),
        "structural_parse": {
            "status": "waiting_for_ramming_pdf",
            "message": "Electrical/layout documents were parsed. Upload the ramming PDF to build blocks, trackers, and piers.",
        },
        "strings_optimizers": {
            "project_type": so_model.get("project_type"),
            "features": so_model.get("features"),
            "metadata": metadata,
            "assets": so_model.get("assets"),
            "map_data": so_model.get("map_data"),
            "summary": so_summary,
            "map_source": so_model.get("map_source"),
            "label_selection": so_model.get("label_selection"),
            "source_label_summaries": so_model.get("source_label_summaries"),
            "issues": so_model.get("issues"),
        },
        "electrical": electrical,
    }


def _save_epl_document_parse(project_id: str, project_uuid: str, files: list[dict], detected_profile: str | None = None) -> dict | None:
    summary = _build_epl_document_summary(files, detected_profile=detected_profile)
    if not summary:
        return None
    from app.modules.epl.map_source import attach_map_source_image_url

    # Preserve any existing structural artifacts. Electrical-only document
    # uploads should not wipe an already-parsed pier map.
    blocks = db_store.get_blocks(project_uuid)
    trackers = db_store.get_trackers(project_uuid)
    piers = db_store.get_piers(project_uuid)
    summary["block_count"] = len(blocks)
    summary["tracker_count"] = len(trackers)
    summary["pier_count"] = len(piers)
    if isinstance(summary.get("strings_optimizers"), dict):
        summary["strings_optimizers"] = attach_map_source_image_url(
            project_id,
            project_uuid,
            summary["strings_optimizers"],
        )

    existing = db_store.get_project_metadata(project_uuid).get("summary") or {}
    merged = dict(existing)
    merged.update(summary)
    db_store.set_project_metadata(project_uuid, merged)
    db_store.upsert_project(
        project_id,
        site_profile=detected_profile or summary.get("site_profile") or "ground_pier",
        status="electrical_ready",
    )

    so_summary = (summary.get("strings_optimizers") or {}).get("summary") or {}
    return {
        "status": "electrical_ready",
        "parse_scope": "electrical_only",
        "block_count": summary["block_count"],
        "tracker_count": summary["tracker_count"],
        "pier_count": summary["pier_count"],
        "string_count": so_summary.get("strings", 0),
        "optimizer_count": so_summary.get("optimizers", 0),
        "module_count": so_summary.get("modules", 0),
        "requires_ramming": True,
    }


# --- Project list / create / delete ---------------------------------------

class ProjectCreate(BaseModel):
    project_id: str
    name: Optional[str] = None
    site_profile: Optional[str] = None
    project_type: Optional[str] = None
    enabled_features: Optional[dict] = None


@app.get("/api/projects")
def api_list_projects(request: Request):
    auth = request.headers.get("authorization", "")
    data = _verify_token(auth[7:]) if auth.startswith("Bearer ") else None
    projects = db_store.list_projects()
    if data and data.get("role") != "admin":
        allowed = _project_access_ids(str(data.get("username") or ""))
        projects = [p for p in projects if str(p.get("project_id")) in allowed]
    # Include the full project row so the frontend can branch on
    # site_profile (ground_pier / floating_string / rooftop) and show
    # lifecycle status.  `summary` stays last for backwards compat.
    return [
        {
            "project_id": p["project_id"],
            "name": p.get("name"),
            "status": p.get("status"),
            "site_profile": p.get("site_profile"),
            "project_type": (p.get("summary") or {}).get("project_type") or p.get("site_profile") or "unknown",
            "parsed_at": p.get("parsed_at"),
            "summary": p.get("summary") or {},
        }
        for p in projects
    ]


@app.post("/api/projects")
def api_create_project(request: Request, body: ProjectCreate):
    _require_admin(request)
    pid = body.project_id.strip()
    if not pid or not all(c.isalnum() or c in "-_" for c in pid):
        raise HTTPException(status_code=400, detail="Invalid project_id (alphanumeric, '-', '_' only)")
    from app.epl_engine.features import CREATABLE_PROJECT_TYPES, merge_enabled_features, normalize_project_type

    if not body.project_type and not body.site_profile:
        raise HTTPException(status_code=400, detail="project_type is required. Choose fixed_ground, floating, tracker, or hybrid.")
    project_type = normalize_project_type(body.project_type or body.site_profile)
    if project_type not in CREATABLE_PROJECT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid project_type. Choose fixed_ground, floating, tracker, or hybrid.")
    uu = db_store.upsert_project(pid, name=body.name or pid, site_profile=project_type, status="draft")
    meta = db_store.get_project_metadata(uu)
    summary = dict(meta.get("summary") or {})
    summary["project_type"] = project_type
    summary["site_profile"] = project_type
    summary["enabled_features"] = merge_enabled_features(project_type, body.enabled_features)
    db_store.set_project_metadata(uu, summary)
    (PROJECTS_ROOT / pid).mkdir(parents=True, exist_ok=True)
    _project_upload_dir(pid)
    return {"project_id": pid, "id": uu, "status": "draft", "project_type": project_type, "enabled_features": summary["enabled_features"]}


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str):
    uu = _require_project_uuid(project_id)
    meta = db_store.get_project_metadata(uu)
    summary = dict(meta.get("summary") or {})
    trackers = db_store.get_trackers(uu)
    row_stats = _compute_row_stats(trackers)
    summary.update(row_stats)
    # Ensure counts reflect DB state
    blocks = db_store.get_blocks(uu)
    piers_count = len(db_store.get_piers(uu))
    summary.setdefault("block_count", len(blocks))
    summary.setdefault("tracker_count", len(trackers))
    summary["block_count"] = len(blocks)
    summary["tracker_count"] = len(trackers)
    summary["pier_count"] = piers_count
    so_summary = (summary.get("strings_optimizers") or {}).get("summary") or {}
    electrical_row_count = so_summary.get("physical_rows") or so_summary.get("rows_with_work")
    if electrical_row_count:
        summary["physical_row_count"] = electrical_row_count
        if not summary.get("row_count"):
            summary["row_count"] = electrical_row_count
    if so_summary.get("string_zones"):
        summary["zone_count"] = so_summary.get("string_zones")
    so_payload = summary.get("strings_optimizers")
    if isinstance(so_payload, dict) and so_payload.get("map_source"):
        from app.modules.epl.map_source import attach_map_source_image_url

        summary["strings_optimizers"] = attach_map_source_image_url(project_id, uu, so_payload)
    return summary


@app.get("/api/projects/{project_id}/blocks")
def api_get_blocks(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_blocks(uu)


@app.get("/api/projects/{project_id}/trackers")
def api_get_trackers(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_trackers(uu)


@app.get("/api/projects/{project_id}/piers")
def api_get_piers(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_piers(uu)


@app.get("/api/projects/{project_id}/pier/{pier_id}")
def api_get_pier(project_id: str, pier_id: str):
    uu = _require_project_uuid(project_id)
    pier = db_store.get_pier(uu, pier_id)
    if not pier:
        raise HTTPException(status_code=404, detail="Pier not found")
    # Lookup tracker + block (cheap since already indexed)
    trackers = db_store.get_trackers(uu)
    blocks = db_store.get_blocks(uu)
    tracker = next((t for t in trackers if t.get("tracker_id") == pier.get("tracker_id")), None)
    block = next((b for b in blocks if b.get("block_id") == pier.get("block_id")), None)
    bundles = db_store.get_drawing_bundles(uu)
    return {"pier": pier, "tracker": tracker, "block": block, "drawing_bundle": bundles.get(pier_id)}


@app.get("/api/projects/{project_id}/pier/{pier_id}/zoom-target")
def api_get_zoom(project_id: str, pier_id: str):
    uu = _require_project_uuid(project_id)
    targets = db_store.get_zoom_targets(uu)
    z = targets.get(pier_id)
    if not z:
        raise HTTPException(status_code=404, detail="Zoom target not found")
    return z


# --- Pier statuses --------------------------------------------------------

class StatusUpdate(BaseModel):
    status: str


@app.get("/api/projects/{project_id}/pier-statuses")
def api_get_pier_statuses(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_pier_statuses(uu)


@app.put("/api/projects/{project_id}/pier/{pier_id}/status")
def api_update_pier_status(project_id: str, pier_id: str, body: StatusUpdate):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}")
    uu = _require_project_uuid(project_id)
    db_store.set_pier_status(uu, pier_id, body.status)
    return {"pier_id": pier_id, "status": body.status}


PIER_STATUS_EVENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pier_status_events (
  id          SERIAL PRIMARY KEY,
  project_id  UUID NOT NULL,
  pier_code   TEXT NOT NULL,
  status      TEXT NOT NULL,
  description TEXT,
  attachments JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_by  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pier_status_events_lookup
  ON pier_status_events(project_id, pier_code, created_at DESC);
"""


def _ensure_pier_status_events_schema() -> None:
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(PIER_STATUS_EVENTS_SCHEMA_SQL)
        conn.commit()


@app.on_event("startup")
def _startup_pier_status_events() -> None:
    try:
        _ensure_pier_status_events_schema()
    except Exception as exc:  # noqa: BLE001
        print(f"[pier_status_events] schema ensure failed: {exc}")


ATTACHMENT_MAX_SIZE_MB = 25
ATTACHMENT_MIME_PREFIXES = ("image/", "video/")
STRING_IMAGE_MAX_SIZE_MB = 12
# --- String Status Engine (AVL section + 6-stage progression) ------------
# NEW -> OPTIMIZER -> CONNECTION -> VOLT_CHECKED -> CABLE_TO_TGA -> TGA_COMMISSIONING ;
# AVL (the 2.x section) and ISSUE are separate states enterable from any stage.
STRING_STATUS_STAGES = ["new", "optimizer", "connection", "volt_checked", "cable_to_tga", "tga_commissioning"]
STRING_STATUS_VALUES = set(STRING_STATUS_STAGES) | {"issue", "avl"}
# Linear progression. The manual picker may set any value (validated against
# STRING_STATUS_VALUES); this table documents the canonical forward/back moves
# for guided flows. Issue can be entered from / restored to any stage.
STRING_STATUS_ALLOWED = {
    s: ({"issue"}
        | ({STRING_STATUS_STAGES[i + 1]} if i + 1 < len(STRING_STATUS_STAGES) else set())
        | ({STRING_STATUS_STAGES[i - 1]} if i > 0 else set()))
    for i, s in enumerate(STRING_STATUS_STAGES)
}
STRING_STATUS_ALLOWED["issue"] = set(STRING_STATUS_STAGES)
# AVL is a separate section designation, not a workflow stage.
STRING_STATUS_ALLOWED["avl"] = set(STRING_STATUS_STAGES) | {"issue"}
# Verified Progress weights spread evenly across stages (New=0 … last stage=1).
STRING_STATUS_WEIGHT = {s: i / (len(STRING_STATUS_STAGES) - 1) for i, s in enumerate(STRING_STATUS_STAGES)}
STRING_STATUS_WEIGHT["issue"] = 0.0
STRING_STATUS_WEIGHT["avl"] = 0.0
PAYMENT_ELIGIBLE_STATUS = STRING_STATUS_STAGES[-1]
STRING_RECORDS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS string_records (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  string_id  TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'new',
  statuses   JSONB NOT NULL DEFAULT '[]'::jsonb,
  pre_block_status TEXT,
  voltage    NUMERIC,
  comment    TEXT NOT NULL DEFAULT '',
  images     JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, string_id)
);
ALTER TABLE string_records ADD COLUMN IF NOT EXISTS pre_block_status TEXT;
ALTER TABLE string_records ADD COLUMN IF NOT EXISTS voltage NUMERIC;
ALTER TABLE string_records ADD COLUMN IF NOT EXISTS statuses JSONB NOT NULL DEFAULT '[]'::jsonb;
UPDATE string_records SET statuses = jsonb_build_array(status) WHERE jsonb_array_length(statuses) = 0 AND status IS NOT NULL;
CREATE TABLE IF NOT EXISTS string_status_history (
  id          BIGSERIAL PRIMARY KEY,
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  string_id   TEXT NOT NULL,
  from_status TEXT,
  to_status   TEXT NOT NULL,
  actor       TEXT,
  note        TEXT,
  gps_lat     NUMERIC, gps_lng NUMERIC,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ssh_proj_string ON string_status_history(project_id, string_id);
CREATE TABLE IF NOT EXISTS string_voltage_test (
  id          BIGSERIAL PRIMARY KEY,
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  string_id   TEXT NOT NULL,
  expected_voltage NUMERIC, measured_voltage NUMERIC,
  result      TEXT, technician TEXT,
  gps_lat     NUMERIC, gps_lng NUMERIC,
  tested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS string_blocker (
  id          BIGSERIAL PRIMARY KEY,
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  string_id   TEXT NOT NULL,
  category    TEXT, severity TEXT DEFAULT 'medium', reason TEXT,
  state       TEXT NOT NULL DEFAULT 'open',
  created_by  TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_by TEXT, resolved_at TIMESTAMPTZ, resolution_note TEXT
);
CREATE INDEX IF NOT EXISTS ix_blocker_open ON string_blocker(project_id, string_id) WHERE state='open';
"""


def _ensure_string_records_schema() -> None:
    # Execute each DDL statement separately: psycopg3's extended-protocol
    # execute() does not reliably run multiple semicolon-separated statements
    # in one call. None of these statements contain a ';' inside a literal,
    # so a simple split is safe.
    statements = [s.strip() for s in STRING_RECORDS_SCHEMA_SQL.split(";") if s.strip()]
    with db_store.get_conn() as conn, conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()


@app.on_event("startup")
def _startup_string_records() -> None:
    try:
        _ensure_string_records_schema()
    except Exception as exc:  # noqa: BLE001
        print(f"[string_records] schema ensure failed: {exc}")


def _safe_string_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return safe[:120] or "string"


def _string_records_dir(project_id: str) -> Path:
    d = PROJECTS_ROOT / project_id / "string_records"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _derive_primary_status(statuses) -> str:
    """Single representative status for the map/progress/payment: Issue wins if
    set, else the most-advanced commissioning stage, else AVL, else New."""
    s = {str(x).lower() for x in (statuses or [])}
    if "issue" in s:
        return "issue"
    stages = [st for st in STRING_STATUS_STAGES if st in s]
    if stages:
        return stages[-1]
    if "avl" in s:
        return "avl"
    return "new"


def _normalize_string_record(row: dict) -> dict:
    v = row.get("voltage")
    statuses = row.get("statuses")
    if isinstance(statuses, str):
        try:
            statuses = json.loads(statuses)
        except Exception:
            statuses = None
    status = row.get("status") or "new"
    if not statuses:
        # Legacy rows / endpoints that don't return the array: fall back to the
        # single status so the client always gets a usable set.
        statuses = [status] if status else []
    return {
        "status": status,
        "statuses": statuses,
        "voltage": float(v) if v is not None else None,
        "comment": row.get("comment") or "",
        "images": row.get("images") or [],
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


@app.get("/api/projects/{project_id}/strings/records")
def api_get_string_records(project_id: str):
    uu = _require_project_uuid(project_id)
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT string_id, status, statuses, voltage, comment, images, updated_at FROM string_records WHERE project_id = %s ORDER BY string_id",
            (uu,),
        )
        rows = cur.fetchall()
    return {"strings": {r["string_id"]: _normalize_string_record(r) for r in rows}}


def _string_current_status(cur, uu: str, string_id: str):
    cur.execute("SELECT status, pre_block_status FROM string_records WHERE project_id=%s AND string_id=%s", (uu, string_id))
    r = cur.fetchone()
    return (r["status"] if r else "new"), (r.get("pre_block_status") if r else None)


def _string_history(cur, uu: str, string_id: str, frm, to, actor=None, note=None, gps=None):
    g = gps or {}
    cur.execute(
        "INSERT INTO string_status_history (project_id, string_id, from_status, to_status, actor, note, gps_lat, gps_lng)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (uu, string_id, frm, to, actor, note, g.get("lat"), g.get("lng")),
    )


@app.put("/api/projects/{project_id}/strings/{string_id}/status")
def api_update_string_status(project_id: str, string_id: str, body: dict = Body(...)):
    uu = _require_project_uuid(project_id)
    to = str(body.get("status") or "new").lower()
    if to not in STRING_STATUS_VALUES:
        raise HTTPException(400, f"Invalid string status. Must be one of: {sorted(STRING_STATUS_VALUES)}")
    actor, note, gps = body.get("actor"), body.get("note"), body.get("gps")
    # MVP: the manual picker may set any of the 5 states; the guided flows
    # (voltage-test, blocker, resolve) drive the canonical transitions. The
    # allowed-transition table (STRING_STATUS_ALLOWED) is kept for those.
    with db_store.get_conn() as conn, conn.cursor() as cur:
        frm, pre = _string_current_status(cur, uu, string_id)
        pre_block = frm if (to == "issue" and frm != "issue") else (pre if to == "issue" else None)
        cur.execute(
            """
            INSERT INTO string_records (project_id, string_id, status, statuses, pre_block_status)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (project_id, string_id) DO UPDATE SET
              status = EXCLUDED.status, statuses = EXCLUDED.statuses, pre_block_status = EXCLUDED.pre_block_status, updated_at = NOW()
            RETURNING status, statuses, comment, images, updated_at
            """,
            (uu, string_id, to, json.dumps([to]), pre_block),
        )
        row = cur.fetchone()
        if to != frm:
            _string_history(cur, uu, string_id, frm, to, actor, note, gps)
        conn.commit()
    return {"string_id": string_id, **_normalize_string_record(row)}


@app.put("/api/projects/{project_id}/strings/{string_id}/statuses")
def api_update_string_statuses(project_id: str, string_id: str, body: dict = Body(...)):
    """Set the full set of statuses for a string (free multi-select). The single
    `status` column is kept in sync as the derived primary so the map, progress
    bar, payment eligibility and status filter keep working unchanged."""
    uu = _require_project_uuid(project_id)
    raw = body.get("statuses")
    if not isinstance(raw, list):
        raise HTTPException(400, "Body must include a 'statuses' list.")
    statuses: list[str] = []
    for x in raw:
        v = str(x or "").lower()
        if v not in STRING_STATUS_VALUES:
            raise HTTPException(400, f"Invalid string status '{v}'. Must be one of: {sorted(STRING_STATUS_VALUES)}")
        if v not in statuses:
            statuses.append(v)
    primary = _derive_primary_status(statuses)
    actor, note, gps = body.get("actor"), body.get("note"), body.get("gps")
    with db_store.get_conn() as conn, conn.cursor() as cur:
        frm, _pre = _string_current_status(cur, uu, string_id)
        cur.execute(
            """
            INSERT INTO string_records (project_id, string_id, status, statuses)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (project_id, string_id) DO UPDATE SET
              status = EXCLUDED.status, statuses = EXCLUDED.statuses, updated_at = NOW()
            RETURNING status, statuses, voltage, comment, images, updated_at
            """,
            (uu, string_id, primary, json.dumps(statuses)),
        )
        row = cur.fetchone()
        if primary != frm:
            _string_history(cur, uu, string_id, frm, primary, actor, note, gps)
        conn.commit()
    return {"string_id": string_id, **_normalize_string_record(row)}


@app.post("/api/projects/{project_id}/strings/{string_id}/voltage-test")
def api_string_voltage_test(project_id: str, string_id: str, body: dict = Body(...)):
    uu = _require_project_uuid(project_id)
    expected = body.get("expected_voltage")
    measured = body.get("measured_voltage")
    result = str(body.get("result") or "").upper()
    if result not in ("PASS", "FAIL"):
        try:
            result = "PASS" if (expected and measured and abs(float(measured) - float(expected)) <= 0.05 * float(expected)) else "FAIL"
        except Exception:
            result = "FAIL"
    tech, gps = body.get("technician") or body.get("actor"), body.get("gps") or {}
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO string_voltage_test (project_id,string_id,expected_voltage,measured_voltage,result,technician,gps_lat,gps_lng)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, tested_at",
            (uu, string_id, expected, measured, result, tech, gps.get("lat"), gps.get("lng")),
        )
        vt = cur.fetchone()
        new_status = None
        if result == "PASS":
            frm, _ = _string_current_status(cur, uu, string_id)
            cur.execute(
                "INSERT INTO string_records (project_id,string_id,status) VALUES (%s,%s,'volt_checked')"
                " ON CONFLICT (project_id,string_id) DO UPDATE SET status='volt_checked', pre_block_status=NULL, updated_at=NOW()",
                (uu, string_id),
            )
            _string_history(cur, uu, string_id, frm, "volt_checked", tech, f"voltage {measured}V {result}", gps)
            new_status = "volt_checked"
        conn.commit()
    return {"string_id": string_id, "result": result, "test_id": vt["id"], "status": new_status}


@app.post("/api/projects/{project_id}/strings/{string_id}/blocker")
def api_string_blocker(project_id: str, string_id: str, body: dict = Body(...)):
    uu = _require_project_uuid(project_id)
    cat, sev, reason = body.get("category"), body.get("severity") or "medium", body.get("reason")
    actor, gps = body.get("created_by") or body.get("actor"), body.get("gps") or {}
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO string_blocker (project_id,string_id,category,severity,reason,created_by)"
            " VALUES (%s,%s,%s,%s,%s,%s) RETURNING id, created_at",
            (uu, string_id, cat, sev, reason, actor),
        )
        b = cur.fetchone()
        frm, pre = _string_current_status(cur, uu, string_id)
        keep_pre = frm if frm != "issue" else pre
        cur.execute(
            "INSERT INTO string_records (project_id,string_id,status,pre_block_status) VALUES (%s,%s,'issue',%s)"
            " ON CONFLICT (project_id,string_id) DO UPDATE SET status='issue', pre_block_status=%s, updated_at=NOW()",
            (uu, string_id, keep_pre, keep_pre),
        )
        if frm != "issue":
            _string_history(cur, uu, string_id, frm, "issue", actor, reason, gps)
        conn.commit()
    return {"string_id": string_id, "blocker_id": b["id"], "status": "issue"}


@app.post("/api/projects/{project_id}/string-blockers/{blocker_id}/resolve")
def api_resolve_string_blocker(project_id: str, blocker_id: int, body: dict = Body(default={})):
    uu = _require_project_uuid(project_id)
    note, actor, resume = body.get("note"), body.get("resolved_by") or body.get("actor"), body.get("resume_to")
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT string_id FROM string_blocker WHERE id=%s AND project_id=%s", (blocker_id, uu))
        br = cur.fetchone()
        if not br:
            raise HTTPException(404, "Blocker not found")
        sid = br["string_id"]
        cur.execute("UPDATE string_blocker SET state='resolved', resolved_by=%s, resolved_at=NOW(), resolution_note=%s WHERE id=%s",
                    (actor, note, blocker_id))
        frm, pre = _string_current_status(cur, uu, sid)
        to = str(resume or pre or "new").lower()
        if to not in STRING_STATUS_VALUES:
            to = "new"
        cur.execute(
            "INSERT INTO string_records (project_id,string_id,status,pre_block_status) VALUES (%s,%s,%s,NULL)"
            " ON CONFLICT (project_id,string_id) DO UPDATE SET status=EXCLUDED.status, pre_block_status=NULL, updated_at=NOW()",
            (uu, sid, to),
        )
        _string_history(cur, uu, sid, frm, to, actor, f"blocker resolved: {note or ''}", None)
        conn.commit()
    return {"string_id": sid, "status": to}


@app.get("/api/projects/{project_id}/strings/progress")
def api_string_progress(project_id: str):
    uu = _require_project_uuid(project_id)
    meta = db_store.get_project_metadata(uu)
    topo = ((((meta.get("summary") or {}).get("strings_optimizers") or {}).get("map_data") or {}).get("layers") or {}).get("string_topology") or []
    info = {}
    for s in topo:
        c = s.get("string")
        if not c:
            continue
        parts = str(c).split(".")
        info[c] = {"rows": [r.get("physical_row") for r in (s.get("rows") or [])],
                   "zone": ".".join(parts[:3]) if len(parts) >= 3 else c}
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT string_id, status FROM string_records WHERE project_id=%s", (uu,))
        st = {r["string_id"]: r["status"] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) AS n FROM string_blocker WHERE project_id=%s AND state='open'", (uu,))
        open_blk = cur.fetchone()["n"]
    codes = list(info.keys()) or list(st.keys())
    total = len(codes)
    by_status = {k: 0 for k in STRING_STATUS_VALUES}
    by_row, by_zone = {}, {}
    blank = lambda: {k: 0 for k in STRING_STATUS_VALUES}
    for c in codes:
        s = st.get(c, "new")
        if s not in by_status:
            s = "new"
        by_status[s] += 1
        z = info.get(c, {}).get("zone")
        if z:
            by_zone.setdefault(z, blank())[s] += 1
        for rw in info.get(c, {}).get("rows") or []:
            if rw is not None:
                by_row.setdefault(rw, blank())[s] += 1
    weighted = sum(STRING_STATUS_WEIGHT.get(s, 0) * n for s, n in by_status.items())
    verified = by_status.get(PAYMENT_ELIGIBLE_STATUS, 0)
    return {
        "total": total,
        "by_status": by_status,
        "pct": {k: round(100 * v / total, 1) if total else 0 for k, v in by_status.items()},
        "verified_progress_pct": round(100 * verified / total, 1) if total else 0,
        "weighted_progress_pct": round(100 * weighted / total, 1) if total else 0,
        "payment_eligible": verified,
        "open_blockers": open_blk,
        "by_row": [{"row": k, **v} for k, v in sorted(by_row.items())],
        "by_zone": [{"zone": k, **v} for k, v in sorted(by_zone.items())],
    }


@app.put("/api/projects/{project_id}/strings/{string_id}/comment")
def api_update_string_comment(project_id: str, string_id: str, body: dict = Body(...)):
    uu = _require_project_uuid(project_id)
    comment = str(body.get("comment") or "")
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO string_records (project_id, string_id, comment)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, string_id) DO UPDATE SET comment = EXCLUDED.comment, updated_at = NOW()
            RETURNING status, comment, images, updated_at
            """,
            (uu, string_id, comment),
        )
        row = cur.fetchone()
        conn.commit()
    return {"string_id": string_id, **_normalize_string_record(row)}


@app.put("/api/projects/{project_id}/strings/{string_id}/voltage")
def api_update_string_voltage(project_id: str, string_id: str, body: dict = Body(...)):
    uu = _require_project_uuid(project_id)
    raw = body.get("voltage")
    try:
        voltage = float(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        voltage = None
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO string_records (project_id, string_id, voltage)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, string_id) DO UPDATE SET voltage = EXCLUDED.voltage, updated_at = NOW()
            RETURNING status, voltage, comment, images, updated_at
            """,
            (uu, string_id, voltage),
        )
        row = cur.fetchone()
        conn.commit()
    return {"string_id": string_id, **_normalize_string_record(row)}


@app.post("/api/projects/{project_id}/strings/{string_id}/images")
async def api_add_string_image(project_id: str, string_id: str, file: UploadFile = File(...)):
    uu = _require_project_uuid(project_id)
    mime = file.content_type or "application/octet-stream"
    if not mime.startswith("image/"):
        raise HTTPException(400, f"Unsupported image type: {mime}")
    content = await file.read()
    if len(content) / (1024 * 1024) > STRING_IMAGE_MAX_SIZE_MB:
        raise HTTPException(413, f"File '{file.filename}' exceeds the {STRING_IMAGE_MAX_SIZE_MB} MB limit.")
    # Cap stored images at ~100 KB so the offline bundle stays small on field devices.
    content, shrunk = shrink_image_to_max(content)
    if shrunk:
        mime = "image/jpeg"
    safe_string = _safe_string_id(string_id)
    images_dir = _string_records_dir(project_id) / "images" / safe_string
    images_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix.lower()
    if shrunk:
        ext = ".jpg"
    elif not ext:
        ext = ".jpg" if mime in {"image/jpeg", "image/jpg"} else ".png"
    file_id = str(uuid.uuid4())
    save_name = f"{file_id}{ext}"
    (images_dir / save_name).write_bytes(content)
    image = {
        "file_id": file_id,
        "original_name": file.filename,
        "mime_type": mime,
        "size": len(content),
        "url": f"/projects/{project_id}/string_records/images/{safe_string}/{save_name}",
    }
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO string_records (project_id, string_id, images)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (project_id, string_id) DO UPDATE SET
              images = string_records.images || EXCLUDED.images,
              updated_at = NOW()
            RETURNING status, comment, images, updated_at
            """,
            (uu, string_id, json.dumps([image])),
        )
        row = cur.fetchone()
        conn.commit()
    return {"string_id": string_id, "image": image, "record": _normalize_string_record(row)}


@app.delete("/api/projects/{project_id}/strings/{string_id}/images")
def api_delete_string_image(project_id: str, string_id: str, body: dict = Body(...)):
    uu = _require_project_uuid(project_id)
    url = str(body.get("url") or "")
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT images FROM string_records WHERE project_id=%s AND string_id=%s", (uu, string_id))
        row = cur.fetchone()
        imgs = (row.get("images") if row else None) or []
        kept = [im for im in imgs if (im.get("url") if isinstance(im, dict) else im) != url]
        cur.execute(
            "INSERT INTO string_records (project_id, string_id, images) VALUES (%s, %s, %s)"
            " ON CONFLICT (project_id, string_id) DO UPDATE SET images = EXCLUDED.images, updated_at = NOW()"
            " RETURNING status, comment, images, updated_at",
            (uu, string_id, json.dumps(kept)),
        )
        r = cur.fetchone()
        conn.commit()
    return {"string_id": string_id, **_normalize_string_record(r)}


@app.post("/api/projects/{project_id}/pier/{pier_code}/status-event")
async def api_create_status_event(
    project_id: str,
    pier_code: str,
    request: Request,
    status: str = Form(...),
    description: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    """Record a pier status change along with an optional description and
    photo / video attachments.  Used when the grid rejects a pier so the
    inspector can capture why.
    """
    if status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}")
    uu = _require_project_uuid(project_id)

    # Who's submitting — best-effort, falls back to "admin" for legacy tokens.
    auth = request.headers.get("authorization", "")
    tok = _verify_token(auth[7:]) if auth.startswith("Bearer ") else None
    created_by = (tok or {}).get("username", "unknown")

    saved: list[dict] = []
    attachments_dir = PROJECTS_ROOT / project_id / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        mime = upload.content_type or "application/octet-stream"
        if not mime.startswith(ATTACHMENT_MIME_PREFIXES):
            raise HTTPException(400, f"Unsupported attachment type: {mime}. Only images and videos are accepted.")
        content = await upload.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > ATTACHMENT_MAX_SIZE_MB:
            raise HTTPException(413, f"File '{upload.filename}' exceeds the {ATTACHMENT_MAX_SIZE_MB} MB limit.")

        file_id = str(uuid.uuid4())
        ext = Path(upload.filename or "").suffix.lower() or ""
        save_name = f"{file_id}{ext}"
        (attachments_dir / save_name).write_bytes(content)

        saved.append({
            "file_id": file_id,
            "original_name": upload.filename,
            "mime_type": mime,
            "size": len(content),
            "url": f"/projects/{project_id}/attachments/{save_name}",
        })

    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pier_status_events
                (project_id, pier_code, status, description, attachments, created_by)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id, created_at
            """,
            (uu, pier_code, status, description or None, json.dumps(saved), created_by),
        )
        row = cur.fetchone()
        conn.commit()

    # Also update the pier's current status so the grid / map reflect it.
    db_store.set_pier_status(uu, pier_code, status)

    return {
        "id": row["id"],
        "pier_code": pier_code,
        "status": status,
        "description": description,
        "attachments": saved,
        "created_at": row["created_at"].isoformat(),
        "created_by": created_by,
    }


@app.get("/api/projects/{project_id}/pier/{pier_code}/status-events")
def api_list_status_events(project_id: str, pier_code: str):
    uu = _require_project_uuid(project_id)
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, description, attachments, created_by, created_at
            FROM pier_status_events
            WHERE project_id = %s AND pier_code = %s
            ORDER BY created_at DESC
            """,
            (uu, pier_code),
        )
        out = []
        for r in cur.fetchall():
            d = dict(r)
            if d.get("created_at") is not None:
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


@app.post("/api/projects/{project_id}/pier-statuses/bulk")
def api_bulk_update_pier_status(project_id: str, body: dict = Body(...)):
    """Update the status of many piers in a single DB round-trip.

    Body: {"pier_codes": ["P-1", "P-2", ...], "status": "Approved"}.
    Previously the frontend issued one PUT per pier — for 20 k piers that
    meant 20 k HTTP + 20 k round-trips to Postgres, which took minutes.
    This version does one HTTP request and one SQL statement (UNNEST ||
    ON CONFLICT), completing in ~hundreds of ms.
    """
    codes = body.get("pier_codes") or []
    status = body.get("status")
    if not isinstance(codes, list) or not isinstance(status, str):
        raise HTTPException(400, "Body must include pier_codes[] and status")
    if status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}")
    uu = _require_project_uuid(project_id)
    written = db_store.bulk_set_pier_status(uu, [str(c) for c in codes], status)
    return {"updated": written, "status": status}


# --- Plant info -----------------------------------------------------------

@app.get("/api/projects/{project_id}/plant-info")
def api_get_plant_info(project_id: str):
    uu = _require_project_uuid(project_id)
    return _load_plant_info(uu)


@app.put("/api/projects/{project_id}/plant-info")
def api_update_plant_info(project_id: str, body: dict):
    uu = _require_project_uuid(project_id)
    meta = db_store.get_project_metadata(uu)
    current_user = dict(meta.get("plant_info") or {})
    for key in PLANT_INFO_DEFAULTS:
        if key in body:
            current_user[key] = body[key]
    db_store.update_plant_info(uu, current_user)
    return _load_plant_info(uu)


# --- File upload + parse --------------------------------------------------

@app.get("/api/projects/{project_id}/files")
def api_list_files(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.list_project_files(uu)


@app.post("/api/projects/{project_id}/files")
async def api_upload_file(
    project_id: str,
    kind: str = Form(...),
    file: UploadFile = File(...),
):
    if kind not in FILE_KINDS:
        raise HTTPException(status_code=400, detail=f"Invalid kind. Must be one of {sorted(FILE_KINDS)}")
    uu = _require_project_uuid(project_id)

    upload_dir = _project_upload_dir(project_id)
    safe_name = f"{kind}_{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = upload_dir / safe_name

    sha = hashlib.sha256()
    size = 0
    with dest.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
            size += len(chunk)
            f.write(chunk)

    file_id = db_store.add_project_file(
        project_uuid=uu,
        kind=kind,
        filename=safe_name,
        storage_path=str(dest.resolve()),
        original_name=file.filename,
        size_bytes=size,
        sha256=sha.hexdigest(),
    )
    return {"id": file_id, "filename": safe_name, "kind": kind, "size": size}


@app.delete("/api/projects/{project_id}/files")
def api_clear_files(project_id: str):
    uu = _require_project_uuid(project_id)
    # Delete physical files too
    upload_dir = PROJECTS_ROOT / project_id / "uploads"
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)
        upload_dir.mkdir(parents=True, exist_ok=True)
    db_store.clear_project_files(uu)
    return {"ok": True}


@app.post("/api/projects/{project_id}/parse")
def api_parse_project(project_id: str):
    """
    Clear all existing artifacts for this project and re-run the parser using the
    currently uploaded files. Returns the new summary.
    """
    uu = _require_project_uuid(project_id)
    files = db_store.list_project_files(uu)
    kinds = _latest_files_by_kind(files)
    construction = kinds.get("construction_pdf")
    ramming = kinds.get("ramming_pdf")
    overlay = kinds.get("overlay_image") or construction  # fall back to construction PDF
    block_mapping = kinds.get("block_mapping")
    if not construction:
        epl_result = _save_epl_document_parse(project_id, uu, files)
        if epl_result:
            return epl_result
        raise HTTPException(status_code=400, detail="Missing construction PDF. Upload a file with kind=construction_pdf first.")

    # Detect the site profile from the uploaded construction PDF so the
    # parse flow can route to the right branch *and* relax requirements
    # that don't apply to the detected profile (e.g. floating sites have
    # no ramming plan).
    from app.parsers.profile_detector import detect_site_profile_from_files
    detected_profile = detect_site_profile_from_files(
        [construction["storage_path"]] + ([ramming["storage_path"]] if ramming else []),
    )

    if detected_profile == "ground_pier" and not ramming:
        epl_result = _save_epl_document_parse(project_id, uu, files, detected_profile=detected_profile)
        if epl_result:
            return epl_result
        raise HTTPException(
            status_code=400,
            detail="Missing ramming PDF. Upload a file with kind=ramming_pdf first "
                   "(required for pile-driven/tracker ground sites).",
        )

    # Clear old artifacts and record the detected site profile on the
    # project row so downstream APIs + the frontend can branch on it.
    db_store.delete_project_artifacts(uu)
    db_store.upsert_project(project_id, site_profile=detected_profile, status="parsing")

    try:
        # Run the parser
        from app.parser import run_pipeline
        from app.site_profiles import load_site_profile
        from app.electrical_metadata import extract_electrical_metadata

        out_dir = PROJECTS_ROOT / project_id
        out_dir.mkdir(parents=True, exist_ok=True)

        input_paths = [construction["storage_path"], ramming["storage_path"]]
        profile = load_site_profile(profile_name="auto", input_paths=input_paths)

        result = run_pipeline(
            construction_pdf=construction["storage_path"],
            ramming_pdf=ramming["storage_path"],
            overlay_source=overlay["storage_path"],
            out_dir=out_dir,
            profile=profile,
            block_mapping_source=block_mapping["storage_path"] if block_mapping else None,
        )

        # Persist into DB
        db_store.insert_blocks(uu, result.get("blocks", []))
        db_store.insert_trackers(uu, result.get("trackers", []))
        db_store.insert_piers(uu, result.get("piers", []))
        db_store.set_drawing_bundles(uu, result.get("drawing_bundles", {}))
        db_store.set_zoom_targets(uu, result.get("zoom_targets", {}))

        # Attach extracted electrical metadata to summary
        summary = dict(result.get("summary") or {})
        try:
            elec = extract_electrical_metadata(
                construction["storage_path"], ramming["storage_path"]
            )
            if elec.get("_extracted"):
                summary["electrical"] = {k: v for k, v in elec.items() if not k.startswith("_")}
        except Exception:
            pass

        # EPL strings/optimizers reconstruction for BHK/SolarEdge/agro-PV style
        # projects.  This is intentionally non-blocking: if a project does not
        # contain 10/11 STRINGS labels or SolarEdge optimizer metadata, the
        # normal pier/tracker parser still completes.
        try:
            from app.modules.epl.string_optimizer_parser import build_string_optimizer_model_from_pdfs

            pdf_paths = [
                f["storage_path"]
                for f in files
                if str(f.get("storage_path", "")).lower().endswith(".pdf")
            ]
            if pdf_paths:
                so_model = build_string_optimizer_model_from_pdfs(pdf_paths)
                so_summary = so_model.get("summary") or {}
                # Save only the light summary in project metadata; the full
                # model/CSV are available through /api/epl/... endpoints.
                if so_summary.get("strings") or so_summary.get("optimizers"):
                    summary["strings_optimizers"] = {
                        "project_type": so_model.get("project_type"),
                        "features": so_model.get("features"),
                        "metadata": so_model.get("metadata"),
                        "assets": so_model.get("assets"),
                        "map_data": so_model.get("map_data"),
                        "summary": so_summary,
                        "map_source": so_model.get("map_source"),
                        "label_selection": so_model.get("label_selection"),
                        "source_label_summaries": so_model.get("source_label_summaries"),
                        "issues": so_model.get("issues"),
                    }
        except Exception as exc:
            summary["strings_optimizers_error"] = str(exc)

        db_store.set_project_metadata(uu, summary)
        db_store.upsert_project(project_id, status="ready")

        return {
            "status": "ready",
            "block_count": len(result.get("blocks", [])),
            "tracker_count": len(result.get("trackers", [])),
            "pier_count": len(result.get("piers", [])),
        }
    except Exception as e:
        db_store.upsert_project(project_id, status="error")
        raise HTTPException(status_code=500, detail=str(e))


# --- Aggregation endpoints (fast DB queries) ------------------------------

@app.get("/api/projects/{project_id}/pier-type-counts")
def api_pier_type_counts(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_pier_type_counts(uu)


@app.get("/api/projects/{project_id}/block-summary")
def api_block_summary(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_block_summary(uu)


@app.get("/api/projects/{project_id}/row-summary")
def api_row_summary(project_id: str):
    uu = _require_project_uuid(project_id)
    return db_store.get_row_summary(uu)
