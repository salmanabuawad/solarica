# Solarica Architecture

This document describes the *target* architecture — the shape the system
is growing into. The deployed app already implements the core foundation
(Phase 0) and the EPL slice (Phase 2). The module scaffolding added in
this commit is **intentionally thin**: stubs that future phases fill in,
so work can happen in parallel without stepping on shared services.

See `ROADMAP.md` for what's shipped vs pending per phase.

---

## Lifecycle

```
           ┌───────────────────────────────────────────────────────────┐
           │                     New / Open Project                    │
           └───────────────────────────────────────────────────────────┘
                                     │
                                     ▼
           ┌───────────────────────────────────────────────────────────┐
           │   EPL — parse docs → blocks / piers / strings / BOM /     │
           │          devices. Validation report.                      │
           └───────────────────────────────────────────────────────────┘
                                     │
                        ┌────────────┴────────────┐
                        ▼                         ▼
      ┌────────────────────────────┐   ┌──────────────────────────────┐
      │   Construction — work      │   │  Inventory — warehouse →     │
      │   packages, tasks, QC,     │◄──┤  block / task. Material-not- │
      │   photo evidence, thread   │   │  applied alerts (email).     │
      └────────────────────────────┘   └──────────────────────────────┘
                        │
                        ▼
           ┌───────────────────────────────────────────────────────────┐
           │   Electrical testing — Megger, continuity, polarity,      │
           │   Voc, Isc, AC, grounding. Commissioning gate.            │
           └───────────────────────────────────────────────────────────┘
                                     │
                                     ▼
           ┌───────────────────────────────────────────────────────────┐
           │   Operation — IV-curve, maintenance, inspection missions. │
           │   Site-access workflow (guard company). Discussion.       │
           └───────────────────────────────────────────────────────────┘
                                     │
                                     ▼
           ┌───────────────────────────────────────────────────────────┐
           │   Device security — registry, firmware tracking, CVE,     │
           │   open-port scan, firmware-update missions.               │
           └───────────────────────────────────────────────────────────┘
                                     │
                                     ▼
           ┌───────────────────────────────────────────────────────────┐
           │   Intelligence — analytics, IV-curve comparison, digital  │
           │   twin, predictive maintenance.                           │
           └───────────────────────────────────────────────────────────┘
```

---

## Module contract

Each module lives in `backend/app/modules/<name>/` and exposes:

| What | Where | Purpose |
|---|---|---|
| Routes | `routes.py` — an `APIRouter()` | HTTP surface under `/api/<module>/` |
| Models | `models.py` | SQLAlchemy / Pydantic schemas owned by the module |
| Events | `events.py` | `event_bus.subscribe(...)` handlers + the event names this module *publishes* |
| Jobs | `jobs.py` | Background workers (cron or queue-triggered) |
| Permissions | `permissions.py` | Per-route role checks |
| UI routes | frontend `pages/<module>/` | React routes mounted by the sidebar |

A module must **not** import from a peer module directly. Cross-module
communication goes through either the event bus (fire-and-forget) or a
shared service (synchronous).

Current module scaffolding:

```
backend/app/modules/
├── __init__.py                    # module registry
├── epl/          # phase 2  — parsed model, validation
├── construction/ # phase 3  — work packages, tasks, progress
├── inventory/    # phase 4  — BOM, warehouse, material reconciliation
├── commissioning/# phase 5  — electrical tests, commissioning gate
├── operations/   # phase 6  — O&M missions, site access, discussion
└── security/     # phase 7  — device registry, firmware / CVE, OT risk
```

The parser app as it stands today predates this structure. Routes live
in `backend/app/main.py`; migrating them into `modules/epl/routes.py`
without behavioural change is a no-risk refactor that unblocks the rest
of the layout.

---

## Shared services

Cross-cutting concerns live under `backend/app/services/` or `core/`:

| Service | Responsibility |
|---|---|
| `AuthService` | HMAC-signed Bearer tokens, password hashing (salted SHA-256), role lookup |
| `ProjectService` | CRUD + lifecycle state (`epl → construction → commissioning → operation`) |
| `DocumentService` | File storage abstraction (local or S3-compatible), dedup by sha256 |
| `AssetService` | Physical asset registry (piers, trackers, blocks, devices) |
| `TaskService` | Work packages, missions, punch items, discussion threads |
| `MissionService` | Operational missions (IV-curve, maintenance, site access) |
| `InventoryService` | BOM templates, warehouse ledger, material-issue records, reconciliation |
| `NotificationService` | Email (SMTP / provider), SMS, in-app |
| `AuditService` | Append-only `audit_events` log |
| `FileStorageService` | The actual byte store — pluggable between local fs and S3 |
| `EventBus` | In-process pub/sub for module decoupling |

