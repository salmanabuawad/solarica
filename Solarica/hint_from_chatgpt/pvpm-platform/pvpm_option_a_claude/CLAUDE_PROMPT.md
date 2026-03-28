You are building a production-ready MVP for a mission-based solar measurement workflow around the PVPM1540X IV curve tracer.

# Product Goal
Implement Option A — Semi-automated mission workflow:
- A user creates a mission with a site and ordered string names.
- An operator opens the mission on a laptop/tablet.
- The UI shows one current string at a time.
- The operator connects the physical PV string.
- The app triggers a measurement through a local Python device service.
- The result is saved to the backend and linked to the active mission item.
- The system advances to the next string.

# Critical Device Assumptions
Do NOT model the PVPM as a filesystem or as a mission executor.
The app/backend is the source of truth for:
- missions
- strings
- ordering
- completion state
- notes
- result linkage

The PVPM should be treated as:
- a measurement engine
- a USB-connected instrument
- a source of raw measurements

# Tech Stack
- Frontend: React + TypeScript
- Backend API: Python FastAPI
- Device service: Python, Windows-friendly, pluggable driver interface
- DB: PostgreSQL

# Deliverables
1. Backend API project in FastAPI
2. React frontend with mission list and mission execution screens
3. Device adapter interface with a mock PVPM adapter first
4. PostgreSQL models / migrations
5. Clean README and run instructions

# Functional Requirements
## Mission management
- Create mission
- Add ordered mission items
- Each mission item represents one string to measure
- Track statuses: pending, measuring, completed, skipped, failed

## Mission execution
- Open a mission
- Show current item clearly
- Provide buttons:
  - Confirm ready
  - Measure
  - Retry
  - Skip
  - Add note
- On Measure:
  - call backend
  - backend calls device service
  - backend stores raw + parsed result
  - backend marks item completed on success
  - backend advances current pointer

## Measurement record
Store:
- mission id
- mission item id
- site id
- string name
- operator id if available
- device serial if available
- measurement timestamp
- raw payload
- parsed electrical values
- notes

## Safety / UX
- show warning that operator must isolate DC and follow field safety procedures
- require explicit confirmation before measurement
- do not auto-advance without successful save

# Non-Functional Requirements
- Keep device integration abstract behind interface/class
- Add a mock adapter returning realistic fake values
- Make it easy later to replace mock with real FTDI/COM integration
- Use clear typing and validation
- Keep code modular and readable

# Frontend Screens
1. Mission list
2. Mission details
3. Mission execution
4. Measurement result detail

# Suggested frontend behavior
Mission execution page should display:
- mission name
- site name
- current string name
- progress (e.g. 2 of 10)
- checklist
- notes field
- result summary after measurement

# Backend Endpoints
Implement endpoints for:
- create mission
- list missions
- get mission details
- start execution of item
- perform measurement for current item
- skip item
- add note
- list measurements
- get measurement by id

# Device Service
Create an interface like:
- connect()
- get_device_info()
- start_measurement()
- fetch_result()
- healthcheck()

Implement a MockPvpmAdapter that returns deterministic sample results.

# Sample parsed result fields
- voc
- isc
- vmp
- imp
- pmax
- ff
- rs
- rp
- irradiance
- module_temp

# Code Quality
- strong typing
- error handling
- loading and retry states
- comments only where needed
- production-style folder structure

# Nice to Have
- ability to retry same mission item without losing failed attempts
- audit log table
- CSV export of results

Create the codebase and include sample data for local testing.
