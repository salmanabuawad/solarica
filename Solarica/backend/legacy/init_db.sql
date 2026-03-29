-- IVCurve / PVPM1540X Database Schema
-- For photovoltaic I-V curve measurement data

-- Measurements (one per I-V curve measurement)
CREATE TABLE IF NOT EXISTS measurements (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_file VARCHAR(512),          -- Original filename (SUI, XLS, etc.)
    
    -- Timestamp from device
    measured_at TIMESTAMP WITH TIME ZONE,
    
    -- Device & sensor info
    device_serial VARCHAR(128),
    irradiance_sensor_type VARCHAR(128),
    irradiance_sensor_serial VARCHAR(128),
    
    -- Permanent (STC) values
    ppk DOUBLE PRECISION,              -- Peak power [W] @ STC
    rs DOUBLE PRECISION,                -- Series resistance [Ω]
    rp DOUBLE PRECISION,               -- Parallel resistance [Ω]
    
    -- Dynamic values (ambient conditions)
    voc DOUBLE PRECISION,              -- Open circuit voltage [V]
    isc DOUBLE PRECISION,              -- Short circuit current [A]
    vpmax DOUBLE PRECISION,            -- Voltage at MPP [V]
    ipmax DOUBLE PRECISION,            -- Current at MPP [A]
    pmax DOUBLE PRECISION,             -- Max power [W]
    ff DOUBLE PRECISION,               -- Fill factor [%]
    
    -- Environmental
    tmod DOUBLE PRECISION,             -- Module temperature [°C]
    eeff DOUBLE PRECISION,            -- Effective irradiance [W/m²]
    
    -- Reference/nominal comparison (deviation %)
    ppk_deviation DOUBLE PRECISION,
    rs_deviation DOUBLE PRECISION,
    rp_deviation DOUBLE PRECISION,
    
    -- Metadata
    customer_id INTEGER,
    module_id INTEGER,
    customer VARCHAR(256),
    module_type VARCHAR(256),
    tcell DOUBLE PRECISION,            -- Cell temperature [°C]
    remarks TEXT
);

-- I-V curve data points (~100 per measurement)
CREATE TABLE IF NOT EXISTS iv_curve_points (
    id SERIAL PRIMARY KEY,
    measurement_id INTEGER NOT NULL REFERENCES measurements(id) ON DELETE CASCADE,
    point_index INTEGER NOT NULL,
    voltage DOUBLE PRECISION NOT NULL,
    current DOUBLE PRECISION NOT NULL,
    UNIQUE(measurement_id, point_index)
);

-- Allow duplicate source_file for different imports
ALTER TABLE measurements DROP CONSTRAINT IF EXISTS measurements_source_file_measured_at_key;

-- Optional: customers (for reference)
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(256),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Optional: module database (nominal specs for comparison)
CREATE TABLE IF NOT EXISTS modules (
    id SERIAL PRIMARY KEY,
    manufacturer VARCHAR(128),
    model VARCHAR(128),
    ppk_nominal DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Site metadata for future site-level organization
CREATE TABLE IF NOT EXISTS site_details (
    id SERIAL PRIMARY KEY,
    site_code VARCHAR(128) NOT NULL UNIQUE,
    site_name VARCHAR(256) NOT NULL,
    layout_name VARCHAR(256),
    source_document VARCHAR(512),
    country VARCHAR(128),
    region VARCHAR(128),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    plant_capacity_mw DOUBLE PRECISION,
    module_type VARCHAR(256),
    module_count INTEGER,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_strings (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES site_details(id) ON DELETE CASCADE,
    string_code VARCHAR(64) NOT NULL,
    section_no INTEGER NOT NULL,
    block_no INTEGER NOT NULL,
    string_no INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(site_id, string_code)
);

-- Auth / RBAC tables
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    role_code VARCHAR(50) NOT NULL UNIQUE,
    role_name VARCHAR(100) NOT NULL,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('global', 'project'))
);

CREATE TABLE IF NOT EXISTS user_global_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, role_id)
);

INSERT INTO roles (role_code, role_name, scope_type) VALUES
    ('manager', 'Manager', 'global'),
    ('project_manager', 'Project Manager', 'project'),
    ('supervisor', 'Supervisor', 'project'),
    ('inventory_keeper', 'Inventory Keeper', 'project')
