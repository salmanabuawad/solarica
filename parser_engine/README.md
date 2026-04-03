# Map Parser V6+ Full Package

A runnable Python parser engine for solar map PDFs and DXF files.

What it does:
- step-based execution with progress reporting
- single-step execution with dependency resolution
- PDF text extraction with OCR fallback
- DXF text extraction
- metadata extraction
- naming-pattern detection for strings and inverters
- extraction of strings, inverters, MPPTs, devices, AC equipment, batteries
- installation type classification
- simplified relative positions for frontend rendering
- string validation, design-vs-declared-output validation
- DC/AC ratio validation
- expected production estimation
- optional IV-curve comparison

## Install

```bash
pip install -r requirements.txt
pip install -e .
```

## CLI

```bash
map-parser-v6 run --files site.pdf --json-out report.json
map-parser-v6 step --step classify_installation --files site.pdf --resolve-dependencies
map-parser-v6 step --step compare_iv_curves --files site.pdf --resolve-dependencies --inputs-json iv_inputs.json
map-parser-v6 serve --host 0.0.0.0 --port 8080
```

## Inputs for IV curve step

```json
{
  "ivcurve_payload": {
    "measurements": [
      {"string_id": "S.1.1.1", "expected_voc": 1200.0, "measured_voc": 1188.0}
    ]
  }
}
```

## Output highlights

- `project_metadata.installation`
- `naming_patterns`
- `simple_layout.pages[].inverters[]`
- `simple_layout.pages[].strings[]`
- `design_validation`
- `dc_ac_validation`
- `expected_production`
- `iv_curve_validation`
