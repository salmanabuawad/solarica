/**
 * Default column definitions for each configurable grid.
 * The admin page reads from this registry to populate initial state.
 */

export interface GridColumnDefault {
  field_name: string;
  header: string;
  visible: boolean;
  width?: number;
}

export interface GridDefault {
  grid_name: string;
  label: string;
  columns: GridColumnDefault[];
}

export const GRID_DEFAULTS: GridDefault[] = [
  {
    grid_name: 'projects',
    label: 'Projects',
    columns: [
      { field_name: 'name',             header: 'Name',           visible: true },
      { field_name: 'customer_name',    header: 'Customer',       visible: true },
      { field_name: 'site_name',        header: 'Site',           visible: true },
      { field_name: 'phase',            header: 'Phase',          visible: true },
      { field_name: 'project_type',     header: 'Type',           visible: true },
      { field_name: 'progress_percent', header: 'Progress',       visible: true },
      { field_name: 'is_active',        header: 'Active',         visible: false },
      { field_name: 'created_at',       header: 'Created',        visible: false },
    ],
  },
  {
    grid_name: 'materials',
    label: 'Materials',
    columns: [
      { field_name: 'name',          header: 'Name',          visible: true },
      { field_name: 'category',      header: 'Category',      visible: true },
      { field_name: 'unit',          header: 'Unit',          visible: true, width: 80 },
      { field_name: 'sku',           header: 'SKU',           visible: true },
      { field_name: 'min_threshold', header: 'Min Threshold', visible: true },
      { field_name: 'unit_cost',     header: 'Unit Cost',     visible: true },
    ],
  },
  {
    grid_name: 'tasks',
    label: 'Tasks',
    columns: [
      { field_name: 'title',        header: 'Title',       visible: true },
      { field_name: 'project_name', header: 'Project',     visible: true },
      { field_name: 'status',       header: 'Status',      visible: true },
      { field_name: 'priority',     header: 'Priority',    visible: true },
      { field_name: 'assigned_to',  header: 'Assigned To', visible: true },
      { field_name: 'due_date',     header: 'Due Date',    visible: true },
      { field_name: 'created_at',   header: 'Created',     visible: false },
    ],
  },
  {
    grid_name: 'measurements',
    label: 'Measurements',
    columns: [
      { field_name: 'project_name',   header: 'Project',    visible: true },
      { field_name: 'test_date',      header: 'Date',       visible: true },
      { field_name: 'string_id',      header: 'String',     visible: true },
      { field_name: 'inverter_id',    header: 'Inverter',   visible: true },
      { field_name: 'voc',            header: 'Voc',        visible: true },
      { field_name: 'isc',            header: 'Isc',        visible: true },
      { field_name: 'vmp',            header: 'Vmp',        visible: false },
      { field_name: 'imp',            header: 'Imp',        visible: false },
      { field_name: 'pmax',           header: 'Pmax',       visible: true },
      { field_name: 'irradiance',     header: 'Irradiance', visible: false },
      { field_name: 'temperature',    header: 'Temp',       visible: false },
    ],
  },
  {
    grid_name: 'device_inventory',
    label: 'Device Inventory',
    columns: [
      { field_name: 'device_tag',      header: 'Tag',          visible: true },
      { field_name: 'device_type',     header: 'Type',         visible: true },
      { field_name: 'manufacturer',    header: 'Manufacturer', visible: true },
      { field_name: 'model',           header: 'Model',        visible: true },
      { field_name: 'site_name',       header: 'Site',         visible: true },
      { field_name: 'status',          header: 'Status',       visible: true },
      { field_name: 'serial_number',   header: 'Serial',       visible: false },
      { field_name: 'firmware',        header: 'Firmware',     visible: false },
      { field_name: 'install_date',    header: 'Installed',    visible: true },
      { field_name: 'warranty_expiry', header: 'Warranty',     visible: false },
      { field_name: 'notes',           header: 'Notes',        visible: false },
    ],
  },
  {
    grid_name: 'solar_catalog',
    label: 'Solar Catalog',
    columns: [
      { field_name: 'manufacturer_name', header: 'Manufacturer', visible: true },
      { field_name: 'model_name',        header: 'Model',        visible: true },
      { field_name: 'brand_name',        header: 'Brand',        visible: false },
      { field_name: 'category_name',     header: 'Category',     visible: true },
      { field_name: 'technology',        header: 'Technology',   visible: true },
      { field_name: 'source_code',       header: 'Source',       visible: true },
      { field_name: 'is_hybrid',         header: 'Hybrid',       visible: false },
      { field_name: 'spec_count',        header: 'Specs',        visible: true },
    ],
  },
  {
    grid_name: 'device_registry',
    label: 'Device Registry (CVEs)',
    columns: [
      { field_name: 'cve_id',       header: 'CVE ID',     visible: true },
      { field_name: 'title',        header: 'Title',      visible: true },
      { field_name: 'severity',     header: 'Severity',   visible: true },
      { field_name: 'cvss_v3',      header: 'CVSS v3',   visible: true },
      { field_name: 'published',    header: 'Published',  visible: true },
      { field_name: 'device_count', header: 'Devices',    visible: true },
    ],
  },
  {
    grid_name: 'vulnerabilities',
    label: 'Vulnerabilities',
    columns: [
      { field_name: 'cve_id',           header: 'CVE ID',      visible: true },
      { field_name: 'title',            header: 'Title',       visible: true },
      { field_name: 'severity',         header: 'Severity',    visible: true },
      { field_name: 'cvss_v3',          header: 'CVSS v3',    visible: true },
      { field_name: 'published_date',   header: 'Published',   visible: true },
      { field_name: 'affected_product', header: 'Product',     visible: true },
      { field_name: 'source_name',      header: 'Source',      visible: false },
    ],
  },
];
