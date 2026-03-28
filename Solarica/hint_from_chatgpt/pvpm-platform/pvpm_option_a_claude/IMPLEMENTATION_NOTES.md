# Implementation Notes

## Phase 1
- Build backend models and CRUD for missions
- Build mission execution UI
- Add mock PVPM adapter
- Save measurements

## Phase 2
- Add Windows local device service
- Define adapter contract over HTTP or local IPC
- Add device health screen

## Phase 3
- Add real FTDI/COM integration
- Add retry logic and richer error states
- Add exports and reports

## Suggested adapter interface in Python
```python
class PvpmAdapter:
    def connect(self) -> None: ...
    def healthcheck(self) -> dict: ...
    def get_device_info(self) -> dict: ...
    def start_measurement(self) -> None: ...
    def fetch_result(self) -> dict: ...
```

## Suggested backend rule
The backend should never mark a mission item as completed before the measurement record is successfully committed.

## Suggested UI rule
Always show the active string name in very large text to reduce field mistakes.