ON CONFLICT (role_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Project linkage (site_id FK on both measurement tables — nullable for backward compat)
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS site_id INTEGER REFERENCES site_details(id) ON DELETE SET NULL;
ALTER TABLE pvpm_measurements ADD COLUMN IF NOT EXISTS site_id INTEGER REFERENCES site_details(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_measurements_site_id ON measurements(site_id);
CREATE INDEX IF NOT EXISTS idx_pvpm_measurements_site_id ON pvpm_measurements(site_id);

CREATE INDEX idx_measurements_measured_at ON measurements(measured_at);
CREATE INDEX idx_measurements_source_file ON measurements(source_file);
CREATE INDEX idx_iv_curve_measurement ON iv_curve_points(measurement_id);
CREATE INDEX idx_site_strings_site_id ON site_strings(site_id);
CREATE INDEX idx_site_strings_section_block ON site_strings(site_id, section_no, block_no);

-- PVPM connector tables (v1 schema — camelCase fields stored in snake_case columns)
CREATE TABLE IF NOT EXISTS pvpm_devices (
    id SERIAL PRIMARY KEY,
    serial_number VARCHAR(128) UNIQUE,
    model VARCHAR(128),
    firmware_version VARCHAR(64),
    calibration_date TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS pvpm_measurements (
    id VARCHAR(64) PRIMARY KEY,
    device_id INTEGER REFERENCES pvpm_devices(id),
    external_measurement_key VARCHAR(128),
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    customer VARCHAR(256),
    installation VARCHAR(256),
    string_no VARCHAR(64),
    module_type VARCHAR(256),
    module_reference VARCHAR(256),
    modules_series INTEGER,
    modules_parallel INTEGER,
    nominal_power_w DOUBLE PRECISION,
    ppk_wp DOUBLE PRECISION,
    rs_ohm DOUBLE PRECISION,
    rp_ohm DOUBLE PRECISION,
    voc_v DOUBLE PRECISION,
    isc_a DOUBLE PRECISION,
    vpmax_v DOUBLE PRECISION,
    ipmax_a DOUBLE PRECISION,
    ff_percent DOUBLE PRECISION,
    sweep_duration_ms DOUBLE PRECISION,
    irradiance_w_m2 DOUBLE PRECISION,
    sensor_temp_c DOUBLE PRECISION,
    module_temp_c DOUBLE PRECISION,
    irradiance_sensor_type VARCHAR(128),
    irradiance_sensor_serial VARCHAR(128),
    raw_payload_json TEXT,
    import_source VARCHAR(128),
    sync_status VARCHAR(32) DEFAULT 'synced',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pvpm_curve_points (
    id SERIAL PRIMARY KEY,
    measurement_id VARCHAR(64) NOT NULL REFERENCES pvpm_measurements(id) ON DELETE CASCADE,
    point_index INTEGER NOT NULL,
    voltage_v DOUBLE PRECISION NOT NULL,
    current_a DOUBLE PRECISION NOT NULL,
    UNIQUE(measurement_id, point_index)
);

CREATE TABLE IF NOT EXISTS pvpm_sync_logs (
    id SERIAL PRIMARY KEY,
    measurement_id VARCHAR(64),
    direction VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    error_message TEXT,
    payload_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pvpm_measurements_measured_at ON pvpm_measurements(measured_at);
CREATE INDEX IF NOT EXISTS idx_pvpm_curve_points_measurement ON pvpm_curve_points(measurement_id);

-- ── String scan tables (v4) ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS string_id_pattern (
    id BIGSERIAL PRIMARY KEY,
    pattern_code VARCHAR(50) NOT NULL UNIQUE,
    pattern_name VARCHAR(100) NOT NULL,
    match_regex TEXT NOT NULL,
    parse_regex TEXT NOT NULL,
    example_value VARCHAR(100),
    level_count INTEGER NOT NULL,
    levels_json JSONB NOT NULL,
    max_digits_per_level INTEGER NOT NULL DEFAULT 2,
    no_leading_zero BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_string_pattern (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    pattern_id BIGINT NOT NULL REFERENCES string_id_pattern(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
    assigned_by BIGINT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_site_one_active_pattern
    ON site_string_pattern(site_id) WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS string_scan_run (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    pattern_id BIGINT NOT NULL REFERENCES string_id_pattern(id),
    detected_pattern_code VARCHAR(50) NOT NULL,
    confidence NUMERIC(5,4) NOT NULL,
    page_no INTEGER NOT NULL DEFAULT 1,
    compare_to_design BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS string_scan_issue (
    id BIGSERIAL PRIMARY KEY,
    scan_run_id BIGINT NOT NULL REFERENCES string_scan_run(id) ON DELETE CASCADE,
    issue_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_key VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS string_scan_summary (
    id BIGSERIAL PRIMARY KEY,
    scan_run_id BIGINT NOT NULL REFERENCES string_scan_run(id) ON DELETE CASCADE,
    expected_total_strings INTEGER,
    found_total_valid_strings INTEGER NOT NULL,
    total_invalid_string_names INTEGER NOT NULL,
    total_duplicates INTEGER NOT NULL,
    expected_inverter_groups INTEGER,
    found_inverter_groups INTEGER NOT NULL,
    matches_design BOOLEAN NOT NULL
);

INSERT INTO string_id_pattern (
    pattern_code, pattern_name, match_regex, parse_regex, example_value,
    level_count, levels_json, max_digits_per_level, no_leading_zero, is_active
) VALUES
(
    'S_DOT_3', 'S.1.2.3 format',
    '^S\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$',
    '^S\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$',
    'S.1.2.3', 3, '["section","inverter","string"]'::JSONB, 2, TRUE, TRUE
),
(
    'S4_LEVEL', 'S1.1.2.3 format',
    '^S(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)\.(?:[1-9]\d?)$',
    '^S([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$',
    'S1.1.2.3', 4, '["major_section","block","inverter","string"]'::JSONB, 2, TRUE, TRUE
)
ON CONFLICT (pattern_code) DO UPDATE SET
    pattern_name = EXCLUDED.pattern_name,
    match_regex = EXCLUDED.match_regex,
    parse_regex = EXCLUDED.parse_regex,
    example_value = EXCLUDED.example_value,
    level_count = EXCLUDED.level_count,
    levels_json = EXCLUDED.levels_json,
    max_digits_per_level = EXCLUDED.max_digits_per_level,
    no_leading_zero = EXCLUDED.no_leading_zero,
    updated_at = NOW();
