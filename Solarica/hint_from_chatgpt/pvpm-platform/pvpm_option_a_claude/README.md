# PVPM1540X Option A Mission Workflow Package

This package is prepared for Claude/Cursor to implement a **semi-automated mission-based measurement workflow** for the **PVPM1540X** device.

## Goal
Build a system where:
1. The user creates a measurement mission in the app.
2. The app lists strings to be measured (for example: S1, S2, S3).
3. The operator is guided step-by-step.
4. The PC service triggers the PVPM measurement.
5. The result is saved in the backend and tagged with the mission item metadata.
6. The flow continues to the next string.

## Important Constraint
Do **not** assume the PVPM device supports:
- folders on device
- project hierarchy on device
- mission queue on device
- arbitrary file writing on device

Treat the PVPM as a **measurement instrument**, not as a workflow or storage system.

## Recommended System
- Frontend: React web app
- Backend: Python API
- Device bridge: Python Windows service/agent
- Database: PostgreSQL
- File/raw measurement storage: filesystem or object storage

## Package contents
- `CLAUDE_PROMPT.md` — ready-to-paste implementation prompt for Claude
- `ARCHITECTURE.md` — architecture and responsibilities
- `API_SPEC.yaml` — proposed REST API
- `DB_SCHEMA.sql` — starter PostgreSQL schema
- `MISSION_FLOW.md` — UX and step-by-step operator flow
- `SAMPLE_DATA.json` — example mission and measurement payloads
- `IMPLEMENTATION_NOTES.md` — practical notes and milestones

