# Refactor Notes

## Main decisions
- Kept the current domain-oriented backend in `backend/app/` as the future path.
- Preserved the older backend under `backend/legacy/` to avoid data loss.
- Moved PVPM parser code into a dedicated package path:
  - `backend/app/parsers/pvpm/parser_v4_1.py`

## Suggested follow-up
- Create `backend/app/api/v1/endpoints/` and migrate legacy endpoints one by one.
- Add a single settings module consumed by frontend and bridge.
- Move connector contracts into `docs/connector/` if they are documentation-only.
- Add tests around parser normalization and measurement import.
