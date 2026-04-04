"""
ParserEngine — DXF-only pipeline for Solarica scan-stream.

Delegates parsing to ``app.parsers.design.dxf_parser.parse_dxf_path`` when the
backend is on ``sys.path`` (uvicorn WorkingDirectory=/opt/solarica/backend).
All step_* methods exist so the scan loop never skips progress; real work runs
once in ``step_extract_strings``.
"""

from __future__ import annotations

import os
from typing import Any, Callable


def _import_parse_dxf_path() -> Callable[..., dict[str, Any]]:
    try:
        from app.parsers.design.dxf_parser import parse_dxf_path
    except ImportError as exc:
        raise RuntimeError(
            "map_parser_v7.ParserEngine requires the Solarica backend on PYTHONPATH "
            "(e.g. run uvicorn with WorkingDirectory=/opt/solarica/backend)."
        ) from exc
    return parse_dxf_path


def _merge_legacy_dxf_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        raise ValueError("No DXF parse results to merge")
    if len(results) == 1:
        return results[0]

    merged: dict[str, Any] = dict(results[0])
    for r in results[1:]:
        merged["valid_count"] = merged.get("valid_count", 0) + r.get("valid_count", 0)
        merged["invalid_count"] = merged.get("invalid_count", 0) + r.get("invalid_count", 0)
        merged["string_rows"] = (merged.get("string_rows") or []) + (r.get("string_rows") or [])
        merged["inverters"] = (merged.get("inverters") or []) + (r.get("inverters") or [])
        merged["ac_assets"] = (merged.get("ac_assets") or []) + (r.get("ac_assets") or [])
        merged["batteries"] = (merged.get("batteries") or []) + (r.get("batteries") or [])
        merged["validation_findings"] = (merged.get("validation_findings") or []) + (
            r.get("validation_findings") or []
        )
        merged["output_validation_findings"] = (merged.get("output_validation_findings") or []) + (
            r.get("output_validation_findings") or []
        )

        m1: dict[str, list[int]] = dict(merged.get("missing_strings_by_inverter") or {})
        for k, v in (r.get("missing_strings_by_inverter") or {}).items():
            m1[k] = sorted(set(m1.get(k, []) + list(v)))
        merged["missing_strings_by_inverter"] = m1

        d1: dict[str, list[int]] = dict(merged.get("duplicate_string_numbers_by_inverter") or {})
        for k, v in (r.get("duplicate_string_numbers_by_inverter") or {}).items():
            d1[k] = sorted(set(d1.get(k, []) + list(v)))
        merged["duplicate_string_numbers_by_inverter"] = d1

        dup_a = list(merged.get("duplicates") or [])
        dup_b = list(r.get("duplicates") or [])
        merged["duplicates"] = dup_a + dup_b

    return merged


def _ac_labels(ac_assets: Any) -> list[str]:
    out: list[str] = []
    if not ac_assets:
        return out
    for a in ac_assets:
        if isinstance(a, str):
            out.append(a)
        elif isinstance(a, dict):
            out.append(str(a.get("label") or a.get("raw_name") or a.get("name") or a))
    return out


def _infer_string_level(valid_codes: list[str]) -> int:
    for s in valid_codes:
        parts = s.split(".")
        if len(parts) >= 5 and parts[0].upper() == "S":
            return 4
    return 3


