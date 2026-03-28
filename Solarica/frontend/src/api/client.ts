const API_BASE = import.meta.env.VITE_API_URL || "/api";
const DEFAULT_BRIDGE_URL = import.meta.env.VITE_BRIDGE_URL || "http://127.0.0.1:8765";

/** Fetch wrapper that attaches the stored Bearer token to every request. */
function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem("solarica.token");
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(input, { ...init, headers });
}

export interface IVPoint {
  voltage: number;
  current: number;
}

export interface Measurement {
  id: number;
  measured_at: string | null;
  device_serial: string | null;
  sensor_serial: string | null;
  customer: string | null;
  module_type: string | null;
  remarks: string | null;
  ppk: number | null;
  rs: number | null;
  rp: number | null;
  voc: number | null;
  isc: number | null;
  vpmax: number | null;
  ipmax: number | null;
  pmax: number | null;
  fill_factor: number | null;
  eeff: number | null;
  tmod: number | null;
  tcell: number | null;
  source_file: string | null;
  created_at: string;
}

export interface MeasurementDetail extends Measurement {
  iv_curve: IVPoint[];
}

export interface SummaryStats {
  total_measurements: number;
  first_measurement: string | null;
  last_measurement: string | null;
  avg_peak_power_kw: number | null;
  avg_irradiance_wm2: number | null;
  unique_customers: number;
}

export interface SiteSummary {
  id: number;
  site_code: string;
  site_name: string;
  layout_name: string | null;
  country: string | null;
  region: string | null;
  module_type: string | null;
  module_count: number | null;
  plant_capacity_mw: number | null;
  string_count: number;
}

export interface SiteDetail extends SiteSummary {
  source_document: string | null;
  latitude: number | null;
  longitude: number | null;
  notes: string | null;
}

export interface SiteString {
  id: number;
  string_code: string;
  section_no: number;
  block_no: number;
  string_no: number;
}

export interface SiteDesignImportResult {
  success: boolean;
  site_id: number;
  site_code: string;
  site_name: string;
  source_document: string;
  string_count: number;
  message: string;
}

export interface SiteDesignPreviewRow {
  row_id: number;
  raw_value: string;
  string_code: string | null;
  section_no: number | null;
  block_no: number | null;
  string_no: number | null;
  is_valid: boolean;
  invalid_reason: string | null;
}

export interface SiteDesignPreviewMetadata {
  project: string;
  location: string | null;
  total_modules: number | null;
}

export interface SiteDesignPreviewResult {
  metadata: SiteDesignPreviewMetadata;
  site_code: string;
  site_name: string;
  layout_name: string;
  source_document: string;
  country: string | null;
  region: string | null;
  latitude: number | null;
  longitude: number | null;
  plant_capacity_mw: number | null;
  module_type: string | null;
  module_count: number | null;
  notes: string;
  strings: Record<string, string[]>;
  anomalies: Record<string, string[]>;
  gaps: Record<string, string[]>;
  duplicates: string[];
  valid_count: number;
  invalid_count: number;
  has_errors: boolean;
  string_rows: SiteDesignPreviewRow[];
}

export interface ImportResult {
  success: boolean;
  measurement_id?: number;
  message: string;
  duplicate?: boolean;
  errors?: string[];
}

export interface MeasurementImportPayload {
  measured_at?: string | null;
  device_serial?: string | null;
  sensor_serial?: string | null;
  irradiance_sensor_serial?: string | null;
  customer?: string | null;
  module_type?: string | null;
  remarks?: string | null;
  ppk?: number | null;
  rs?: number | null;
  rp?: number | null;
  voc?: number | null;
  isc?: number | null;
  vpmax?: number | null;
  ipmax?: number | null;
  pmax?: number | null;
  fill_factor?: number | null;
  ff?: number | null;
  eeff?: number | null;
  tmod?: number | null;
  tcell?: number | null;
  source_file?: string | null;
  device_record_id?: string | null;
  sync_source?: string | null;
  iv_curve: IVPoint[];
}

export interface ImportBatchResult {
  success: boolean;
  total: number;
  imported: number;
  duplicates: number;
  failed: number;
  results: ImportResult[];
}

export interface BridgeStatus {
  status: "online" | "offline";
  bridge_version?: string;
  device_connected: boolean;
  device_mode?: string | null;
  requires_transfer_mode?: boolean;
  sample_mode?: boolean;
  last_sync_at?: string | null;
  message: string;
}

export interface BridgeSyncResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  message: string;
}

export interface BridgeJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  message: string;
  measurements: MeasurementImportPayload[];
  imported_count: number;
  duplicate_count: number;
  failed_count: number;
  started_at?: string | null;
  completed_at?: string | null;
}

