-- SQLite schema for IVCurve (dev fallback when PostgreSQL unavailable)
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    source_file TEXT,
    measured_at TEXT,
    device_serial TEXT,
    irradiance_sensor_type TEXT,
    irradiance_sensor_serial TEXT,
    ppk REAL, rs REAL, rp REAL,
    voc REAL, isc REAL, vpmax REAL, ipmax REAL, pmax REAL, ff REAL,
    tmod REAL, eeff REAL,
    ppk_deviation REAL, rs_deviation REAL, rp_deviation REAL,
    customer_id INTEGER, module_id INTEGER,
    customer TEXT, module_type TEXT, tcell REAL, remarks TEXT
);

CREATE TABLE IF NOT EXISTS iv_curve_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_id INTEGER NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    point_index INTEGER NOT NULL,
    voltage REAL NOT NULL,
    current REAL NOT NULL,
    UNIQUE(measurement_id, point_index)
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer TEXT,
    model TEXT,
    ppk_nominal REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS site_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_code TEXT NOT NULL UNIQUE,
    site_name TEXT NOT NULL,
    layout_name TEXT,
    source_document TEXT,
    country TEXT,
    region TEXT,
    latitude REAL,
    longitude REAL,
    plant_capacity_mw REAL,
    module_type TEXT,
    module_count INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS site_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL REFERENCES site_details(id) ON DELETE CASCADE,
    string_code TEXT NOT NULL,
    section_no INTEGER NOT NULL,
    block_no INTEGER NOT NULL,
    string_no INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(site_id, string_code)
);

-- Auth / RBAC tables
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_code TEXT NOT NULL UNIQUE,
    role_name TEXT NOT NULL,
    scope_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_global_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    assigned_at TEXT DEFAULT (datetime('now')),
    UNIQUE (user_id, role_id)
);

INSERT OR IGNORE INTO roles (role_code, role_name, scope_type) VALUES
    ('manager', 'Manager', 'global'),
    ('project_manager', 'Project Manager', 'project'),
    ('supervisor', 'Supervisor', 'project'),
    ('inventory_keeper', 'Inventory Keeper', 'project');

CREATE INDEX IF NOT EXISTS idx_measurements_measured_at ON measurements(measured_at);
CREATE INDEX IF NOT EXISTS idx_measurements_source_file ON measurements(source_file);
CREATE INDEX IF NOT EXISTS idx_iv_curve_measurement ON iv_curve_points(measurement_id);
CREATE INDEX IF NOT EXISTS idx_site_strings_site_id ON site_strings(site_id);
CREATE INDEX IF NOT EXISTS idx_site_strings_section_block ON site_strings(site_id, section_no, block_no);

-- PVPM connector tables (v1 schema)
CREATE TABLE IF NOT EXISTS pvpm_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial_number TEXT UNIQUE,
    model TEXT,
    firmware_version TEXT,
    calibration_date TEXT,
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS pvpm_measurements (
    id TEXT PRIMARY KEY,
    device_id INTEGER REFERENCES pvpm_devices(id),
    external_measurement_key TEXT,
    measured_at TEXT NOT NULL,
    customer TEXT,
    installation TEXT,
    string_no TEXT,
    module_type TEXT,
    module_reference TEXT,
    modules_series INTEGER,
    modules_parallel INTEGER,
    nominal_power_w REAL,
    ppk_wp REAL,
    rs_ohm REAL,
    rp_ohm REAL,
    voc_v REAL,
    isc_a REAL,
    vpmax_v REAL,
    ipmax_a REAL,
    ff_percent REAL,
    sweep_duration_ms REAL,
    irradiance_w_m2 REAL,
    sensor_temp_c REAL,
    module_temp_c REAL,
    irradiance_sensor_type TEXT,
    irradiance_sensor_serial TEXT,
    raw_payload_json TEXT,
    import_source TEXT,
    sync_status TEXT DEFAULT 'synced',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pvpm_curve_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_id TEXT NOT NULL REFERENCES pvpm_measurements(id) ON DELETE CASCADE,
    point_index INTEGER NOT NULL,
    voltage_v REAL NOT NULL,
    current_a REAL NOT NULL,
    UNIQUE(measurement_id, point_index)
);

CREATE TABLE IF NOT EXISTS pvpm_sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_id TEXT,
    direction TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pvpm_measurements_measured_at ON pvpm_measurements(measured_at);
CREATE INDEX IF NOT EXISTS idx_pvpm_curve_points_measurement ON pvpm_curve_points(measurement_id);
