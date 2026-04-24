# Solarica Roadmap

**Product statement.** Solarica converts solar project design documents into an
executable project model, then manages construction, material accountability,
electrical validation, operation missions, site access, collaboration, and
OT / device security — **from design to operation**.

Each phase below adds one layer of the lifecycle. Progress ticks reflect the
state of `main` at time of writing; the running deployment at
`solarica.wavelync.com` is the single source of truth.

Legend: `[x]` shipped • `[~]` partial / stub • `[ ]` not started.

---

## Phase 0 — Platform foundation (shipped)

The shell every other module plugs into.

- [x] React + Vite + TypeScript frontend (PWA)
- [x] FastAPI backend, PostgreSQL persistence
- [x] Admin auth: `admin / admin123` seeded, HMAC Bearer tokens, DB-backed `users` table + CRUD (admin / editor / viewer)
- [x] Sidebar navigation with collapsible groups + responsive drawer on iPad / mobile
- [x] 6-language i18n (`en he ar ru de fr`), RTL flip for Hebrew + Arabic
- [x] Theme + brightness + font-size preferences (persisted in `localStorage`, reflected via `data-*` attributes on `<html>`)
- [x] KortexdUI visual baseline — Tailwind + PostCSS theme tokens
- [x] Field-configurations table + admin editor — per-grid column prefs (visibility / order / pin / width)
- [x] Offline mode — Workbox precache of the app shell, IndexedDB project bundle cache, mutation queue with auto-sync on reconnect
- [x] PWA `autoUpdate` + `controllerchange` reload — new builds propagate to open tabs automatically
- [x] Nginx + `systemd` deploy (`solarica-backend.service`) with static SPA served from `/opt/solarica/frontend/dist`

---

## Phase 1 — Core lifecycle primitives

Projects, roles, documents, events, audit log.

- [x] Projects table + `GET/POST /api/projects`
- [x] Document upload (`construction_pdf`, `ramming_pdf`, `block_mapping`)
- [~] Role matrix — 3 basic roles today (`admin / editor / viewer`); blueprint calls for 12 project roles (project_manager, field_supervisor, qc_engineer, inventory_keeper, technician, electrician, construction_worker, security_guard_company, client_representative, higher_manager, site_manager, admin)
- [ ] Customer + site setup (separate from project name)
- [ ] Audit log — `audit_events (id, project_id, actor, verb, target, payload, created_at)`
- [ ] Module registry — each module self-registers routes, permissions, events, jobs, DB models, UI routes
- [~] Event bus — scaffolding in `backend/app/core/events.py` (this commit); subscribers not yet wired

---

## Phase 2 — EPL (Execution Planning Layer)

Convert a design package into an executable site model. **This is the core of
the currently running app.**

### Inputs
- [x] Construction PDF (vector extraction via PyMuPDF)
- [x] Ramming plan PDF
- [ ] Block-mapping image / spreadsheet (upload wiring in place; mapping logic pending)
- [ ] DXF / DWG imports
- [ ] Inverter / string schedules as first-class uploads
- [ ] Floating-structure plans

### Parsed outputs
- [x] Blocks / zones — polygon + label
- [x] Trackers with per-row metadata (full vs short / `S`-prefixed)
- [x] Piers (~24 130 on Ashalim with Hungarian bipartite matching)
- [x] Electrical summary (inverters, DCCB, string groups, total modules, module power, BOM, pier-type specs)
- [x] Lat / long, wind load, snow load, issue date, Nextracker model
- [ ] Panels / modules as individual records (currently only BOM totals)
- [ ] String-level geometry
- [ ] AC assets inventory
- [ ] BESS assets
- [ ] Per-device list with physical + network attributes

### Validations
- [x] Duplicate pier detection (Hungarian matching removes collisions by construction)
- [x] Missing pier numbers (gap report in grid)
- [x] Expected vs actual counts (trackers / piers / modules) with tolerance band
- [ ] Duplicate strings
- [ ] Missing strings
- [ ] Inverter count mismatch across documents
- [ ] MPPT / string mismatch
- [ ] BOM vs drawing mismatch
- [ ] Block-naming mismatch between documents
- [ ] Document conflict detection (two sources disagree)

### UI
- [x] Project Info tab — site / structure / electrical / module / validation metadata cards
- [x] Details tab — Grid (ag-grid, virtual-scrolled, field-config-driven) + Map (MapLibre, 24 k piers in one GL draw call)
- [x] Pier status pill with icon + colour (New / In Progress / Implemented / Approved / Rejected / Fixed)
- [x] Map pier colouring by status + coloured halo + symbol icons
- [x] Status change event table (`pier_status_events`) with description + photo / video attachments on Rejected
- [x] Bulk status update via `POST /api/projects/{id}/pier-statuses/bulk` (one HTTP, one SQL)
- [x] Row-number pills on the map are clickable → filter grid to that row
- [x] Fixed-size draggable zoom selector (Box Select) — drop on an area to zoom-fit