async function parseJsonResponse<T>(res: Response, fallbackMessage: string): Promise<T> {
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg =
      data?.detail ||
      data?.message ||
      (Array.isArray(data?.detail) ? data.detail[0]?.msg : null) ||
      `${fallbackMessage} (${res.status})`;
    throw new Error(msg);
  }
  return data as T;
}

function getBridgeBaseUrl(bridgeUrl?: string): string {
  return (bridgeUrl || DEFAULT_BRIDGE_URL).replace(/\/$/, "");
}

export async function fetchMeasurements(params?: {
  skip?: number;
  limit?: number;
  customer?: string;
  module_type?: string;
  date_from?: string;
  date_to?: string;
  site_id?: number;
}): Promise<Measurement[]> {
  const sp = new URLSearchParams();
  if (params?.skip != null) sp.set("skip", String(params.skip));
  if (params?.limit != null) sp.set("limit", String(params.limit));
  if (params?.customer) sp.set("customer", params.customer);
  if (params?.module_type) sp.set("module_type", params.module_type);
  if (params?.date_from) sp.set("date_from", params.date_from);
  if (params?.date_to) sp.set("date_to", params.date_to);
  if (params?.site_id != null) sp.set("site_id", String(params.site_id));
  const res = await authedFetch(`${API_BASE}/measurements?${sp}`);
  if (!res.ok) throw new Error("Failed to fetch measurements");
  return res.json();
}

export async function fetchMeasurement(id: number): Promise<MeasurementDetail> {
  const res = await authedFetch(`${API_BASE}/measurements/${id}`);
  if (!res.ok) throw new Error("Failed to fetch measurement");
  return res.json();
}

export async function fetchSummaryStats(siteId?: number): Promise<SummaryStats> {
  const sp = new URLSearchParams();
  if (siteId != null) sp.set("site_id", String(siteId));
  const res = await authedFetch(`${API_BASE}/measurements/stats/summary?${sp}`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchSites(): Promise<SiteSummary[]> {
  const res = await authedFetch(`${API_BASE}/sites`);
  if (!res.ok) throw new Error("Failed to fetch sites");
  return res.json();
}

export async function fetchSite(siteId: number): Promise<SiteDetail> {
  const res = await authedFetch(`${API_BASE}/sites/${siteId}`);
  if (!res.ok) throw new Error("Failed to fetch site");
  return res.json();
}

export async function fetchSiteStrings(
  siteId: number,
  params?: { search?: string; skip?: number; limit?: number },
): Promise<SiteString[]> {
  const sp = new URLSearchParams();
  if (params?.search) sp.set("search", params.search);
  if (params?.skip != null) sp.set("skip", String(params.skip));
  if (params?.limit != null) sp.set("limit", String(params.limit));
  const res = await authedFetch(`${API_BASE}/sites/${siteId}/strings?${sp}`);
  if (!res.ok) throw new Error("Failed to fetch site strings");
  return res.json();
}

export interface PdfRegion {
  x: number;
  y: number;
  w: number;
  h: number;
}

export async function importSiteDesignPdf(
  files: File[],
  regions?: PdfRegion[],
): Promise<SiteDesignImportResult> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (regions && regions.length > 0) form.append("regions", JSON.stringify(regions));
  const res = await authedFetch(`${API_BASE}/sites/import-design-pdf`, {
    method: "POST",
    body: form,
  });
  return parseJsonResponse<SiteDesignImportResult>(res, "Design PDF import failed");
}

export async function previewSiteDesignPdf(
  files: File[],
  regions?: PdfRegion[],
): Promise<SiteDesignPreviewResult> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (regions && regions.length > 0) form.append("regions", JSON.stringify(regions));
  const res = await authedFetch(`${API_BASE}/sites/preview-design-pdf`, {
    method: "POST",
    body: form,
  });
  return parseJsonResponse<SiteDesignPreviewResult>(res, "Design PDF preview failed");
}

export async function uploadFile(file: File, siteId?: number): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  if (siteId != null) form.append("site_id", String(siteId));
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  const res = await authedFetch(`${API_BASE}/import/upload`, {
    method: "POST",
    body: form,
    signal: controller.signal,
  });
  clearTimeout(timeout);
  try {
    return await parseJsonResponse<ImportResult>(res, "Upload failed");
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : String(error),
    };
  }
}

