Solarica Python Connector
=========================

The local connector runs on the PC connected to your PVPM 1540X device.
It caches measurements in a local SQLite database and syncs them to the
Solarica cloud web app.

Requirements
------------
  - Python 3.11 or higher  →  https://python.org/downloads
  - PVPM vendor USB driver (separate install from EKO / IMT / Solmetric)

Quick Start (Windows)
---------------------
  1. Double-click  install.bat
     (creates virtual env, installs dependencies, creates .env)

  2. Open .env in Notepad and set:
       PVPM_DRIVER=vendor_export
       WATCH_FOLDER=C:\path\to\pvpm\exports
       BACKEND_BASE_URL=https://solarica.wavelync.com

  3. Double-click  start.bat
     The connector listens on  http://127.0.0.1:8765

Quick Start (Linux / macOS)
---------------------------
  1.  chmod +x install.sh && ./install.sh
  2.  Edit .env
  3.  ./start.sh

Driver Modes
------------
  mock          - Generates synthetic data for testing (no device needed)
  vendor_export - Watches a folder for files exported by PVPM Transfer software
                  Set WATCH_FOLDER= to that folder path
  serial        - Direct COM port / ttyUSB connection (protocol in progress)

Configuration (.env)
--------------------
  PVPM_DRIVER         = mock | vendor_export | serial
  BACKEND_BASE_URL    = https://solarica.wavelync.com
  LOCAL_DB_PATH       = ./data/connector.db
  WATCH_FOLDER        = ./import_watch
  CONNECTOR_PORT      = 8765
  LOG_LEVEL           = INFO

API
---
  Health:        GET  http://127.0.0.1:8765/health
  Device status: GET  http://127.0.0.1:8765/api/device/status
  Measurements:  GET  http://127.0.0.1:8765/api/measurements
  Sync:          POST http://127.0.0.1:8765/api/sync/upload

Support
-------
  https://solarica.wavelync.com
