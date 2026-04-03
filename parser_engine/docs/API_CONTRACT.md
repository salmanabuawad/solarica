# API Contract

## POST /run

Request:
```json
{
  "files": ["/absolute/path/site.pdf"],
  "force_ocr": false
}
```

Response includes:
- `job_id`
- `status`
- `steps`
- `results`

## POST /step

Request:
```json
{
  "step_id": "validate_output",
  "files": ["/absolute/path/site.pdf"],
  "resolve_dependencies": true,
  "force_ocr": false
}
```

## GET /progress/{job_id}
Returns stored job progress and final results.
