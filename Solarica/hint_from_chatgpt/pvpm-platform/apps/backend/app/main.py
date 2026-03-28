from __future__ import annotations
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from .database import Base, engine, SessionLocal
from .models import Device, Measurement, MeasurementCurvePoint, SyncLog
from .schemas import BatchImportPayload

app = FastAPI(title='PVPM Backend', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
Base.metadata.create_all(engine)

@app.get('/health')
def health():
    return {'ok': True}

@app.post('/api/v1/import/batch')
def import_batch(payload: BatchImportPayload):
    with SessionLocal() as session:
        device_payload = payload.device or {}
        serial_number = device_payload.get('deviceSerial') or 'unknown-device'
        device = session.scalar(select(Device).where(Device.serial_number == serial_number))
        if device is None:
            device = Device(
                serial_number=serial_number,
                model=device_payload.get('deviceModel'),
                firmware_version=device_payload.get('firmwareVersion'),
                last_seen_at=datetime.utcnow(),
            )
            session.add(device)
            session.flush()
        for item in payload.measurements:
            measurement = session.get(Measurement, item.id)
            if measurement is None:
                measurement = Measurement(id=item.id, measured_at=item.measuredAt)
                session.add(measurement)
            measurement.device_id = device.id
            measurement.external_measurement_key = item.externalMeasurementKey
            measurement.measured_at = item.measuredAt
            measurement.customer = item.customer
            measurement.installation = item.installation
            measurement.string_no = item.stringNo
            measurement.module_type = item.moduleType
            measurement.module_reference = item.moduleReference
            measurement.modules_series = item.modulesSeries
            measurement.modules_parallel = item.modulesParallel
            measurement.nominal_power_w = item.nominalPowerW
            measurement.ppk_wp = item.ppkWp
            measurement.rs_ohm = item.rsOhm
            measurement.rp_ohm = item.rpOhm
            measurement.voc_v = item.vocV
            measurement.isc_a = item.iscA
            measurement.vpmax_v = item.vpmaxV
            measurement.ipmax_a = item.ipmaxA
            measurement.ff_percent = item.ffPercent
            measurement.sweep_duration_ms = item.sweepDurationMs
            measurement.irradiance_w_m2 = item.irradianceWM2
            measurement.sensor_temp_c = item.sensorTempC
            measurement.module_temp_c = item.moduleTempC
            measurement.irradiance_sensor_type = item.irradianceSensorType
            measurement.irradiance_sensor_serial = item.irradianceSensorSerial
            measurement.raw_payload_json = item.rawPayloadJson
            measurement.import_source = item.importSource
            measurement.sync_status = 'synced'
            measurement.notes = item.notes
            session.query(MeasurementCurvePoint).filter(MeasurementCurvePoint.measurement_id == item.id).delete()
            for point in item.curvePoints:
                session.add(MeasurementCurvePoint(
                    measurement_id=item.id,
                    point_index=point.pointIndex,
                    voltage_v=point.voltageV,
                    current_a=point.currentA,
                ))
            session.add(SyncLog(
                measurement_id=item.id,
                direction='reader_to_backend',
                status='success',
                payload_json={'measurementId': item.id},
            ))
        session.commit()
    return {'imported': len(payload.measurements)}

@app.get('/api/v1/measurements')
def list_measurements():
    with SessionLocal() as session:
        items = session.scalars(select(Measurement).order_by(Measurement.measured_at.desc())).all()
        return {'items': [
            {
                'id': item.id,
                'measuredAt': item.measured_at.isoformat(),
                'customer': item.customer,
                'installation': item.installation,
                'moduleType': item.module_type,
                'ppkWp': item.ppk_wp,
                'vocV': item.voc_v,
                'iscA': item.isc_a,
                'irradianceWM2': item.irradiance_w_m2,
                'syncStatus': item.sync_status,
            }
            for item in items
        ]}
