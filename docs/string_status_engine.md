# Solarica — BHK String Status Engine (MVP design + build plan)

Foundation for **Verified Progress** and **Payment Intelligence**. Replaces subjective % with **verifiable per‑string execution states** so every stakeholder sees one reality.

Builds on what already exists in this repo:
- **String identity** — the colour‑partition engine yields exactly **288 strings** (`x.x.x.x`), each with rows, panel/optimizer counts, start/end. These become the `string` rows.
- **Status pattern** — the pier‑status flow (optimistic write → offline mutation queue → colour on map/grid) is the template for string status.
- **Stack** — FastAPI + PostgreSQL (psycopg) backend; React + MapLibre + ag‑grid + IndexedDB offline.

BHK reference: 8.2 MWp · 12,672 modules · 6,336 optimizers · **288 strings** · 107 rows · 209 trackers.

---

## 1. Status model (MVP — exactly 5)

| # | Status | Code | Colour | Icon (glyph / lucide) | Meaning |
|---|---|---|---|---|---|
| 1 | NEW | `NEW` | Gray `#9ca3af` | ○ / `circle-dashed` | In EPL, no field work |
| 2 | Optimizers mounted | `OPT_ATTACHED` | Blue `#3b82f6` | 🔧 / `wrench` | Optimizers mounted, panels not connected |
| 3 | Panel‑optimizers connected | `PANELS_CONNECTED` | Yellow `#eab308` | ▦ / `layout-grid` | Physically assembled, voltage pending |
| 4 | Volt tested | `VOLT_TESTED` | Green `#16a34a` | ⚡ / `zap` (✓ pass) | Voltage measured + passed |
| 5 | Blocked | `BLOCKED` | Red `#dc2626` | ⛔ / `octagon-x` | Execution stopped, needs action (from any state) |

Each status has a **colour, an icon, and a label** — used consistently everywhere (map markers, grid chips, dashboards, mobile buttons). Each string has **one and only one** active status. `BLOCKED` records the state it interrupted (`pre_block_status`) so resolution restores context.

Single source of truth for status presentation (frontend constant):

```ts
export const STATUS_META = {
  NEW:              { label: "New",              color: "#9ca3af", bg: "#f3f4f6", icon: "circle-dashed" },
  OPT_ATTACHED:     { label: "Optimizers mounted", color: "#3b82f6", bg: "#dbeafe", icon: "wrench" },
  PANELS_CONNECTED: { label: "Panels connected", color: "#eab308", bg: "#fef9c3", icon: "layout-grid" },
  VOLT_TESTED:      { label: "Volt tested",      color: "#16a34a", bg: "#dcfce7", icon: "zap" },
  BLOCKED:          { label: "Blocked",          color: "#dc2626", bg: "#fee2e2", icon: "octagon-x" },
} as const;
```

## 2. State machine

```
NEW ─▶ OPT_ATTACHED ─▶ PANELS_CONNECTED ─▶ VOLT_TESTED
  └────────────┴───────────────┴───────────────┘
                     ▼  (from any)
                  BLOCKED ──▶ (resume to pre_block_status, or advance)
```

Rules enforced server‑side:
- Forward one step at a time along the main chain (configurable: allow skips off by default).
- `BLOCKED` reachable from any state; stores `pre_block_status`.
- Resolving a blocker returns to `pre_block_status` (or a chosen forward state).
- Every transition is validated against an allowed‑transition table → easy to extend (Roadmap).

```python
ALLOWED = {
  "NEW": {"OPT_ATTACHED", "BLOCKED"},
  "OPT_ATTACHED": {"PANELS_CONNECTED", "BLOCKED", "NEW"},
  "PANELS_CONNECTED": {"VOLT_TESTED", "BLOCKED", "OPT_ATTACHED"},
  "VOLT_TESTED": {"BLOCKED", "PANELS_CONNECTED"},
  "BLOCKED": set(),  # resolve() restores pre_block_status / chosen target
}
```

## 3. Database schema (PostgreSQL)

