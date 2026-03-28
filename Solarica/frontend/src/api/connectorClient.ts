/**
 * Solarica Connector API client.
 *
 * Works with both the Python connector and the .NET connector — they expose
 * the same REST contract on http://127.0.0.1:8765 (configurable).
 *
 * The web app never needs to know which runtime is active; the /health
 * `runtime` field identifies it for display purposes only.
 */

const DEFAULT_CONNECTOR_URL =
  window.localStorage.getItem("solarica.connectorUrl") ||
  (import.meta.env.VITE_CONNECTOR_URL as string | undefined) ||
  "http://127.0.0.1:8765";

// ---------------------------------------------------------------------------
// Types (mirror of openapi.yaml schemas)
// ---------------------------------------------------------------------------

export type ConnectorRuntime = "python" | "dotnet" | "unknown";

export interface ConnectorHealth {
  ok: boolean;
  version: string;
  runtime: ConnectorRuntime;
}

export interface ConnectorPortInfo {
  name: string;
  description: string;
}

export interface ConnectorPortsResponse {
  items: ConnectorPortInfo[];
}

export interface ConnectorDeviceStatus {
  connected: boolean;
  mode: "mock" | "serial" | "vendor_export" | string;
  port: string | null;
  deviceModel: string | null;
  deviceSerial: string | null;
  firmwareVersion: string | null;
  transferModeRequired: boolean;
  transferModeDetected: boolean;
  lastError: string | null;
}

export interface ConnectorCurvePoint {
  pointIndex: number;
  voltageV: number;
  currentA: number;
}

export interface ConnectorMeasurement {
  id: string;
  externalMeasurementKey: string | null;
  measuredAt: string;
  customer: string | null;
  installation: string | null;
  stringNo: string | null;
  moduleType: string | null;
  moduleReference: string | null;
  modulesSeries: number | null;
  modulesParallel: number | null;
  nominalPowerW: number | null;
  ppkWp: number | null;
  rsOhm: number | null;
  rpOhm: number | null;
  vocV: number | null;
  iscA: number | null;
  vpmaxV: number | null;
  ipmaxA: number | null;
  ffPercent: number | null;
  sweepDurationMs: number | null;
  irradianceWM2: number | null;
  sensorTempC: number | null;
  moduleTempC: number | null;
  irradianceSensorType: string | null;
  irradianceSensorSerial: string | null;
  importSource: string | null;
  syncStatus: "unsynced" | "synced" | "error";
  notes: string | null;
  curvePoints: ConnectorCurvePoint[];
}

export interface ConnectorMeasurementsResponse {
  items: ConnectorMeasurement[];
}

export interface ConnectorImportStartResult {
  ok: boolean;
  imported: number;
}

export interface ConnectorImportStatus {
  state: "idle" | "running" | "completed" | "failed" | string;
  lastImportedCount: number;
  unsyncedCount: number;
}

export interface ConnectorSyncResult {
  uploaded: number;
  error?: string | null;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function base(url?: string): string {
  return (url || DEFAULT_CONNECTOR_URL).replace(/\/$/, "");
}

async function get<T>(path: string, url?: string): Promise<T> {
  const res = await fetch(`${base(url)}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? body?.message ?? `HTTP ${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown, url?: string): Promise<T> {
  const res = await fetch(`${base(url)}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail ?? data?.message ?? `HTTP ${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Health / detection
// ---------------------------------------------------------------------------

/**
 * Try to reach the connector. Returns null if offline or unreachable.
 */
export async function detectConnector(url?: string): Promise<ConnectorHealth | null> {
  try {
    const res = await fetch(`${base(url)}/health`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return null;
    return res.json() as Promise<ConnectorHealth>;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Device
// ---------------------------------------------------------------------------

export function getDeviceStatus(url?: string): Promise<ConnectorDeviceStatus> {
  return get("/api/device/status", url);
}

export function listPorts(url?: string): Promise<ConnectorPortsResponse> {
  return get("/api/device/ports", url);
}

export function connectPort(port: string, url?: string): Promise<ConnectorDeviceStatus> {
  return post("/api/device/connect", { port }, url);
}

export function disconnectPort(url?: string): Promise<{ ok: boolean }> {
  return post("/api/device/disconnect", undefined, url);
}

export interface ConnectorFileInfo {
  name: string;
  size: number;
  modified: string;
  type: string;
  stringNo?: string | null;
  customer?: string | null;
  moduleType?: string | null;
  measuredAt?: string | null;
  moduleCount?: number | null;
  externalMeasurementKey?: string | null;
}

export interface ConnectorFilesResponse {
  items: ConnectorFileInfo[];
}

export function listConnectorFiles(url?: string): Promise<ConnectorFilesResponse> {
  return get("/api/device/files", url);
}

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

export function startImport(url?: string): Promise<ConnectorImportStartResult> {
  return post("/api/import/start", undefined, url);
}

export function getImportStatus(url?: string): Promise<ConnectorImportStatus> {
  return get("/api/import/status", url);
}

// ---------------------------------------------------------------------------
// Measurements (local cache)
// ---------------------------------------------------------------------------

export function listConnectorMeasurements(url?: string): Promise<ConnectorMeasurementsResponse> {
  return get("/api/measurements", url);
}

export function getConnectorMeasurement(id: string, url?: string): Promise<ConnectorMeasurement> {
  return get(`/api/measurements/${encodeURIComponent(id)}`, url);
}

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------

export function syncUpload(url?: string): Promise<ConnectorSyncResult> {
  return post("/api/sync/upload", undefined, url);
}

// ---------------------------------------------------------------------------
// Export URLs (direct download links)
// ---------------------------------------------------------------------------

export function getExportCsvUrl(url?: string): string {
  return `${base(url)}/api/export/csv`;
}

export function getExportJsonUrl(url?: string): string {
  return `${base(url)}/api/export/json`;
}

// ---------------------------------------------------------------------------
// Persisted URL helpers
// ---------------------------------------------------------------------------

export function getSavedConnectorUrl(): string {
  return DEFAULT_CONNECTOR_URL;
}

export function saveConnectorUrl(url: string): void {
  window.localStorage.setItem("solarica.connectorUrl", url.trim());
}
