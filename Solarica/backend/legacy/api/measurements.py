"""Measurement API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database import get_db_connection

router = APIRouter()


class IVPoint(BaseModel):
    voltage: float
    current: float


class MeasurementResponse(BaseModel):
    id: int
    measured_at: Optional[datetime] = None
    device_serial: Optional[str]
    sensor_serial: Optional[str]
    customer: Optional[str]
    module_type: Optional[str]
    remarks: Optional[str]
    ppk: Optional[float]
    rs: Optional[float]
    rp: Optional[float]
    voc: Optional[float]
    isc: Optional[float]
    vpmax: Optional[float]
    ipmax: Optional[float]
    pmax: Optional[float]
    fill_factor: Optional[float]
    eeff: Optional[float]
    tmod: Optional[float]
    tcell: Optional[float]
    source_file: Optional[str]
    created_at: Optional[datetime] = None
    site_id: Optional[int] = None

    class Config:
        from_attributes = True


class MeasurementDetailResponse(MeasurementResponse):
    iv_curve: list[IVPoint] = []


@router.get("", response_model=list[MeasurementResponse])
async def list_measurements(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    customer: Optional[str] = None,
    module_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    site_id: Optional[int] = None,
    conn=Depends(get_db_connection),
):
    """List measurements with optional filters."""
    where_clauses = []
    params: dict = {"skip": skip, "limit": limit}

    if customer:
        where_clauses.append("m.customer ILIKE %(customer)s")
        params["customer"] = f"%{customer}%"
    if module_type:
        where_clauses.append("m.module_type ILIKE %(module_type)s")
        params["module_type"] = f"%{module_type}%"
    if date_from:
        where_clauses.append("m.measured_at >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("m.measured_at <= %(date_to)s")
        params["date_to"] = date_to
    if site_id is not None:
        where_clauses.append("m.site_id = %(site_id)s")
        params["site_id"] = site_id

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT m.id, m.measured_at, m.device_serial, m.irradiance_sensor_serial AS sensor_serial,
                   m.customer, m.module_type, m.remarks,
                   m.ppk, m.rs, m.rp, m.voc, m.isc, m.vpmax, m.ipmax,
                   m.pmax, m.ff AS fill_factor, m.eeff, m.tmod, m.tcell,
                   m.source_file, m.created_at, m.site_id
            FROM measurements m
            WHERE {where_sql}
            ORDER BY m.measured_at DESC
            LIMIT %(limit)s OFFSET %(skip)s
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        MeasurementResponse(
            id=r[0],
            measured_at=r[1],
            device_serial=r[2],
            sensor_serial=r[3],
            customer=r[4],
            module_type=r[5],
            remarks=r[6],
            ppk=r[7],
            rs=r[8],
            rp=r[9],
            voc=r[10],
            isc=r[11],
            vpmax=r[12],
            ipmax=r[13],
            pmax=r[14],
            fill_factor=r[15],
            eeff=r[16],
            tmod=r[17],
            tcell=r[18],
            source_file=r[19],
            created_at=r[20],
            site_id=r[21],
        )
        for r in rows
    ]


@router.get("/stats/summary")
async def get_summary_stats(
    site_id: Optional[int] = None,
    conn=Depends(get_db_connection),
):
    """Get summary statistics for the dashboard."""
    site_filter = "AND site_id = %(site_id)s" if site_id is not None else ""
    params: dict = {}
    if site_id is not None:
        params["site_id"] = site_id

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                COUNT(*) as total_measurements,
                MIN(measured_at) as first_measurement,
                MAX(measured_at) as last_measurement,
                AVG(ppk) as avg_ppk,
                AVG(eeff) as avg_irradiance
            FROM measurements
            WHERE ppk IS NOT NULL {site_filter}
            """,
            params,
        )
        row = cur.fetchone()

        cur.execute(
            f"SELECT COUNT(DISTINCT customer) FROM measurements WHERE customer IS NOT NULL AND customer != '' {site_filter}",
            params,
        )
        customer_count = cur.fetchone()[0]

    return {
        "total_measurements": row[0] or 0,
        "first_measurement": row[1],
        "last_measurement": row[2],
        "avg_peak_power_kw": round(row[3] / 1000, 2) if row[3] else None,
        "avg_irradiance_wm2": round(row[4], 1) if row[4] else None,
        "unique_customers": customer_count,
    }


@router.get("/{measurement_id}", response_model=MeasurementDetailResponse)
async def get_measurement(
    measurement_id: int,
    conn=Depends(get_db_connection),
):
    """Get a single measurement with its I-V curve."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, m.measured_at, m.device_serial, m.irradiance_sensor_serial AS sensor_serial,
                   m.customer, m.module_type, m.remarks,
                   m.ppk, m.rs, m.rp, m.voc, m.isc, m.vpmax, m.ipmax,
                   m.pmax, m.ff AS fill_factor, m.eeff, m.tmod, m.tcell,
                   m.source_file, m.created_at, m.site_id
            FROM measurements m
            WHERE m.id = %s
            """,
            (measurement_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Measurement not found")

        cur.execute(
            "SELECT voltage, current FROM iv_curve_points WHERE measurement_id = %s ORDER BY point_index",
            (measurement_id,),
        )
        iv_rows = cur.fetchall()

    return MeasurementDetailResponse(
        id=row[0],
        measured_at=row[1] if row[1] else None,
        device_serial=row[2],
        sensor_serial=row[3],
        customer=row[4],
        module_type=row[5],
        remarks=row[6],
        ppk=row[7],
        rs=row[8],
        rp=row[9],
        voc=row[10],
        isc=row[11],
        vpmax=row[12],
        ipmax=row[13],
        pmax=row[14],
        fill_factor=row[15],
        eeff=row[16],
        tmod=row[17],
        tcell=row[18],
        source_file=row[19],
        created_at=row[20] if row[20] else None,
        site_id=row[21],
        iv_curve=[IVPoint(voltage=r[0], current=r[1]) for r in iv_rows],
    )
