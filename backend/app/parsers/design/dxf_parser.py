"""
DXF design file parser — extracts labels and runs the same analysis pipeline
as the PDF extractor. Uses ezdxf for DXF reading.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.parsers.design.pdf_string_extractor import (
    _tokenize,
    _extract_string_rows,
    _preprocess_text,
    _build_strings_map,
    _build_gaps,
    _build_duplicates,
    _build_anomalies,
    _annotate_rows_with_inverter_key,
    _build_inverter_summary,
    _build_per_inverter_gaps,
    _build_per_inverter_duplicates,
    _extract_dc_buckets,
    _extract_inverters,
    _fill_and_extend_inverters,
    _extract_ac_assets,
    _extract_batteries,
    _extract_extended_metadata,
    _extract_mppt_channels,
    _extract_icb_zones,
    _validate_output,
    _identify_risks,
    _derive_layout_name,
    _derive_site_code,
    _search,
    _parse_float,
    _parse_int,
    STRING_EXTRACT_PATTERN,
)


def parse_dxf(content: bytes, filename: str) -> dict[str, Any]:
    """
    Parse a DXF file and return the same structure as build_site_design_preview.
    """
    try:
        import ezdxf
    except ImportError as exc:
        raise RuntimeError("DXF parsing requires the 'ezdxf' package: pip install ezdxf") from exc

    import io as _io
    doc = ezdxf.read(_io.BytesIO(content))
    msp = doc.modelspace()

    labels: list[str] = []
    for entity in msp:
        if entity.dxftype() in {"TEXT", "MTEXT"}:
            t = getattr(entity.dxf, "text", None) or getattr(entity, "plain_mtext", lambda: "")()
            if t and t.strip():
                labels.append(t.strip())

    # Build a single joined text for metadata/pattern extraction
    text = _preprocess_text("\n".join(labels))
    tokens = _tokenize(text)

    if not text:
        raise ValueError("No text labels found in DXF file")

    rows = _extract_string_rows(text)
    if not rows:
        raise ValueError("No solar string IDs found in DXF file")

    rows_sorted = sorted(
        rows,
        key=lambda r: (
            r["section_no"] if r["section_no"] is not None else 10**9,
            r["block_no"] if r["block_no"] is not None else 10**9,
            r["string_no"] if r["string_no"] is not None else 10**9,
            r["raw_value"],
        ),
    )
    _annotate_rows_with_inverter_key(rows_sorted)
    valid_rows = [r for r in rows_sorted if r["is_valid"]]
    invalid_rows = [r for r in rows_sorted if not r["is_valid"]]

    layout_name = _derive_layout_name(text, filename)
    site_code = _derive_site_code(layout_name)
    site_name = _search(r"\b([A-Za-z0-9-]+-FPV)\b", text) or site_code

    ext_meta = _extract_extended_metadata(text)
    inverters = _extract_inverters(tokens, string_rows=valid_rows, text=text)
    inverter_count_doc = ext_meta.get("inverter_count_doc")
    inverters = _fill_and_extend_inverters(
        inverters,
        doc_count=int(inverter_count_doc) if inverter_count_doc else None,
        string_rows=valid_rows,
    )
    ac_assets = _extract_ac_assets(tokens)
    batteries = _extract_batteries(tokens)
    dc_buckets = _extract_dc_buckets(text)
    inverter_summary = _build_inverter_summary(valid_rows)
    missing_strings_by_inverter = _build_per_inverter_gaps(valid_rows)
    duplicate_string_numbers_by_inverter = _build_per_inverter_duplicates(rows_sorted)

    plant_capacity_mw = _parse_float(_search(r"System Capacity\s*-\s*([0-9.]+)\s*MW", text, 2))
    module_count = _parse_int(_search(r"Number of\s+Modules\s*-\s*([0-9,]+)", text, 2))

    base_meta: dict[str, Any] = {
        "module_count": module_count,
        "plant_capacity_mw": plant_capacity_mw,
    }
    duplicates = _build_duplicates(rows_sorted)
    validation_findings = _validate_output(base_meta, ext_meta, len(valid_rows), inverters=inverters)
    validation_findings += _identify_risks(duplicates, ext_meta, ac_assets, batteries)

    return {
        "site_code": site_code,
        "site_name": site_name,
        "layout_name": layout_name,
        "source_document": Path(filename).name,
        "country": _search(r"Country\s*-\s*([A-Z][A-Z ]+)", text),
        "region": _search(r"Region\s*/\s*Province\s*-\s*([A-Z][A-Z ]+)", text),
        "latitude": _parse_float(_search(r"Coordinates\s+([0-9.]+)\s*N", text, 2)),
        "longitude": _parse_float(_search(r"Coordinates\s+[0-9.]+\s*N\s+([0-9.]+)\s*E", text, 2)),
        "plant_capacity_mw": plant_capacity_mw,
        "module_type": _search(r"Type of Module / Power\s*-\s*([A-Z0-9-]+)", text, 2),
        "module_count": module_count,
        "module_power_wp": ext_meta.get("module_power_wp"),
        "modules_per_string": ext_meta.get("modules_per_string"),
        "system_rating_kwp": ext_meta.get("system_rating_kwp"),
        "battery_capacity_mwh": ext_meta.get("battery_capacity_mwh"),
        "tracker_enabled": ext_meta.get("tracker_enabled", False),
        "tracker_rotation_deg": ext_meta.get("tracker_rotation_deg"),
        "azimuth_deg": ext_meta.get("azimuth_deg"),
        "dxf_layers": list(doc.layers.names()),
        "total_strings_doc": ext_meta.get("total_strings_doc"),
        "string_rows": rows_sorted,
        "strings": _build_strings_map(rows_sorted),
        "gaps": _build_gaps(rows_sorted),
        "duplicates": duplicates,
        "anomalies": _build_anomalies(text),
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "has_errors": bool(invalid_rows),
        "inverters": inverters,
        "inverter_count_detected": len(inverters),
        "ac_assets": ac_assets,
        "batteries": batteries,
        "mppt_channels": _extract_mppt_channels(text),
        "icb_zones": _extract_icb_zones(text),
        "inverter_summary": inverter_summary,
        "missing_strings_by_inverter": missing_strings_by_inverter,
        "duplicate_string_numbers_by_inverter": duplicate_string_numbers_by_inverter,
        "dc_string_buckets_found": dc_buckets,
        "validation_findings": validation_findings,
        "metadata": {
            "project": site_name,
            "location": None,
            "total_modules": module_count,
        },
    }
