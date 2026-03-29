# Solarica Refactored

This package is a cleaned and reorganized version of the original Solarica app.

## What changed
- removed Git metadata, cache files, local logs, and binary DB artifacts
- removed experimental `hint_from_chatgpt` content from the deliverable
- promoted `backend/app` as the primary backend application
- moved the older root-level backend implementation into `backend/legacy/`
- added a dedicated PVPM parser package under `backend/app/parsers/pvpm/`
- kept frontend, bridge, connector, DB, deployment, and docs folders

## Recommended structure
- `frontend/` — React + Vite UI
- `backend/app/` — primary FastAPI-style application code
- `backend/app/parsers/pvpm/` — PVPM SUI/XLS parser
- `backend/legacy/` — older backend implementation preserved for reference
- `bridge/` — local device bridge / integration layer
- `connector/` — connector-related code and contracts
- `db/` — schema and seed SQL
- `deploy/` — deployment assets
- `docs/` — architecture and workflow docs

## Immediate next steps
1. Point deployments to `backend/app/main.py` as the main backend entrypoint.
2. Gradually migrate any still-needed endpoints from `backend/legacy/` into `backend/app/`.
3. Wire the PVPM parser package into an upload/import API route.
4. Remove `mobile/` if it is not an active product line.

## Notes
This refactor is structural cleanup. It does not attempt to merge or rewrite business logic automatically.
