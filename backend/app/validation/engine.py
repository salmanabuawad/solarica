"""
Validation Engine — run orchestration.

Loads a project's assets once, invokes the requested (or all) validator
plugins, persists their findings, and rolls the run up into counts + an
asset-relative validation score. Importing this module registers the built-in
validators (via ``app.validation.validators``).

Later phases hang the REST API (Phase 3), event-driven / incremental runs, and
rule-based enable/disable off this same entry point.
"""
from __future__ import annotations

from typing import Optional

from app.validation import store
from app.validation.validators import base  # noqa: F401 — importing registers plugins
from app.validation.validators.base import ValidationContext, get_validators

# Severity weights for the run score (asset-relative penalty).
_WEIGHT = {"critical": 5.0, "warning": 1.0, "info": 0.2}


def _score(counts: dict, total_assets: int) -> float:
    if total_assets <= 0:
        return 100.0
    penalty = sum(_WEIGHT.get(sev, 0.0) * n for sev, n in counts.items())
    return round(max(0.0, 100.0 - min(100.0, 100.0 * penalty / total_assets)), 1)


def run_validation(project_slug: str, project_uuid: str, *,
                   validators: Optional[list[str]] = None,
                   trigger: str = "manual", actor: Optional[str] = None) -> dict:
    """Execute a validation run and return its summary.

    Parameters mirror the future API: ``validators`` selects a subset by enum
    value (e.g. ``["gap", "naming"]``); ``None`` runs them all.
    """
    ctx = ValidationContext(project_slug, project_uuid).load()
    selected = get_validators(validators)
    selected_names = [v.validator.value for v in selected]

    run_id = store.create_run(project_uuid, trigger, {"validators": selected_names}, actor)
    # Supersede the previous open findings for these validators so the same
    # issue isn't listed twice; new findings from this run replace them.
    store.clear_open_findings(project_uuid, selected_names)

    counts = {"critical": 0, "warning": 0, "info": 0}
    total = ctx.total_assets
    try:
        for v in selected:
            for f in v.run(ctx):
                store.add_result(project_uuid, run_id, f)
                counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        score = _score(counts, total)
        store.finish_run(run_id, "completed", score, {**counts, "assets": total})
    except Exception as exc:  # noqa: BLE001 — record the failure, then re-raise
        store.finish_run(run_id, "failed", None, {"error": str(exc)})
        raise

    return {
        "run_id": run_id,
        "score": score,
        "counts": counts,
        "assets": total,
        "validators": selected_names,
    }