---

## Phase 3 — Construction mode

Site construction + field progress against the EPL model.

- [ ] Work packages per block / zone
- [ ] Task assignment (supervisor → technician)
- [ ] Field-supervisor dashboard
- [ ] Technician mobile view (offline-friendly — reuse existing PWA + IndexedDB)
- [ ] Photo + video upload per task (reuse `pier_status_events` attachments infrastructure)
- [ ] Daily progress reports
- [ ] QC inspections
- [ ] Punch-list items
- [ ] Task discussion thread (back-and-forth with timestamps + attachments)

---

## Phase 4 — BOM & Inventory accountability

Track material from warehouse to installed asset.

- [ ] BOM templates per module / panel / asset type
- [ ] Warehouse — stock ledger
- [ ] Material-issue records (warehouse → block / task / worker)
- [ ] Material usage reporting (what got installed)
- [ ] Return of leftover materials
- [ ] Business-day threshold rules (configurable per project)
- [ ] Missing-material alerts
- [ ] Email notifications to project managers
- [ ] Escalation rules when material is not applied nor returned in time
- [ ] Background reconciliation job (stub at `backend/app/jobs/material_reconciliation.py`)

**Key rule:** if material is issued but not reflected in construction progress
within the configured number of business days, Solarica raises an alert.

---

## Phase 5 — Electrical testing & commissioning

Gate the transition into operation.

- [ ] Test registry: Megger / insulation resistance, continuity, polarity, string Voc, string Isc, AC checks, grounding checks
- [ ] Per-test thresholds + pass / fail evaluation
- [ ] Attachment support (photos of meter reading, exported test files)
- [ ] Commissioning checklist per project
- [ ] Commissioning gate — a project cannot move to operation until:
  - [ ] all required tests uploaded
  - [ ] failures resolved
  - [ ] QC approves
  - [ ] project manager approves
  - [ ] (optional) client approval

---

## Phase 6 — Operation mode

Day-to-day missions + site access coordination.

- [ ] Operational missions (IV-curve, maintenance, inspection)
- [ ] Site-access request flow (technician → guard company approval → notification)
- [ ] Technician mobile workflow
- [ ] Evidence upload per mission
- [ ] Manager / QC approval of mission closure
- [ ] Mission discussion thread
- [ ] Integration with `pier_status_events` so operational findings update the pier model

---

## Phase 7 — Device security & firmware intelligence

Asset-centric OT security for solar sites.

- [ ] Device registry covering inverters, BESS / BMS, PCS, SCADA / PLC, gateways, routers, meters, cameras, weather stations, sensors, Wi-Fi / Bluetooth / IoT endpoints
- [ ] Firmware version tracking per device
- [ ] Vendor advisory ingestion
- [ ] CVE / vulnerability mapping
- [ ] Open-port / exposure scan results
- [ ] Risk scoring
- [ ] Firmware-update missions linked to the operation module
- [ ] Site-access workflow for update missions
- [ ] Proof-of-update upload
- [ ] Closure approval

**Inspiration.** OTORIO-style asset-centric OT security, but solar-specific —
connected to missions, access, assets, and operation, not generic IT.

---

## Phase 8 — Intelligence layer

Turn the captured data into insight.

- [ ] Construction-efficiency analytics (rate per team, per block type)
- [ ] Material-loss analytics
- [ ] Performance baselines
- [ ] IV-curve comparison (string-level over time)
- [ ] Security-risk dashboard
- [ ] Predictive maintenance
- [ ] Digital-twin view (combine design model + live telemetry)

---

## MVP slice (thin cut across all phases)

When the rest of the roadmap is on hold, the minimum product is:

1. Project setup + roles (phase 1)
2. EPL doc upload + parser integration (phase 2) — **done**
3. Piers / blocks validation (phase 2) — **done for Ashalim**
4. Construction task management (phase 3)
5. BOM + warehouse issue + missing-material alerts (phase 4)
6. Electrical-test gate (phase 5)
7. Operation mission + discussion + site access (phase 6)
8. Device registry + basic firmware risk (phase 7)

---

## Related docs

- `docs/ARCHITECTURE.md` — lifecycle diagram, module contract, event bus, shared services
- `CLAUDE.md` — codebase walk-through
- `README.md` — product pitch + quick start
