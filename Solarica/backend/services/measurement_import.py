"""Shared helpers for importing measurements into the database."""

from typing import Any, Optional

from config import settings
from database import get_connection


class MeasurementImportError(Exception):
    """Raised when a measurement payload cannot be imported."""


def _normalize_curve_point(point: Any) -> dict[str, float]:
    if hasattr(point, "model_dump"):
        point = point.model_dump()
    elif hasattr(point, "dict"):
        point = point.dict()

    if not isinstance(point, dict):
        raise MeasurementImportError("Invalid I-V curve point payload")

    return {
        "voltage": float(point.get("voltage", 0)),
        "current": float(point.get("current", 0)),
    }


def normalize_measurement_payload(payload: Any) -> dict[str, Any]:
    """Convert payloads from parsers or API models to a DB-ready dict."""
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(exclude_none=True)
    elif hasattr(payload, "dict"):
        payload = payload.dict(exclude_none=True)

    if not isinstance(payload, dict):
        raise MeasurementImportError("Measurement payload must be an object")

    normalized = {
        "measured_at": payload.get("measured_at"),
        "device_serial": payload.get("device_serial"),
        "sensor_serial": payload.get("sensor_serial") or payload.get("irradiance_sensor_serial"),
        "customer": payload.get("customer"),
        "module_type": payload.get("module_type"),
        "remarks": payload.get("remarks"),
        "ppk": payload.get("ppk"),
        "rs": payload.get("rs"),
        "rp": payload.get("rp"),
        "voc": payload.get("voc"),
        "isc": payload.get("isc"),
        "vpmax": payload.get("vpmax"),
        "ipmax": payload.get("ipmax"),
        "pmax": payload.get("pmax"),
        "fill_factor": payload.get("fill_factor") or payload.get("ff"),
        "eeff": payload.get("eeff"),
        "tmod": payload.get("tmod"),
        "tcell": payload.get("tcell"),
        "source_file": payload.get("source_file"),
        "device_record_id": payload.get("device_record_id"),
        "sync_source": payload.get("sync_source"),
        "iv_curve": [_normalize_curve_point(point) for point in (payload.get("iv_curve") or [])],
    }
    return normalized


def _build_duplicate_query(data: dict[str, Any]) -> tuple[str, list[Any]]:
    field_to_column = {
        "device_serial": "device_serial",
        "measured_at": "measured_at",
        "voc": "voc",
        "isc": "isc",
        "pmax": "pmax",
    }
    clauses: list[str] = []
    params: list[Any] = []

    for field, column in field_to_column.items():
        value = data.get(field)
        if value is None:
            clauses.append(f"{column} IS NULL")
        else:
            clauses.append(f"{column} = %s")
            params.append(value)

    sql = (
        "SELECT id FROM measurements "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY id DESC LIMIT 1"
    )
    return sql, params


def find_duplicate_measurement_id(cur, data: dict[str, Any]) -> Optional[int]:
    """Look up an existing measurement using a stable fingerprint."""
    sql, params = _build_duplicate_query(data)
    cur.execute(sql, params)
    row = cur.fetchone()
    return int(row[0]) if row else None


def insert_measurement_payload(
    payload: Any,
    *,
    allow_duplicates: bool = False,
    source_file_override: Optional[str] = None,
    site_id: Optional[int] = None,
) -> dict[str, Any]:
    """Insert one parsed measurement payload and its I-V curve."""
    data = normalize_measurement_payload(payload)
    if source_file_override:
        data["source_file"] = source_file_override

    use_sqlite = settings.database_url.strip().lower().startswith("sqlite")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if not allow_duplicates:
                duplicate_id = find_duplicate_measurement_id(cur, data)
                if duplicate_id is not None:
                    conn.rollback()
                    return {
                        "success": True,
                        "measurement_id": duplicate_id,
                        "message": f"Measurement already exists as #{duplicate_id}",
                        "duplicate": True,
                    }

            insert_sql = """
                INSERT INTO measurements (
                    measured_at, device_serial, irradiance_sensor_serial, customer, module_type, remarks,
                    ppk, rs, rp, voc, isc, vpmax, ipmax, pmax, ff, eeff, tmod, tcell, source_file, site_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            if not use_sqlite:
                insert_sql += " RETURNING id"
            cur.execute(
                insert_sql,
                (
                    data.get("measured_at"),
                    data.get("device_serial"),
                    data.get("sensor_serial"),
                    data.get("customer"),
                    data.get("module_type"),
                    data.get("remarks"),
                    data.get("ppk"),
                    data.get("rs"),
                    data.get("rp"),
                    data.get("voc"),
                    data.get("isc"),
                    data.get("vpmax"),
                    data.get("ipmax"),
                    data.get("pmax"),
                    data.get("fill_factor"),
                    data.get("eeff"),
                    data.get("tmod"),
                    data.get("tcell"),
                    data.get("source_file"),
                    site_id,
                ),
            )
            row = cur.fetchone()
            measurement_id = row[0] if row else getattr(cur, "lastrowid", None)
            if measurement_id is None:
                raise MeasurementImportError("Failed to get inserted measurement id")

            for index, point in enumerate(data.get("iv_curve") or []):
                cur.execute(
                    "INSERT INTO iv_curve_points (measurement_id, point_index, voltage, current) VALUES (%s, %s, %s, %s)",
                    (measurement_id, index, point["voltage"], point["current"]),
                )

        conn.commit()
        return {
            "success": True,
            "measurement_id": int(measurement_id),
            "message": f"Imported measurement #{measurement_id}",
            "duplicate": False,
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "measurement_id": None,
            "message": str(exc),
            "duplicate": False,
            "errors": [str(exc)],
        }
    finally:
        conn.close()
