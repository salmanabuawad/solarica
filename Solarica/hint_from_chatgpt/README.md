# Solar String Scan API Spec v3

This package contains an exact API contract for:

- DB-driven site string patterns
- fast pattern detection
- operator-drawn scan rectangles
- string classification:
  - valid_string
  - invalid_string_name
  - non_string
- summary generation
- design comparison
- issue reporting

Main files:
- `docs/api-spec.yaml`
- `docs/data-model.md`
- `backend/app/schemas/string_scan.py`
- `backend/app/api/routes_string_scan.py`
- `db/migrations/20260328_string_scan_v3.sql`
- `examples/scan-request.json`
- `examples/scan-response.json`
