"""
Validation Engine — persistence layer.

A thin repository over the ``validation_*`` tables. Reads return plain dicts
(API-ready: timestamps ISO-formatted, numerics coerced to float); writes are
small and explicit. Every result-status change is also appended to
``validation_history`` for a full audit trail.

Follows the codebase conventions: ``app.db.get_conn`` (psycopg3, dict_row),
``%s`` params, JSONB written via ``json.dumps``.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from app.db import get_conn
from app.validation.models import Finding


def _iso(v: Any) -> Any:
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else v


def _num(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


# --- runs -----------------------------------------------------------------

def create_run(project_uuid: str, trigger: str = "manual",
               scope: Optional[dict] = None, triggered_by: Optional[str] = None) -> int:
    """Open a validation run and return its id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO validation_runs (project_id, trigger, scope, status, triggered_by) "
            "VALUES (%s, %s, %s, 'running', %s) RETURNING id",
            (project_uuid, trigger, json.dumps(scope or {}), triggered_by),
        )
        rid = int(cur.fetchone()["id"])
        conn.commit()
        return rid


def finish_run(run_id: int, status: str = "completed",
               score: Optional[float] = None, counts: Optional[dict] = None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE validation_runs SET status = %s, score = %s, counts = %s, finished_at = NOW() "
            "WHERE id = %s",
            (status, score, json.dumps(counts or {}), run_id),
        )
        conn.commit()


def get_run(run_id: int) -> Optional[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM validation_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
        return _run_dict(row) if row else None


def list_runs(project_uuid: str, limit: int = 50) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM validation_runs WHERE project_id = %s ORDER BY started_at DESC LIMIT %s",
            (project_uuid, limit),
        )
        return [_run_dict(r) for r in cur.fetchall()]


def _run_dict(r: Any) -> dict:
    d = dict(r)
    d["id"] = int(d["id"])
    d["project_id"] = str(d["project_id"])
    d["score"] = _num(d.get("score"))
    d["started_at"] = _iso(d.get("started_at"))
    d["finished_at"] = _iso(d.get("finished_at"))
    return d


# --- results (findings) ---------------------------------------------------

def add_result(project_uuid: str, run_id: Optional[int], f: Finding) -> int:
    """Persist one finding (plus its optional repair) and log its creation."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO validation_results
              (run_id, project_id, validator, code, category, severity, source,
               asset_type, asset_ref, description, suggested_fix, confidence, status,
               evidence, fingerprint)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (run_id, project_uuid, f.validator.value, f.code, f.category.value, f.severity.value,
             f.source.value if f.source else None, f.asset_type, f.asset_ref, f.description,
             f.suggested_fix, f.confidence, f.status.value, json.dumps(f.evidence or {}),
             f.fingerprint()),
        )
        rid = int(cur.fetchone()["id"])
        if f.repair is not None:
            cur.execute(
                "INSERT INTO validation_repairs (result_id, action, reason, confidence, patch) "
                "VALUES (%s, %s, %s, %s, %s)",
                (rid, f.repair.action.value, f.repair.reason, f.repair.confidence,
                 json.dumps(f.repair.patch or {})),
            )
        cur.execute(
            "INSERT INTO validation_history (result_id, project_id, action, to_status) "
            "VALUES (%s, %s, 'created', %s)",
            (rid, project_uuid, f.status.value),
        )
        conn.commit()
        return rid


def list_results(project_uuid: str, *, run_id: Optional[int] = None, severity: Optional[str] = None,
                 validator: Optional[str] = None, status: Optional[str] = None,
                 asset_ref: Optional[str] = None, limit: int = 1000, offset: int = 0) -> list[dict]:
    clauses = ["project_id = %s"]
    params: list[Any] = [project_uuid]
    if run_id is not None:
        clauses.append("run_id = %s"); params.append(run_id)
    if severity:
        clauses.append("severity = %s"); params.append(severity)
    if validator:
        clauses.append("validator = %s"); params.append(validator)
    if status:
        clauses.append("status = %s"); params.append(status)
    if asset_ref:
        clauses.append("asset_ref = %s"); params.append(asset_ref)
    params.extend([limit, offset])
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM validation_results WHERE {' AND '.join(clauses)} "
            "ORDER BY (severity = 'critical') DESC, (severity = 'warning') DESC, created_at DESC "
            "LIMIT %s OFFSET %s",
            params,
        )
        return [_result_dict(r) for r in cur.fetchall()]


def get_result(result_id: int) -> Optional[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM validation_results WHERE id = %s", (result_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = _result_dict(row)
        cur.execute(
            "SELECT * FROM validation_repairs WHERE result_id = %s ORDER BY confidence DESC NULLS LAST, id",
            (result_id,),
        )
        d["repairs"] = [_repair_dict(x) for x in cur.fetchall()]
        return d


def update_result_status(result_id: int, status: str, actor: Optional[str] = None,
                         note: Optional[str] = None) -> Optional[dict]:
    """Move a finding through its lifecycle and record the transition."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, project_id FROM validation_results WHERE id = %s", (result_id,))
        row = cur.fetchone()
        if not row:
            return None
        prev = row["status"]
        proj = str(row["project_id"])
        cur.execute("UPDATE validation_results SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, result_id))
        cur.execute(
            "INSERT INTO validation_history (result_id, project_id, action, from_status, to_status, actor, note) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (result_id, proj, status, prev, status, actor, note),
        )
        conn.commit()
    return get_result(result_id)


def clear_open_findings(project_uuid: str, validators: Optional[list[str]] = None) -> int:
    """Resolve superseded open findings before a fresh run writes new ones, so
    the same issue isn't listed twice. Returns the number resolved."""
    clauses = ["project_id = %s", "status IN ('open','acknowledged','reopened')"]
    params: list[Any] = [project_uuid]
    if validators:
        clauses.append("validator = ANY(%s)"); params.append(list(validators))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE validation_results SET status = 'resolved', updated_at = NOW() "
            f"WHERE {' AND '.join(clauses)}",
            params,
        )
        n = cur.rowcount
        conn.commit()
        return n