```sql
-- One row per string per project (seeded from the EPL string engine).
CREATE TABLE string (
  id            BIGSERIAL PRIMARY KEY,
  project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  string_code   TEXT NOT NULL,                 -- "2.1.5.4"
  zone          TEXT,
  row_start     INT,
  row_end       INT,
  cross_row     BOOLEAN DEFAULT FALSE,
  panel_count   INT DEFAULT 44,
  optimizer_count INT DEFAULT 22,
  expected_voltage NUMERIC,                     -- design Voc/Vmp
  centroid_json JSONB,                          -- map position
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (project_id, string_code)
);

-- Current status (one per string). History lives in status_history.
CREATE TABLE string_status (
  string_id     BIGINT PRIMARY KEY REFERENCES string(id) ON DELETE CASCADE,
  status        TEXT NOT NULL DEFAULT 'NEW',
  pre_block_status TEXT,                        -- state before BLOCKED
  updated_by    TEXT,
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE voltage_test (
  id            BIGSERIAL PRIMARY KEY,
  string_id     BIGINT NOT NULL REFERENCES string(id) ON DELETE CASCADE,
  expected_voltage NUMERIC,
  measured_voltage NUMERIC,
  result        TEXT CHECK (result IN ('PASS','FAIL')),
  technician    TEXT,
  gps_lat       NUMERIC, gps_lng NUMERIC,
  photo_url     TEXT,
  tested_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE blocker (
  id            BIGSERIAL PRIMARY KEY,
  string_id     BIGINT NOT NULL REFERENCES string(id) ON DELETE CASCADE,
  category      TEXT,            -- broken_panel, missing_optimizer, missing_cable,
                                 -- wrong_numbering, missing_bolts, eng_conflict,
                                 -- material_shortage, safety
  severity      TEXT DEFAULT 'medium',
  reason        TEXT,
  state         TEXT DEFAULT 'open' CHECK (state IN ('open','resolved')),
  photo_url     TEXT, gps_lat NUMERIC, gps_lng NUMERIC,
  created_by    TEXT, created_at TIMESTAMPTZ DEFAULT now(),
  resolved_by   TEXT, resolved_at TIMESTAMPTZ, resolution_note TEXT
);

CREATE TABLE status_history (
  id            BIGSERIAL PRIMARY KEY,
  string_id     BIGINT NOT NULL REFERENCES string(id) ON DELETE CASCADE,
  from_status   TEXT, to_status TEXT NOT NULL,
  actor         TEXT, note TEXT,
  gps_lat NUMERIC, gps_lng NUMERIC, photo_url TEXT,
  changed_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_trail (
  id            BIGSERIAL PRIMARY KEY,
  entity_type   TEXT, entity_id BIGINT, action TEXT,
  actor         TEXT, payload JSONB, at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_string_project ON string(project_id);
CREATE INDEX ix_status_status ON string_status(status);
CREATE INDEX ix_blocker_open ON blocker(string_id) WHERE state='open';
```

Extensibility: new statuses (IV_CURVE_PASSED, QA_APPROVED, COMMISSIONED) = new enum values + rows in the allowed‑transition table; **no schema change**.

## 4. API (FastAPI, under `/api/projects/{pid}`)

| Method | Path | Body / returns |
|---|---|---|
| GET | `/strings` | `?status=&zone=&row=` → list with current status |
| POST | `/strings/{sid}/status` | `{to, note, gps, photo}` → validates transition, writes status + history + audit |
| POST | `/strings/bulk-status` | `{string_ids[], to, ...}` → batch advance (foreman) |
| POST | `/strings/{sid}/voltage-test` | `{expected, measured, technician, gps, photo}` → records test, auto‑sets VOLT_TESTED on PASS |
| POST | `/strings/{sid}/blocker` | `{category, severity, reason, gps, photo}` → opens blocker, sets BLOCKED (saves pre_block_status) |
| POST | `/blockers/{bid}/resolve` | `{note, resume_to}` → closes blocker, restores status |
| GET | `/progress` | counts, %, row breakdown, zone breakdown |
| GET | `/dashboard/{role}` | role metrics (electrician/foreman/site_manager/developer) |

All status‑changing endpoints are **idempotent by (string_id, to, client_mutation_id)** so the offline queue can retry safely.

## 5. Verified Progress (states, not %)

```
GET /progress →
{
  "total": 288,
  "by_status": {"NEW":80,"OPT_ATTACHED":60,"PANELS_CONNECTED":90,"VOLT_TESTED":50,"BLOCKED":8},
  "pct": {"VOLT_TESTED": 17.4, ...},
  "verified_progress_pct": 17.4,         // VOLT_TESTED / total (definition of "done")
  "weighted_progress_pct": 51.2,         // configurable weights per state
  "by_row":  [{"row":45,"NEW":1,...}],
  "by_zone": [{"zone":"2.1","VOLT_TESTED":12,...}]
}
```
Default weights (configurable per contract): NEW 0, OPT 0.33, PANELS 0.66, VOLT 1.0, BLOCKED 0.

## 6. Map + grid rendering

- **Map:** a `string_status` fill/line layer keyed by `status` → the 5 colours (expression `match ['get','status'] ...`). Reuse the string geometry already on the map; box‑select + bulk status from the existing toolbar.
- **Grid:** **Status** column = icon + coloured chip + label; **the whole row background is tinted by status** (`STATUS_META[status].bg`), BLOCKED rows red. ag‑grid `getRowStyle`/`rowClassRules`:
  ```ts
  getRowStyle: p => ({ background: STATUS_META[p.data.status]?.bg ?? "#fff" })
  ```
  Plus status filter + row‑grouped view:
  ```
  Row 45:  S.1.5.1 🟢  S.1.5.2 🟢  S.1.5.3 🟡  S.1.5.4 🔵  S.1.5.5 🔴
  ```
- **Legend + counts** in the toolbar (NEW/OPT/PANELS/VOLT/BLOCKED with live counts).

## 7. Dashboards

- **Electrician:** my assigned strings · current status · my blocked · voltage tests pending · one‑tap advance.
- **Foreman:** strings by status · open blockers · today's transitions · crew throughput (transitions/person/day).
- **Site Manager:** status distribution · blockers by category/severity · progress trend · completion forecast (velocity → ETA).
- **Developer/Owner:** verified progress · payment‑ready strings · risk areas (blocker clusters) · forecast.

