# Solar EPC Platform - Cursor Handoff

This package is a **production-oriented architecture scaffold** for a multi-site solar EPC platform with:

- **Backend**: Python (FastAPI), Celery, SQLAlchemy, Alembic
- **Frontend**: React + TypeScript + Vite
- **Database**: PostgreSQL
- **Proxy**: Nginx
- **Workers/Queue**: Redis + Celery
- **File storage**: local volume first, S3-compatible later

## Supported business flows

1. Multi-site / multi-project management
2. Admin-managed validation rules for uploaded solar design drawings
3. Design parsing + validation runs + issue tracking
4. Construction progress reporting from field supervisors
5. Project-scoped inventory management
6. Testing & commissioning (continuity, polarity, megger, IV curve)
7. Ongoing O&M scheduling and periodic retesting

## Roles

- **manager** (global)
- **project_manager** (project-scoped)
- **supervisor** (project-scoped)
- **inventory_keeper** (project-scoped)

## How to use in Cursor

1. Unzip this package.
2. Open the root folder in Cursor.
3. Start from:
   - `docs/architecture.md`
   - `docs/api-contracts.md`
   - `db/schema.sql`
   - `backend/app/main.py`
   - `frontend/src/App.tsx`
4. Ask Cursor to:
   - wire auth
   - generate Alembic migrations from models
   - build CRUD screens from the contracts
   - implement parser/validator services incrementally

## Recommended implementation order

1. Auth + RBAC
2. Sites / Projects / Assignments
3. Design upload + parsed entities
4. Validation rules + validation run + issues
5. Daily progress + work packages
6. Inventory
7. Testing & commissioning
8. O&M

## Monolith first

This scaffold is designed as a **modular monolith**. Keep it that way until traffic/teams justify service extraction.
