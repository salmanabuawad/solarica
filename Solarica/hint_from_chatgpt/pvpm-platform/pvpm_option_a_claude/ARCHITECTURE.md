# Architecture

## Principle
The backend owns workflow state. The PVPM does not.

## Components

### 1. React frontend
Responsibilities:
- Create and browse missions
- Guide operator through active mission
- Display current string to measure
- Trigger measurement
- Show result and progress

### 2. FastAPI backend
Responsibilities:
- Store missions, mission items, measurements
- Validate transitions
- Call device bridge/service
- Persist raw and parsed measurement data

### 3. Device bridge/service
Responsibilities:
- Connect to PVPM over USB/serial/FTDI
- Expose a stable API to backend
- Normalize device responses
- Return parsed + raw data

### 4. PostgreSQL
Responsibilities:
- Persist structured mission and result data

## Flow
1. User creates mission.
2. Mission has ordered items: S1, S2, S3.
3. Operator opens execution screen.
4. Operator confirms readiness.
5. Backend calls device service to measure.
6. Result is stored and linked to current mission item.
7. Item marked completed.
8. Next item becomes active.

## State model
Mission statuses:
- draft
- ready
- in_progress
- completed
- cancelled

Mission item statuses:
- pending
- measuring
- completed
- skipped
- failed

## Future-proofing
The real PVPM integration should be an adapter. Keep mock and real adapter behind same interface.
