"""
Database-backed project store.

Provides read/write access to project entities (blocks, trackers, piers, metadata,
pier_statuses) via Postgres. Replaces the JSON-file-based ProjectCache for all
API reads, while the parser still writes JSON artifacts as well for debug/history.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Optional
from uuid import UUID

from app.db import get_conn


# --- Projects -------------------------------------------------------------

def upsert_project(project_id: str, name: Optional[str] = None, site_profile: Optional[str] = None,
                   status: str = "draft") -> str:
    """Create or update the project row. Returns the UUID."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (project_id, name, site_profile, status, updated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (project_id) DO UPDATE SET
                name = COALESCE(EXCLUDED.name, projects.name),
                site_profile = COALESCE(EXCLUDED.site_profile, projects.site_profile),
                status = EXCLUDED.status,
                updated_at = now()
            RETURNING id
            """,
            (project_id, name or project_id, site_profile, status),
        )
        row = cur.fetchone()
        conn.commit()
        return str(row["id"])


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
                   p.created_at,
                   COALESCE(m.summary, '{}'::jsonb) AS summary
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
                "summary": r["summary"] or {},
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
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO project_files (project_id, kind, filename, original_name, storage_path, size_bytes, sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (project_uuid, kind, filename, original_name, storage_path, size_bytes, sha256),
        )
        row = cur.fetchone()
        conn.commit()
        return str(row["id"])


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
                INSERT INTO project_metadata (project_id, summary, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (project_id) DO UPDATE SET summary = EXCLUDED.summary, updated_at = now()
                """,
                (project_uuid, json.dumps(summary)),
            )
        else:
            cur.execute(
                """
                INSERT INTO project_metadata (project_id, summary, plant_info, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (project_id) DO UPDATE SET
                    summary = EXCLUDED.summary,
                    plant_info = EXCLUDED.plant_info,
                    updated_at = now()
                """,
                (project_uuid, json.dumps(summary), json.dumps(plant_info)),
            )
        conn.commit()


def update_plant_info(project_uuid: str, plant_info: dict) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO project_metadata (project_id, plant_info, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (project_id) DO UPDATE SET plant_info = EXCLUDED.plant_info, updated_at = now()
            RETURNING plant_info
            """,
            (project_uuid, json.dumps(plant_info)),
        )
        row = cur.fetchone()
        conn.commit()
        return row["plant_info"]


def get_project_metadata(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT summary, plant_info FROM project_metadata WHERE project_id = %s",
            (project_uuid,),
        )
        row = cur.fetchone()
        if not row:
            return {"summary": {}, "plant_info": {}}
        return {"summary": row["summary"] or {}, "plant_info": row["plant_info"] or {}}


# --- Bulk insert artifacts ------------------------------------------------

def insert_blocks(project_uuid: str, blocks: Iterable[dict]) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for b in blocks:
            cur.execute(
                """
                INSERT INTO blocks (project_id, block_code, label, color, original_block_id,
                                     block_pier_plan_sheet, bbox_json, centroid_json, polygon_json, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, block_code) DO UPDATE SET
                    label = EXCLUDED.label,
                    color = EXCLUDED.color,
                    bbox_json = EXCLUDED.bbox_json,
                    centroid_json = EXCLUDED.centroid_json,
                    polygon_json = EXCLUDED.polygon_json,
                    data = EXCLUDED.data
                """,
                (
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
                ),
            )
        conn.commit()


def insert_trackers(project_uuid: str, trackers: Iterable[dict]) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for t in trackers:
            cur.execute(
                """
                INSERT INTO trackers (project_id, tracker_code, block_code, row_num, trk,
                                       tracker_type_code, tracker_sheet, orientation, pier_count,
                                       bbox_json, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, tracker_code) DO UPDATE SET
                    block_code = EXCLUDED.block_code,
                    row_num = EXCLUDED.row_num,
                    trk = EXCLUDED.trk,
                    tracker_type_code = EXCLUDED.tracker_type_code,
                    pier_count = EXCLUDED.pier_count,
                    bbox_json = EXCLUDED.bbox_json,
                    data = EXCLUDED.data
                """,
                (
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
                ),
            )
        conn.commit()


def insert_piers(project_uuid: str, piers: Iterable[dict]) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        batch = list(piers)
        # Bulk insert with executemany for speed
        rows = [
            (
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
        cur.executemany(
            """
            INSERT INTO piers (project_id, pier_code, tracker_code, block_code, row_num,
                                row_pier_count, tracker_type_code, tracker_sheet, structure_code,
                                structure_sheet, pier_type, pier_type_sheet, slope_band, slope_sheet,
                                x, y, bbox_json, assignment_method, data)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (project_id, pier_code) DO UPDATE SET
                tracker_code = EXCLUDED.tracker_code,
                block_code = EXCLUDED.block_code,
                row_num = EXCLUDED.row_num,
                row_pier_count = EXCLUDED.row_pier_count,
                pier_type = EXCLUDED.pier_type,
                x = EXCLUDED.x, y = EXCLUDED.y,
                bbox_json = EXCLUDED.bbox_json,
                data = EXCLUDED.data
            """,
            rows,
        )
        conn.commit()


def set_drawing_bundles(project_uuid: str, bundles: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO drawing_bundles (project_id, bundles) VALUES (%s, %s)
            ON CONFLICT (project_id) DO UPDATE SET bundles = EXCLUDED.bundles
            """,
            (project_uuid, json.dumps(bundles)),
        )
        conn.commit()


