# Site / Part handling for PVPM

This build adds code to:

1. create connector-side Site records
2. create connector-side Part records
3. bind an active Site / Part / Customer / Module Part Number to incoming measurements

## Why

The available documentation supports PC-side creation and selection of Customer / Plant / Part
through the Windows software workflow, but it does not prove a confirmed direct device-side
command to create a persistent Site or Part object inside the PVPM.

So this implementation uses the safe path:
- catalog in connector
- bind metadata to imported measurements
- keep room for a future direct PVPM write protocol

## API flow

1. `POST /api/catalog/sites`
2. `POST /api/catalog/parts`
3. `POST /api/session/binding`
4. `POST /api/import/start`

Imported measurements will be tagged with the active binding.

## Future extension

If a confirmed PVPM command set is discovered, add it in:
- `connector/python/app/drivers/serial_driver.py`

and then extend the binding endpoint to optionally push metadata to the device.
