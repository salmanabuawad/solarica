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
import secrets
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import PROJECTS_ROOT
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


def _ensure_users_schema() -> None:
    with db_store.get_conn() as conn, conn.cursor() as cur:
        cur.execute(USERS_SCHEMA_SQL)
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


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if path.startswith("/api/") and path not in _PUBLIC_API_PATHS:
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or not _verify_token(auth[7:]):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


def _require_admin(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    data = _verify_token(auth[7:]) if auth.startswith("Bearer ") else None
    if not data:
        raise HTTPException(401, "Not authenticated")
    if data.get("role") != "admin":
        raise HTTPException(403, "Admin role required")
    return data


@app.post("/api/auth/login")
async def api_login(creds: dict = Body(...)):
    username = str(creds.get("username") or "")
    password = str(creds.get("password") or "")
    # Try DB first
    row = _db_user_row(username)
    if row and row.get("is_active") and _verify_pw(password, row.get("password_hash") or ""):
        role = row.get("role") or "viewer"
        return {
            "access_token": _sign_token(username, role),
            "token_type": "bearer",
            "user": {"username": username, "role": role, "display_name": row.get("display_name")},
        }
    # Env-var fallback (only if no such user in DB)
    if not row and username == ADMIN_USER and password == ADMIN_PASS:
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
    if role not in {"admin", "editor", "viewer"}:
        raise HTTPException(400, "role must be admin, editor, or viewer")
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
        if role not in {"admin", "editor", "viewer"}:
            raise HTTPException(400, "role must be admin, editor, or viewer")
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

app.include_router(security_router,  prefix="/api/security",  tags=["security"])


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


# --- Project list / create / delete ---------------------------------------

class ProjectCreate(BaseModel):
    project_id: str
    name: Optional[str] = None
    site_profile: Optional[str] = None


@app.get("/api/projects")
def api_list_projects():
    projects = db_store.list_projects()
    # Include the full project row so the frontend can branch on
    # site_profile (ground_pier / floating_string / rooftop) and show
    # lifecycle status.  `summary` stays last for backwards compat.
    return [
        {
            "project_id": p["project_id"],
            "name": p.get("name"),
            "status": p.get("status"),
            "site_profile": p.get("site_profile"),
            "parsed_at": p.get("parsed_at"),
            "summary": p.get("summary") or {},
        }
        for p in projects
    ]


@app.post("/api/projects")
def api_create_project(body: ProjectCreate):
    pid = body.project_id.strip()
    if not pid or not all(c.isalnum() or c in "-_" for c in pid):
        raise HTTPException(status_code=400, detail="Invalid project_id (alphanumeric, '-', '_' only)")
    uu = db_store.upsert_project(pid, name=body.name or pid, site_profile=body.site_profile, status="draft")
    (PROJECTS_ROOT / pid).mkdir(parents=True, exist_ok=True)
    _project_upload_dir(pid)
    return {"project_id": pid, "id": uu, "status": "draft"}


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str):
    uu = _require_project_uuid(project_id)
    meta = db_store.get_project_metadata(uu)
    summary = dict(meta.get("summary") or {})
    trackers = db_store.get_trackers(uu)
    summary.update(_compute_row_stats(trackers))
    # Ensure counts reflect DB state
    blocks = db_store.get_blocks(uu)
    piers_count = len(db_store.get_piers(uu))
    summary.setdefault("block_count", len(blocks))
    summary.setdefault("tracker_count", len(trackers))
    summary["block_count"] = len(blocks)
    summary["tracker_count"] = len(trackers)
    summary["pier_count"] = piers_count
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
    kinds = {f["kind"]: f for f in files}
    construction = kinds.get("construction_pdf")
    ramming = kinds.get("ramming_pdf")
    overlay = kinds.get("overlay_image") or construction  # fall back to construction PDF
    block_mapping = kinds.get("block_mapping")
    if not construction:
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
