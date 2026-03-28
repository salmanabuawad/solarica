from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings

settings.local_db_file.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{settings.local_db_file}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class MeasurementRecord(Base):
    __tablename__ = "measurements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
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
    import_source: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_status: Mapped[str] = mapped_column(String, default="unsynced")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CurvePointRecord(Base):
    __tablename__ = "curve_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    measurement_id: Mapped[str] = mapped_column(String)
    point_index: Mapped[int] = mapped_column(Integer)
    voltage_v: Mapped[float] = mapped_column(Float)
    current_a: Mapped[float] = mapped_column(Float)


class SyncStateRecord(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)


Base.metadata.create_all(engine)
