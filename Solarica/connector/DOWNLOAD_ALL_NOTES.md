# Download all available data from device

This build adds a connector endpoint to download all currently available measurements
from the connected PVPM device session.

## Endpoint

`POST /api/device/download-all`

## What it does

- calls the active driver to fetch all available measurements
- applies the active session binding (site / part / customer / module)
- stores measurements in the local connector DB
- saves raw `.sui` captures under `data/raw_sui/`
- writes export snapshots under `data/exports/`
  - JSON
  - CSV

## Direct USB mode note

With direct USB access, "all available data" means:
- all measurements currently available through the active PVPM Transfer session / stream

It does not guarantee reading a hidden persistent device filesystem, because the PVPM
is treated as a streamed measurement source, not a mounted disk.
