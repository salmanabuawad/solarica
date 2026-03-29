"""Import site metadata and string lists from a design PDF."""

from __future__ import annotations

import io
import re
from pathlib import Path
from collections import defaultdict
from typing import Any

from config import settings
from database import get_connection


# String code formats accepted:
#   Format 1 – dot-separated prefix, 3 components: S.1.2.3
#   Format 2 – section fused to S,   3 components: S1.2.3
#   Format 3 – section fused to S,   4 components: S1.2.3.4
#
# The `\.?` makes the dot between S and the first digit optional.
# The `(?:\.(\d+))?` optionally captures a 4th numeric component.
# `(?![\d.])` prevents greedy over-capture when the code is immediately
# followed by another digit or dot (PDF artefact or genuine anomaly).
STRING_PATTERN = re.compile(r"^S\.?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$", re.IGNORECASE)
STRING_EXTRACT_PATTERN = re.compile(
    r"S\.?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?![\d.])", re.IGNORECASE
)

# Anomaly pattern – codes that look like malformed string IDs.
# The extra segment MUST contain at least one letter so that valid 4-component
# numeric codes (S1.2.3.4) are NOT flagged as anomalies.
# Non-S patterns (e.g. cable IDs like 2.2.2.5.1B) are ignored entirely.
ANOMALY_PATTERN = re.compile(
    r"\b(S\.?\d+\.\d+\.\d+\.[0-9]*[A-Za-z][0-9A-Za-z]*)\b", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _preprocess_text(text: str) -> str:
    """Ensure string codes are space-separated even when pypdf concatenates tokens.

    Dense vector drawings sometimes produce runs like "19S.1.2.3",
    "S.1.2.3S.1.2.4", or "11AS1.2.3".  Injecting a space before every
    S. / S<digit> that is immediately preceded by a non-whitespace character
    separates the tokens so the regex can match each code independently.
    """
    # Dot-prefix format:  ...S.X  → ... S.X
    text = re.sub(r"(?<=[^\s])(S\.)", r" \1", text, flags=re.IGNORECASE)
    # Fused-digit format: ...SX   → ... SX  (only when S is immediately followed
    # by a digit, to avoid splitting words like "STRINGS" or "SENSOR")
    text = re.sub(r"(?<=[^\s])(S(?=\d))", r" \1", text, flags=re.IGNORECASE)
    return text


def _extract_text_in_regions(page: Any, regions: list[dict]) -> str:
    """Extract only the text that falls within the supplied rectangular regions.

    regions: list of {x, y, w, h} in normalised 0–1 coordinates with the
             origin at the **top-left** of the page (browser convention).
             The function converts these to PDF user-space coordinates
             (origin bottom-left, units in points) before filtering.
    """
    mb = page.mediabox
    page_x0 = float(mb.left)
    page_y0 = float(mb.bottom)
    page_w = float(mb.right) - page_x0
    page_h = float(mb.top) - page_y0

    # Convert each region to PDF points bounding box [x0, y0, x1, y1]
    boxes: list[tuple[float, float, float, float]] = []
    for r in regions:
        x0 = page_x0 + r["x"] * page_w
        x1 = page_x0 + (r["x"] + r["w"]) * page_w
        # Flip Y: browser top → PDF bottom
        y0 = page_y0 + (1.0 - r["y"] - r["h"]) * page_h
        y1 = page_y0 + (1.0 - r["y"]) * page_h
        boxes.append((x0, y0, x1, y1))

    parts: list[str] = []

    def _visitor(text: str, _cm: Any, tm: Any, _fd: Any, _fs: Any) -> None:
        if not text:
            return
        tx: float = tm[4]
        ty: float = tm[5]
        for (x0, y0, x1, y1) in boxes:
            if x0 <= tx <= x1 and y0 <= ty <= y1:
                parts.append(text)
                break

    page.extract_text(visitor_text=_visitor)
    return "".join(parts)


def _extract_text_from_pdf(
    content: bytes,
    regions: list[dict] | None = None,
) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF import requires the 'pypdf' package on the server") from exc

    reader = PdfReader(io.BytesIO(content), strict=False)

    if regions:
        # Region-filtered extraction: collect text only inside the drawn boxes
        page_texts = [
            _extract_text_in_regions(page, regions)
            for page in reader.pages
        ]
        text = _preprocess_text("\n".join(p for p in page_texts if p).strip())
    else:
        # Full-page extraction: try both plain and layout mode; use whichever
        # yields more valid string codes.  Layout mode preserves horizontal
        # spacing in clean drawings; plain mode handles PDFs where layout mode
        # drops rotated or off-axis annotations.
        plain_parts: list[str] = []
        layout_parts: list[str] = []
        for page in reader.pages:
            plain_parts.append((page.extract_text() or "").strip())
            try:
                layout_parts.append(
                    (page.extract_text(extraction_mode="layout") or "").strip()
                )
            except Exception:
                layout_parts.append(plain_parts[-1])

        text_plain = _preprocess_text("\n".join(p for p in plain_parts if p).strip())
        text_layout = _preprocess_text("\n".join(p for p in layout_parts if p).strip())
        n_plain = len(STRING_EXTRACT_PATTERN.findall(text_plain))
        n_layout = len(STRING_EXTRACT_PATTERN.findall(text_layout))
        text = text_layout if n_layout >= n_plain else text_plain

    if not text:
        raise ValueError("No text could be extracted from the PDF")
    return text


# ---------------------------------------------------------------------------
# Code normalisation & row building
# ---------------------------------------------------------------------------

def _normalize_code(raw_value: str) -> tuple[str | None, str | None]:
    candidate = raw_value.strip().rstrip(".,;:)]}")
    match = STRING_PATTERN.fullmatch(candidate)
    if not match:
        return None, "Invalid format. Expected S.<digits>.<digits>.<digits>."

    section, block, string_no, fourth = match.groups()
    normalized = f"S.{int(section)}.{int(block)}.{int(string_no)}"
    if fourth:
        normalized += f".{int(fourth)}"
    return normalized, None


def _extract_string_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    row_id = 1

    for section, block, string_no, fourth in STRING_EXTRACT_PATTERN.findall(text):
        normalized = f"S.{int(section)}.{int(block)}.{int(string_no)}"
        if fourth:
            normalized += f".{int(fourth)}"
        duplicate = normalized in seen_codes
        if not duplicate:
            seen_codes.add(normalized)

        rows.append(
            {
                "row_id": row_id,
                "raw_value": normalized,
                "string_code": normalized,
                "section_no": int(section),
                "block_no": int(block),
                "string_no": int(string_no),
                "fourth_no": int(fourth) if fourth else None,
                "is_valid": not duplicate,
                "invalid_reason": "Duplicate string code in document." if duplicate else None,
            }
        )
        row_id += 1

    for candidate in ANOMALY_PATTERN.findall(text):
        rows.append(
            {
                "row_id": row_id,
                "raw_value": candidate,
                "string_code": None,
                "section_no": None,
                "block_no": None,
                "string_no": None,
                "is_valid": False,
                "invalid_reason": "Invalid format. Expected S.<digits>.<digits>.<digits>.",
            }
        )
        row_id += 1

    if not rows:
        raise ValueError("No solar string IDs were found in the PDF")

    return rows


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def _build_strings_map(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if not row["is_valid"] or not row["string_code"]:
            continue
        group_key = f"S.{row['section_no']}"
        grouped[group_key].append(row["string_code"])

    for codes in grouped.values():
        codes.sort(key=lambda code: tuple(int(part) for part in code.split(".")[1:]))
    return dict(sorted(grouped.items(), key=lambda item: int(item[0].split(".")[1])))


def _build_gaps(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped_numbers: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if not row["is_valid"] or not row["string_code"]:
            continue
        group_key = f"S.{row['section_no']}.{row['block_no']}"
        grouped_numbers[group_key].add(int(row["string_no"]))

    gaps: dict[str, list[str]] = {}
    for group_key, numbers in grouped_numbers.items():
        if not numbers:
            continue
        low = min(numbers)
        high = max(numbers)
        missing = [
            f"{group_key}.{value}"
            for value in range(low, high + 1)
            if value not in numbers
        ]
        if missing:
            gaps[group_key] = missing

    return dict(
        sorted(
            gaps.items(),
            key=lambda item: tuple(int(part) for part in item[0].split(".")[1:]),
        )
    )


def _build_duplicates(rows: list[dict[str, Any]]) -> list[str]:
    duplicates = sorted(
        {
            row["string_code"]
            for row in rows
            if row["invalid_reason"] == "Duplicate string code in document." and row["string_code"]
        },
        key=lambda code: tuple(int(part) for part in code.split(".")[1:]),
    )
    return duplicates


def _build_anomalies(text: str) -> dict[str, list[str]]:
    """Return malformed S.-prefixed codes grouped by their S.X.Y.Z base prefix.

    ANOMALY_PATTERN matches 5-segment codes in either format:
      Format 1: S.X.Y.Z.extra  → 5 dot-separated parts, first part is "S"
      Format 2: SX.Y.Z.extra   → 4 dot-separated parts, first part is "S<digits>"
    These are near-miss string-code candidates with an unexpected extra segment.
    """
    grouped: dict[str, set[str]] = defaultdict(set)
    for candidate in ANOMALY_PATTERN.findall(text):
        parts = candidate.split(".")
        first = parts[0].upper()
        if first == "S" and len(parts) >= 5:
            # Format 1: S · section · block · string · extra
            key = ".".join(parts[:4])
        elif first.startswith("S") and first[1:].isdigit() and len(parts) >= 4:
            # Format 2: S<section> · block · string · extra
            key = ".".join(parts[:3])
        else:
            continue
        grouped[key].add(candidate)

    result: dict[str, list[str]] = {}
    for key, values in grouped.items():
        result[key] = sorted(values)

    def _sort_key(item: tuple[str, list[str]]) -> tuple:
        return tuple(int(p) if p.lstrip("-").isdigit() else 0 for p in item[0].split("."))

    return dict(sorted(result.items(), key=_sort_key))


# ---------------------------------------------------------------------------
# Site metadata parsing
# ---------------------------------------------------------------------------

def _search(pattern: str, text: str, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    return match.group(1).strip()


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    return float(cleaned) if cleaned else None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    return int(cleaned) if cleaned else None


def _derive_layout_name(text: str, filename: str) -> str:
    from_text = _search(r"\b([A-Z]{3}_[A-Z]_\d+_Color Map)\b", text, re.IGNORECASE)
    if from_text:
        return from_text.replace(" ", "_")

    stem = Path(filename).stem
    stem = re.sub(r"_rev[^_]+$", "", stem, flags=re.IGNORECASE)
    if "Color Map" in stem:
        return stem.replace(" ", "_")
    return stem.replace(" ", "_")


def _derive_site_code(layout_name: str) -> str:
    match = re.match(r"([A-Za-z0-9]+_[A-Za-z0-9]+_\d+)", layout_name)
    if match:
        return match.group(1).upper()
    return layout_name.split("_")[0].upper()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_site_design_pdf(
    content: bytes,
    filename: str,
    regions: list[dict] | None = None,
) -> dict[str, Any]:
    text = _extract_text_from_pdf(content, regions=regions)
    string_rows = _extract_string_rows(text)

    layout_name = _derive_layout_name(text, filename)
    site_code = _derive_site_code(layout_name)
    source_document = Path(filename).name

    site_name = _search(r"\b([A-Za-z0-9-]+-FPV)\b", text)
    if not site_name:
        site_name = site_code

    latitude = _parse_float(
        _search(r"Coordinates\s+([0-9.]+)\s*N", text, re.IGNORECASE)
    )
    longitude = _parse_float(
        _search(r"Coordinates\s+[0-9.]+\s*N\s+([0-9.]+)\s*E", text, re.IGNORECASE)
    )
    country = _search(r"Country\s*-\s*([A-Z][A-Z ]+)", text)
    region = _search(r"Region\s*/\s*Province\s*-\s*([A-Z][A-Z ]+)", text)
    plant_capacity_mw = _parse_float(
        _search(r"System Capacity\s*-\s*([0-9.]+)\s*MW", text, re.IGNORECASE)
    )
    module_type = _search(
        r"Type of Module / Power\s*-\s*([A-Z0-9-]+)", text, re.IGNORECASE
    )
    module_count = _parse_int(
        _search(r"Number of\s+Modules\s*-\s*([0-9,]+)", text, re.IGNORECASE)
    )

    return {
        "site_code": site_code,
        "site_name": site_name,
        "layout_name": layout_name,
        "source_document": source_document,
        "country": country,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "plant_capacity_mw": plant_capacity_mw,
        "module_type": module_type,
        "module_count": module_count,
        "notes": f"Imported from design PDF: {source_document}",
        "string_rows": string_rows,
        "raw_text": text,
    }


def build_site_design_preview(
    content: bytes,
    filename: str,
    regions: list[dict] | None = None,
) -> dict[str, Any]:
    parsed = parse_site_design_pdf(content, filename, regions=regions)
    text = parsed.pop("raw_text")
    rows = sorted(
        parsed["string_rows"],
        key=lambda row: (
            row["section_no"] if row["section_no"] is not None else 10**9,
            row["block_no"] if row["block_no"] is not None else 10**9,
            row["string_no"] if row["string_no"] is not None else 10**9,
            row["raw_value"],
        ),
    )
    valid_rows = [row for row in rows if row["is_valid"]]
    invalid_rows = [row for row in rows if not row["is_valid"]]
    strings_map = _build_strings_map(rows)
    gaps = _build_gaps(rows)
    duplicates = _build_duplicates(rows)
    anomalies = _build_anomalies(text)

    return {
        **parsed,
        "string_rows": rows,
        "metadata": {
            "project": parsed["site_name"],
            "location": (
                f"{parsed['latitude']}N, {parsed['longitude']}E"
                if parsed["latitude"] is not None and parsed["longitude"] is not None
                else None
            ),
            "total_modules": parsed["module_count"],
        },
        "strings": strings_map,
        "anomalies": anomalies,
        "gaps": gaps,
        "duplicates": duplicates,
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "has_errors": bool(invalid_rows),
    }


def _upsert_site(cur, site: dict[str, Any], *, is_sqlite: bool) -> int:
    values = (
        site["site_code"],
        site["site_name"],
        site["layout_name"],
        site["source_document"],
        site["country"],
        site["region"],
        site["latitude"],
        site["longitude"],
        site["plant_capacity_mw"],
        site["module_type"],
        site["module_count"],
        site["notes"],
    )

    if is_sqlite:
        cur.execute(
            """
            INSERT INTO site_details (
                site_code, site_name, layout_name, source_document, country, region,
                latitude, longitude, plant_capacity_mw, module_type, module_count, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_code) DO UPDATE SET
                site_name = excluded.site_name,
                layout_name = excluded.layout_name,
                source_document = excluded.source_document,
                country = excluded.country,
                region = excluded.region,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                plant_capacity_mw = excluded.plant_capacity_mw,
                module_type = excluded.module_type,
                module_count = excluded.module_count,
                notes = excluded.notes
            """,
            values,
        )
        cur.execute("SELECT id FROM site_details WHERE site_code = ?", (site["site_code"],))
        return int(cur.fetchone()[0])

    cur.execute(
        """
        INSERT INTO site_details (
            site_code, site_name, layout_name, source_document, country, region,
            latitude, longitude, plant_capacity_mw, module_type, module_count, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(site_code) DO UPDATE SET
            site_name = EXCLUDED.site_name,
            layout_name = EXCLUDED.layout_name,
            source_document = EXCLUDED.source_document,
            country = EXCLUDED.country,
            region = EXCLUDED.region,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            plant_capacity_mw = EXCLUDED.plant_capacity_mw,
            module_type = EXCLUDED.module_type,
            module_count = EXCLUDED.module_count,
            notes = EXCLUDED.notes
        RETURNING id
        """,
        values,
    )
    return int(cur.fetchone()[0])


def _format_code_for_pattern(section: int, block: int, string_no: int, fourth: int | None, pattern_code: str) -> str:
    """Format a string code to match the site's active pattern storage convention."""
    if pattern_code == "S4_LEVEL":
        base = f"S{section}.{block}.{string_no}"
        return f"{base}.{fourth}" if fourth is not None else base
    # Default (S_DOT_3 and others): dot after S
    base = f"S.{section}.{block}.{string_no}"
    return f"{base}.{fourth}" if fourth is not None else base


def import_site_design_pdf(
    content: bytes,
    filename: str,
    regions: list[dict] | None = None,
) -> dict[str, Any]:
    site_data = build_site_design_preview(content, filename, regions=regions)
    rows = site_data.pop("string_rows")
    valid_rows = [row for row in rows if row["is_valid"]]
    invalid_rows = [row for row in rows if not row["is_valid"]]
    if invalid_rows:
        raise ValueError(
            f"Import blocked: {len(invalid_rows)} invalid or duplicate string rows found."
        )

    is_sqlite = settings.database_url.strip().lower().startswith("sqlite")
    placeholder = "?" if is_sqlite else "%s"
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            site_id = _upsert_site(cur, site_data, is_sqlite=is_sqlite)

            # Look up the active pattern for this site to format string codes consistently
            cur.execute(
                "SELECT p.pattern_code FROM string_id_pattern p "
                "JOIN site_string_pattern sp ON sp.pattern_id = p.id "
                f"WHERE sp.site_id = {placeholder}",
                (site_id,),
            )
            pattern_row = cur.fetchone()
            active_pattern_code = pattern_row[0] if pattern_row else "S4_LEVEL"

            cur.execute(
                f"DELETE FROM site_strings WHERE site_id = {placeholder}",
                (site_id,),
            )

            insert_sql = (
                "INSERT INTO site_strings (site_id, string_code, section_no, block_no, string_no) "
                f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})"
            )
            for row in valid_rows:
                code = _format_code_for_pattern(
                    row["section_no"], row["block_no"], row["string_no"],
                    row.get("fourth_no"), active_pattern_code,
                )
                cur.execute(
                    insert_sql,
                    (
                        site_id,
                        code,
                        row["section_no"],
                        row["block_no"],
                        row["string_no"],
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "success": True,
        "site_id": site_id,
        "site_code": site_data["site_code"],
        "site_name": site_data["site_name"],
        "source_document": site_data["source_document"],
        "string_count": len(valid_rows),
        "message": f"Imported {len(valid_rows)} strings for site {site_data['site_code']}.",
    }


def _merge_string_rows(all_rows: list[dict]) -> list[dict]:
    """Deduplicate a combined list of rows from multiple PDFs."""
    seen: set[str] = set()
    merged = []
    row_id = 1
    for row in all_rows:
        code = row.get("string_code")
        if code is None:
            # anomaly row — keep as-is
            merged.append({**row, "row_id": row_id})
        elif code in seen:
            merged.append({**row, "row_id": row_id, "is_valid": False,
                           "invalid_reason": "Duplicate string code in document."})
        else:
            seen.add(code)
            merged.append({**row, "row_id": row_id, "is_valid": True, "invalid_reason": None})
        row_id += 1
    return merged


def _merge_metadata(parsed_list: list[dict]) -> dict[str, Any]:
    """
    Merge site metadata from multiple parsed PDFs.

    Rules per field:
    - site_code, site_name, layout_name: first non-None wins (they identify the project)
    - country, region, latitude, longitude: first non-None wins
    - plant_capacity_mw: first non-None wins (project-level total)
    - module_type: first non-None wins
    - module_count: SUM of all non-None values (each PDF may cover a section)
    - source_document: all filenames joined
    - notes: combined from all files
    """
    scalar_first = [
        "site_code", "site_name", "layout_name",
        "country", "region", "latitude", "longitude",
        "plant_capacity_mw", "module_type",
    ]
    merged: dict[str, Any] = {k: None for k in scalar_first}
    merged["module_count"] = None
    merged["source_document"] = None
    merged["notes"] = None

    for p in parsed_list:
        for key in scalar_first:
            if merged[key] is None and p.get(key) is not None:
                merged[key] = p[key]

        # module_count: sum non-None across files
        mc = p.get("module_count")
        if mc is not None:
            merged["module_count"] = (merged["module_count"] or 0) + mc

    # source_document: concatenate all filenames
    docs = [p["source_document"] for p in parsed_list if p.get("source_document")]
    merged["source_document"] = ", ".join(dict.fromkeys(docs)) if docs else None

    # notes: combine
    notes_parts = [p["notes"] for p in parsed_list if p.get("notes")]
    merged["notes"] = "; ".join(notes_parts) if notes_parts else None

    return merged


def build_site_design_preview_multi(
    files: list[tuple[bytes, str]],
    regions: list[dict] | None = None,
) -> dict[str, Any]:
    """Preview multiple PDFs treated as one project, merging metadata from all files."""
    if not files:
        raise ValueError("No files provided")

    parsed_list = []
    combined_rows: list[dict] = []
    all_text = ""

    for content, filename in files:
        parsed = parse_site_design_pdf(content, filename, regions=regions)
        all_text += "\n" + parsed.pop("raw_text")
        combined_rows.extend(parsed.pop("string_rows"))
        parsed_list.append(parsed)

    site_data = _merge_metadata(parsed_list)

    merged = _merge_string_rows(combined_rows)
    rows = sorted(
        merged,
        key=lambda r: (
            r["section_no"] if r["section_no"] is not None else 10**9,
            r["block_no"] if r["block_no"] is not None else 10**9,
            r["string_no"] if r["string_no"] is not None else 10**9,
            r["raw_value"],
        ),
    )
    valid_rows = [r for r in rows if r["is_valid"]]
    invalid_rows = [r for r in rows if not r["is_valid"]]
    strings_map = _build_strings_map(rows)
    gaps = _build_gaps(rows)
    duplicates = _build_duplicates(rows)
    anomalies = _build_anomalies(all_text)

    lat = site_data.get("latitude")
    lon = site_data.get("longitude")
    return {
        **site_data,
        "string_rows": rows,
        "metadata": {
            "project": site_data["site_name"],
            "location": f"{lat}N, {lon}E" if lat is not None and lon is not None else None,
            "total_modules": site_data["module_count"],
        },
        "strings": strings_map,
        "anomalies": anomalies,
        "gaps": gaps,
        "duplicates": duplicates,
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "has_errors": bool(invalid_rows),
    }


def import_site_design_pdf_multi(
    files: list[tuple[bytes, str]],
    regions: list[dict] | None = None,
) -> dict[str, Any]:
    """Import multiple PDFs as one project. Strings from all files are merged."""
    if not files:
        raise ValueError("No files provided")

    site_data = build_site_design_preview_multi(files, regions=regions)
    rows = site_data.pop("string_rows")
    valid_rows = [r for r in rows if r["is_valid"]]
    invalid_rows = [r for r in rows if not r["is_valid"]]
    if invalid_rows:
        raise ValueError(
            f"Import blocked: {len(invalid_rows)} invalid or duplicate string rows found."
        )

    is_sqlite = settings.database_url.strip().lower().startswith("sqlite")
    placeholder = "?" if is_sqlite else "%s"
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            site_id = _upsert_site(cur, site_data, is_sqlite=is_sqlite)

            cur.execute(
                "SELECT p.pattern_code FROM string_id_pattern p "
                "JOIN site_string_pattern sp ON sp.pattern_id = p.id "
                f"WHERE sp.site_id = {placeholder}",
                (site_id,),
            )
            pattern_row = cur.fetchone()
            active_pattern_code = pattern_row[0] if pattern_row else "S4_LEVEL"

            cur.execute(
                f"DELETE FROM site_strings WHERE site_id = {placeholder}",
                (site_id,),
            )

            insert_sql = (
                "INSERT INTO site_strings (site_id, string_code, section_no, block_no, string_no) "
                f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})"
            )
            for row in valid_rows:
                code = _format_code_for_pattern(
                    row["section_no"], row["block_no"], row["string_no"],
                    row.get("fourth_no"), active_pattern_code,
                )
                cur.execute(insert_sql, (site_id, code, row["section_no"], row["block_no"], row["string_no"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    filenames = ", ".join(Path(fn).name for _, fn in files)
    return {
        "success": True,
        "site_id": site_id,
        "site_code": site_data["site_code"],
        "site_name": site_data["site_name"],
        "source_document": filenames,
        "string_count": len(valid_rows),
        "message": f"Imported {len(valid_rows)} strings for site {site_data['site_code']} from {len(files)} file(s).",
    }
