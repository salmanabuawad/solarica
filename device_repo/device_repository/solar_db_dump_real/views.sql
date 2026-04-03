
CREATE OR REPLACE VIEW vw_devices AS
SELECT
    d.device_id,
    c.category_code,
    c.category_name,
    m.manufacturer_name,
    d.model_name,
    d.brand_name,
    d.technology,
    d.description,
    s.source_code,
    s.name AS source_name,
    d.source_release_date,
    d.source_last_update,
    d.is_hybrid
FROM device_models d
JOIN asset_categories c ON c.category_id = d.category_id
JOIN manufacturers m ON m.manufacturer_id = d.manufacturer_id
JOIN data_sources s ON s.source_id = d.source_id;

CREATE OR REPLACE VIEW vw_device_vulnerabilities AS
SELECT
    d.device_id,
    mf.manufacturer_name,
    d.model_name,
    v.cve_id,
    v.advisory_id,
    v.title,
    v.severity,
    v.cvss_v3,
    v.published_date
FROM device_models d
JOIN manufacturers mf ON mf.manufacturer_id = d.manufacturer_id
JOIN vulnerability_matches vm
  ON mf.manufacturer_name ILIKE vm.manufacturer_pattern
 AND d.model_name ILIKE vm.model_pattern
JOIN vulnerabilities v ON v.vulnerability_id = vm.vulnerability_id;
