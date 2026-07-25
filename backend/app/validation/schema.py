"""
Validation Engine — database schema (strictly additive).

Five new tables, all ``CREATE TABLE IF NOT EXISTS`` and foreign-keyed to the
existing ``projects`` table. Nothing here alters or drops existing tables, so
current APIs and screens keep working unchanged. ``ensure_validation_schema``
is idempotent and called once on FastAPI startup (see ``main.py``), mirroring
the existing ``_ensure_users_schema`` pattern.

Tables
------
- ``validation_rules``    — per-project (or global) validator configuration.
- ``validation_runs``     — one validation execution + its rolled-up score.
- ``validation_results``  — the findings (Severity/Category/Source/Asset/…).
- ``validation_repairs``  — suggested corrections (never auto-applied).
- ``validation_history``  — append-only audit of every result state change.
"""
from __future__ import annotations

from app.db import get_conn

VALIDATION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS validation_rules (
  id           BIGSERIAL PRIMARY KEY,
  project_id   UUID REFERENCES projects(id) ON DELETE CASCADE,   -- NULL = global template
  validator    TEXT NOT NULL,
  code         TEXT NOT NULL,
  name         TEXT NOT NULL,
  category     TEXT NOT NULL,
  severity     TEXT NOT NULL DEFAULT 'warning',
  enabled      BOOLEAN NOT NULL DEFAULT TRUE,
  config       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_val_rules_project ON validation_rules (project_id, validator);

CREATE TABLE IF NOT EXISTS validation_runs (
  id           BIGSERIAL PRIMARY KEY,
  project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  trigger      TEXT NOT NULL DEFAULT 'manual',
  scope        JSONB NOT NULL DEFAULT '{}'::jsonb,
  status       TEXT NOT NULL DEFAULT 'running',
  score        NUMERIC,
  counts       JSONB NOT NULL DEFAULT '{}'::jsonb,
  triggered_by TEXT,
  started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_val_runs_project ON validation_runs (project_id, started_at DESC);

CREATE TABLE IF NOT EXISTS validation_results (
  id            BIGSERIAL PRIMARY KEY,
  run_id        BIGINT REFERENCES validation_runs(id) ON DELETE CASCADE,
  project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  validator     TEXT NOT NULL,
  code          TEXT NOT NULL,
  category      TEXT NOT NULL,
  severity      TEXT NOT NULL,
  source        TEXT,
  asset_type    TEXT,
  asset_ref     TEXT,
  description   TEXT NOT NULL,
  suggested_fix TEXT,
  confidence    NUMERIC,
  status        TEXT NOT NULL DEFAULT 'open',
  evidence      JSONB NOT NULL DEFAULT '{}'::jsonb,
  fingerprint   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_val_results_project ON validation_results (project_id, severity, status);
CREATE INDEX IF NOT EXISTS idx_val_results_run     ON validation_results (run_id);
CREATE INDEX IF NOT EXISTS idx_val_results_asset   ON validation_results (project_id, asset_ref);
CREATE INDEX IF NOT EXISTS idx_val_results_fp      ON validation_results (project_id, fingerprint);

CREATE TABLE IF NOT EXISTS validation_repairs (
  id           BIGSERIAL PRIMARY KEY,
  result_id    BIGINT NOT NULL REFERENCES validation_results(id) ON DELETE CASCADE,
  action       TEXT NOT NULL,
  reason       TEXT,
  confidence   NUMERIC,
  patch        JSONB NOT NULL DEFAULT '{}'::jsonb,
  status       TEXT NOT NULL DEFAULT 'proposed',
  applied_at   TIMESTAMPTZ,
  applied_by   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_val_repairs_result ON validation_repairs (result_id);

CREATE TABLE IF NOT EXISTS validation_history (
  id           BIGSERIAL PRIMARY KEY,
  result_id    BIGINT REFERENCES validation_results(id) ON DELETE CASCADE,
  project_id   UUID NOT NULL,
  action       TEXT NOT NULL,
  from_status  TEXT,
  to_status    TEXT,
  actor        TEXT,
  note         TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_val_history_result ON validation_history (result_id, created_at);
"""


def ensure_validation_schema() -> None:
    """Create the validation tables if they don't exist. Idempotent; safe to
    run on every boot. Never touches non-validation tables."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(VALIDATION_SCHEMA_SQL)
        conn.commit()
