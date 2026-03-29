"""
PVPM v1 import API – accepts the connector's native camelCase format.

POST /api/v1/import/batch   – upsert measurements from the connector
GET  /api/v1/import/measurements – list all synced pvpm measurements
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import get_db_connection

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CurvePointIn(BaseModel):
    pointIndex: int
    voltageV: float
    currentA: float


class MeasurementIn(BaseModel):
    id: str
    externalMeasurementKey: Optional[str] = None
    measuredAt: datetime
    customer: Optional[str] = None
    installation: Optional[str] = None
    stringNo: Optional[str] = None
    moduleType: Optional[str] = None
    moduleReference: Optional[str] = None
    modulesSeries: Optional[int] = None
    modulesParallel: Optional[int] = None
    nominalPowerW: Optional[float] = None
    ppkWp: Optional[float] = None
    rsOhm: Optional[float] = None
    rpOhm: Optional[float] = None
    vocV: Optional[float] = None
    iscA: Optional[float] = None
    vpmaxV: Optional[float] = None
    ipmaxA: Optional[float] = None
    ffPercent: Optional[float] = None
    sweepDurationMs: Optional[float] = None
    irradianceWM2: Optional[float] = None
    sensorTempC: Optional[float] = None
    moduleTempC: Optional[float] = None
    irradianceSensorType: Optional[str] = None
    irradianceSensorSerial: Optional[str] = None
    rawPayloadJson: Optional[dict[str, Any]] = None
    importSource: Optional[str] = None
    notes: Optional[str] = None
    curvePoints: list[CurvePointIn] = []


class DeviceIn(BaseModel):
    deviceSerial: Optional[str] = None
    deviceModel: Optional[str] = None
    firmwareVersion: Optional[str] = None


class BatchImportRequest(BaseModel):
    device: DeviceIn = DeviceIn()
    measurements: list[MeasurementIn]
    site_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/batch")
def import_batch(request: BatchImportRequest, conn=Depends(get_db_connection)):
    """
    Upsert a batch of PVPM measurements (camelCase format) from the connector.
    Creates or updates the device record, upserts each measurement, replaces
    curve points, and logs each sync operation.
    """
    now = datetime.utcnow().isoformat()
    serial = request.device.deviceSerial or "unknown"

    with conn.cursor() as cur:
        # Upsert device
        cur.execute("SELECT id FROM pvpm_devices WHERE serial_number = %s", (serial,))
        row = cur.fetchone()
        if row:
            device_id = row[0]
            cur.execute(
                "UPDATE pvpm_devices SET last_seen_at = %s WHERE id = %s",
                (now, device_id),
            )
        else:
            cur.execute(
                """INSERT INTO pvpm_devices (serial_number, model, firmware_version, last_seen_at)
                   VALUES (%s, %s, %s, %s)""",
                (serial, request.device.deviceModel, request.device.firmwareVersion, now),
            )
            # Fetch the new id (works for both PostgreSQL lastrowid and RETURNING)
            cur.execute("SELECT id FROM pvpm_devices WHERE serial_number = %s", (serial,))
            device_id = cur.fetchone()[0]

        for item in request.measurements:
            measured_at_str = item.measuredAt.isoformat()
            raw_json = json.dumps(item.rawPayloadJson) if item.rawPayloadJson else None

            # Check if measurement already exists
            cur.execute("SELECT id FROM pvpm_measurements WHERE id = %s", (item.id,))
            exists = cur.fetchone()

            if not exists:
                cur.execute(
                    "INSERT INTO pvpm_measurements (id, measured_at) VALUES (%s, %s)",
                    (item.id, measured_at_str),
                )

            cur.execute(
                """UPDATE pvpm_measurements SET
                    device_id = %s,
                    external_measurement_key = %s,
                    measured_at = %s,
                    customer = %s,
                    installation = %s,
                    string_no = %s,
                    module_type = %s,
                    module_reference = %s,
                    modules_series = %s,
                    modules_parallel = %s,
                    nominal_power_w = %s,
                    ppk_wp = %s,
                    rs_ohm = %s,
                    rp_ohm = %s,
                    voc_v = %s,
                    isc_a = %s,
                    vpmax_v = %s,
                    ipmax_a = %s,
                    ff_percent = %s,
                    sweep_duration_ms = %s,
                    irradiance_w_m2 = %s,
                    sensor_temp_c = %s,
                    module_temp_c = %s,
                    irradiance_sensor_type = %s,
                    irradiance_sensor_serial = %s,
                    raw_payload_json = %s,
                    import_source = %s,
                    sync_status = %s,
                    notes = %s,
                    site_id = %s
                WHERE id = %s""",
                (
                    device_id,
                    item.externalMeasurementKey,
                    measured_at_str,
                    item.customer,
                    item.installation,
                    item.stringNo,
                    item.moduleType,
                    item.moduleReference,
                    item.modulesSeries,
                    item.modulesParallel,
                    item.nominalPowerW,
                    item.ppkWp,
                    item.rsOhm,
                    item.rpOhm,
                    item.vocV,
                    item.iscA,
                    item.vpmaxV,
                    item.ipmaxA,
                    item.ffPercent,
                    item.sweepDurationMs,
                    item.irradianceWM2,
                    item.sensorTempC,
                    item.moduleTempC,
                    item.irradianceSensorType,
                    item.irradianceSensorSerial,
                    raw_json,
                    item.importSource,
                    "synced",
                    item.notes,
                    request.site_id,
                    item.id,
                ),
            )

            # Replace curve points
            cur.execute("DELETE FROM pvpm_curve_points WHERE measurement_id = %s", (item.id,))
            for point in item.curvePoints:
                cur.execute(
                    """INSERT INTO pvpm_curve_points (measurement_id, point_index, voltage_v, current_a)
                       VALUES (%s, %s, %s, %s)""",
                    (item.id, point.pointIndex, point.voltageV, point.currentA),
                )

            # Sync log
            cur.execute(
                """INSERT INTO pvpm_sync_logs (measurement_id, direction, status, payload_json, created_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (item.id, "reader_to_backend", "success", json.dumps({"measurementId": item.id}), now),
            )

    conn.commit()
    return {"imported": len(request.measurements)}


@router.get("/measurements")
def list_pvpm_measurements(
    site_id: Optional[int] = None,
    conn=Depends(get_db_connection),
):
    """List all PVPM measurements synced from the connector."""
    where = "WHERE site_id = %(site_id)s" if site_id is not None else ""
    params: dict = {}
    if site_id is not None:
        params["site_id"] = site_id
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, measured_at, customer, installation, module_type,
                      ppk_wp, voc_v, isc_a, irradiance_w_m2, sync_status
               FROM pvpm_measurements
               {where}
               ORDER BY measured_at DESC""",
            params,
        )
        rows = cur.fetchall()

    return {
        "items": [
            {
                "id": r[0],
                "measuredAt": r[1] if isinstance(r[1], str) else (r[1].isoformat() if r[1] else None),
                "customer": r[2],
                "installation": r[3],
                "moduleType": r[4],
                "ppkWp": r[5],
                "vocV": r[6],
                "iscA": r[7],
                "irradianceWM2": r[8],
                "syncStatus": r[9],
            }
            for r in rows
        ]
    }
