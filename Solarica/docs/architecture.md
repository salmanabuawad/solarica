# Architecture

## 1) High-level system

```text
Users
  |
  v
Nginx
  |-- /          -> React SPA
  |-- /api       -> FastAPI
  |-- /uploads   -> protected file/media access
                    |
                    +--> PostgreSQL
                    +--> Redis
                    +--> Celery Worker
                    +--> File Storage
```

## 2) Core principles

- Multi-site, multi-project from day one
- Every business record belongs to a `project_id`
- Rules are stored in DB and evaluated by Python handlers
- Uploaded design files produce a **parsed model**, not just OCR text
- Validation is a **stage gate**
- Construction, inventory, tests, and O&M all reference the same project structure

## 3) Main bounded modules

### Auth & RBAC
Users, roles, project assignments, permissions.

### Master Data
Sites, projects, sections, inverters, strings, panel groups, cable paths, equipment models.

### Design Ingestion
Upload files, parse text/labels/geometry, normalize extracted entities, store parser output.

### Validation
Admin-editable rules, validation runs, issues, exceptions, approvals.

### Construction Execution
Work packages, daily reports, field progress, photos, blockers, ETA calculation.

### Inventory
Receipts, issues, returns, wastage, reserved materials, project warehouse.

### Testing & Commissioning
Continuity, polarity, insulation/megger, string voltage, IV curve, punch list, commissioning gate.

### O&M
Scheduled checks, recurring tests, incidents, support visits, preventive maintenance.

## 4) Recommended deployment

- `nginx`
- `frontend` container (or built static files served by nginx)
- `backend-api`
- `backend-worker`
- `redis`
- `postgres`

## 5) Suggested backend modules

```text
app/
  api/
  core/
  models/
  schemas/
  services/
  tasks/
  utils/
```

## 6) Suggested frontend modules

```text
src/
  app/
  pages/
  components/
  services/
  hooks/
  types/
  routes/
```

## 7) Project stages

1. planning
2. design_review
3. approved_for_construction
4. under_construction
5. testing_commissioning
6. operational
7. maintenance

Project stage gates should be enforced in backend service rules.
