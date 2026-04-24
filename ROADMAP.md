# Solarica Roadmap

Based on field assessments of >2 GW across 130+ operating solar assets (Enurgen guide) and current platform capabilities.

## Current State (v1)

- [x] PDF parsing: construction + ramming plans → blocks, trackers, piers (24130 exact via Hungarian matching)
- [x] MapLibre GL map with 25k+ piers, row labels, block polygons, tracker lines
- [x] Grid view with filtering by rows/trackers (comma-separated)
- [x] Pier status tracking (New → In Progress → Implemented → Approved → Rejected → Fixed)
- [x] Offline mode with IndexedDB cache + mutation queue + auto-sync
- [x] PWA service worker for field use without network
- [x] Electrical metadata extraction (inverters, DCCB, BOM, pier type specs)
- [x] Project Info / Details / Devices / Config tab layout

## Phase 1.5: Block Mapping (Design → Execution)

- [ ] Support optional 3rd file upload: block mapping (Excel/CSV or PDF table)
- [ ] New upload kind: `block_mapping` in SystemPanel + backend
- [ ] Auto-detect format by extension (.xlsx/.csv → pandas, .pdf → pdfplumber table extraction, .png/.jpg → OCR/CV to extract block boundaries and labels from image)
- [ ] Mapping structure: design blocks can split or merge into execution blocks
- [ ] Mapping includes which trackers/rows belong to which execution block
- [ ] When mapping file is present, parser overrides PDF-derived block assignments
- [ ] Reassign all piers and trackers to execution blocks per the mapping
- [ ] UI: show execution block names everywhere (grid, map, filters, Project Info)
- [ ] Backward compatible: if no mapping file uploaded, use design blocks as before

## Phase 2: Loss Detection & Recovery

### 2.1 Inverter Monitoring
- [ ] Add inverter inventory to Devices tab (model, serial, firmware version, location/block)
- [ ] Track inverter status: online / derated / tripped / offline
- [ ] Fan fault tracking per inverter
- [ ] MPPT channel health status (per-channel DC/AC ratio monitoring)
- [ ] Ground fault event log with timestamps and affected circuits
- [ ] Link inverters to their DC collection segments (combiners → strings → trackers)

### 2.2 Tracker Health
- [ ] Tracker status field: tracking / stalled / backtracking / manual override
- [ ] Stall detection: flag trackers stuck at same angle across timestamps
- [ ] Slope-aware optimization: per-block target angles vs actual (AM/PM comparison)
- [ ] Capacity test backtracking audit: identify trackers still running test-mode limits
- [ ] Mechanical issue log per tracker (motor, bearing, drive shaft, controller)
- [ ] Map visualization: color trackers by health status (green/yellow/red)

### 2.3 DC Health
- [ ] Combiner box inventory (location, fuse count, connected strings)
- [ ] Fuse status tracking: intact / blown / pulled / replaced
- [ ] MC4 connector inspection log (resistance readings, thermal images)
- [ ] Module-level degradation tracking (IV curve data, visual inspection notes)
- [ ] String-level current comparison (flag underperforming strings vs neighbors)

## Phase 3: Performance Baseline

### 3.1 Expected vs Actual
- [ ] Import energy model baseline (per-timestep expected output per inverter/block)
- [ ] Compare actual yield vs expected at each hierarchy level
- [ ] Automatic loss quantification in MWh per device/block/row
- [ ] Loss categorization: recoverable vs unrecoverable
- [ ] Trend analysis: persistent vs intermittent losses

### 3.2 Hierarchy Drill-Down
- [ ] Portfolio → Site → Block → Inverter → Tracker → Combiner navigation
- [ ] Each level shows: expected MWh, actual MWh, delta, loss type, priority
- [ ] Click-through from loss to specific field work order

### 3.3 Prioritization
- [ ] Rank losses by estimated MWh impact
- [ ] Rank by persistence (days since first detected)
- [ ] Rank by fix complexity (config change vs field visit vs hardware replacement)
- [ ] Dashboard showing top-N recoverable losses across portfolio

## Phase 4: Field Workflow

### 4.1 Work Orders
- [ ] Create work orders from detected losses (auto-populated with device, location, loss type)
- [ ] Assign to field crew with GPS coordinates
- [ ] Photo capture for before/after documentation
- [ ] Offline-capable work order completion with sync

### 4.2 Closed-Loop Verification
- [ ] After fix is applied, compare post-fix performance vs baseline
- [ ] Confirm MWh recovery within expected range
- [ ] Auto-close work order if performance returns to baseline
- [ ] Flag regressions if loss reappears after fix

### 4.3 Reporting
- [ ] Monthly loss recovery report per site
- [ ] Cumulative MWh recovered by loss type
- [ ] Field crew productivity metrics (work orders completed, MWh recovered)
- [ ] Export to PDF/Excel for stakeholder reporting

## Phase 5: Device Inventory & Security

### 5.1 Physical Security
- [ ] Device location on map (inverters, combiner boxes, disconnect switches, junction boxes)
- [ ] Lock status and last inspection date
- [ ] Tamper detection alerts

### 5.2 Cyber/OT Security
- [ ] Device firmware version tracking
- [ ] Network connectivity inventory (IP, port, protocol)
- [ ] Known CVE matching against device models
- [ ] Access control audit log

### 5.3 Electrical Safety
- [ ] Overcurrent / ground fault / arc flash risk per device
- [ ] Inspection schedule and compliance tracking
- [ ] Rating vs actual load monitoring

## Technical Debt / Infrastructure

- [ ] Backend: add device inventory DB tables (devices, device_events, work_orders)
- [ ] Backend: add energy baseline import API (CSV/API integration)
- [ ] Backend: add time-series data store for production metrics
- [ ] Frontend: multi-site portfolio view
- [ ] Frontend: dashboard with charts (loss trends, recovery progress)
- [ ] Frontend: device detail modal with event history timeline
- [ ] Server: scale beyond 1 uvicorn worker (async parser or job queue)
- [ ] Server: add Redis for caching hot queries
