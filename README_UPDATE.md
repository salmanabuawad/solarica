# Solarica BHK EPL Update

This update adds support for the new BHK/SolarEdge/agro-PV site in the EPL phase.

## New backend capabilities

- Detect/extract BHK string/optimizer metadata from uploaded PDFs:
  - 288 strings
  - 6,336 optimizers
  - 12,672 modules
  - 22 optimizers/string
  - 44 modules/string
- Rebuild physical rows from visible row-number sequences:
  - 107 physical rows
- Use `BHK_E_20_Electrical Cable Plan` as authoritative string-zone source when its `10 STRINGS` / `11 STRINGS` labels sum to the metadata total.
- Generate:
  - physical rows
  - string zones
  - strings
  - optimizers
  - modules
  - validation issues

## New endpoints

```text
GET /api/epl/projects/{project_id}/string-optimizer-model
GET /api/epl/projects/{project_id}/string-optimizer-model?include_optimizers=true
GET /api/epl/projects/{project_id}/string-optimizer-export
```

## Frontend API additions

```ts
getStringOptimizerModel(projectId, includeOptimizers?)
getStringOptimizerExportUrl(projectId)
downloadStringOptimizerExport(projectId)
```

## Files included

Only changed/new files are included in this zip.
