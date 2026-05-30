"""
Database-backed project store (MySQL/MariaDB).

Read/write access to project entities (blocks, trackers, piers, metadata,
pier_statuses). Ported from the original PostgreSQL version. The schema lives
in db/solarica_mysql_schema.sql.

Notes about the MySQL port:
- UUID PKs are CHAR(36); new ids are generated in Python (uuid4) and passed
  explicitly to INSERT, replacing PostgreSQL's RETURNING id.
- ON CONFLICT (...) DO UPDATE -> INSERT ... ON DUPLICATE KEY UPDATE col=VALUES(col).
- JSON columns return strings from PyMySQL; ``_jload`` parses them on read.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Iterable, Optional

from app.db import get_conn


def _jload(value: Any) -> Any:
    """Parse a JSON column value coming back from PyMySQL (string/bytes) into
    a Python object. Tolerates ``None`` and already-decoded values."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _new_uuid() -> str:
    return str(uuid.uuid4())


# --- Projects -------------------------------------------------------------

def upsert_project(project_id: str, name: Optional[str] = None, site_profile: Optional[str] = None,
                   status: str = "draft") -> str:
    """Create or update the project row. Returns the UUID (existing or new)."""
    new_id = _new_uuid()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (id, project_id, name, site_profile, status, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                name         = COALESCE(VALUES(name), projects.name),
                site_profile = COALESCE(VALUES(site_profile), projects.site_profile),
                status       = VALUES(status),
                updated_at   = NOW()
            """,
            (new_id, project_id, name or project_id, site_profile, status),
        )
        cur.execute("SELECT id FROM projects WHERE project_id = %s", (project_id,))
        row = cur.fetchone()
        conn.commit()
        return str(row["id"]) if row else new_id


def get_project_uuid(project_id: str) -> Optional[str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM projects WHERE project_id = %s", (project_id,))
        row = cur.fetchone()
        return str(row["id"]) if row else None


def list_projects() -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.project_id, p.name, p.status, p.site_profile, p.parsed_at,
                   p.created_at, m.summary
            FROM projects p
            LEFT JOIN project_metadata m ON m.project_id = p.id
            ORDER BY p.created_at DESC
            """
        )
        rows = cur.fetchall()
        return [
            {
                "project_id": r["project_id"],
                "name": r["name"],
                "status": r["status"],
                "site_profile": r.get("site_profile"),
                "parsed_at": r["parsed_at"].isoformat() if r.get("parsed_at") else None,
                "summary": _jload(r.get("summary")) or {},
            }
            for r in rows
        ]


def delete_project_artifacts(project_uuid: str) -> None:
    """Clear all parsed artifacts for a project (kept: project row, files, plant_info)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM piers WHERE project_id = %s", (project_uuid,))
        cur.execute("DELETE FROM trackers WHERE project_id = %s", (project_uuid,))
        cur.execute("DELETE FROM blocks WHERE project_id = %s", (project_uuid,))
        cur.execute("DELETE FROM drawing_bundles WHERE project_id = %s", (project_uuid,))
        cur.execute("DELETE FROM zoom_targets WHERE project_id = %s", (project_uuid,))
        cur.execute("DELETE FROM pier_statuses WHERE project_id = %s", (project_uuid,))
        conn.commit()


# --- Files ----------------------------------------------------------------

def add_project_file(project_uuid: str, kind: str, filename: str, storage_path: str,
                     original_name: Optional[str] = None, size_bytes: Optional[int] = None,
                     sha256: Optional[str] = None) -> str:
    file_id = _new_uuid()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO project_files (id, project_id, kind, filename, original_name, storage_path, size_bytes, sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (file_id, project_uuid, kind, filename, original_name, storage_path, size_bytes, sha256),
        )
        conn.commit()
        return file_id


def list_project_files(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, kind, filename, original_name, storage_path, size_bytes, sha256, uploaded_at
            FROM project_files
            WHERE project_id = %s
            ORDER BY uploaded_at DESC
            """,
            (project_uuid,),
        )
        rows = cur.fetchall()
        return [
            {
                **r,
                "id": str(r["id"]),
                "uploaded_at": r["uploaded_at"].isoformat() if r.get("uploaded_at") else None,
            }
            for r in rows
        ]


