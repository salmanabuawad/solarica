from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class PortInfo(BaseModel):
    name: str
    description: str


class PortsResponse(BaseModel):
    items: list[PortInfo]


class ConnectRequest(BaseModel):
    port: str


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
    syncStatus: Literal["unsynced", "synced", "error"] = "unsynced"
    notes: str | None = None
    rawPayloadJson: dict[str, Any] | None = None
    curvePoints: list[CurvePoint] = []


class MeasurementsResponse(BaseModel):
    items: list[Measurement]


class ImportStartResult(BaseModel):
    ok: bool
    imported: int


class ImportStatus(BaseModel):
    state: str
    lastImportedCount: int = 0
    unsyncedCount: int = 0
    watcherActive: bool = False


class SyncUploadResult(BaseModel):
    uploaded: int
    error: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    version: str
    runtime: Literal["python", "dotnet", "unknown"] = "python"


class AutoConnectResponse(BaseModel):
    ok: bool
    connected: bool
    port: str | None = None
    message: str | None = None
    status: DeviceStatus | None = None

class SiteCatalogItem(BaseModel):
    id: int | None = None
    siteName: str
    customer: str | None = None
    notes: str | None = None


class PartCatalogItem(BaseModel):
    id: int | None = None
    siteName: str | None = None
    partName: str
    modulePartNumber: str | None = None
    notes: str | None = None


class SiteCatalogResponse(BaseModel):
    items: list[SiteCatalogItem]


class PartCatalogResponse(BaseModel):
    items: list[PartCatalogItem]


class CreateSiteRequest(BaseModel):
    siteName: str
    customer: str | None = None
    notes: str | None = None


class CreatePartRequest(BaseModel):
    siteName: str | None = None
    partName: str
    modulePartNumber: str | None = None
    notes: str | None = None


class SessionBinding(BaseModel):
    siteName: str | None = None
    partName: str | None = None
    customer: str | None = None
    modulePartNumber: str | None = None
    applyToIncomingMeasurements: bool = True
    writeToDeviceRequested: bool = False


class SessionResponse(BaseModel):
    ok: bool
    binding: SessionBinding
    message: str | None = None

class DeviceDownloadSummary(BaseModel):
    ok: bool
    downloadedCount: int
    savedRawCount: int
    exportedJsonPath: str | None = None
    exportedCsvPath: str | None = None
    message: str | None = None

class ModuleCatalogItem(BaseModel):
    id: int | None = None
    modulePartNumber: str
    manufacturer: str | None = None
    technology: str | None = None
    nominalPowerW: float | None = None
    notes: str | None = None


class ModuleCatalogResponse(BaseModel):
    items: list[ModuleCatalogItem]


class CreateModuleRequest(BaseModel):
    modulePartNumber: str
    manufacturer: str | None = None
    technology: str | None = None
    nominalPowerW: float | None = None
    notes: str | None = None
