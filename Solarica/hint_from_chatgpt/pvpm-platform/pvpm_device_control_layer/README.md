# PVPM Device Control Layer

A clean-room local bridge for PVPM workflows.

## What this is

This project gives you a **device control layer** for the workflow you chose:
- create mission in your app
- set `site` and `part/string` metadata in the bridge session
- guide the operator through measurements
- trigger measurement through a device adapter
- save raw `.SUI` and structured JSON

## Important limitation

This code is **production-shaped**, but the actual low-level PVPM command protocol is **not implemented** because the uploaded materials do not publish an official serial/D2XX command set.

So the project includes:
- a complete local API
- mission/session state management
- metadata injection model
- file ingestion/parsing hooks
- a **simulator adapter** that works now
- a **serial adapter stub** where the real protocol goes later

## Architecture

React/Electron/Web UI -> localhost FastAPI bridge -> adapter -> PVPM

## Main concepts

- **Session metadata**: `site_name`, `part_name`, `module_part_number`
- **Measurement session**: one operator-guided measurement cycle
- **Adapter**: transport/protocol implementation
- **Storage**: raw files + parsed JSON + session metadata

## Endpoints

- `GET /api/health`
- `GET /api/device`
- `POST /api/session`
- `GET /api/session/{session_id}`
- `POST /api/session/{session_id}/metadata`
- `POST /api/session/{session_id}/measure`
- `GET /api/session/{session_id}/result`
- `GET /api/results`

## Run

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8765
```

## Switch adapter mode

By default the app uses `simulator` mode.

Set environment variable:

```bash
PVPM_ADAPTER=serial
```

The serial adapter is intentionally a stub. Replace methods in:
- `app/adapters/serial_adapter.py`

## Protocol integration plan

Implement these methods in the serial adapter:
- `detect_device()`
- `open()`
- `close()`
- `apply_metadata(site_name, part_name, module_part_number)`
- `trigger_measurement()`
- `fetch_result()`

If the real device cannot accept metadata writes before measurement, keep metadata authoritative in your DB and attach it at save time.

## Files written

Output folder:
- `./data/raw`
- `./data/json`

Each measurement stores:
- raw SUI bytes (simulated in current mode)
- enriched JSON payload
- session metadata

