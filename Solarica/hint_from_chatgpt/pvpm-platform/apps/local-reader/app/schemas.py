from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class PortInfo(BaseModel):
    name: str
    description: str

class DeviceStatus(BaseModel):
    connected: bool
    mode: str
    port: str | None = None
    deviceModel: str | None = None
    deviceSerial: str | None = None
    firmwareVersion: str | None = None
    transferModeRequired: bool = True
    transferModeDetected: bool = False
    lastError: str | None = None

class CurvePoint(BaseModel):
    pointIndex: int
    voltageV: float
    currentA: float

class Measurement(BaseModel):
    id: str
    externalMeasurementKey: str | None = None
    measuredAt: datetime
    customer: str | None = None
    installation: str | None = None
    stringNo: str | None = None
    moduleType: str | None = None
    moduleReference: str | None = None
    modulesSeries: int | None = None
    modulesParallel: int | None = None
    nominalPowerW: float | None = None
    ppkWp: float | None = None
    rsOhm: float | None = None
    rpOhm: float | None = None
    vocV: float | None = None
    iscA: float | None = None
    vpmaxV: float | None = None
    ipmaxA: float | None = None
    ffPercent: float | None = None
    sweepDurationMs: float | None = None
    irradianceWM2: float | None = None
    sensorTempC: float | None = None
    moduleTempC: float | None = None
    irradianceSensorType: str | None = None
    irradianceSensorSerial: str | None = None
    importSource: str | None = None
    syncStatus: str = 'unsynced'
    notes: str | None = None
    rawPayloadJson: dict[str, Any] | None = None
    curvePoints: list[CurvePoint] = []

class MeasurementsResponse(BaseModel):
    items: list[Measurement]

class PortsResponse(BaseModel):
    items: list[PortInfo]

class ConnectRequest(BaseModel):
    port: str

class ImportStatus(BaseModel):
    state: str
    lastImportedCount: int = 0
    unsyncedCount: int = 0