All derived from `string_status` + `status_history` (time series) → no separate reporting store.

## 8. Payment Intelligence

```
payment_eligible(string) := status == 'VOLT_TESTED'        # default milestone
```
Configurable milestone contracts:
- **Milestone payments:** weight per state (e.g. OPT 20% / PANELS 30% / VOLT 50%).
- **Partial payments:** sum of reached‑milestone weights × string value.
- **Retention:** hold % until QA/COMMISSIONED (future state).
Payment view = join `string_status` × contract config → `payable_amount`, `eligible_count`. Every eligible string carries its evidence chain (voltage test + photo + GPS + history) = audit‑ready claim.

## 9. Mobile / tablet workflow (DC electrician)

Optimise for gloves + sun + no signal:
1. **Find string** — scan QR/barcode on the tracker, or tap it on the map, or pick from "my row".
2. **One‑tap advance** — big status buttons; current state highlighted; next state one tap.
3. **Voltage test** — numeric pad (expected pre‑filled), PASS/FAIL auto from tolerance, **photo + GPS auto‑captured**.
4. **Block** — pick category (icon grid) + photo → BLOCKED.
Offline: writes go to the **IndexedDB mutation queue** (existing pattern), coalesced per string, auto‑sync on reconnect; each write stamped `client_mutation_id` for idempotency. (Re‑enable the PWA offline shell — currently self‑destructing — before field rollout.)

## 10. Implementation plan (phased)

- **Phase 0 — Seed strings.** Persist the 288 EPL strings into `string` (code, rows, counts, expected_voltage, centroid). One migration + a seed run from the color‑partition engine.
- **Phase 1 — Status core.** Tables `string_status` + `status_history` + `audit_trail`; transition‑validated status API; map status‑colour layer + grid Status column + legend/counts. (Mirrors pier‑status code.)
- **Phase 2 — Tests & blockers.** `voltage_test` + `blocker`; voltage‑test and block/resolve flows; status auto‑set on PASS/block.
- **Phase 3 — Verified Progress + dashboards.** `/progress` + the 4 role dashboards.
- **Phase 4 — Payment Intelligence.** Contract config + payment view.
- **Phase 5 — Mobile polish & offline.** QR/barcode, tablet UI, re‑enable PWA offline.

Each phase is shippable and additive; future states (IV_CURVE, QA, COMMISSIONED) drop into the transition table without touching the core.

---

## 11. Implementation status (shipped — MVP build)

Built directly on the existing `string_records` table (no separate seed step needed — strings are keyed by their `x.x.x.x` code, joined to the EPL topology on read).

**Backend (`backend/app/main.py`)** — live:
- 5‑state model: `STRING_STATUS_VALUES = {new, opt_attached, panels_connected, volt_tested, blocked}`, plus `STRING_STATUS_ALLOWED` (transition table), `STRING_STATUS_WEIGHT`, `PAYMENT_ELIGIBLE_STATUS="volt_tested"`.
- Schema (auto‑ensured on startup, each DDL run separately): `string_records.pre_block_status` column + `string_status_history`, `string_voltage_test`, `string_blocker` tables (+ indexes, partial index on open blockers).
- Routes:
  - `PUT  /api/projects/{pid}/strings/{sid}/status` — sets status, stores `pre_block_status` on block, writes a history row. (Manual picker may set any state; guided flows drive canonical transitions.)
  - `POST /api/projects/{pid}/strings/{sid}/voltage-test` — records expected/measured/result (+GPS, technician); auto‑PASS within 5% tolerance; on PASS auto‑sets `volt_tested` + history.
  - `POST /api/projects/{pid}/strings/{sid}/blocker` — opens a blocker, sets `blocked`, saves `pre_block_status`, history.
  - `POST /api/projects/{pid}/string-blockers/{bid}/resolve` — closes blocker, restores `pre_block_status` (or `resume_to`), history.
  - `GET  /api/projects/{pid}/strings/progress` — total, by_status, pct, **verified %** (volt_tested share), **weighted %**, payment_eligible count, open_blockers, by_row, by_zone.

**Frontend** — live:
- Shared 5‑state presentation (`STRING_STATUS_META`: label/icon/color/bg) in `App.tsx` and `SiteMapMapLibre.tsx`.
- Map: string lines + markers coloured by status; click‑to‑inspect popup status picker shows all 5 states with icons.
- Strings grid (Details → String routes): **Status column** (icon + label chip, single‑click dropdown editor) and **row background coloured by status** (red = blocked), wired to `handleStringStatusChange` (optimistic + offline queue).
- **Verified‑Progress strip** above the grid: stacked progress bar, `⚡ verified %`, weighted %, blocked count, and per‑status count chips.

**Pending (next increments):** role dashboards (§6), Payment Intelligence contract view (§7), mobile QR/barcode + numeric voltage pad (§9), re‑enable PWA offline shell (currently self‑destructing), and persisting EPL strings into a dedicated `string` table if richer per‑string fields are needed.
