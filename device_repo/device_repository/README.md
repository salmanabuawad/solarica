# Device repository for Hamadiya and Qunitra-FPV

This package contains a SQLite database plus CSV exports for the device inventory visible in the uploaded drawings.

## Files
- devices_repository.sqlite
- schema.sql
- sites.csv
- devices.csv
- device_specs.csv
- vulnerabilities.csv
- repository.json

## Notes
- model_raw is what the drawing shows.
- model_normalized is a best-effort normalized identifier.
- is_exact_model_confirmed = 0 means the drawing did not show enough detail to prove the exact vendor suffix/variant.
- Some vulnerability rows are adjacent_monitoring_platform_only. That means the advisory is relevant to the vendor ecosystem (for example WiNet-S / iSolarCloud) but the exact affected communications module is not explicitly shown on the drawing.
