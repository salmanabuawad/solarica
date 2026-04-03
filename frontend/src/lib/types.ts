// ── Roles & Users ──────────────────────────────────────────────

export type UserRole = 'admin' | 'manager' | 'technician' | 'warehouse' | 'owner';

export interface User {
  id: number;
  username: string;
  role: UserRole;
  display_name: string;
}

// ── Projects ───────────────────────────────────────────────────

export interface ProjectCreate {
  name: string;
  customer_name?: string | null;
  customer_id?: number | null;
  site_name: string;
  project_type: string;
  description?: string | null;
}

export interface Project extends ProjectCreate {
  id: number;
  phase: string;
  progress_percent: number;
  company_id?: number | null;
  company_name?: string | null;
  /** When false, project is inactive; data is retained. Omitted treated as active. */
  is_active?: boolean;
  /** Admin-configured string naming pattern, e.g. "S.N.N.N" or "S.N.N.N.N" */
  string_pattern?: string | null;
  created_at?: string | null;
}

export interface ProjectPhaseUpdate {
  phase: string;
}

export interface ValidationIssue {
  severity: string;
  asset_type?: string | null;
  asset_ref?: string | null;
  issue_type: string;
  message: string;
}

export interface ValidationRun {
  status: string;
  issues: ValidationIssue[];
}

// ── Tasks ──────────────────────────────────────────────────────

export interface TaskCreate {
  project_id: number;
  site_name: string;
  asset_type: string;
  asset_ref?: string | null;
  title: string;
  description?: string | null;
  task_type?: string;
  priority?: string;
  assigned_to?: string | null;
  requires_approval?: boolean;
  requires_test_result?: boolean;
}

export interface TaskMessage {
  author_name: string;
  message_type?: string;
  message_text?: string | null;
  created_at?: string;
}

export interface TaskApproval {
  approver_name: string;
  decision_note?: string | null;
  approved?: boolean;
}

export interface TaskTestResult {
  test_type: string;
  title: string;
  status?: string;
  summary?: string | null;
  raw_result_json?: Record<string, unknown> | null;
}

export interface MaintenanceTask extends TaskCreate {
  id: number;
  status: string;
  messages: TaskMessage[];
  approvals: TaskApproval[];
  test_results: TaskTestResult[];
}

// ── Inventory ──────────────────────────────────────────────────

export interface MaterialCreate {
  name: string;
  category?: string | null;
  unit: string;
  sku?: string | null;
  min_threshold?: number;
  unit_cost?: number | null;
}

export interface Material extends MaterialCreate {
  id: number;
  current_quantity: number;
}

export interface MaterialIssueItem {
  material_name: string;
  quantity_issued: number;
  quantity_returned?: number;
  quantity_consumed?: number;
  quantity_missing?: number;
  unit?: string | null;
}

export interface MaterialIssueCreate {
  project_id: number | string;
  warehouse_name: string;
  issued_to_user: string;
  issued_by_user: string;
  site_name?: string | null;
  asset_type?: string | null;
  asset_ref?: string | null;
  expected_usage_days?: number;
  notes?: string | null;
  items: MaterialIssueItem[];
}

export interface MaterialIssue extends MaterialIssueCreate {
  id: number;
  status: string;
  red_flags: VarianceFlag[] | Record<string, unknown>[];
  issued_at?: string;
}

export interface MaterialIssueItemDetail {
  material_id: number;
  material_name: string | null;
  quantity_issued: number;
  quantity_returned: number;
  quantity_consumed: number;
  quantity_missing: number;
  unit: string | null;
}

export interface VarianceFlag {
  id: number;
  transaction_id: number;
  material_id: number;
  expected_quantity: number;
  actual_quantity: number;
  variance_quantity: number;
  rule_type: string;
  severity: string;
  description: string;
  status: string;
  reviewed_by: string | null;
  created_at: string | null;
  resolved_at: string | null;
}

export interface MaterialIssueDetail extends Omit<MaterialIssue, 'items' | 'red_flags'> {
  warehouse_id?: number;
  task_id?: number | null;
  issued_at?: string;
  expected_usage_by_date?: string | null;
  items: MaterialIssueItemDetail[];
  red_flags: VarianceFlag[];
}