The `NotificationService` in this repo is a stub today (prints to stdout);
swap for `smtplib` or a transactional-email provider in phase 4.

---

## Event bus

Minimal in-process pub/sub in `backend/app/core/events.py`. Suitable for
single-process deployments (our uvicorn single-worker). For multi-process
or horizontal scale, replace the implementation with Redis pub/sub or
Postgres `LISTEN / NOTIFY` without changing call-sites.

### Canonical events

| Event | Publisher | Typical subscriber |
|---|---|---|
| `project.created` | `projects` route | Audit, Module registry |
| `epl.document_uploaded` | EPL upload route | Parser job |
| `epl.validation_completed` | Parser | Construction (open for work), Audit |
| `construction.task_created` | Construction module | Notification, Audit |
| `construction.task_completed` | Construction module | Inventory reconciliation, Commissioning gate |
| `inventory.material_issued` | Inventory route | Reconciliation job, Audit |
| `inventory.material_unmatched` | Reconciliation job | Notification, Audit |
| `commissioning.test_failed` | Commissioning route | Notification, Construction (open punch item) |
| `commissioning.gate_passed` | Commissioning route | Operations (allow missions), Audit |
| `operation.mission_created` | Operations route | Notification, Audit |
| `access.requested` | Operations route | Security Guard module |
| `access.approved` | Security Guard module | Operations (unblock mission), Notification |
| `security.device_vulnerable` | Security module | Operations (create update mission), Notification |
| `firmware.update_required` | Security module | Operations (mission), Audit |
| `pier.status_changed` | EPL (already published) | Audit, Intelligence analytics |

---

## Frontend module shape

Mirrors the backend. Each frontend module owns:

```
frontend/src/modules/<name>/
├── routes.tsx        # React routes mounted by the sidebar
├── api.ts            # typed client for /api/<module>/*
├── components/       # private to this module
└── i18n/             # per-module keys, merged at boot
```

Shared primitives (`SimpleGrid`, `StatusPill`, `SettingsModal`,
`FieldConfigManager`, etc.) live under `frontend/src/components/` and
stay module-agnostic.

---

## Data model — current vs target

| Table | Phase | Status |
|---|---|---|
| `projects` | 1 | shipped |
| `project_files` | 2 | shipped |
| `blocks`, `trackers`, `piers` | 2 | shipped |
| `pier_statuses` | 2 | shipped |
| `pier_status_events` | 2 | shipped (attachments JSONB) |
| `users` | 1 | shipped |
| `field_configurations` | 0 | shipped |
| `audit_events` | 1 | planned |
| `customers`, `sites` | 1 | planned |
| `work_packages`, `tasks`, `task_messages` | 3 | planned |
| `bom_templates`, `material_issues`, `material_usage` | 4 | planned |
| `electrical_tests`, `commissioning_gates` | 5 | planned |
| `missions`, `access_requests` | 6 | planned |
| `devices`, `device_firmware_events`, `vulnerabilities` | 7 | planned |

---

## Deployment topology

Currently — all in one box (`solarica.wavelync.com`):

```
Nginx (80/443, TLS)
  ├── /  → /opt/solarica/frontend/dist (static SPA)
  └── /api/*  → 127.0.0.1:8010 (uvicorn / solarica-backend.service)
         │
         └─ PostgreSQL 16 (local socket, db: solarica_parser)
```

Horizontal split when the load model needs it (phase 8-ish):
- separate job runner (`systemd` unit for `python -m app.jobs.<worker>`)
- Redis between uvicorn and the jobs + for event bus
- object storage (MinIO / S3) for `pier_status_events` attachments

---

## Design principles

1. **Modules are optional.** You can disable `security` or `inventory` on a project and the rest still runs.
2. **Events over imports.** If module A needs to know B did something, B publishes; A subscribes. No cross-module `from app.modules.b import X`.
3. **Offline-first for the field.** Anything a technician might do while standing in a field of 24 000 piers has an IndexedDB cache + mutation queue + auto-sync.
4. **Attachments are first-class.** Photos, videos, IV-curve files, meter readings — store the file, reference by URL, render in the timeline of the entity.
5. **Audit everything that changes state.** An append-only log is cheap in Postgres and invaluable when a dispute lands on a Tuesday morning.