def _result_dict(r: Any) -> dict:
    d = dict(r)
    d["id"] = int(d["id"])
    d["run_id"] = int(d["run_id"]) if d.get("run_id") is not None else None
    d["project_id"] = str(d["project_id"])
    d["confidence"] = _num(d.get("confidence"))
    d["created_at"] = _iso(d.get("created_at"))
    d["updated_at"] = _iso(d.get("updated_at"))
    return d


def _repair_dict(r: Any) -> dict:
    d = dict(r)
    d["id"] = int(d["id"])
    d["result_id"] = int(d["result_id"])
    d["confidence"] = _num(d.get("confidence"))
    d["applied_at"] = _iso(d.get("applied_at"))
    d["created_at"] = _iso(d.get("created_at"))
    return d


# --- rules ----------------------------------------------------------------

def list_rules(project_uuid: Optional[str]) -> list[dict]:
    """Rules for a project, plus global templates (project_id IS NULL)."""
    with get_conn() as conn, conn.cursor() as cur:
        if project_uuid:
            cur.execute(
                "SELECT * FROM validation_rules WHERE project_id = %s OR project_id IS NULL "
                "ORDER BY validator, code",
                (project_uuid,),
            )
        else:
            cur.execute("SELECT * FROM validation_rules WHERE project_id IS NULL ORDER BY validator, code")
        return [_rule_dict(r) for r in cur.fetchall()]


def set_rule_enabled(rule_id: int, enabled: bool) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE validation_rules SET enabled = %s, updated_at = NOW() WHERE id = %s",
                    (enabled, rule_id))
        conn.commit()


def _rule_dict(r: Any) -> dict:
    d = dict(r)
    d["id"] = int(d["id"])
    d["project_id"] = str(d["project_id"]) if d.get("project_id") else None
    d["created_at"] = _iso(d.get("created_at"))
    d["updated_at"] = _iso(d.get("updated_at"))
    return d


# --- summary --------------------------------------------------------------

def score_summary(project_uuid: str, run_id: Optional[int] = None) -> dict:
    """Rolled-up counts + a headline validation score for the dashboard.

    Placeholder scoring (penalty-based); Phase 2 replaces this with an
    asset-count-relative score computed inside each run.
    """
    where = "project_id = %s AND status IN ('open','acknowledged','reopened')"
    params: list[Any] = [project_uuid]
    if run_id is not None:
        where += " AND run_id = %s"; params.append(run_id)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT severity, COUNT(*) AS n FROM validation_results WHERE {where} GROUP BY severity",
                    params)
        counts = {row["severity"]: int(row["n"]) for row in cur.fetchall()}
    crit = counts.get("critical", 0)
    warn = counts.get("warning", 0)
    info = counts.get("info", 0)
    score = max(0.0, 100.0 - (crit * 3.0 + warn * 1.0 + info * 0.25))
    return {
        "critical": crit, "warning": warn, "info": info,
        "open_total": crit + warn + info, "score": round(score, 1),
    }