def set_zoom_targets(project_uuid: str, targets: dict) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO zoom_targets (project_id, targets) VALUES (%s, %s)
            ON CONFLICT (project_id) DO UPDATE SET targets = EXCLUDED.targets
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
        return [r["data"] for r in cur.fetchall()]


def get_trackers(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM trackers WHERE project_id = %s ORDER BY tracker_code",
            (project_uuid,),
        )
        return [r["data"] for r in cur.fetchall()]


def get_piers(project_uuid: str) -> list:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM piers WHERE project_id = %s ORDER BY pier_code",
            (project_uuid,),
        )
        return [r["data"] for r in cur.fetchall()]


def get_pier(project_uuid: str, pier_code: str) -> Optional[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data FROM piers WHERE project_id = %s AND pier_code = %s",
            (project_uuid, pier_code),
        )
        row = cur.fetchone()
        return row["data"] if row else None


def get_drawing_bundles(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT bundles FROM drawing_bundles WHERE project_id = %s", (project_uuid,))
        row = cur.fetchone()
        return row["bundles"] if row else {}


def get_zoom_targets(project_uuid: str) -> dict:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT targets FROM zoom_targets WHERE project_id = %s", (project_uuid,))
        row = cur.fetchone()
        return row["targets"] if row else {}


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
                ON CONFLICT (project_id, pier_code) DO UPDATE SET status = EXCLUDED.status, updated_at = now()
                """,
                (project_uuid, pier_code, status),
            )
        conn.commit()


def bulk_set_pier_status(project_uuid: str, pier_codes: list, status: str) -> int:
    """Set the same status for many piers in ONE round-trip.

    - status == "New"     → delete rows (row absence is treated as "New")
    - status == <other>   → upsert in a single statement via UNNEST.

    Returns the number of piers written (or deleted).
    """
    if not pier_codes:
        return 0
    with get_conn() as conn, conn.cursor() as cur:
        if status == "New":
            cur.execute(
                "DELETE FROM pier_statuses WHERE project_id = %s AND pier_code = ANY(%s)",
                (project_uuid, list(pier_codes)),
            )
            conn.commit()
            return cur.rowcount
        cur.execute(
            """
            INSERT INTO pier_statuses (project_id, pier_code, status)
            SELECT %s, code, %s FROM UNNEST(%s::text[]) AS t(code)
            ON CONFLICT (project_id, pier_code) DO UPDATE
                SET status = EXCLUDED.status, updated_at = now()
            """,
            (project_uuid, status, list(pier_codes)),
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
        return [{"pier_type": r["pier_type"], "count": r["count"]} for r in cur.fetchall()]


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
