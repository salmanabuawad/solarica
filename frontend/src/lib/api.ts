import axios from 'axios';
import type {
  Branding,
  DeviceCVE,
  DeviceInventoryItem,
  DeviceInventorySummary,
  DeviceSite,
  DeviceSpec,
  LowStockItem,
  Material,
  MaterialCreate,
  MaterialIssue,
  MaterialIssueCreate,
  MaterialIssueDetail,
  MaintenanceTask,
  Measurement,
  MobileHomeResponse,
  MobileSummary,
  Project,
  ProjectCreate,
  ProjectPhaseUpdate,
  NamingPattern,
  TaskApproval,
  TaskCreate,
  TaskMessage,
  TaskTestResult,
  User,
  ValidationRun,
  VarianceFlag,
  Warehouse,
  WarehouseStock,
} from './types';

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// ── JWT expiry helper ────────────────────────────────────────────
/** Decode the JWT payload (no signature check) and return true if not expired. */
function isTokenValid(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

/** Clear all stored session data and dispatch a custom event so AppContext reacts. */
export function clearSession(): void {
  localStorage.removeItem('solarica_token');
  localStorage.removeItem('solarica_user');
  localStorage.removeItem('solarica_session');
  sessionStorage.removeItem('solarica_token');
  sessionStorage.removeItem('solarica_user');
  window.dispatchEvent(new CustomEvent('solarica:logout'));
}

// Attach auth token to every request when available
client.interceptors.request.use((config) => {
  // Try localStorage first (persists across page reloads), fall back to sessionStorage
  const stored = localStorage.getItem('solarica_user') || sessionStorage.getItem('solarica_user');
  if (stored) {
    try {
      const user = JSON.parse(stored) as User;
      config.headers.set('X-User', user.username);
      config.headers.set('X-Role', user.role);
    } catch {
      // ignore malformed session data
    }
  }
  // Bearer token — always from localStorage so it survives page reloads
  const token = localStorage.getItem('solarica_token') || sessionStorage.getItem('solarica_token');
  if (token) {
    if (isTokenValid(token)) {
      config.headers.set('Authorization', `Bearer ${token}`);
    } else {
      // Token is expired — clear session before the request fires so the
      // response interceptor doesn't need to race with in-flight calls.
      clearSession();
    }
  }
  return config;
});

// Auto-logout on 401 responses (expired / revoked token reaching a protected endpoint)
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      clearSession();
    }
    return Promise.reject(error);
  },
);

// ── Auth ────────────────────────────────────────────────────────

export async function login(username: string, password: string): Promise<{ user: User; token: string }> {
  const { data } = await client.post<{ access_token: string; user: User }>('/auth/login', { username, password });
  return { user: data.user, token: data.access_token };
}

export async function listUsers(): Promise<User[]> {
  const { data } = await client.get<User[]>('/auth/users');
  return data;
}

// ── Branding ────────────────────────────────────────────────────

export async function getBranding(): Promise<Branding> {
  const { data } = await client.get<Branding>('/branding');
  return data;
}

// ── Projects ────────────────────────────────────────────────────

export async function listProjects(): Promise<Project[]> {
  const { data } = await client.get<Project[]>('/projects');
  return data;
}

export async function getProject(id: number): Promise<Project> {
  const { data } = await client.get<Project>(`/projects/${id}`);
  return data;
}

export async function deleteProject(id: number): Promise<void> {
  await client.delete(`/projects/${id}`);
}

export async function setProjectActive(id: number, is_active: boolean): Promise<Project> {
  const { data } = await client.patch<Project>(`/projects/${id}/active`, { is_active });
  return data;
}

export async function createProject(payload: ProjectCreate): Promise<Project> {
  const { data } = await client.post<Project>('/projects', payload);
  return data;
}

export async function updatePhase(id: number, phase: string): Promise<Project> {
  const payload: ProjectPhaseUpdate = { phase };
  const { data } = await client.post<Project>(`/projects/${id}/phase`, payload);
  return data;
}

export async function updateStringPattern(id: number, string_pattern: string | null): Promise<Project> {
  const { data } = await client.patch<Project>(`/projects/${id}/string-pattern`, { string_pattern });
  return data;
}

export async function listProjectNamingPatterns(projectId: number, asset_type?: string): Promise<NamingPattern[]> {
  const { data } = await client.get<NamingPattern[]>(`/projects/${projectId}/naming-patterns`, {
    params: asset_type ? { asset_type } : undefined,
  });
  return data;
}

export async function createProjectNamingPattern(
  projectId: number,
  payload: Pick<NamingPattern, 'asset_type' | 'pattern_name' | 'pattern_regex' | 'is_active'>,
): Promise<NamingPattern> {
  const { data } = await client.post<NamingPattern>(`/projects/${projectId}/naming-patterns`, payload);
  return data;
}

