"""
Map :func:`unified_layout_parser.run_full` output to the legacy scan dict used by
string sync, topology validation, and project analytics.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.parsers.design.unified_layout_parser import (
    HAMADIYA_STRING_RE,
    QUNITRA_STRING_RE,
    run_full,
)

STRING_EXTRACT_PATTERN = re.compile(
    r"S\.?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?![\d.A-Za-z])", re.IGNORECASE
)

_LABEL_TOKEN_RE = re.compile(r"[A-Za-z0-9.]+")


def plain_text_stub_scan(text: str) -> dict[str, Any]:
    """
    Legacy ``POST /scan``: decoded UTF-8 text, Qunitra-style ``S.N.N.N`` tokens only.
    For PDF/DXF use the project string-scan API.
    """
    from collections import Counter, defaultdict

    labels = _LABEL_TOKEN_RE.findall(text)
    valid: list[str] = [lb for lb in labels if QUNITRA_STRING_RE.match(lb)]
    invalid = [lb for lb in labels if not QUNITRA_STRING_RE.match(lb)]
    groups: dict[str, set[int]] = defaultdict(set)
    for s in valid:
        m = QUNITRA_STRING_RE.match(s)
        if m:
            st, inv, sn = m.groups()
            groups[f"{int(st)}.{int(inv)}"].add(int(sn))
    missing: dict[str, list[int]] = {}
    for inv, nums in groups.items():
        if not nums:
            continue
        expected = set(range(1, max(nums) + 1))
        gap = sorted(expected - nums)
        if gap:
            missing[inv] = gap
    counts = Counter(valid)
    dups = {k: v for k, v in counts.items() if v > 1}
    return {
        "valid_total": len(set(valid)),
        "invalid_total": len(invalid),
        "duplicates": dups,
        "missing": missing,
    }


def _pattern_search_regex(pattern_regex: str | None) -> re.Pattern[str]:
    if not pattern_regex:
        return STRING_EXTRACT_PATTERN
    inner = pattern_regex.strip()
    if inner.startswith("^"):
        inner = inner[1:]
    if inner.endswith("$"):
        inner = inner[:-1]
    return re.compile(rf"(?<![A-Za-z0-9])(?:{inner})(?![A-Za-z0-9])", re.IGNORECASE)


def detect_string_pattern_candidates(
    text: str,
    patterns: list[dict[str, Any]],
    preferred_pattern_name: str | None = None,
) -> dict[str, Any]:
    ranked: list[dict[str, Any]] = []
    for index, pattern in enumerate(patterns):
        regex = pattern.get("pattern_regex")
        search_re = _pattern_search_regex(regex)
        match_count = sum(1 for _ in search_re.finditer(text))
        ranked.append({**pattern, "match_count": match_count, "_rank": index})
    ranked.sort(
        key=lambda item: (
            -(item.get("match_count") or 0),
            0 if preferred_pattern_name and item.get("pattern_name") == preferred_pattern_name else 1,
            item.get("_rank", 0),
        )
    )
    detected = next((item for item in ranked if item.get("match_count", 0) > 0), None)
    selected = (
        next(
            (item for item in ranked if preferred_pattern_name and item.get("pattern_name") == preferred_pattern_name),
            None,
        )
        or detected
        or (ranked[0] if ranked else None)
    )
    return {
        "patterns": [{k: v for k, v in item.items() if k != "_rank"} for item in ranked],
        "detected_pattern_name": detected.get("pattern_name") if detected else None,
        "selected_pattern_name": selected.get("pattern_name") if selected else None,
    }


def _inverter_key_for_string_code(code: str, site_pattern: str) -> str | None:
    m = QUNITRA_STRING_RE.match(code)
    if site_pattern == "qunitra" and m:
        st, inv, _s = m.groups()
        return f"{int(st)}.{int(inv)}"
    m = HAMADIYA_STRING_RE.match(code)
    if site_pattern == "hamadiya" and m:
        st, blk, inv, _s = m.groups()
        return f"{int(st)}.{int(blk)}.{int(inv)}"
    return None


def _dup_numbers_for_inverter(inv_id: str, dup_raw_labels: list[str], site_pattern: str) -> list[int]:
    nums: list[int] = []
    for label in dup_raw_labels:
        key = _inverter_key_for_string_code(label, site_pattern)
        if key != inv_id:
            continue
        m = QUNITRA_STRING_RE.match(label) if site_pattern == "qunitra" else HAMADIYA_STRING_RE.match(label)
        if m:
            nums.append(int(m.groups()[-1]))
    return sorted(set(nums))


def adapt_unified_report_to_legacy_scan_result(
    report: dict[str, Any],
    *,
    source_document: str,
    approved_pattern_name: str | None = None,
    approved_pattern_regex: str | None = None,
) -> dict[str, Any]:
    """Build legacy `result` dict for topology/string DB sync."""
    site_pattern: str = (report.get("summary") or {}).get("site_pattern") or "unknown"
    pm = report.get("project_metadata") or {}
    design = pm.get("design") or {}
    inv_list = list(report.get("inverters") or [])
    per_inv = report.get("per_inverter") or {}
    str_block = report.get("strings") or {}
    db_ui = report.get("db_ui_export") or {}
    unique_valid: list[str] = list(db_ui.get("valid_strings") or [])
    if not unique_valid:
        unique_valid = sorted(set(str_block.get("valid_examples") or []))

    string_rows: list[dict[str, Any]] = []
    for code in unique_valid:
        ik = _inverter_key_for_string_code(code, site_pattern)
        string_rows.append(
            {
                "is_valid": True,
                "string_code": code,
                "raw_value": code,
                "inverter_key": ik,
                "invalid_reason": None,
            }
        )
    for raw in sorted(set(str_block.get("invalid_examples") or [])):
        string_rows.append(
            {
                "is_valid": False,
                "string_code": None,
                "raw_value": raw,
                "inverter_key": None,
                "invalid_reason": "Does not match site string pattern.",
            }
        )

    np = report.get("naming_patterns") or {}
    pattern_label = np.get("string_pattern") or approved_pattern_name

    inverters_out: list[dict[str, Any]] = []
    for inv_id in inv_list:
        block = per_inv.get(inv_id) or {}
        inverters_out.append(
            {
                "raw_name": inv_id,
                "normalized_name": inv_id,
                "strings_count": block.get("string_count", len(block.get("strings") or [])),
                "pattern": pattern_label,
            }
        )

    missing = {k: list(v) for k, v in (report.get("missing") or {}).items()}
    dup_map: dict[str, list[int]] = {}
    for inv_id, block in per_inv.items():
        dlabels = block.get("duplicates") or []
        if dlabels:
            dup_map[inv_id] = _dup_numbers_for_inverter(inv_id, dlabels, site_pattern)

    coords = pm.get("coordinates")
    lat = coords.get("lat") if isinstance(coords, dict) else None
    lon = coords.get("lon") if isinstance(coords, dict) else None
    plant_mw = design.get("system_capacity_mw")
    rating_kwp = design.get("plant_system_rating_kwp")
    storage_kwh = design.get("storage_capacity_kwh")
    storage_mwh = float(storage_kwh) / 1000.0 if storage_kwh is not None else None

    inv_model = design.get("string_inverter_model")
    validation_findings: list[dict[str, Any]] = []
    for w in pm.get("metadata_warnings") or []:
        validation_findings.append(
            {"severity": "warning", "issue_type": "metadata", "message": w, "title": "Metadata"}
        )
    dv = report.get("design_validation") or {}
    if dv.get("status") == "mismatch":
        validation_findings.append(
            {
                "severity": "warning",
                "issue_type": "design_validation",
                "message": "Design validation reported mismatched declared vs calculated values.",
                "title": "Design validation",
            }
        )

    layout_name = pm.get("site_name") or source_document
    site_code = (layout_name or "site").replace(" ", "_")[:32]

    out: dict[str, Any] = {
        "site_code": site_code,
        "site_name": pm.get("site_name"),
        "project_name": pm.get("site_name"),
        "layout_name": layout_name,
        "source_document": source_document,
        "country": pm.get("country"),
        "region": pm.get("region"),
        "latitude": lat,
        "longitude": lon,
        "coordinates": coords if isinstance(coords, dict) else None,
        "plant_capacity_mw": plant_mw,
        "system_rating_kwp": rating_kwp,
        "module_count": design.get("modules_total"),
        "module_power_wp": design.get("module_power_w"),
        "modules_per_string": design.get("modules_per_string_declared"),
        "module_type": design.get("module_model"),
        "tracker_enabled": bool((pm.get("installation") or {}).get("has_trackers")),
        "battery_capacity_mwh": storage_mwh,
        "string_rows": string_rows,
        "valid_count": len([r for r in string_rows if r.get("is_valid")]),
        "invalid_count": len([r for r in string_rows if not r.get("is_valid")]),
        "inverters": inverters_out,
        "inverter_count_detected": len(inverters_out),
        "missing_strings_by_inverter": missing,
        "duplicate_string_numbers_by_inverter": dup_map,
        "outlier_strings_by_inverter": {},
        "validation_findings": validation_findings,
        "output_validation_findings": [],
        "design_validation": dv,
        "invalid_ab_labels": [],
        "suffix_string_issues": [],
        "mppt_validation_issues": [],
        "ac_assets": [],
        "batteries": [],
        "mppt_groups": [],
        "page_count": None,
        "inverter_models": [inv_model] if inv_model else [],
        "approved_pattern_name": approved_pattern_name,
        "approved_pattern_regex": approved_pattern_regex,
        "unified_report": report,
        "parse_report": None,
        "compact": report.get("compact"),
        "devices": list(report.get("devices") or []),
        "device_summary": dict(report.get("device_summary") or {}),
    }
    try:
        from app.services.output_validation import validate as _output_validate

        out["output_validation_findings"] = _output_validate(out)
    except Exception:
        out["output_validation_findings"] = []

    try:
        from app.parsers.design.unified_layout_parser import to_frontend_parse_report

        out["parse_report"] = to_frontend_parse_report(
            {
                "summary": report.get("summary"),
                "site_pattern": site_pattern,
                "strings": report.get("strings"),
                "duplicates": report.get("duplicates"),
                "missing": report.get("missing"),
                "per_inverter": per_inv,
                "inverters": inv_list,
            },
            site_name=pm.get("site_name"),
            country=pm.get("country"),
            region=pm.get("region"),
            lat=lat,
            lon=lon,
        )
    except Exception:
        pass
    return out


def run_unified_on_paths(
    paths: list[Path],
    *,
    primary_source_name: str,
    approved_pattern_name: str | None = None,
    approved_pattern_regex: str | None = None,
) -> dict[str, Any]:
    report = run_full(paths)
    return adapt_unified_report_to_legacy_scan_result(
        report,
        source_document=primary_source_name,
        approved_pattern_name=approved_pattern_name,
        approved_pattern_regex=approved_pattern_regex,
    )
