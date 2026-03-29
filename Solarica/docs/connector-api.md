# Solarica Connector REST API

Both the Python connector and the .NET connector expose the **same REST API** on
`http://127.0.0.1:8765` (default port).
The web app never needs to know which runtime is active.

The canonical contract is in `connector/api-contract/openapi.yaml`.

---

## Base URL

```
http://127.0.0.1:8765
```

Change the port via `CONNECTOR_PORT` (.env) or `Urls` (appsettings.json).

---

## Endpoints

### Health & detection

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{ ok, version, runtime }`. `runtime` is `"python"` or `"dotnet"`. |

The web app calls `/health` on startup to auto-detect which connector is running.

---

### Device management

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/api/device/status` | — | Current connection state |
| GET | `/api/device/ports` | — | Available serial/virtual ports |
| POST | `/api/device/connect` | `{ "port": "COM3" }` | Connect to a port |
| POST | `/api/device/auto-connect` | — | Auto-pick the best FTDI / USB-Serial port for direct PVPM USB access |
| POST | `/api/device/disconnect` | — | Disconnect |

---

### Import (device → local cache)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/import/start` | Pull measurements from the active driver into SQLite |
| GET | `/api/import/status` | State, last count, unsynced count |

---

### Measurements (local cache)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/measurements` | List all cached measurements (newest first) |
| GET | `/api/measurements/{id}` | Single measurement with full I-V curve |

---

### Sync (local cache → cloud backend)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sync/upload` | Push unsynced measurements to `BACKEND_BASE_URL/api/import/batch` |

---

### Export

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/export/csv` | Download all cached measurements as CSV |
| GET | `/api/export/json` | Download all cached measurements as JSON |

---

## Measurement schema

All field names are **camelCase** in JSON responses.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | UUID hex |
| `externalMeasurementKey` | string? | Device-assigned key |
| `measuredAt` | ISO 8601 datetime | |
| `customer` | string? | |
| `installation` | string? | Site/plant name |
| `stringNo` | string? | e.g. `S.1.2.3` |
| `moduleType` | string? | |
| `ppkWp` | float? | Peak power (W) |
| `rsOhm` | float? | Series resistance (Ω) |
| `rpOhm` | float? | Parallel resistance (Ω) |
| `vocV` | float? | Open circuit voltage (V) |
| `iscA` | float? | Short circuit current (A) |
| `vpmaxV` | float? | MPP voltage (V) |
| `ipmaxA` | float? | MPP current (A) |
| `ffPercent` | float? | Fill factor (%) |
| `irradianceWM2` | float? | Irradiance (W/m²) |
| `moduleTempC` | float? | Module temperature (°C) |
| `sensorTempC` | float? | Sensor/cell temperature (°C) |
| `syncStatus` | `"unsynced"` \| `"synced"` \| `"error"` | |
| `curvePoints` | `[{ pointIndex, voltageV, currentA }]` | I-V curve data |

---

## Driver modes

| Driver | `PVPM_DRIVER` value | Description |
|--------|---------------------|-------------|
| Mock | `mock` | Synthetic data for testing and demo |
| Vendor export | `vendor_export` | Reads PVPM export files from `WATCH_FOLDER` |
| Serial (direct) | `serial` | Direct FTDI / COM access to PVPM Transfer Mode; captures streamed SUI files over USB |

---

## Adding a new driver (Python)

1. Create `connector/python/app/drivers/my_driver.py`
2. Implement all methods of `PVPMDriver` protocol (`app/drivers/base.py`)
3. Register the driver name in `app/driver_factory.py`
4. Set `PVPM_DRIVER=my_driver` in `.env`

## Adding a new driver (.NET)

1. Create `Services/MyDriver.cs` implementing `IDeviceDriver`
2. Add a case to the `IDeviceDriver` singleton factory in `Program.cs`
3. Set `PvpmDriver=my_driver` in `appsettings.json`

## Site / Part catalog and session binding

These endpoints let you create a connector-side site/part catalog and bind the active
site/part/module to incoming measurements. This is the safe implementation until a
confirmed PVPM write protocol exists.

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/api/catalog/sites` | — | List connector-side sites |
| POST | `/api/catalog/sites` | `{ "siteName": "HAMADYA", "customer": "M" }` | Create/update a connector-side site |
| GET | `/api/catalog/parts?siteName=HAMADYA` | — | List connector-side parts |
| POST | `/api/catalog/parts` | `{ "siteName": "HAMADYA", "partName": "S.2.7.2", "modulePartNumber": "TWMND-72HD580" }` | Create/update a connector-side part |
| GET | `/api/session/binding` | — | Read the active site/part binding |
| POST | `/api/session/binding` | `{ "siteName": "HAMADYA", "partName": "S.2.7.2", "customer": "M", "modulePartNumber": "TWMND-72HD580" }` | Apply site/part/module to imported measurements |

### Important note

These endpoints do **not** claim a device-side write into the PVPM itself.
They create connector-side metadata and apply it to imported measurements.

| POST | `/api/device/download-all` | — | Download all currently available data from the connected PVPM, save locally, and export JSON/CSV snapshots |


| GET | `/api/catalog/modules` | — | List connector-side modules |
| POST | `/api/catalog/modules` | `{ "modulePartNumber": "TWMND-72HD580", "manufacturer": "TW SOLAR", "technology": "mono", "nominalPowerW": 580 }` | Create/update a connector-side module |

### Module note

Modules are stored in the connector catalog and can be bound to imported measurements through `/api/session/binding`.
This does **not** confirm a persistent module database write into the PVPM device itself.
