Solarica .NET Connector
=======================

The local connector runs on the PC connected to your PVPM 1540X device.
It caches measurements in a local SQLite database and syncs them to the
Solarica cloud web app. Runs as a Windows Service — survives reboots
automatically.

Requirements
------------
  - .NET 8 SDK   →  https://dotnet.microsoft.com/download/dotnet/8.0
  - PVPM vendor USB driver (separate install from EKO / IMT / Solmetric)
  - Windows 10/11 (primary). Linux / macOS supported via ./install.sh

Quick Start (Windows — installs as a Service)
---------------------------------------------
  1. Right-click  install.bat  →  "Run as administrator"
     (builds the app, installs it as a Windows Service, starts it)

  2. Edit  dist\appsettings.json  to configure:
       "PvpmDriver": "vendor_export"
       "BackendBaseUrl": "https://solarica.wavelync.com"
       "WatchFolder": "C:\\path\\to\\pvpm\\exports"

  3. Restart the service to apply changes:
       sc stop SolaricaConnector
       sc start SolaricaConnector

  The connector listens on  http://127.0.0.1:8765

Run Without Installing as Service (Windows)
-------------------------------------------
  Double-click  start.bat
  (requires install.bat to have been run at least once to build the binary)

Quick Start (Linux / macOS)
---------------------------
  chmod +x install.sh && ./install.sh
  ./start.sh

Configuration (dist\appsettings.json)
--------------------------------------
  PvpmDriver    - "mock" | "serial"   (vendor_export coming in .NET connector)
  BackendBaseUrl - https://solarica.wavelync.com
  LocalDbPath   - ./data/connector.db
  Urls          - http://127.0.0.1:8765

Driver Modes
------------
  mock    - Generates synthetic data for testing (no device needed)
  serial  - Direct COM port connection (System.IO.Ports)

Uninstall Service
-----------------
  Right-click  uninstall.bat  →  "Run as administrator"

API
---
  Health:        GET  http://127.0.0.1:8765/health
  Device status: GET  http://127.0.0.1:8765/api/device/status
  Measurements:  GET  http://127.0.0.1:8765/api/measurements
  Sync:          POST http://127.0.0.1:8765/api/sync/upload

Support
-------
  https://solarica.wavelync.com
