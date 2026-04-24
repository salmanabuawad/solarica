"""Solarica module scaffolding.

Each module corresponds to one lifecycle phase (see `docs/ARCHITECTURE.md`
and `ROADMAP.md`). The current deployed routes still live in
`backend/app/main.py`; these packages give the skeleton to migrate into
so independent phases can progress in parallel without stepping on
shared services.

Modules:
  - epl            — parsed model + validation (phase 2, today's core app)
  - construction   — work packages, tasks, progress (phase 3)
  - inventory      — BOM, warehouse, material reconciliation (phase 4)
  - commissioning  — electrical testing + commissioning gate (phase 5)
  - operations     — O&M missions, site access (phase 6)
  - security       — device registry, firmware intelligence (phase 7)

Each submodule exposes a `router: APIRouter` that `app.main` mounts when
the module is ready to ship. Mounts are intentionally commented out in
main.py until a module actually has behaviour beyond a stub.
"""
