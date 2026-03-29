from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select

from .database import CurvePointRecord, MeasurementRecord, ModuleCatalogRecord, PartCatalogRecord, SessionLocal, SiteCatalogRecord, SyncStateRecord


def upsert_measurement(payload: dict) -> None:
    with SessionLocal() as session:
        existing = session.get(MeasurementRecord, payload["id"])
        if existing is None:
            existing = MeasurementRecord(
                id=payload["id"],
                measured_at=_parse_dt(payload.get("measuredAt")),
            )
            session.add(existing)

        existing.external_measurement_key = payload.get("externalMeasurementKey")
        existing.measured_at = _parse_dt(payload.get("measuredAt"))
        existing.customer = payload.get("customer")
        existing.installation = payload.get("installation")
        existing.string_no = payload.get("stringNo")
        existing.module_type = payload.get("moduleType")
        existing.module_reference = payload.get("moduleReference")
        existing.modules_series = payload.get("modulesSeries")
        existing.modules_parallel = payload.get("modulesParallel")
        existing.nominal_power_w = payload.get("nominalPowerW")
        existing.ppk_wp = payload.get("ppkWp")
        existing.rs_ohm = payload.get("rsOhm")
        existing.rp_ohm = payload.get("rpOhm")
        existing.voc_v = payload.get("vocV")
        existing.isc_a = payload.get("iscA")
        existing.vpmax_v = payload.get("vpmaxV")
        existing.ipmax_a = payload.get("ipmaxA")
        existing.ff_percent = payload.get("ffPercent")
        existing.sweep_duration_ms = payload.get("sweepDurationMs")
        existing.irradiance_w_m2 = payload.get("irradianceWM2")
        existing.sensor_temp_c = payload.get("sensorTempC")
        existing.module_temp_c = payload.get("moduleTempC")
        existing.irradiance_sensor_type = payload.get("irradianceSensorType")
        existing.irradiance_sensor_serial = payload.get("irradianceSensorSerial")
        existing.import_source = payload.get("importSource")
        existing.sync_status = payload.get("syncStatus", "unsynced")
        existing.notes = payload.get("notes")
        existing.raw_payload_json = payload.get("rawPayloadJson")

        # Replace curve points
        session.execute(
            delete(CurvePointRecord).where(CurvePointRecord.measurement_id == payload["id"])
        )
        for point in payload.get("curvePoints", []):
            session.add(
                CurvePointRecord(
                    measurement_id=payload["id"],
                    point_index=point["pointIndex"],
                    voltage_v=point["voltageV"],
                    current_a=point["currentA"],
                )
            )
        session.commit()


def list_measurements() -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(MeasurementRecord).order_by(MeasurementRecord.measured_at.desc())
        ).all()
        return [_serialize(session, row.id) for row in rows]


def get_measurement(measurement_id: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(MeasurementRecord, measurement_id)
        if row is None:
            return None
        return _serialize(session, measurement_id)


def count_unsynced() -> int:
    with SessionLocal() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(MeasurementRecord)
                .where(MeasurementRecord.sync_status != "synced")
            )
            or 0
        )


def mark_synced(ids: list[str]) -> None:
    with SessionLocal() as session:
        for measurement_id in ids:
            row = session.get(MeasurementRecord, measurement_id)
            if row:
                row.sync_status = "synced"
        session.commit()


def set_sync_state(key: str, value: str) -> None:
    with SessionLocal() as session:
        row = session.get(SyncStateRecord, key)
        if row is None:
            row = SyncStateRecord(key=key, value=value)
            session.add(row)
        else:
            row.value = value
        session.commit()


def get_sync_state(key: str, default: str = "") -> str:
    with SessionLocal() as session:
        row = session.get(SyncStateRecord, key)
        return row.value if row else default


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime:
    if not value:
        from datetime import timezone
        return datetime.now(timezone.utc)
    # ISO format (with or without timezone)
    value = value.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt.replace("%z", "")).replace()
        except ValueError:
            continue
    from datetime import timezone
    return datetime.now(timezone.utc)


def _serialize(session, measurement_id: str) -> dict:
    row = session.get(MeasurementRecord, measurement_id)
    points = session.scalars(
        select(CurvePointRecord)
        .where(CurvePointRecord.measurement_id == measurement_id)
        .order_by(CurvePointRecord.point_index)
    ).all()
    return {
        "id": row.id,
        "externalMeasurementKey": row.external_measurement_key,
        "measuredAt": row.measured_at.isoformat(),
        "customer": row.customer,
        "installation": row.installation,
        "stringNo": row.string_no,
        "moduleType": row.module_type,
        "moduleReference": row.module_reference,
        "modulesSeries": row.modules_series,
        "modulesParallel": row.modules_parallel,
        "nominalPowerW": row.nominal_power_w,
        "ppkWp": row.ppk_wp,
        "rsOhm": row.rs_ohm,
        "rpOhm": row.rp_ohm,
        "vocV": row.voc_v,
        "iscA": row.isc_a,
        "vpmaxV": row.vpmax_v,
        "ipmaxA": row.ipmax_a,
        "ffPercent": row.ff_percent,
        "sweepDurationMs": row.sweep_duration_ms,
        "irradianceWM2": row.irradiance_w_m2,
        "sensorTempC": row.sensor_temp_c,
        "moduleTempC": row.module_temp_c,
        "irradianceSensorType": row.irradiance_sensor_type,
        "irradianceSensorSerial": row.irradiance_sensor_serial,
        "importSource": row.import_source,
        "syncStatus": row.sync_status,
        "notes": row.notes,
        "rawPayloadJson": row.raw_payload_json,
        "curvePoints": [
            {
                "pointIndex": p.point_index,
                "voltageV": p.voltage_v,
                "currentA": p.current_a,
            }
            for p in points
        ],
    }


