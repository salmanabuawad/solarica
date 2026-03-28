export type SyncStatus = "unsynced" | "synced" | "failed";

export interface DeviceStatus {
  connected: boolean;
  mode: "mock" | "serial" | "vendor_export";
  port: string | null;
  deviceModel: string | null;
  deviceSerial: string | null;
  firmwareVersion: string | null;
  transferModeRequired: boolean;
  transferModeDetected: boolean;
  lastError: string | null;
}

export interface MeasurementCurvePoint {
  pointIndex: number;
  voltageV: number;
  currentA: number;
}

export interface Measurement {
  id: string;
  externalMeasurementKey?: string | null;
  measuredAt: string;
  customer?: string | null;
  installation?: string | null;
  stringNo?: string | null;
  moduleType?: string | null;
  moduleReference?: string | null;
  modulesSeries?: number | null;
  modulesParallel?: number | null;
  nominalPowerW?: number | null;
  ppkWp?: number | null;
  rsOhm?: number | null;
  rpOhm?: number | null;
  vocV?: number | null;
  iscA?: number | null;
  vpmaxV?: number | null;
  ipmaxA?: number | null;
  ffPercent?: number | null;
  sweepDurationMs?: number | null;
  irradianceWM2?: number | null;
  sensorTempC?: number | null;
  moduleTempC?: number | null;
  irradianceSensorType?: string | null;
  irradianceSensorSerial?: string | null;
  importSource?: string | null;
  syncStatus?: SyncStatus;
  notes?: string | null;
  rawPayloadJson?: unknown;
  curvePoints?: MeasurementCurvePoint[];
}
