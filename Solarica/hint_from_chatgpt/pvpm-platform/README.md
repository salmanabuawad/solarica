# PVPM Platform

Production-oriented monorepo scaffold for reading PVPM 1540X measurements on Windows through a local Python reader service, showing them in a React UI, and syncing them to a central Python backend.

## Apps
- `apps/web` — React + Vite + TypeScript frontend
- `apps/local-reader` — FastAPI + SQLite + pluggable driver local service
- `apps/backend` — FastAPI + SQLAlchemy + PostgreSQL backend
- `packages/shared-types` — shared TypeScript types
- `packages/shared-schemas` — OpenAPI/JSON schema notes

## Quick start
See each app README.
