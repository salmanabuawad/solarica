from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Device(Base):
    __tablename__ = 'devices'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial_number: Mapped[str | None] = mapped_column(String, unique=True)
    model: Mapped[str | None] = mapped_column(String)
    firmware_version: Mapped[str | None] = mapped_column(String)
    calibration_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Measurement(Base):
    __tablename__ = 'measurements'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey('devices.id'), nullable=True)
    external_measurement_key: Mapped[str | None] = mapped_column(String, nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    customer: Mapped[str | None] = mapped_column(String, nullable=True)
    installation: Mapped[str | None] = mapped_column(String, nullable=True)
    string_no: Mapped[str | None] = mapped_column(String, nullable=True)
    module_type: Mapped[str | None] = mapped_column(String, nullable=True)
    module_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    modules_series: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modules_parallel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nominal_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    ppk_wp: Mapped[float | None] = mapped_column(Float, nullable=True)
    rs_ohm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rp_ohm: Mapped[float | None] = mapped_column(Float, nullable=True)
    voc_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    isc_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    vpmax_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    ipmax_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    ff_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    sweep_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    irradiance_w_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    sensor_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    module_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    irradiance_sensor_type: Mapped[str | None] = mapped_column(String, nullable=True)
    irradiance_sensor_serial: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    import_source: Mapped[str | None] = mapped_column(String, nullable=True)
    import_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_status: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class MeasurementCurvePoint(Base):
    __tablename__ = 'measurement_curve_points'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    measurement_id: Mapped[str] = mapped_column(ForeignKey('measurements.id'))
    point_index: Mapped[int] = mapped_column(Integer)
    voltage_v: Mapped[float] = mapped_column(Float)
    current_a: Mapped[float] = mapped_column(Float)

class SyncLog(Base):
    __tablename__ = 'sync_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    measurement_id: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