export interface LowStockItem {
  material_id: number;
  material_name: string;
  category: string | null;
  unit: string;
  total_available: number;
  min_threshold: number;
  deficit: number;
}

export interface Warehouse {
  id: number;
  name: string;
  location: string | null;
  manager_name: string | null;
  project_id: number | null;
  created_at: string | null;
}

export interface WarehouseStock {
  id: number;
  warehouse_id: number;
  material_id: number;
  material_name: string | null;
  quantity_available: number;
  quantity_reserved: number;
  last_updated: string | null;
}

// ── Measurements ───────────────────────────────────────────────

export interface Measurement {
  id: number;
  project_id: number | null;
  string_id: number | null;
  file_name: string;
  device_serial: string | null;
  site_label: string | null;
  string_label: string | null;
  module_part_number: string | null;
  records: Record<string, unknown>[];
  record_count: number;
  uploaded_at: string;
  pmax_w: number | null;
  voc_v: number | null;
  isc_a: number | null;
}

// ── Mobile ─────────────────────────────────────────────────────

export interface MobileCard {
  title: string;
  count?: number;
  route?: string;
}

export interface MobileHomeResponse {
  role: string;
  cards: string[];
}

export interface MobileSummary {
  open_tasks: number;
  pending_approvals: number;
  active_projects: number;
  open_flags: number;
  open_issues: number;
  low_stock_items: number;
}

// ── Device Inventory Repository ────────────────────────────────

export interface DeviceSite {
  id: number;
  site_name: string;
  country: string | null;
  region: string | null;
  source_notes: string | null;
  device_count: number;
}

export interface DeviceSpec {
  id: number;
  device_id: number;
  spec_key: string;
  spec_value: string;
  source_note: string | null;
}

export interface DeviceCVE {
  id: number;
  manufacturer: string | null;
  product_scope: string;
  cve_id: string | null;
  title: string;
  severity: string | null;   // Critical, High, Medium, Low
  affected_versions: string | null;
  fixed_versions: string | null;
  advisory_source: string | null;
  applicability: string;
  notes: string | null;
  affected_device_count: number;
}

export interface DeviceVulnLink {
  id: number;
  device_id: number;
  vuln_id: number;
  cve_id: string | null;
  title: string | null;
  severity: string | null;
  relationship_type: string;  // direct, adjacent, indirect
}

export interface DeviceInventoryItem {
  id: number;
  site_id: number;
  site_name: string | null;
  area: string | null;
  category: string;
  manufacturer: string | null;
  model_raw: string | null;
  model_normalized: string | null;
  quantity: number | null;
  unit: string;
  is_exact_model_confirmed: boolean;
  role: string | null;
  source_notes: string | null;
  vuln_count: number;
  specs?: DeviceSpec[];
  vulnerabilities?: DeviceCVE[];
}

export interface DeviceInventorySummary {
  site_count: number;
  device_type_count: number;
  total_units: number;
  cve_count: number;
  severity_breakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  categories: Record<string, number>;
}

// ── Solar Catalog ─────────────────────────────────────────────

export interface SolarCatalogSpec {
  id: number;
  device_id: number;
  spec_group: string;
  spec_key: string;
  spec_value_text: string | null;
  spec_value_num: number | null;
  unit: string | null;
}

export interface SolarCatalogDevice {
  id: number;
  model_name: string;
  brand_name: string | null;
  technology: string | null;
  description: string | null;
  category_code: string;
  category_name: string;
  manufacturer_name: string;
  source_code: string;
  source_release_date?: string | null;
  is_hybrid: boolean | null;
  spec_count?: number;
  specs?: SolarCatalogSpec[];
}

export interface SolarCatalogStatus {
  loaded: boolean;
  device_count: number;
  spec_count: number;
  manufacturer_count: number;
  vulnerability_count: number;
  by_category: Record<string, number>;
}

// ── Branding ───────────────────────────────────────────────────

export interface Branding {
  name: string;
  tagline: string;
  positioning: string;
}

// ── UI State ───────────────────────────────────────────────────

export interface Tab {
  id: string;
  type: string;
  label: string;
  icon?: string;
  projectId?: string;
}

export type Theme = 'light' | 'dark' | 'ocean' | 'mist';
export type FontSize = 'small' | 'normal' | 'large';
