
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sites (site_id INTEGER PRIMARY KEY, site_name TEXT NOT NULL UNIQUE, country TEXT, region TEXT, source_notes TEXT);
CREATE TABLE IF NOT EXISTS devices (device_id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL, area TEXT, category TEXT NOT NULL, manufacturer TEXT, model_raw TEXT, model_normalized TEXT, quantity INTEGER, unit TEXT DEFAULT 'ea', is_exact_model_confirmed INTEGER DEFAULT 1, role TEXT, source_notes TEXT, FOREIGN KEY (site_id) REFERENCES sites(site_id));
CREATE TABLE IF NOT EXISTS device_specs (spec_id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, spec_key TEXT NOT NULL, spec_value TEXT NOT NULL, source_type TEXT DEFAULT 'web', source_note TEXT, FOREIGN KEY (device_id) REFERENCES devices(device_id));
CREATE TABLE IF NOT EXISTS vulnerabilities (vuln_id INTEGER PRIMARY KEY, manufacturer TEXT, product_scope TEXT NOT NULL, cve_id TEXT, title TEXT NOT NULL, severity TEXT, affected_versions TEXT, fixed_versions TEXT, advisory_source TEXT, applicability TEXT NOT NULL, notes TEXT);
CREATE TABLE IF NOT EXISTS device_vulnerabilities (id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL, vuln_id INTEGER NOT NULL, relationship_type TEXT NOT NULL, FOREIGN KEY (device_id) REFERENCES devices(device_id), FOREIGN KEY (vuln_id) REFERENCES vulnerabilities(vuln_id));
