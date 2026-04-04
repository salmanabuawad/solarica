"""
Output validation service — ported from
from_chatgpt/app/services/validation/output_validation_service.py.

Adapted to work with plain Python dicts rather than SQLAlchemy models.
Rules operate on the legacy scan-result dict from
:func:`unified_scan_adapter.adapt_unified_report_to_legacy_scan_result`.

Usage:
    from app.services.output_validation import validate
    findings = validate(parse_result)   # returns list[dict]
"""
from __future__ import annotations
from typing import Any


# Tolerance for system-rating comparison (5 %)
_RATING_TOLERANCE = 0.05


def validate(result: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Cross-validate extracted metadata fields and string/inverter counts.

    Parameters
    ----------
    result:
        The dict returned by the unified parser adapter (string-scan shape).

    Returns
    -------
    list of finding dicts, each with keys:
        risk_code   – machine-readable rule identifier
        severity    – "high" | "medium" | "low"
        title       – short human-readable title
        description – detailed explanation with extracted values
    """
    findings: list[dict[str, Any]] = []

    # ── Pull values from result dict ──────────────────────────────────────────
    module_count: int | None = result.get("module_count")
    module_power_wp: float | None = result.get("module_power_wp")
    system_rating_kwp: float | None = result.get("system_rating_kwp")
    modules_per_string: int | None = result.get("modules_per_string")
    inverters: list | None = result.get("inverters")
    valid_count: int = result.get("valid_count", 0)

    # Fallback: derive system_rating_kwp from plant_capacity_mw
    if system_rating_kwp is None:
        plant_mw = result.get("plant_capacity_mw")
        if plant_mw is not None:
            try:
                system_rating_kwp = float(plant_mw) * 1000
            except (TypeError, ValueError):
                pass

    # ── Rule 1: system rating calculation ────────────────────────────────────
    # module_count × module_power_wp ≈ system_rating_kwp  (within 5 % tolerance)
    if module_count and module_power_wp and system_rating_kwp is not None:
        try:
            calculated_kwp = (float(module_count) * float(module_power_wp)) / 1000.0
            reported_kwp = float(system_rating_kwp)
            if reported_kwp > 0:
                pct_diff = abs(calculated_kwp - reported_kwp) / reported_kwp
            else:
                pct_diff = abs(calculated_kwp - reported_kwp)
            if pct_diff > _RATING_TOLERANCE:
                findings.append({
                    "risk_code": "OUTPUT_RATING_MISMATCH",
                    "severity": "high",
                    "title": "Reported system rating mismatch",
                    "description": (
                        f"Calculated {calculated_kwp:.3f} kWp "
                        f"({module_count} modules × {module_power_wp} Wp) "
                        f"vs reported {reported_kwp:.3f} kWp "
                        f"(diff {pct_diff * 100:.1f}%, tolerance 5%)"
                    ),
                })
        except (TypeError, ValueError):
            pass

    # ── Rule 2: string divisibility ──────────────────────────────────────────
    # module_count % modules_per_string == 0
    if module_count and modules_per_string:
        try:
            mc = int(module_count)
            mps = int(modules_per_string)
            if mps > 0:
                remainder = mc % mps
                if remainder != 0:
                    findings.append({
                        "risk_code": "STRING_DIVISIBILITY_MISMATCH",
                        "severity": "medium",
                        "title": "Modules do not divide cleanly into strings",
                        "description": (
                            f"module_count={mc}, modules_per_string={mps}, "
                            f"remainder={remainder}"
                        ),
                    })
        except (TypeError, ValueError):
            pass

    # ── Rule 3: detected string count vs calculated string count ─────────────
    if module_count and modules_per_string and valid_count > 0:
        try:
            mc = int(module_count)
            mps = int(modules_per_string)
            if mps > 0 and mc % mps == 0:
                expected_strings = mc // mps
                if expected_strings != valid_count:
                    findings.append({
                        "risk_code": "COUNTED_STRINGS_MISMATCH",
                        "severity": "medium",
                        "title": "Detected strings do not match expected string count",
                        "description": (
                            f"expected_strings={expected_strings}, "
                            f"detected_strings={valid_count}"
                        ),
                    })
        except (TypeError, ValueError):
            pass

    # ── Rule 4: inverter presence ────────────────────────────────────────────
    if inverters is not None and len(inverters) == 0:
        findings.append({
            "risk_code": "NO_INVERTERS_DETECTED",
            "severity": "high",
            "title": "No inverters detected",
            "description": "No inverter entities were extracted from the drawing.",
        })

    return findings
