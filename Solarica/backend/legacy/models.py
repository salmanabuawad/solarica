"""SQLAlchemy models for IVCurve."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# --- Pydantic schemas (API) ---
class IVPoint(BaseModel):
    voltage: float
    current: float


class MeasurementCreate(BaseModel):
    measured_at: Optional[datetime] = None
    source_file: Optional[str] = None
    device_serial: Optional[str] = None
    irradiance_sensor_type: Optional[str] = None
    irradiance_sensor_serial: Optional[str] = None
    ppk: Optional[float] = None
    rs: Optional[float] = None
    rp: Optional[float] = None
    voc: Optional[float] = None
    isc: Optional[float] = None
    vpmax: Optional[float] = None
    ipmax: Optional[float] = None
    pmax: Optional[float] = None
    ff: Optional[float] = None
    tmod: Optional[float] = None
    eeff: Optional[float] = None
    ppk_deviation: Optional[float] = None
    rs_deviation: Optional[float] = None
    rp_deviation: Optional[float] = None
    remarks: Optional[str] = None
    iv_curve: Optional[list[IVPoint]] = None


class MeasurementResponse(BaseModel):
    id: int
    created_at: datetime
    measured_at: Optional[datetime]
    source_file: Optional[str]
    device_serial: Optional[str]
    ppk: Optional[float]
    rs: Optional[float]
    rp: Optional[float]
    voc: Optional[float]
    isc: Optional[float]
    vpmax: Optional[float]
    ipmax: Optional[float]
    pmax: Optional[float]
    ff: Optional[float]
    tmod: Optional[float]
    eeff: Optional[float]
    remarks: Optional[str]

    class Config:
        from_attributes = True


class MeasurementDetail(MeasurementResponse):
    iv_curve: list[IVPoint] = []
