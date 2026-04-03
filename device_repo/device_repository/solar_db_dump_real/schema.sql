
BEGIN;

CREATE TABLE IF NOT EXISTS data_sources (
    source_id INTEGER PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    publisher TEXT,
    source_url TEXT,
    retrieved_on DATE,
    release_date DATE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS asset_categories (
    category_id INTEGER PRIMARY KEY,
    category_code TEXT NOT NULL UNIQUE,
    category_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manufacturers (
    manufacturer_id INTEGER PRIMARY KEY,
    manufacturer_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS device_models (
    device_id BIGINT PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES asset_categories(category_id),
    source_id INTEGER NOT NULL REFERENCES data_sources(source_id),
    manufacturer_id INTEGER NOT NULL REFERENCES manufacturers(manufacturer_id),
    model_name TEXT NOT NULL,
    brand_name TEXT,
    technology TEXT,
    description TEXT,
    source_release_date DATE,
    source_last_update DATE,
    is_hybrid BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_device_models_category ON device_models(category_id);
CREATE INDEX IF NOT EXISTS idx_device_models_manufacturer ON device_models(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_device_models_model_name ON device_models(model_name);

CREATE TABLE IF NOT EXISTS device_specs (
    spec_id BIGINT PRIMARY KEY,
    device_id BIGINT NOT NULL REFERENCES device_models(device_id) ON DELETE CASCADE,
    spec_group TEXT NOT NULL,
    spec_key TEXT NOT NULL,
    spec_value_text TEXT,
    spec_value_num DOUBLE PRECISION,
    unit TEXT
);

CREATE INDEX IF NOT EXISTS idx_device_specs_device ON device_specs(device_id);
CREATE INDEX IF NOT EXISTS idx_device_specs_key ON device_specs(spec_key);
CREATE INDEX IF NOT EXISTS idx_device_specs_group ON device_specs(spec_group);

CREATE TABLE IF NOT EXISTS vulnerabilities (
    vulnerability_id INTEGER PRIMARY KEY,
    cve_id TEXT,
    advisory_id TEXT,
    source_name TEXT,
    title TEXT NOT NULL,
    severity TEXT,
    cvss_v3 DOUBLE PRECISION,
    published_date DATE,
    description TEXT,
    affected_product TEXT
);

CREATE INDEX IF NOT EXISTS idx_vulnerabilities_cve ON vulnerabilities(cve_id);
CREATE INDEX IF NOT EXISTS idx_vulnerabilities_advisory ON vulnerabilities(advisory_id);

CREATE TABLE IF NOT EXISTS vulnerability_matches (
    match_id INTEGER PRIMARY KEY,
    vulnerability_id INTEGER NOT NULL REFERENCES vulnerabilities(vulnerability_id) ON DELETE CASCADE,
    manufacturer_pattern TEXT,
    model_pattern TEXT,
    notes TEXT
);

COMMIT;