def clear_project_files(project_uuid: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM project_files WHERE project_id = %s", (project_uuid,))
        conn.commit()


# --- Metadata -------------------------------------------------------------

def set_project_metadata(project_uuid: str, summary: dict, plant_info: Optional[dict] = None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        if plant_info is None:
            cur.execute(
                """
                INSERT INTO project_metadata (project_id, summary, plant_info, updated_at)
                VALUES (%s, %s, '{}', NOW())
                ON DUPLICATE KEY UPDATE
                    summary    = VALUES(summary),
                    updated_at = NOW()
                """,
                (project_uuid, json.dumps(summary)),
            )
        else:
            cur.execute(
                """
                INSERT INTO project_metadata (project_id, summary, plant_info, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    summary    = VALUES(summary),
                    plant_info = VALUES(plant_info),
                    updated_at = NOW()
                """,
                (project_uuid, json.dumps(summary), json.dumps(plant_info)),
            )
        conn.commit()


def update_plant_info(project_uuid: str, plant_info: dict) -> dict:
    payload = json.dumps(plant_info)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO project_metadata (project_id, summary, plant_info, updated_at)
            VALUES (%s, '{}', %s, NOW())
            ON DUPLICATE KEY UPDATE
                plant_info = VALUES(plant_info),
                updated_at = NOW()
            """,
            (project_uuid, payload),
        )
        cur.execute(
            "SELECT plant_info FROM project_metadata WHERE project_id = %s",
            (project_uuid,),
        )
        row = cur.fetchone()
        conn.commit()
        return _jload(row["plant_info"]) if row else plant_info


def get_project_metadata(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT summary, plant_info FROM project_metadata WHERE project_id = %s",
            (project_uuid,),
        )
        row = cur.fetchone()
        if not row:
            return {"summary": {}, "plant_info": {}}
        return {
            "summary":    _jload(row.get("summary")) or {},
            "plant_info": _jload(row.get("plant_info")) or {},
        }


# --- Bulk insert artifacts ------------------------------------------------

def insert_blocks(project_uuid: str, blocks: Iterable[dict]) -> None:
    rows = [
        (
            _new_uuid(),
            project_uuid,
            b.get("block_code"),
            b.get("label"),
            b.get("color"),
            str(b.get("original_block_id") or ""),
            b.get("block_pier_plan_sheet"),
            json.dumps(b.get("bbox", {})),
            json.dumps(b.get("centroid", {})),
            json.dumps(b.get("polygon", [])),
            json.dumps(b),
        )
        for b in blocks
    ]
    if not rows:
        return
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO blocks (id, project_id, block_code, label, color, original_block_id,
                                 block_pier_plan_sheet, bbox_json, centroid_json, polygon_json, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                label         = VALUES(label),
                color         = VALUES(color),
                bbox_json     = VALUES(bbox_json),
                centroid_json = VALUES(centroid_json),
                polygon_json  = VALUES(polygon_json),
                data          = VALUES(data)
            """,
            rows,
        )
        conn.commit()


def insert_trackers(project_uuid: str, trackers: Iterable[dict]) -> None:
    rows = [
        (
            _new_uuid(),
            project_uuid,
            t.get("tracker_code"),
            t.get("block_code"),
            str(t.get("row", "")),
            str(t.get("trk", "")),
            t.get("tracker_type_code"),
            t.get("tracker_sheet"),
            t.get("orientation"),
            t.get("pier_count"),
            json.dumps(t.get("bbox", {})),
            json.dumps({k: v for k, v in t.items() if k != "piers"}),
        )
        for t in trackers
    ]
    if not rows:
        return
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO trackers (id, project_id, tracker_code, block_code, row_num, trk,
                                   tracker_type_code, tracker_sheet, orientation, pier_count,
                                   bbox_json, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                block_code        = VALUES(block_code),
                row_num           = VALUES(row_num),
                trk               = VALUES(trk),
                tracker_type_code = VALUES(tracker_type_code),
                pier_count        = VALUES(pier_count),
                bbox_json         = VALUES(bbox_json),
                data              = VALUES(data)
            """,
            rows,
        )
        conn.commit()


def insert_piers(project_uuid: str, piers: Iterable[dict]) -> None:
    batch = list(piers)
    if not batch:
        return
    rows = [
        (
            _new_uuid(),
            project_uuid,
            p.get("pier_code"),
            p.get("tracker_code"),
            p.get("block_code"),
            str(p.get("row_num", "")),
            p.get("row_pier_count"),
            p.get("tracker_type_code"),
            p.get("tracker_sheet"),
            p.get("structure_code"),
            p.get("structure_sheet"),
            p.get("pier_type"),
            p.get("pier_type_sheet"),
            p.get("slope_band"),
            p.get("slope_sheet"),
            p.get("x"),
            p.get("y"),
            json.dumps(p.get("bbox", {})),
            p.get("assignment_method"),
            json.dumps(p),
        )
        for p in batch
    ]
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO piers (id, project_id, pier_code, tracker_code, block_code, row_num,
                                row_pier_count, tracker_type_code, tracker_sheet, structure_code,
                                structure_sheet, pier_type, pier_type_sheet, slope_band, slope_sheet,
                                x, y, bbox_json, assignment_method, data)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                tracker_code   = VALUES(tracker_code),
                block_code     = VALUES(block_code),
                row_num        = VALUES(row_num),
                row_pier_count = VALUES(row_pier_count),
                pier_type      = VALUES(pier_type),
                x              = VALUES(x),
                y              = VALUES(y),
                bbox_json      = VALUES(bbox_json),
                data           = VALUES(data)
            """,
            rows,
        )
        conn.commit()


def set_drawing_bundles(project_uuid: str, bundles: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO drawing_bundles (project_id, bundles) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE bundles = VALUES(bundles)
            """,
            (project_uuid, json.dumps(bundles)),
        )
        conn.commit()


def set_zoom_targets(project_uuid: str, targets: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO zoom_targets (project_id, targets) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE targets = VALUES(targets)
            """,
            (project_uuid, json.dumps(targets)),
        )
        conn.commit()


# --- Reads ----------------------------------------------------------------

def get_blocks(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM blocks WHERE project_id = %s ORDER BY block_code",
            (project_uuid,),
        )
        return [_jload(r["data"]) for r in cur.fetchall()]


def get_trackers(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM trackers WHERE project_id = %s ORDER BY tracker_code",
            (project_uuid,),
        )
        return [_jload(r["data"]) for r in cur.fetchall()]


def get_piers(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM piers WHERE project_id = %s ORDER BY pier_code",
            (project_uuid,),
        )
        return [_jload(r["data"]) for r in cur.fetchall()]


def get_pier(project_uuid: str, pier_code: str) -> Optional[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM piers WHERE project_id = %s AND pier_code = %s",
            (project_uuid, pier_code),
        )
        row = cur.fetchone()
        return _jload(row["data"]) if row else None


def get_drawing_bundles(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT bundles FROM drawing_bundles WHERE project_id = %s", (project_uuid,))
        row = cur.fetchone()
        return _jload(row["bundles"]) if row else {}


def get_zoom_targets(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT targets FROM zoom_targets WHERE project_id = %s", (project_uuid,))
        row = cur.fetchone()
        return _jload(row["targets"]) if row else {}


# --- Pier statuses --------------------------------------------------------

def get_pier_statuses(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT pier_code, status FROM pier_statuses WHERE project_id = %s", (project_uuid,))
        return {r["pier_code"]: r["status"] for r in cur.fetchall()}


def set_pier_status(project_uuid: str, pier_code: str, status: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        if status == "New":
            cur.execute(
                "DELETE FROM pier_statuses WHERE project_id = %s AND pier_code = %s",
                (project_uuid, pier_code),
            )
        else:
            cur.execute(
                """
                INSERT INTO pier_statuses (project_id, pier_code, status)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status), updated_at = NOW()
                """,
                (project_uuid, pier_code, status),
            )
        conn.commit()


def bulk_set_pier_status(project_uuid: str, pier_codes: list, status: str) -> int:
    """Set the same status for many piers in ONE round-trip.

    - status == "New"     -> delete rows (row absence is treated as "New")
    - status == <other>   -> upsert all via a single multi-row INSERT...ON DUPLICATE.

    Returns the number of piers written (or deleted).
    """
    codes = list(pier_codes)
    if not codes:
        return 0
    with get_conn() as conn, conn.cursor() as cur:
        if status == "New":
            placeholders = ", ".join(["%s"] * len(codes))
            cur.execute(
                f"DELETE FROM pier_statuses WHERE project_id = %s AND pier_code IN ({placeholders})",
                (project_uuid, *codes),
            )
            conn.commit()
            return cur.rowcount
        # Build a multi-row VALUES list for one INSERT ... ON DUPLICATE KEY UPDATE.
        value_tuples = ", ".join(["(%s, %s, %s)"] * len(codes))
        params: list = []
        for code in codes:
            params.extend([project_uuid, code, status])
        cur.execute(
            f"""
            INSERT INTO pier_statuses (project_id, pier_code, status)
            VALUES {value_tuples}
            ON DUPLICATE KEY UPDATE status = VALUES(status), updated_at = NOW()
            """,
            params,
        )
        conn.commit()
        return cur.rowcount


# --- Aggregations ---------------------------------------------------------

def get_pier_type_counts(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT pier_type, count FROM project_pier_type_counts WHERE project_id = %s ORDER BY count DESC",
            (project_uuid,),
        )
        return [{"pier_type": r["pier_type"], "count": int(r["count"])} for r in cur.fetchall()]


def get_block_summary(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT block_code, pier_count, tracker_count, row_count FROM project_block_summary WHERE project_id = %s ORDER BY block_code",
            (project_uuid,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_row_summary(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT row_num, tracker_count, pier_count FROM project_row_summary WHERE project_id = %s ORDER BY row_num",
            (project_uuid,),
        )
        return [dict(r) for r in cur.fetchall()]