export async function updateProjectNamingPattern(
  projectId: number,
  patternId: number,
  payload: Partial<Pick<NamingPattern, 'pattern_name' | 'pattern_regex' | 'is_active'>>,
): Promise<NamingPattern> {
  const { data } = await client.patch<NamingPattern>(`/projects/${projectId}/naming-patterns/${patternId}`, payload);
  return data;
}

export async function deleteProjectNamingPattern(projectId: number, patternId: number): Promise<void> {
  await client.delete(`/projects/${projectId}/naming-patterns/${patternId}`);
}

export async function validateDesign(id: number): Promise<ValidationRun> {
  const { data } = await client.post<ValidationRun>(`/projects/${id}/validate-design`);
  return data;
}

// ── Tasks ───────────────────────────────────────────────────────

export async function listTasks(projectId?: number): Promise<MaintenanceTask[]> {
  const { data } = await client.get<MaintenanceTask[]>('/tasks', {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
}

export async function getTask(id: number): Promise<MaintenanceTask> {
  const { data } = await client.get<MaintenanceTask>(`/tasks/${id}`);
  return data;
}

export async function createTask(payload: TaskCreate): Promise<MaintenanceTask> {
  const { data } = await client.post<MaintenanceTask>('/tasks', payload);
  return data;
}

export async function addMessage(taskId: number, payload: TaskMessage): Promise<MaintenanceTask> {
  const { data } = await client.post<MaintenanceTask>(`/tasks/${taskId}/messages`, payload);
  return data;
}

export async function approveTask(taskId: number, payload: TaskApproval): Promise<MaintenanceTask> {
  const { data } = await client.post<MaintenanceTask>(`/tasks/${taskId}/approve`, payload);
  return data;
}

export async function addTestResult(taskId: number, payload: TaskTestResult): Promise<MaintenanceTask> {
  const { data } = await client.post<MaintenanceTask>(`/tasks/${taskId}/test-results`, payload);
  return data;
}

// ── Task Attachments ────────────────────────────────────────────

export interface TaskAttachment {
  id: number;
  task_id: number;
  file_type: string;
  file_name: string;
  mime_type: string | null;
  uploaded_by: string | null;
  created_at: string;
}

export async function listTaskAttachments(taskId: number): Promise<TaskAttachment[]> {
  const { data } = await client.get<TaskAttachment[]>(`/tasks/${taskId}/attachments`);
  return data;
}

export async function uploadTaskAttachments(taskId: number, files: FileList): Promise<TaskAttachment[]> {
  const form = new FormData();
  Array.from(files).forEach(f => form.append('files', f));
  const { data } = await client.post<TaskAttachment[]>(`/tasks/${taskId}/attachments`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export function taskAttachmentDownloadUrl(taskId: number, attId: number): string {
  return `/api/tasks/${taskId}/attachments/${attId}/download`;
}

// ── Measurements ────────────────────────────────────────────────

export async function listMeasurements(params?: { project_id?: number; string_label?: string; limit?: number; offset?: number }): Promise<Measurement[]> {
  const { data } = await client.get<Measurement[]>('/measurements', { params });
  return data;
}

export interface SuiImportResult {
  imported: number;
  failed: number;
  results: { id: number; file_name: string; ok: boolean }[];
  errors: { file: string; error: string }[];
}

export async function uploadSui(files: File | FileList | File[]): Promise<SuiImportResult> {
  const form = new FormData();
  const arr = files instanceof FileList
    ? Array.from(files)
    : Array.isArray(files) ? files : [files];
  arr.forEach(f => form.append('files', f));
  const { data } = await client.post<SuiImportResult>('/measurements/upload-sui', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// ── Inventory ───────────────────────────────────────────────────

export async function listMaterials(): Promise<Material[]> {
  const { data } = await client.get<Material[]>('/inventory/materials');
  return data;
}

export async function createMaterial(payload: MaterialCreate): Promise<Material> {
  const { data } = await client.post<Material>('/inventory/materials', payload);
  return data;
}

export async function issueMaterial(payload: MaterialIssueCreate): Promise<MaterialIssue> {
  const { data } = await client.post<MaterialIssue>('/inventory/issue', payload);
  return data;
}

export async function listIssues(projectId?: number): Promise<MaterialIssue[]> {
  const { data } = await client.get<MaterialIssue[]>('/inventory/issues', {
    params: projectId != null ? { project_id: projectId } : undefined,
  });
  return data;
}

/** Topology inverters (from design scan / map). */
export interface ProjectTopologyInverter {
  id: number;
  project_id: number;
  inverter_label: string;
  section_no: number | null;
  block_no: number | null;
  icb_zone: string | null;
  color_group: string | null;
  expected_string_count: number | null;
  detected_string_count: number;
  detection_pattern: string | null;
  is_inferred: boolean;
}

/** DC strings persisted on the project (design model). */
export interface ProjectDesignString {
  id: number;
  project_id: number;
  string_no: string;
  status: string;
  inverter_id: number | null;
  inverter_no: string | null;
}

export async function listProjectTopologyInverters(projectId: number): Promise<ProjectTopologyInverter[]> {
  const { data } = await client.get<ProjectTopologyInverter[]>(`/projects/${projectId}/topology/inverters`);
  return data;
}

export async function listProjectDesignStrings(projectId: number): Promise<ProjectDesignString[]> {
  const { data } = await client.get<ProjectDesignString[]>(`/projects/${projectId}/strings`);
  return data;
}

/** Compact parse summary (parser engine / future scan API). */
export interface StructuredParseReport {
  site?: {
    name?: string;
    installation_type?: string;
    country?: string;
    region?: string;
    coordinates?: { lat?: number; lon?: number };
  };
  patterns?: {
    valid_string_pattern?: string;
    valid_inverter_pattern?: string;
    mode?: string;
  };
  inverters?: {
    total?: number;
    present?: string[];
    status?: string;
  };
  strings?: {
    valid_total?: number;
    invalid_total?: number;
    invalid_examples?: string[];
  };
  duplicates?: {
    exact?: Record<string, number>;
  };
  missing?: Record<string, number[]>;
  spatial_validation?: {
    status?: string;
    reason?: string;
  };
  final_status?: string;
}

export interface DesignMetadata {
  project_name?:              string | null;
  site_code?:                 string | null;
  site_name?:                 string | null;
  source_document?:           string | null;
  country?:                   string | null;
  region?:                    string | null;
  coordinates?:               string | null;
  latitude?:                  number | null;
  longitude?:                 number | null;
  plant_capacity_mw?:         number | null;
  system_rating_kwp?:         number | null;
  module_type?:               string | null;
  module_count?:              number | null;
  module_power_wp?:           number | null;
  modules_per_string?:        number | null;
  total_strings_doc?:         number | null;
  tracker_enabled?:           boolean;
  tracker_rotation_deg?:      number | null;
  azimuth_deg?:               number | null;
  battery_capacity_mwh?:      number | null;
  battery_type?:              string | null;
  storage_capacity_mwh?:      number | null;
  bess_inv?:                  string | null;
  building_area_ha?:          number | null;
  fenced_area_ha?:            number | null;
  fence_length_m?:            number | null;
  system_license?:            string | null;
  inverter_models?:           string[];
  inverter_count_detected?:   number;
  page_count?:                number | null;
  invalid_ab_labels?:         string[];
  validation_findings?:       { risk_code: string; severity: string; title: string; description: string; recommendations?: string[] }[];
  output_validation_findings?: { risk_code: string; severity: string; title: string; description: string; recommendations?: string[] }[];
  suffix_string_issues?:      { base_id: string; issue: string; found: string }[];
  mppt_validation_issues?:    { mppt_no: number; issue: string }[];
  /** Embedded compact parse summary when backend provides it. */
  parse_report?:             StructuredParseReport;
}

export interface ScanAnalytics {
  pattern:       string | null;
  approved_pattern_name?: string | null;
  approved_pattern_regex?: string | null;
  /** Compact parse summary for dashboard (optional). */
  parse_report?: StructuredParseReport;
  valid_count:   number;
  invalid_count: number;
  invalid_rows:  { string_code: string | null; raw_value: string; inverter_key: string | null; invalid_reason: string | null }[];
  missing_strings_by_inverter:          Record<string, number[]>;
  duplicate_string_numbers_by_inverter: Record<string, number[]>;
  outlier_strings_by_inverter:          Record<string, number[]>;
  design_metadata?: DesignMetadata;
}

export async function getScanAnalytics(projectId: number): Promise<ScanAnalytics | null> {
  try {
    const { data } = await client.get<ScanAnalytics>(`/projects/${projectId}/scan-analytics`);
    return data && Object.keys(data).length ? data : null;
  } catch {
    return null;
  }
}

export async function syncStringsFromScan(
  projectId: number,
  scanResult: StringScanResult,
): Promise<{ inverters_synced: number; strings_synced: number }> {
  const { extractStructuredParseReport } = await import('./parseReportUtils');
  const parse_report_embedded =
    scanResult.parse_report ?? extractStructuredParseReport(scanResult as unknown) ?? undefined;

  // Build condensed analytics to persist alongside the sync
  const design_metadata: DesignMetadata = {
    project_name:              scanResult.project_name ?? null,
    site_code:                 scanResult.site_code,
    site_name:                 scanResult.site_name,
    source_document:           scanResult.source_document,
    country:                   scanResult.country,
    region:                    scanResult.region,
    coordinates:               scanResult.coordinates ?? null,
    latitude:                  scanResult.latitude,
    longitude:                 scanResult.longitude,
    plant_capacity_mw:         scanResult.plant_capacity_mw,
    system_rating_kwp:         scanResult.system_rating_kwp,
    module_type:               scanResult.module_type,
    module_count:              scanResult.module_count,
    module_power_wp:           scanResult.module_power_wp,
    modules_per_string:        scanResult.modules_per_string,
    total_strings_doc:         scanResult.total_strings_doc ?? null,
    tracker_enabled:           scanResult.tracker_enabled,
    battery_capacity_mwh:      scanResult.battery_capacity_mwh,
    battery_type:              scanResult.battery_type ?? null,
    storage_capacity_mwh:      scanResult.storage_capacity_mwh ?? null,
    bess_inv:                  scanResult.bess_inv ?? null,
    building_area_ha:          scanResult.building_area_ha ?? null,
    fenced_area_ha:            scanResult.fenced_area_ha ?? null,
    fence_length_m:            scanResult.fence_length_m ?? null,
    system_license:            scanResult.system_license ?? null,
    inverter_models:           scanResult.inverter_models ?? [],
    inverter_count_detected:   scanResult.inverter_count_detected,
    page_count:                scanResult.page_count ?? null,
    validation_findings:       scanResult.validation_findings ?? [],
    output_validation_findings: scanResult.output_validation_findings ?? [],
    suffix_string_issues:      scanResult.suffix_string_issues ?? [],
    mppt_validation_issues:    scanResult.mppt_validation_issues ?? [],
    parse_report:              parse_report_embedded,
  };

  const analytics: ScanAnalytics = {
    pattern:       scanResult.inverters?.[0]?.pattern ?? null,
    parse_report:  parse_report_embedded,
    valid_count:   scanResult.valid_count ?? parse_report_embedded?.strings?.valid_total ?? 0,
    invalid_count: scanResult.invalid_count ?? parse_report_embedded?.strings?.invalid_total ?? 0,
    invalid_rows:  (scanResult.string_rows ?? [])
      .filter(r => !r.is_valid)
      .map(r => ({
        string_code:    r.string_code,
        raw_value:      r.raw_value,
        inverter_key:   (r as any).inverter_key ?? null,
        invalid_reason: r.invalid_reason,
      })),
    missing_strings_by_inverter:          scanResult.missing_strings_by_inverter          ?? {},
    duplicate_string_numbers_by_inverter: scanResult.duplicate_string_numbers_by_inverter ?? {},
    outlier_strings_by_inverter:          scanResult.outlier_strings_by_inverter          ?? {},
    design_metadata,
  };
  const { data } = await client.post(`/projects/${projectId}/strings/sync`, {
    inverters:   scanResult.inverters,
    string_rows: scanResult.string_rows ?? [],
    analytics,
  });
  return data;
}

export async function syncTopologyInverters(
  projectId: number,
  inverters: StringScanResult['inverters'],
): Promise<{ synced: number }> {
  const { data } = await client.post(`/projects/${projectId}/topology/inverters/sync`, { inverters });
  return data;
}

export async function scanProjectFileIds(
  projectId: number,
  fileIds: string[],
): Promise<StringScanResult> {
  const form = new FormData();
  form.append('file_ids', fileIds.join(','));
  const { data } = await client.post<StringScanResult>(
    `/projects/${projectId}/scan-strings`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function runRedFlags(): Promise<Record<string, unknown>> {
  const { data } = await client.post<Record<string, unknown>>('/inventory/run-red-flags');
  return data;
}

export async function updateMaterial(id: number, payload: Partial<MaterialCreate>): Promise<Material> {
  const { data } = await client.patch<Material>(`/inventory/materials/${id}`, payload);
  return data;
}

export async function deleteMaterial(id: number): Promise<void> {
  await client.delete(`/inventory/materials/${id}`);
}

export async function getIssue(id: number): Promise<MaterialIssueDetail> {
  const { data } = await client.get<MaterialIssueDetail>(`/inventory/issues/${id}`);
  return data;
}

export async function recordConsumption(
  issueId: number,
  items: { material_id: number; quantity_consumed?: number; quantity_returned?: number; quantity_missing?: number }[]
): Promise<MaterialIssueDetail> {
  const { data } = await client.patch<MaterialIssueDetail>(`/inventory/issues/${issueId}/consume`, items);
  return data;
}

export async function listFlags(params?: { status?: string; project_id?: number }): Promise<VarianceFlag[]> {
  const { data } = await client.get<VarianceFlag[]>('/inventory/flags', { params });
  return data;
}

export async function resolveFlag(flagId: number, reviewer?: string): Promise<VarianceFlag> {
  const { data } = await client.patch<VarianceFlag>(`/inventory/flags/${flagId}/resolve`, { reviewer: reviewer || '' });
  return data;
}

export async function getLowStock(): Promise<LowStockItem[]> {
  const { data } = await client.get<LowStockItem[]>('/inventory/stock/low');
  return data;
}

// ── Warehouse ───────────────────────────────────────────────────

export async function listWarehouses(): Promise<Warehouse[]> {
  const { data } = await client.get<Warehouse[]>('/warehouses');
  return data;
}

export async function createWarehouse(payload: { name: string; location?: string; manager_name?: string; project_id?: number }): Promise<Warehouse> {
  const { data } = await client.post<Warehouse>('/warehouses', payload);
  return data;
}

export async function getWarehouseStock(warehouseId: number): Promise<WarehouseStock[]> {
  const { data } = await client.get<WarehouseStock[]>(`/warehouses/${warehouseId}/stock`);
  return data;
}

export async function receiveStock(warehouseId: number, materialId: number, quantity: number): Promise<WarehouseStock> {
  const { data } = await client.post<WarehouseStock>(`/warehouses/${warehouseId}/receive`, { material_id: materialId, quantity });
  return data;
}

export async function getWarehouseTransactions(warehouseId: number): Promise<MaterialIssueDetail[]> {
  const { data } = await client.get<MaterialIssueDetail[]>(`/warehouses/${warehouseId}/transactions`);
  return data;
}

// ── Audit Log ───────────────────────────────────────────────────

export interface AuditEntry {
  id: number;
  actor_username: string;
  actor_role: string;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  detail: string | null;
  created_at: string;
}

export async function listAuditLog(limit = 200): Promise<AuditEntry[]> {
  const { data } = await client.get<AuditEntry[]>('/audit', { params: { limit } });
  return data;
}

// ── Security ───────────────────────────────────────────────────

export async function listSecurityDevices(projectId?: string) {
  const { data } = await client.get('/security/devices', { params: { project_id: projectId } });
  return data;
}

export async function registerSecurityDevice(payload: Record<string, unknown>) {
  const { data } = await client.post('/security/devices', payload);
  return data;
}

export async function getSecurityDevice(id: string) {
  const { data } = await client.get(`/security/devices/${id}`);
  return data;
}

export async function runSecurityScan(payload: { project_id: string; scan_type?: string }) {
  const { data } = await client.post('/security/scan', payload);
  return data;
}

export async function listVulnerabilities(params?: { project_id?: string; severity?: string; status?: string }) {
  const { data } = await client.get('/security/vulnerabilities', { params });
  return data;
}

export async function updateVulnerabilityStatus(id: string, newStatus: string) {
  const { data } = await client.patch(`/security/vulnerabilities/${id}/status`, null, { params: { new_status: newStatus } });
  return data;
}

export async function getSecurityDashboard(projectId?: string) {
  const { data } = await client.get('/security/dashboard', { params: { project_id: projectId } });
  return data;
}

export async function checkFirmwareUpdates(projectId?: string) {
  const { data } = await client.post('/security/firmware/check', null, { params: { project_id: projectId } });
  return data;
}

export async function getFirmwareAlerts(projectId?: string) {
  const { data } = await client.get('/security/firmware/alerts', { params: { project_id: projectId } });
  return data;
}

export async function getFirmwareSummary(projectId?: string) {
  const { data } = await client.get('/security/firmware/summary', { params: { project_id: projectId } });
  return data;
}

export async function getRemediationTasks(projectId?: string) {
  const { data } = await client.get('/security/firmware/remediation-tasks', { params: { project_id: projectId } });
  return data;
}

// ── Mobile ──────────────────────────────────────────────────────

// ── Device Inventory Repository ─────────────────────────────────

export async function listDeviceSites(): Promise<DeviceSite[]> {
  const { data } = await client.get<DeviceSite[]>('/device-inventory/sites');
  return data;
}

export async function getDeviceSite(siteId: number): Promise<DeviceSite> {
  const { data } = await client.get<DeviceSite>(`/device-inventory/sites/${siteId}`);
  return data;
}

export async function createDeviceSite(payload: {
  site_name: string;
  country?: string;
  region?: string;
  source_notes?: string;
}): Promise<DeviceSite> {
  const { data } = await client.post<DeviceSite>('/device-inventory/sites', payload);
  return data;
}

export async function listDeviceInventory(params?: {
  site_id?: number;
  category?: string;
  manufacturer?: string;
}): Promise<DeviceInventoryItem[]> {
  const { data } = await client.get<DeviceInventoryItem[]>('/device-inventory/devices', { params });
  return data;
}

export async function getDeviceInventoryItem(id: number): Promise<DeviceInventoryItem> {
  const { data } = await client.get<DeviceInventoryItem>(`/device-inventory/devices/${id}`);
  return data;
}

export async function createDeviceInventoryItem(payload: Partial<DeviceInventoryItem> & { site_id: number; category: string }): Promise<DeviceInventoryItem> {
  const { data } = await client.post<DeviceInventoryItem>('/device-inventory/devices', payload);
  return data;
}

export async function updateDeviceInventoryItem(id: number, payload: Partial<DeviceInventoryItem>): Promise<DeviceInventoryItem> {
  const { data } = await client.patch<DeviceInventoryItem>(`/device-inventory/devices/${id}`, payload);
  return data;
}

export async function deleteDeviceInventoryItem(id: number): Promise<void> {
  await client.delete(`/device-inventory/devices/${id}`);
}

export async function listDeviceSpecs(deviceId: number): Promise<DeviceSpec[]> {
  const { data } = await client.get<DeviceSpec[]>(`/device-inventory/devices/${deviceId}/specs`);
  return data;
}

export async function upsertDeviceSpec(deviceId: number, payload: { spec_key: string; spec_value: string; source_note?: string }): Promise<DeviceSpec> {
  const { data } = await client.put<DeviceSpec>(`/device-inventory/devices/${deviceId}/specs`, payload);
  return data;
}

export async function listDeviceCVEs(params?: { manufacturer?: string; severity?: string }): Promise<DeviceCVE[]> {
  const { data } = await client.get<DeviceCVE[]>('/device-inventory/cves', { params });
  return data;
}

export async function getDeviceCVE(id: number): Promise<DeviceCVE> {
  const { data } = await client.get<DeviceCVE>(`/device-inventory/cves/${id}`);
  return data;
}

export async function createDeviceCVE(payload: Partial<DeviceCVE> & { product_scope: string; title: string; applicability: string }): Promise<DeviceCVE> {
  const { data } = await client.post<DeviceCVE>('/device-inventory/cves', payload);
  return data;
}

export async function linkDeviceToCVE(deviceId: number, vulnId: number, relationshipType = 'direct'): Promise<{ id: number; device_id: number; vuln_id: number; relationship_type: string }> {
  const { data } = await client.post(`/device-inventory/devices/${deviceId}/cves`, { vuln_id: vulnId, relationship_type: relationshipType });
  return data;
}

export async function unlinkDeviceFromCVE(deviceId: number, vulnId: number): Promise<void> {
  await client.delete(`/device-inventory/devices/${deviceId}/cves/${vulnId}`);
}

export async function getDeviceInventorySummary(): Promise<DeviceInventorySummary> {
  const { data } = await client.get<DeviceInventorySummary>('/device-inventory/summary');
  return data;
}

export async function seedDeviceInventory(): Promise<Record<string, unknown>> {
  const { data } = await client.post('/device-inventory/seed');
  return data;
}

// ── Solar Catalog ───────────────────────────────────────────────

export async function getSolarCatalogStatus(): Promise<import('./types').SolarCatalogStatus> {
  const { data } = await client.get('/solar-catalog/status');
  return data;
}

export async function searchSolarCatalog(params?: {
  q?: string;
  category?: string;
  manufacturer?: string;
  technology?: string;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_dir?: string;
}): Promise<{ items: import('./types').SolarCatalogDevice[]; total: number }> {
  const { data } = await client.get<{ total: number; results: import('./types').SolarCatalogDevice[] }>(
    '/solar-catalog/devices', { params }
  );
  return { items: data.results, total: data.total };
}

export async function listSolarCatalogManufacturers(params?: {
  q?: string;
  category?: string;
}): Promise<{ manufacturer_name: string; device_count: number }[]> {
  const { data } = await client.get('/solar-catalog/manufacturers', { params });
  return data;
}

export async function listSolarCatalogCategories(): Promise<{ id: number; category_code: string; category_name: string }[]> {
  const { data } = await client.get('/solar-catalog/categories');
  return data;
}

export async function getSolarCatalogDevice(id: number): Promise<import('./types').SolarCatalogDevice> {
  const { data } = await client.get(`/solar-catalog/devices/${id}`);
  return data;
}

// ── Field Testing ───────────────────────────────────────────────

export interface TestType {
  id: number;
  test_code: string;
  test_name: string;
  unit: string | null;
  description: string | null;
}

export interface TestRecord {
  id: number;
  project_id: number;
  test_type_id: number;
  test_code: string;
  test_name: string;
  unit: string | null;
  entity_type: string;
  entity_ref: string | null;
  test_date: string | null;
  result_status: string;
  measured_values: Record<string, number | string> | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
}

export interface TestRecordCreate {
  test_code: string;
  entity_type: string;
  entity_ref?: string;
  result_status: string;
  measured_values?: Record<string, number | string>;
  test_date?: string;
  notes?: string;
  recorded_by?: string;
}

export interface CommissioningStatus {
  ready: boolean;
  passed: string[];
  missing: string[];
  required: string[];
}

export async function listTestTypes(projectId: number): Promise<TestType[]> {
  const { data } = await client.get<TestType[]>(`/projects/${projectId}/tests/types`);
  return data;
}

export async function listTestRecords(projectId: number, testCode?: string): Promise<TestRecord[]> {
  const { data } = await client.get<TestRecord[]>(`/projects/${projectId}/tests`, {
    params: testCode ? { test_code: testCode } : undefined,
  });
  return data;
}

export async function createTestRecord(projectId: number, payload: TestRecordCreate): Promise<TestRecord> {
  const { data } = await client.post<TestRecord>(`/projects/${projectId}/tests`, payload);
  return data;
}

export async function deleteTestRecord(projectId: number, recordId: number): Promise<void> {
  await client.delete(`/projects/${projectId}/tests/${recordId}`);
}

export async function getCommissioningStatus(projectId: number): Promise<CommissioningStatus> {
  const { data } = await client.get<CommissioningStatus>(`/projects/${projectId}/tests/commissioning-ready`);
  return data;
}

// ── String Scan ─────────────────────────────────────────────────

// ── Companies & Customers ────────────────────────────────────────

export interface Company {
  id: number;
  name: string;
  code: string | null;
  country: string | null;
  contact_email: string | null;
  created_at: string;
  customer_count: number;
}

export interface Customer {
  id: number;
  company_id: number;
  company_name: string | null;
  name: string;
  code: string | null;
  contact_email: string | null;
  notes: string | null;
  created_at: string;
  project_count: number;
}

export async function listCompanies(): Promise<Company[]> {
  const { data } = await client.get<Company[]>('/companies');
  return data;
}

export async function createCompany(payload: { name: string; code?: string; country?: string; contact_email?: string }): Promise<Company> {
  const { data } = await client.post<Company>('/companies', payload);
  return data;
}

export async function listCustomers(companyId?: number): Promise<Customer[]> {
  const params = companyId != null ? { company_id: companyId } : {};
  const { data } = await client.get<Customer[]>('/customers', { params });
  return data;
}

export async function createCustomer(payload: { company_id: number; name: string; code?: string; contact_email?: string; notes?: string }): Promise<Customer> {
  const { data } = await client.post<Customer>('/customers', payload);
  return data;
}

export interface StringScanResult {
  /** When API returns compact summary only or embeds it alongside legacy fields. */
  parse_report?: StructuredParseReport;
  site_code: string | null;
  site_name: string | null;
  layout_name: string | null;
  source_document: string | null;
  source_documents?: string[];
  country: string | null;
  region: string | null;
  latitude: number | null;
  longitude: number | null;
  plant_capacity_mw: number | null;
  module_type: string | null;
  module_count: number | null;
  string_rows?: {
    row_id: number;
    raw_value: string;
    string_code: string | null;
    section_no: number | null;
    block_no: number | null;
    string_no: number | null;
    is_valid: boolean;
    invalid_reason: string | null;
  }[];
  strings?: Record<string, string[]>;
  gaps?: Record<string, string[]>;
  duplicates?: string[];
  anomalies?: Record<string, string[]>;
  valid_count?: number;
  invalid_count?: number;
  has_errors?: boolean;
  // Extended metadata (from_chatgpt integration)
  module_power_wp: number | null;
  modules_per_string: number | null;
  system_rating_kwp: number | null;
  battery_capacity_mwh: number | null;
  tracker_enabled: boolean;
  // Detected entities
  inverters: { raw_name: string; normalized_name: string; pattern: string; strings_count?: number }[];
  inverter_count_detected: number;
  total_strings_doc?: number;
  ac_assets: { asset_type: string; raw_name: string; normalized_name: string }[];
  batteries: { asset_type: string; raw_name: string; normalized_name: string }[];
  // Validation findings
  validation_findings: {
    risk_code: string;
    severity: string;
    title: string;
    description: string;
    recommendations: string[];
  }[];
  metadata: { project: string | null; location: string | null; total_modules: number | null };
  mppt_channels?: { icb_zone: string; dc_terminal_no: number; mppt_no: number; string_count: number; channel_labels: string[] }[];
  icb_zones?: { label: string; zone_id: string }[];
  // Per-inverter analytics (improved parser)
  inverter_summary?: Record<string, { string_count: number; min_string_no: number | null; max_string_no: number | null; string_numbers: number[] }>;
  missing_strings_by_inverter?: Record<string, number[]>;
  duplicate_string_numbers_by_inverter?: Record<string, number[]>;
  outlier_strings_by_inverter?: Record<string, number[]>;
  dc_string_buckets_found?: number[];
  topology_findings?: { risk_code: string; severity: string; title: string; description: string; related_assets?: string[] }[];
  reconciliation?: { table_inverter_count?: number; map_inverter_count?: number; map_string_total?: number; table_string_count?: number; icb_zones_detected?: string[]; mppt_groups_detected?: number; status?: string; issues?: { code: string; severity: string; message: string }[] };
  events?: { event: string; timestamp: string; payload: Record<string, unknown> }[];
  // New extended fields from extra_patterns / from_chatgpt integration
  project_name?:              string | null;
  coordinates?:               string | null;
  building_area_ha?:          number | null;
  fenced_area_ha?:            number | null;
  fence_length_m?:            number | null;
  system_license?:            string | null;
  storage_capacity_mwh?:      number | null;
  inverter_models?:           string[];
  battery_type?:              string | null;
  bess_inv?:                  string | null;
  page_count?:                number | null;
  mppt_groups?:               { mppt_no: number; mppt_label: string; pv_labels: string[]; estimated_string_count: number; st_labels?: string[] }[];
  suffix_strings?:            { base_id: string; suffix: string; full_id: string }[];
  suffix_string_issues?:      { base_id: string; issue: string; found: string }[];
  mppt_validation_issues?:    { mppt_no: number; issue: string }[];
  output_validation_findings?: { risk_code: string; severity: string; title: string; description: string; recommendations?: string[] }[];
  approved_pattern_name?: string | null;
  approved_pattern_regex?: string | null;
}

export interface ApprovedStringPattern {
  pattern_name: string;
  pattern_regex: string;
}

export interface StringPatternOption extends ApprovedStringPattern {
  id?: number | null;
  source?: 'project' | 'default';
  match_count: number;
}

export interface StringPatternDetectionResult {
  patterns: StringPatternOption[];
  detected_pattern_name: string | null;
  selected_pattern_name: string | null;
  saved_pattern_name: string | null;
  file_count: number;
  detect_token?: string | null;
}

export interface ProjectFile {
  id:            string;
  original_name: string;
  file_type:     string;
  size_bytes:    number;
  uploaded_at:   string;
  is_active:     boolean;
}

export async function listProjectFiles(projectId: number): Promise<ProjectFile[]> {
  const { data } = await client.get<ProjectFile[]>(`/projects/${projectId}/files`);
  return data;
}

export async function uploadProjectFiles(projectId: number, files: File[]): Promise<ProjectFile[]> {
  const form = new FormData();
  files.forEach(f => form.append('files', f));
  const { data } = await client.post<ProjectFile[]>(`/projects/${projectId}/files`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function scanProjectStrings(
  projectId: number,
  fileIds?: string[],
  files?: FileList,
  approvedPattern?: ApprovedStringPattern,
  detectToken?: string | null,
): Promise<StringScanResult> {
  const form = new FormData();
  if (fileIds?.length) form.append('file_ids', fileIds.join(','));
  if (files) Array.from(files).forEach(f => form.append('files', f));
  if (approvedPattern) {
    form.append('approved_pattern_name', approvedPattern.pattern_name);
    form.append('approved_pattern_regex', approvedPattern.pattern_regex);
  }
  if (detectToken) form.append('detect_token', detectToken);
  const { data } = await client.post<StringScanResult>(
    `/projects/${projectId}/scan-strings`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function detectStringPattern(
  projectId: number,
  fileIds?: string[],
  files?: FileList,
): Promise<StringPatternDetectionResult> {
  const form = new FormData();
  if (fileIds?.length) form.append('file_ids', fileIds.join(','));
  if (files) Array.from(files).forEach(f => form.append('files', f));
  const { data } = await client.post<StringPatternDetectionResult>(
    `/projects/${projectId}/detect-string-pattern`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

// ── Mobile ──────────────────────────────────────────────────────

export async function getMobileHome(role: string): Promise<MobileHomeResponse> {
  const { data } = await client.get<MobileHomeResponse>(`/mobile/home/${role}`);
  return data;
}

export async function getMobileSummary(role: string): Promise<MobileSummary> {
  const { data } = await client.get<MobileSummary>(`/mobile/summary/${role}`);
  return data;
}

export async function getMeasurement(id: number): Promise<Measurement> {
  const { data } = await client.get<Measurement>(`/measurements/${id}`);
  return data;
}

// ── Field Configs ────────────────────────────────────────────────

export interface FieldConfigItem {
  id?: number;
  grid_name: string;
  field_name: string;
  visible: boolean;
  width?: number | null;
  column_order?: number | null;
}

export async function getFieldConfigs(gridName?: string): Promise<FieldConfigItem[]> {
  const params = gridName ? { grid_name: gridName } : {};
  const { data } = await client.get<FieldConfigItem[]>('/field-configs', { params });
  return data;
}

export async function saveFieldConfigs(items: FieldConfigItem[]): Promise<{ saved: number }> {
  const { data } = await client.put<{ saved: number }>('/field-configs', items);
  return data;
}

export default client;
