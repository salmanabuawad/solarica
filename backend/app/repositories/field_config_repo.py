from __future__ import annotations
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.field_config import FieldConfig


def get_all(db: Session, grid_name: str) -> List[FieldConfig]:
    return (
        db.query(FieldConfig)
        .filter(FieldConfig.grid_name == grid_name)
        .order_by(FieldConfig.column_order.asc().nulls_last(), FieldConfig.field_name)
        .all()
    )


def get_all_grids(db: Session) -> List[FieldConfig]:
    return (
        db.query(FieldConfig)
        .order_by(FieldConfig.grid_name, FieldConfig.column_order.asc().nulls_last(), FieldConfig.field_name)
        .all()
    )


def seed_defaults(db: Session) -> int:
    """
    Insert default field configurations for all grids if none exist yet.
    Number columns → width 80px, long-text columns → width 300px, others → None (flex).
    Skips grids that already have any rows.
    """
    N  = 80    # number / date / short fields
    LT = 300   # long text fields

    DEFAULTS: list[dict] = []

    def col(grid, order, field, visible, width=None):
        DEFAULTS.append({
            "grid_name": grid, "field_name": field,
            "visible": visible, "width": width, "column_order": order,
        })

    # ── projects ──────────────────────────────────────────────────────────────
    g = "projects"
    col(g, 0,  "id",               False, N)
    col(g, 1,  "name",             True,  LT)
    col(g, 2,  "customer_name",    True,  LT)
    col(g, 3,  "site_name",        True,  LT)
    col(g, 4,  "project_type",     True,  None)
    col(g, 5,  "phase",            True,  None)
    col(g, 6,  "progress_percent", True,  N)
    col(g, 7,  "is_active",        False, N)
    col(g, 8,  "created_at",       False, N)

    # ── materials ─────────────────────────────────────────────────────────────
    g = "materials"
    col(g, 0, "name",          True,  LT)
    col(g, 1, "category",      True,  None)
    col(g, 2, "unit",          True,  N)
    col(g, 3, "sku",           True,  None)
    col(g, 4, "min_threshold", True,  N)
    col(g, 5, "unit_cost",     True,  N)

    # ── tasks ─────────────────────────────────────────────────────────────────
    g = "tasks"
    col(g, 0, "title",        True,  LT)
    col(g, 1, "project_name", True,  LT)
    col(g, 2, "status",       True,  None)
    col(g, 3, "priority",     True,  None)
    col(g, 4, "assigned_to",  True,  None)
    col(g, 5, "due_date",     True,  N)
    col(g, 6, "created_at",   False, N)

    # ── measurements ─────────────────────────────────────────────────────────
    g = "measurements"
    col(g, 0,  "project_name", True,  LT)
    col(g, 1,  "test_date",    True,  N)
    col(g, 2,  "string_id",    True,  None)
    col(g, 3,  "inverter_id",  True,  None)
    col(g, 4,  "voc",          True,  N)
    col(g, 5,  "isc",          True,  N)
    col(g, 6,  "vmp",          False, N)
    col(g, 7,  "imp",          False, N)
    col(g, 8,  "pmax",         True,  N)
    col(g, 9,  "irradiance",   False, N)
    col(g, 10, "temperature",  False, N)

    # ── device_inventory ─────────────────────────────────────────────────────
    g = "device_inventory"
    col(g, 0,  "device_tag",      True,  None)
    col(g, 1,  "device_type",     True,  None)
    col(g, 2,  "manufacturer",    True,  LT)
    col(g, 3,  "model",           True,  LT)
    col(g, 4,  "site_name",       True,  LT)
    col(g, 5,  "status",          True,  None)
    col(g, 6,  "serial_number",   False, None)
    col(g, 7,  "firmware",        False, None)
    col(g, 8,  "install_date",    True,  N)
    col(g, 9,  "warranty_expiry", False, N)
    col(g, 10, "notes",           False, LT)

    # ── solar_catalog ─────────────────────────────────────────────────────────
    g = "solar_catalog"
    col(g, 0, "manufacturer_name", True,  LT)
    col(g, 1, "model_name",        True,  LT)
    col(g, 2, "brand_name",        False, LT)
    col(g, 3, "category_name",     True,  None)
    col(g, 4, "technology",        True,  None)
    col(g, 5, "source_code",       True,  None)
    col(g, 6, "is_hybrid",         False, N)
    col(g, 7, "spec_count",        True,  N)

    # ── device_registry ───────────────────────────────────────────────────────
    g = "device_registry"
    col(g, 0, "cve_id",       True,  None)
    col(g, 1, "title",        True,  LT)
    col(g, 2, "severity",     True,  None)
    col(g, 3, "cvss_v3",      True,  N)
    col(g, 4, "published",    True,  N)
    col(g, 5, "device_count", True,  N)

    # ── vulnerabilities ───────────────────────────────────────────────────────
    g = "vulnerabilities"
    col(g, 0, "cve_id",           True,  None)
    col(g, 1, "title",            True,  LT)
    col(g, 2, "severity",         True,  None)
    col(g, 3, "cvss_v3",          True,  N)
    col(g, 4, "published_date",   True,  N)
    col(g, 5, "affected_product", True,  LT)
    col(g, 6, "source_name",      False, None)

    # Only seed grids that have no rows yet
    existing_grids = {
        r[0] for r in db.query(FieldConfig.grid_name).distinct().all()
    }
    rows_to_insert = [r for r in DEFAULTS if r["grid_name"] not in existing_grids]

    if not rows_to_insert:
        return 0

    stmt = (
        pg_insert(FieldConfig)
        .values(rows_to_insert)
        .on_conflict_do_nothing(constraint="uq_field_config_grid_field")
    )
    db.execute(stmt)
    db.commit()
    return len(rows_to_insert)


def bulk_upsert(db: Session, rows: list[dict]) -> int:
    """
    Upsert a list of {grid_name, field_name, visible, width, column_order} dicts.
    Uses PostgreSQL ON CONFLICT DO UPDATE for atomicity.
    """
    if not rows:
        return 0

    stmt = (
        pg_insert(FieldConfig)
        .values(rows)
        .on_conflict_do_update(
            constraint="uq_field_config_grid_field",
            set_={
                "visible":      pg_insert(FieldConfig).excluded.visible,
                "width":        pg_insert(FieldConfig).excluded.width,
                "column_order": pg_insert(FieldConfig).excluded.column_order,
            },
        )
    )
    db.execute(stmt)
    db.commit()
    return len(rows)
