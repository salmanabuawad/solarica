# Module catalog handling for PVPM

This build adds a connector-side Module catalog.

## What it does

- stores module records locally in the connector database
- lets the operator create / list modules through the connector API
- lets the active session binding attach `modulePartNumber` to incoming measurements

## What it does not claim

The available documentation supports PC-side module database handling through the Windows software workflow,
but this build does not claim a confirmed persistent module-database write into the PVPM device itself.

## API

- `GET /api/catalog/modules`
- `POST /api/catalog/modules`
- `POST /api/session/binding`

## Recommended flow

1. Create or import module records into the connector catalog
2. Set active session binding with the selected module part number
3. Import / download measurements from the PVPM
4. Measurements are tagged with the module part number
