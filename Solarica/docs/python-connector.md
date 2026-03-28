# Python Connector — Installation & Packaging Guide

The Python connector is the **reference implementation** of the Solarica connector API.
It runs as a standalone HTTP server on `http://127.0.0.1:8765`.

---

## Requirements (development)

| Component | Version |
|-----------|---------|
| Python | 3.11+ |
| pip | latest |

---

## Quick start (development)

```bash
cd connector/python

# Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set PVPM_DRIVER=mock (or vendor_export)

# Run
uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

Browse to `http://127.0.0.1:8765/docs` for the Swagger UI.

---

## Driver configuration

Edit `.env`:

```dotenv
# mock: synthetic data for testing
# vendor_export: reads PVPM export files from WATCH_FOLDER
# serial: direct COM port (protocol pending)
PVPM_DRIVER=vendor_export

# Folder where the PVPM Transfer software exports files
WATCH_FOLDER=C:\PVPM\exports

# Cloud backend
BACKEND_BASE_URL=http://your-server:8000
```

---

## Vendor export driver setup

1. Install the PVPM vendor USB driver and Transfer software (from EKO / IMT / vendor portal).
2. Configure the Transfer software to export measurements to a folder.
3. Set `WATCH_FOLDER` in `.env` to that folder.
4. Set `PVPM_DRIVER=vendor_export`.
5. Run the connector — click "Pull measurements from device" in the web app.

The connector reads `.csv`, `.txt`, `.asc`, `.dat`, `.xls`, `.xlsx` files from the folder.

**Note:** The vendor USB driver installation is entirely separate from this connector.
This connector only reads the files that the vendor software produces.

---

## Packaging with PyInstaller

```bash
cd connector/python

# Install PyInstaller
pip install pyinstaller

# Build (one-dir bundle)
pyinstaller solarica_connector.spec

# Output: dist/solarica_connector/
```

### Distribute

Zip the `dist/solarica_connector/` folder. Users:
1. Extract the zip.
2. Copy `.env.example` to `.env` and edit.
3. Run `solarica_connector.exe` (Windows) or `./solarica_connector` (Linux/macOS).

No Python installation required on the target machine.

---

## Running as a Windows Service

Use NSSM (Non-Sucking Service Manager) or WinSW:

```powershell
# NSSM example
nssm install SolaricaConnector "C:\SolaricaConnector\solarica_connector.exe"
nssm set SolaricaConnector AppDirectory "C:\SolaricaConnector"
nssm start SolaricaConnector
```

---

## Running as a systemd service (Linux)

```ini
# /etc/systemd/system/solarica-connector.service
[Unit]
Description=Solarica Python Connector
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/solarica-connector
ExecStart=/opt/solarica-connector/solarica_connector
EnvironmentFile=/opt/solarica-connector/.env
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now solarica-connector
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PVPM_DRIVER` | `mock` | Driver: `mock`, `vendor_export`, `serial` |
| `BACKEND_BASE_URL` | `http://localhost:8000` | Cloud backend for sync upload |
| `LOCAL_DB_PATH` | `./data/connector.db` | SQLite cache location |
| `WATCH_FOLDER` | `./import_watch` | Export folder (vendor_export driver) |
| `SERIAL_BAUD_RATE` | `115200` | Baud rate (serial driver) |
| `SERIAL_TIMEOUT_SECONDS` | `3` | Serial timeout (serial driver) |
| `CONNECTOR_PORT` | `8765` | HTTP listen port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Project structure

```
connector/python/
├── main.py                     # FastAPI app + all endpoints
├── requirements.txt            # Python dependencies
├── solarica_connector.spec     # PyInstaller build spec
├── .env.example                # Environment template
└── app/
    ├── config.py               # Settings (pydantic-settings)
    ├── database.py             # SQLAlchemy + SQLite models
    ├── schemas.py              # Pydantic request/response schemas
    ├── driver_factory.py       # Driver selection
    ├── mock_data.py            # Synthetic measurement generator
    ├── repository.py           # SQLite CRUD
    ├── services.py             # Import + sync business logic
    ├── export.py               # CSV / JSON export
    └── drivers/
        ├── base.py             # PVPMDriver Protocol
        ├── mock_driver.py      # Mock (demo)
        ├── serial_driver.py    # COM port (protocol pending)
        └── vendor_export_driver.py  # Read PVPM export files
```
