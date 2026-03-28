# .NET Connector — Installation & Packaging Guide

The .NET connector implements the same REST API as the Python connector.
It is optimised for Windows environments where running as a **Windows Service** is preferred.

---

## Requirements

| Component | Version |
|-----------|---------|
| .NET SDK | 8.0+ |
| OS | Windows 10/11, Windows Server 2019+ (primary); Linux and macOS supported |

---

## Quick start (development)

```bash
cd connector/dotnet/SolaricaConnector

# Restore packages
dotnet restore

# Run (default: http://127.0.0.1:8765)
dotnet run
```

Browse to `http://127.0.0.1:8765/health` to verify.

---

## Configuration

Edit `appsettings.json`:

```json
{
  "Urls": "http://127.0.0.1:8765",
  "PvpmDriver": "mock",
  "BackendBaseUrl": "http://your-server:8000",
  "LocalDbPath": "./data/connector.db"
}
```

Override with environment variables (prefix: none — standard ASP.NET Core):

```
PVPM_DRIVER=mock
BACKEND_BASE_URL=http://localhost:8000
LOCAL_DB_PATH=./data/connector.db
```

---

## Publishing a self-contained executable

```bash
# Windows x64 — single-folder publish
dotnet publish -r win-x64 -c Release --self-contained \
  -o ./publish/win-x64

# Linux x64
dotnet publish -r linux-x64 -c Release --self-contained \
  -o ./publish/linux-x64
```

The output folder is self-contained — no .NET runtime required on the target machine.

---

## Installing as a Windows Service

```powershell
# Copy publish output to C:\SolaricaConnector\
# Then:

sc create SolaricaConnector `
  binPath= "C:\SolaricaConnector\solarica_connector.exe" `
  start= auto `
  DisplayName= "Solarica Local Connector"

sc description SolaricaConnector "Solarica connector for PVPM 1540X measurement sync"
sc start SolaricaConnector
```

To remove:
```powershell
sc stop SolaricaConnector
sc delete SolaricaConnector
```

Logs appear in **Windows Event Viewer → Application**.

---

## Running as a systemd service (Linux)

```ini
# /etc/systemd/system/solarica-connector.service
[Unit]
Description=Solarica .NET Connector
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/solarica-connector
ExecStart=/opt/solarica-connector/solarica_connector
Environment=ASPNETCORE_URLS=http://127.0.0.1:8765
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Driver support

| Driver | Config value | Status |
|--------|-------------|--------|
| Mock | `mock` | Complete |
| Serial | `serial` | Port enumeration complete; protocol pending |
| Vendor export | *(not yet ported)* | Port from Python reference |

To add the vendor export driver:
1. Create `Services/VendorExportDriver.cs` implementing `IDeviceDriver`.
2. Add a CSV/XLS parser (see Python reference in `connector/python/app/drivers/vendor_export_driver.py`).
3. Register it in `Program.cs`.

---

## Project structure

```
connector/dotnet/SolaricaConnector/
├── SolaricaConnector.csproj    # SDK-style project, .NET 8, Windows Service
├── Program.cs                  # Minimal API endpoints + DI setup
├── appsettings.json            # Configuration
├── Models/
│   └── ConnectorModels.cs      # Shared record types (match Python schemas)
├── Data/
│   └── ConnectorDbContext.cs   # EF Core + SQLite entities
└── Services/
    ├── IDeviceDriver.cs        # Driver interface
    ├── MockDriver.cs           # Mock driver + data generator
    ├── SerialDriver.cs         # System.IO.Ports driver
    ├── MeasurementRepository.cs # SQLite CRUD via EF Core
    └── SyncService.cs          # Upload unsynced to cloud backend
```

---

## API contract compliance

The .NET connector implements every endpoint defined in
`connector/api-contract/openapi.yaml`. All JSON field names are camelCase to
match the Python connector. The web app is entirely agnostic to the runtime —
it works with either connector without any code changes.