export async function uploadMeasurementBatch(
  measurements: MeasurementImportPayload[],
  allowDuplicates = false,
): Promise<ImportBatchResult> {
  const res = await authedFetch(`${API_BASE}/import/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ measurements, allow_duplicates: allowDuplicates }),
  });
  return parseJsonResponse<ImportBatchResult>(res, "Batch import failed");
}

export async function fetchBridgeStatus(bridgeUrl?: string): Promise<BridgeStatus> {
  const baseUrl = getBridgeBaseUrl(bridgeUrl);
  try {
    const res = await fetch(`${baseUrl}/status`);
    return await parseJsonResponse<BridgeStatus>(res, "Bridge status failed");
  } catch (error) {
    return {
      status: "offline",
      device_connected: false,
      requires_transfer_mode: true,
      message: error instanceof Error ? error.message : "Bridge unavailable",
    };
  }
}

export async function startDeviceImport(bridgeUrl?: string): Promise<BridgeSyncResponse> {
  const baseUrl = getBridgeBaseUrl(bridgeUrl);
  const res = await fetch(`${baseUrl}/sync`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  return parseJsonResponse<BridgeSyncResponse>(res, "Bridge sync failed");
}

export async function getImportProgress(jobId: string, bridgeUrl?: string): Promise<BridgeJob> {
  const baseUrl = getBridgeBaseUrl(bridgeUrl);
  const res = await fetch(`${baseUrl}/jobs/${jobId}`);
  return parseJsonResponse<BridgeJob>(res, "Bridge job failed");
}

export interface StringPattern {
  id: number;
  pattern_code: string;
  pattern_name: string;
  example_value: string | null;
  level_count: number;
  levels: string[];
  is_active: boolean;
}

export interface ScanIssue {
  issue_type: string;
  severity: "info" | "warning" | "error" | "blocker";
  entity_type: string;
  entity_key: string;
  message: string;
  details: Record<string, unknown>;
}

export interface InverterSummary {
  inverter_key: string;
  expected_strings: number;
  found_valid_strings: number;
  duplicate_count: number;
  invalid_name_count: number;
  missing_sequence: number[];
  status: "match" | "mismatch" | "manual_review_required";
}

export interface SectionSummary {
  section_code: string;
  found_inverters: number;
  found_valid_strings: number;
  inverter_summaries: InverterSummary[];
}

export interface ScanResult {
  site_id: number;
  run_id: number;
  pattern_code_used: string;
  fast_detect: { configured_pattern_code: string; detected_pattern_code: string; confidence: number; token_counts: Record<string, number> };
  summary: { total_valid_strings: number; total_invalid_string_names: number; total_duplicates: number; total_inverters_found: number };
  design_comparison: { expected_total_strings: number; found_total_valid_strings: number; expected_inverter_groups: number; found_inverter_groups: number; matches_design: boolean };
  sections: SectionSummary[];
  invalid_string_names: Array<{ raw_text: string; normalized_text: string; classification: string; reason: string | null }>;
  issues: ScanIssue[];
}

export async function listStringPatterns(): Promise<StringPattern[]> {
  const res = await authedFetch(`${API_BASE}/string-patterns`);
  if (!res.ok) throw new Error("Failed to load patterns");
  return res.json();
}

export async function getSitePattern(siteId: number): Promise<{ site_id: number; pattern: StringPattern } | null> {
  const res = await authedFetch(`${API_BASE}/sites/${siteId}/string-pattern`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to load site pattern");
  return res.json();
}

export async function setSitePattern(siteId: number, patternId: number): Promise<{ site_id: number; pattern: StringPattern }> {
  const res = await authedFetch(`${API_BASE}/sites/${siteId}/string-pattern`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern_id: patternId }),
  });
  if (!res.ok) throw new Error("Failed to set pattern");
  return res.json();
}

export async function scanStrings(
  siteId: number,
  files: File[],
  regions?: PdfRegion[],
  options?: { saveRun?: boolean; compareToDesign?: boolean },
): Promise<ScanResult> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  if (regions && regions.length > 0) {
    // Convert normalized (0-1) to percentage (0-100) for the scan API
    const rects = regions.map((r, i) => ({
      section_code: String(i + 1),
      x_pct: r.x * 100,
      y_pct: r.y * 100,
      w_pct: r.w * 100,
      h_pct: r.h * 100,
    }));
    form.append("regions", JSON.stringify(rects));
  }
  if (options?.saveRun !== undefined) form.append("save_run", String(options.saveRun));
  if (options?.compareToDesign !== undefined) form.append("compare_to_design", String(options.compareToDesign));

  const res = await authedFetch(`${API_BASE}/sites/${siteId}/scan-strings`, {
    method: "POST",
    body: form,
  });
  return parseJsonResponse<ScanResult>(res, "String scan failed");
}

export const api = {
  listMeasurements: (params?: Parameters<typeof fetchMeasurements>[0]) =>
    fetchMeasurements(params),
  getMeasurement: fetchMeasurement,
  getSummary: (siteId?: number): Promise<SummaryStats> => fetchSummaryStats(siteId),
  listSites: fetchSites,
  getSite: fetchSite,
  listSiteStrings: fetchSiteStrings,
  previewSiteDesignPdf,
  importSiteDesignPdf,
  uploadFile,
  uploadMeasurementBatch,
  getBridgeStatus: fetchBridgeStatus,
  startDeviceImport,
  getImportProgress,
  listStringPatterns,
  getSitePattern,
  setSitePattern,
  scanStrings,
};