def create_site(site_name: str, customer: str | None = None, notes: str | None = None) -> dict:
    with SessionLocal() as session:
        existing = session.scalar(
            select(SiteCatalogRecord).where(SiteCatalogRecord.site_name == site_name)
        )
        if existing is None:
            existing = SiteCatalogRecord(site_name=site_name, customer=customer, notes=notes)
            session.add(existing)
        else:
            existing.customer = customer or existing.customer
            existing.notes = notes if notes is not None else existing.notes
        session.commit()
        session.refresh(existing)
        return {
            "id": existing.id,
            "siteName": existing.site_name,
            "customer": existing.customer,
            "notes": existing.notes,
        }


def list_sites() -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(SiteCatalogRecord).order_by(SiteCatalogRecord.site_name.asc())
        ).all()
        return [
            {"id": r.id, "siteName": r.site_name, "customer": r.customer, "notes": r.notes}
            for r in rows
        ]


def create_part(
    part_name: str,
    site_name: str | None = None,
    module_part_number: str | None = None,
    notes: str | None = None,
) -> dict:
    with SessionLocal() as session:
        existing = session.scalar(
            select(PartCatalogRecord).where(
                PartCatalogRecord.part_name == part_name,
                PartCatalogRecord.site_name == site_name,
            )
        )
        if existing is None:
            existing = PartCatalogRecord(
                part_name=part_name,
                site_name=site_name,
                module_part_number=module_part_number,
                notes=notes,
            )
            session.add(existing)
        else:
            existing.module_part_number = module_part_number or existing.module_part_number
            existing.notes = notes if notes is not None else existing.notes
        session.commit()
        session.refresh(existing)
        return {
            "id": existing.id,
            "siteName": existing.site_name,
            "partName": existing.part_name,
            "modulePartNumber": existing.module_part_number,
            "notes": existing.notes,
        }


def list_parts(site_name: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        stmt = select(PartCatalogRecord)
        if site_name:
            stmt = stmt.where(PartCatalogRecord.site_name == site_name)
        rows = session.scalars(stmt.order_by(PartCatalogRecord.site_name.asc(), PartCatalogRecord.part_name.asc())).all()
        return [
            {
                "id": r.id,
                "siteName": r.site_name,
                "partName": r.part_name,
                "modulePartNumber": r.module_part_number,
                "notes": r.notes,
            }
            for r in rows
        ]


def set_active_binding(
    site_name: str | None = None,
    part_name: str | None = None,
    customer: str | None = None,
    module_part_number: str | None = None,
) -> dict:
    set_sync_state("active_site_name", site_name or "")
    set_sync_state("active_part_name", part_name or "")
    set_sync_state("active_customer", customer or "")
    set_sync_state("active_module_part_number", module_part_number or "")
    return get_active_binding()


def get_active_binding() -> dict:
    return {
        "siteName": get_sync_state("active_site_name", "") or None,
        "partName": get_sync_state("active_part_name", "") or None,
        "customer": get_sync_state("active_customer", "") or None,
        "modulePartNumber": get_sync_state("active_module_part_number", "") or None,
        "applyToIncomingMeasurements": True,
        "writeToDeviceRequested": False,
    }


def create_module(
    module_part_number: str,
    manufacturer: str | None = None,
    technology: str | None = None,
    nominal_power_w: float | None = None,
    notes: str | None = None,
) -> dict:
    with SessionLocal() as session:
        existing = session.scalar(
            select(ModuleCatalogRecord).where(
                ModuleCatalogRecord.module_part_number == module_part_number
            )
        )
        if existing is None:
            existing = ModuleCatalogRecord(
                module_part_number=module_part_number,
                manufacturer=manufacturer,
                technology=technology,
                nominal_power_w=nominal_power_w,
                notes=notes,
            )
            session.add(existing)
        else:
            existing.manufacturer = manufacturer or existing.manufacturer
            existing.technology = technology or existing.technology
            existing.nominal_power_w = nominal_power_w if nominal_power_w is not None else existing.nominal_power_w
            existing.notes = notes if notes is not None else existing.notes
        session.commit()
        session.refresh(existing)
        return {
            "id": existing.id,
            "modulePartNumber": existing.module_part_number,
            "manufacturer": existing.manufacturer,
            "technology": existing.technology,
            "nominalPowerW": existing.nominal_power_w,
            "notes": existing.notes,
        }


def list_modules() -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(ModuleCatalogRecord).order_by(ModuleCatalogRecord.module_part_number.asc())
        ).all()
        return [
            {
                "id": r.id,
                "modulePartNumber": r.module_part_number,
                "manufacturer": r.manufacturer,
                "technology": r.technology,
                "nominalPowerW": r.nominal_power_w,
                "notes": r.notes,
            }
            for r in rows
        ]
