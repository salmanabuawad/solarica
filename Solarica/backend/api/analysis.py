"""Analysis API endpoints for PV measurement data."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from database import get_db_connection

router = APIRouter()


class ComparisonResult(BaseModel):
    measurement_id: int
    ppk: float | None
    ppk_deviation_pct: float | None
    rs: float | None
    rp: float | None


@router.get("/summary")
async def analysis_summary(conn=Depends(get_db_connection)):
    """Aggregated analysis: total measurements, avg Ppk, Rs, irradiance by period."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) as n,
                AVG(ppk) as avg_ppk,
                AVG(rs) as avg_rs,
                AVG(rp) as avg_rp,
                AVG(eeff) as avg_eeff,
                MIN(measured_at) as first_at,
                MAX(measured_at) as last_at
            FROM measurements
            WHERE ppk IS NOT NULL
            """
        )
        row = cur.fetchone()
    return {
        "total_measurements": row[0] or 0,
        "avg_peak_power_w": round(row[1], 2) if row[1] else None,
        "avg_series_resistance_ohm": round(row[2], 4) if row[2] else None,
        "avg_parallel_resistance_ohm": round(row[3], 2) if row[3] else None,
        "avg_irradiance_wm2": round(row[4], 1) if row[4] else None,
        "first_measurement": row[5],
        "last_measurement": row[6],
    }


@router.get("/compare")
async def compare_measurements(
    ids: str = Query(..., description="Comma-separated measurement IDs"),
    conn=Depends(get_db_connection),
):
    """Compare multiple measurements by ID (for side-by-side IV curves)."""
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    if not id_list:
        return []
    placeholders = ",".join("%s" for _ in id_list)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, ppk, rs, rp, ppk_deviation, measured_at, source_file
            FROM measurements
            WHERE id IN ({placeholders})
            ORDER BY measured_at
            """,
            tuple(id_list),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "ppk": r[1],
            "rs": r[2],
            "rp": r[3],
            "ppk_deviation_pct": r[4],
            "measured_at": r[5],
            "source_file": r[6],
        }
        for r in rows
    ]
