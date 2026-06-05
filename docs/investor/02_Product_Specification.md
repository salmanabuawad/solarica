# Solarica — Product Specification (v1)

*Living document. EPL reflects what is built; other modules are buildable specs on the same model.*

---

## 0. Architecture overview

- **Ingest:** engineering package (CAD/PDF, electrical + structural + panel layouts, BOM).
- **EPL engine:** parses drawings → **Execution Model** (canonical entities below).
- **Execution Model (single source of truth):** Site → Blocks → Rows → Trackers → Piers → Strings → Panels → Devices, each with geometry, identifiers, and state.
- **Field layer:** offline‑first web/mobile app (map + grid) capturing progress, tests, materials, defects, safety.
- **Intelligence modules:** read/write the model (Verified Progress, Payment, Test, Inventory, Change, Blocker, Safety, Operations).
- **Stack:** Python/FastAPI + PostgreSQL backend; React/TypeScript + MapLibre (WebGL) frontend; IndexedDB + service‑worker offline; PyMuPDF for vector extraction.

### 0.1 Canonical entities
`Site, Block, Row(physical), Tracker, Pier, String, Panel/Module, Optimizer/Inverter/Combiner, Device, TestRecord, ProgressRecord, Claim, Defect, Blocker, ChangeEvent, EvidenceItem.`

---

## 1. EPL — Execution Preparation Layer  *(built & proven)*

### 1.1 CAD/PDF parsing
- Read vector geometry + OCG **layer** structure directly (PyMuPDF) — **no rasterization**, so colors, symbols, text labels and layer names are preserved.
- Layer analysis + semantic classification (structural, electrical, panels, grid, strings, devices).
- Handles page rotation, multi‑sheet sets, and shared coordinate frames across sheets (rigid registration between sheets).

### 1.2 Physical row & tracker detection
- Reconstructs physical rows/trackers from the drawing grid (BE‑Vertical‑Grid class layers); south‑origin numbering; per‑row panel assignment.
- Output: `Row{row_number, tracker_count, panel_count, geometry}`.

### 1.3 Pier extraction
- Vector symbol + label extraction; per‑round assignment (Hungarian matching) to produce **BOM‑exact** pier counts and per‑row numbering.
- Proven: 24,130 piers matching BOM on a real construction set.

### 1.4 String detection (deterministic colour‑partition)
- Site invariants: each string = **44 panels**, **one colour**, one **green‑start + red‑end** marker.
- Per colour, panel_count == 44 × (start markers) → clean partition; each start claims its 44 nearest connected same‑colour panels via **capacity‑44 region‑grow seeded from both start and end**.
- Output per string: panels, rows occupied, single‑row vs cross‑row, start/end, confidence.
- Proven: **288 strings, exactly 44 panels each, 100% named & validated** on BHK.

### 1.5 Numbering validation & cross‑row detection
- Cross‑checks the drawing's own `x.x.x.x` string numbers (block.inverter.combiner.string) against detected strings; surfaces mismatches.
- Flags cross‑row strings with per‑row panel split; confidence < 0.70 → UNKNOWN (no guessing).

### 1.6 Outputs
- Execution Model (DB) + map/grid visualization + exports (CSV/JSON reports A/B/C, string map).

---

## 2. Verified Progress
- **Definition of Done** per component type (e.g., pier driven & torqued; module clamped; string terminated & tested).
- **Completion criteria** = required evidence set (photo, test pass, scan, signature).
- **Evidence collection** in field app (offline); each component's state transitions are auditable.
- Output: measured % complete by block/row/string/area, with evidence drill‑down.

## 3. Payment Intelligence
- Contractor **claim** import (by component/area/activity).
- Match claim ↔ Verified Progress; compute **payment eligibility** (only verified scope is payable).
- Approval workflow (roles, thresholds); dispute log; export to finance.

## 4. Test Intelligence
- Test types: **IV‑curve, Megger (insulation), polarity, continuity, grounding, commissioning**.
- Each test record bound to its asset (string/array/device); pass/fail thresholds; trends.
- Commissioning readiness = test completeness per zone; export certificates with provenance.

## 5. Inventory Intelligence
- Material receipt → installation reconciliation (BOM vs installed vs remaining).
- Shortage/overage alerts; tie consumption to verified installations.

## 6. Change Impact Intelligence
- Detect drawing **revisions** (diff between revs at the model level: rows/strings/piers/numbering).
- Compute impact on already‑built and already‑claimed scope → rework list + payment adjustments.

## 7. Blocker Intelligence
- Model access / material / dependency blockers against the execution model.
- Quantify schedule impact; ownership + escalation.

## 8. Safety & Structural Compliance
- Capture/inspect structural fasteners (bolts, nuts, locking pins) per tracker assembly.
- Missing‑fastener / structural‑defect register; severity; escalation; link to safety + schedule + liability.
- Inspection campaigns by area; closure evidence.

## 9. Operations Module / Solarica Case™
- Post‑construction hand‑over: the Execution Twin becomes the O&M source of truth.
- **Solarica Case™:** a defect/issue case carrying full execution provenance (who built it, when, with what materials, which tests, which rev).

## 10. Non‑functional
- **Offline‑first** field operation (IndexedDB cache, optimistic writes, mutation queue, auto‑sync).
- Role‑based access; audit trail on every state change.
- Performance: WebGL map for 25k+ piers; bundle de‑duplication; lazy loading.
- Security: tenant isolation, encrypted transport, evidence immutability.

## 11. Integrations (roadmap)
- EPC ERPs / finance (claims & payment export), document systems, scheduling (P6/MSP), BI export.

---

*Each section above can be expanded to full detail (data schemas, API contracts, UI flows, acceptance tests) on request.*