def legacy_dxf_result_to_ctx(legacy: dict[str, Any]) -> dict[str, Any]:
    """Map Solarica DXF result dict → ParserEngine ctx for string_scan._pe_ctx_to_result."""
    string_rows: list[dict[str, Any]] = list(legacy.get("string_rows") or [])

    valid_strings: list[str] = []
    invalid_strings: list[str] = []
    for r in string_rows:
        if r.get("is_valid") and r.get("string_code"):
            valid_strings.append(str(r["string_code"]))
        elif not r.get("is_valid"):
            raw = str(r.get("raw_value") or r.get("string_code") or "").strip()
            if raw:
                invalid_strings.append(raw)

    by_inverter: dict[str, dict[str, Any]] = {}
    for r in string_rows:
        if not r.get("is_valid"):
            continue
        key = r.get("inverter_key")
        if not key:
            continue
        bucket = by_inverter.setdefault(key, {"strings": [], "count": 0})
        sc = r.get("string_code")
        if sc:
            bucket["strings"].append(str(sc))
    for _k, bucket in by_inverter.items():
        bucket["count"] = len(bucket["strings"])

    missing_raw: list[dict[str, Any]] = []
    for inv, nums in (legacy.get("missing_strings_by_inverter") or {}).items():
        missing_raw.append({"inverter": str(inv), "missing_strings": list(nums)})

    lat = legacy.get("latitude")
    lon = legacy.get("longitude")
    coords = None
    if lat is not None and lon is not None:
        coords = {"lat": lat, "lon": lon}

    invs = legacy.get("inverters") or []
    str_pattern = None
    if invs and isinstance(invs[0], dict):
        str_pattern = invs[0].get("pattern")

    meta_block = legacy.get("metadata")
    inv_model = None
    if isinstance(meta_block, dict):
        inv_model = meta_block.get("inverter_model")

    md: dict[str, Any] = {
        "site_name": legacy.get("site_name"),
        "country": legacy.get("country"),
        "region": legacy.get("region"),
        "coordinates": coords,
        "declared_dc_power_kwp": legacy.get("system_rating_kwp"),
        "declared_modules": legacy.get("module_count"),
        "declared_modules_per_string": legacy.get("modules_per_string"),
        "module_wattages": [legacy["module_power_wp"]] if legacy.get("module_power_wp") else [],
        "inverter_model": inv_model,
        "installation": {"tracking": {"enabled": bool(legacy.get("tracker_enabled"))}},
    }

    level = _infer_string_level(valid_strings)

    batteries_ctx = {
        "storage_capacity_mwh": legacy.get("battery_capacity_mwh"),
        "has_battery": bool(legacy.get("batteries")),
    }

    return {
        "strings": {
            "valid_strings": valid_strings,
            "invalid_strings": invalid_strings,
            "by_inverter": by_inverter,
            "duplicates": list(legacy.get("duplicates") or []),
        },
        "project_metadata": md,
        "batteries": batteries_ctx,
        "string_level": level,
        "naming_patterns": {"strings": {"detected_pattern": str_pattern}},
        "string_validation": {"missing_by_inverter": missing_raw},
        "design_validation": {"flags": list(legacy.get("validation_findings") or [])},
        "ac_equipment": {"items": _ac_labels(legacy.get("ac_assets"))},
        "extracted": {"pages": []},
    }


class ParserEngine:
    """Multi-step facade over Solarica DXF parsing."""

    def step_load_files(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_text(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_metadata(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_classify_installation(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_detect_patterns(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_inverters(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_strings(self, ctx: dict[str, Any]) -> dict[str, Any]:
        if ctx.get("_v7_parsed"):
            return {}
        paths: list[str] = list(ctx.get("files") or [])
        if not paths:
            raise ValueError("ParserEngine: ctx['files'] is empty")

        parse_dxf_path = _import_parse_dxf_path()
        results: list[dict[str, Any]] = []
        for path in paths:
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Design file not found: {path}")
            ext = os.path.splitext(path)[1].lower()
            if ext != ".dxf":
                raise ValueError(f"ParserEngine DXF path expects .dxf files, got {ext!r}")

            filename = os.path.basename(path)
            results.append(
                parse_dxf_path(
                    path,
                    filename,
                    approved_pattern_regex=None,
                    approved_pattern_name=None,
                    extracted_text=None,
                )
            )

        merged = _merge_legacy_dxf_results(results)
        fragment = legacy_dxf_result_to_ctx(merged)
        fragment["_v7_parsed"] = True
        return fragment

    def step_extract_mppts(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_ac_equipment(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_batteries(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_extract_simple_layout(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_assign_profiles(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_validate_strings(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_validate_output(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def step_build_report(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}
