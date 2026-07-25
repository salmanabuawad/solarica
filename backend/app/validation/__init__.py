"""
Solarica Validation Engine.

A modular, plugin-based subsystem that validates the Digital Twin against every
source (engineering drawings, metadata, GIS, commissioning, PVPM, SCADA, the
asset database) and records typed, actionable findings.

The package is purely additive — it introduces its own ``validation_*`` tables
and its own routes, and never modifies existing schema, APIs or screens.

Layers
------
- ``models``  — enums + the ``Finding`` / ``Repair`` contract validators emit.
- ``schema``  — additive DDL + ``ensure_validation_schema`` (called on startup).
- ``store``   — thin persistence layer over the ``validation_*`` tables.

Later phases add ``validators/`` (the plugins), ``engine`` (orchestration),
REST routes, and the frontend dashboard.
"""
