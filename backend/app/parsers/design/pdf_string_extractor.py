"""
Pure-logic PDF/DXF string extraction — no DB or config dependencies.
Adapted from Solarica/backend/services/site_design_import.py.
Extended with inverter, AC, battery extraction and output validation
from from_chatgpt analysis pipeline.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from collections import defaultdict
from typing import Any

# Extra patterns from from_chatgpt solarica_parsers/patterns.py
from app.parsers.design.extra_patterns import (
    PROJECT_NAME_PATTERNS,
    COORDINATES_PATTERN,
    COUNTRY_PATTERN,
    REGION_PATTERN,
    BUILDING_AREA_PATTERN,
    FENCED_AREA_PATTERN,
    FENCE_LENGTH_PATTERN,
    SYSTEM_RATING_PATTERN,
    SYSTEM_CAPACITY_MW_PATTERN,
    SYSTEM_LICENSE_PATTERN,
    STORAGE_CAPACITY_PATTERN,
    MODULE_TYPE_PATTERN,
    MODULE_COUNT_PATTERN,
    MODULE_POWER_PATTERN,
    MODULES_PER_STRING_PATTERN,
    MPPT_LABEL_PATTERN,
    PV_LABEL_PATTERN,
    ST_LABEL_PATTERN,
    TRACKER_PATTERN,
    BATTERY_CAPACITY_PATTERN,
    SUFFIX_STRING_PATTERN,
    INVERTER_MODEL_PATTERN,
    BATTERY_TYPE_PATTERN,
    BESS_INV_PATTERN,
    AREA_STRING_COUNT_PATTERN,
    MODULE_BREAKDOWN_PATTERN,
    INVALID_BARE_AB_RE,
    _first_match,
    _to_float,
    _to_int,
)

# ---------------------------------------------------------------------------
# String patterns
# ---------------------------------------------------------------------------

STRING_PATTERN = re.compile(r"^S\.?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$", re.IGNORECASE)
STRING_EXTRACT_PATTERN = re.compile(
    r"S\.?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?![\d.A-Za-z])", re.IGNORECASE
)
STRING_TOKEN_PATTERN = re.compile(
    r"\bS\.?[A-Za-z0-9]+(?:\.[A-Za-z0-9]+){2,4}\b", re.IGNORECASE
)
ANOMALY_PATTERN = re.compile(
    r"\b(S\.?\d+\.\d+\.\d+\.[0-9]*[A-Za-z][0-9A-Za-z]*)\b", re.IGNORECASE
)

# Catches dotted string-like labels STRING_TOKEN_PATTERN can miss (extra segments,
# letters/suffixes, hyphens) so they still surface as invalid when they fail the
# configured regex. Used by PDF and DXF via _extract_string_rows.
LOOSE_STRING_CANDIDATE_RE = re.compile(
    r"\bS\.?[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+){2,}\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Inverter patterns (from_chatgpt PatternService)
# static: "1.1", "2.3"  |  tracker: "1.1.1", "2.3.4"
# ---------------------------------------------------------------------------
INVERTER_STATIC_RE  = re.compile(r"^\d{1,3}\.\d{1,3}$")
INVERTER_TRACKER_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")

# ---------------------------------------------------------------------------
# AC asset / battery keywords (from_chatgpt AcService / BatteryService)
# ---------------------------------------------------------------------------
AC_KEYWORDS      = {"MV", "MV ROOM", "RMU", "TRAFO", "TRANSFORMER", "PCS", "ICB", "MVPS",
                    "HV", "LV ROOM", "SMA MVPS", "CABLE AC"}
BATTERY_KEYWORDS = {"BESS", "BATTERY", "BATTERY STORAGE", "BATTERY CONTAINER",
                    "ST5015", "GOTION", "ST "}

# ---------------------------------------------------------------------------
# Declared inverter / DC bucket patterns (user-provided parser improvement)
# ---------------------------------------------------------------------------
DECLARED_INVERTERS_RE = re.compile(r'Strings\s+Inverters\s*-\s*(\d+)\s*x', re.IGNORECASE)
DC_BUCKET_RE = re.compile(r'input\s+DC\s+(\d+)\s+Strings', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Extended metadata patterns (from_chatgpt MetadataService)
# ---------------------------------------------------------------------------
_META_PATTERNS: dict[str, str] = {
    "module_power_wp":       r"(?:Type of Module\s*/\s*Power|Module Power|Output of Solar Modules)\s*[-:]\s*.*?(\d{3,4})\s*W(?:p\b|\b(?!h))",
    "system_rating_kwp":     r"(?:System Rating|Plant System Rating)\s*[-:]\s*([\d,\.]+)\s*kWp",
    "modules_per_string":    r"Connection\s*[-:]\s*(\d+)\s*/\s*String",
    "battery_capacity_mwh":  r"(?:Storage Capacity|BESS\s+kWh\s+BoL)\s*[-:]\s*([\d,\.]+)\s*(MWh|kWh)",
    "inverter_count_doc":    r"(?:Number of Inverters?|Inverter Count|String Inverter\b)\s*[-:]\s*(\d+)",
    "tracker_rotation_deg":  r"System Rotation\s*[-:]\s*\+?-?([\d.]+)\s*deg",
    "azimuth_deg":           r"Azimuth\s*[-:]\s*([\d.]+)\s*deg",
    "total_strings_doc":     r"Total\s+Strings\s*[-:·]?\s*(\d{3,5})\b",
}

# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _preprocess_text(text: str) -> str:
    text = re.sub(r"(?<=[^\s])(S\.)", r" \1", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[^\s])(S(?=\d))", r" \1", text, flags=re.IGNORECASE)
    return text


def _extract_text_in_regions(page: Any, regions: list[dict]) -> str:
    mb = page.mediabox
    page_x0 = float(mb.left)
    page_y0 = float(mb.bottom)
    page_w = float(mb.right) - page_x0
    page_h = float(mb.top) - page_y0

    boxes: list[tuple[float, float, float, float]] = []
    for r in regions:
        x0 = page_x0 + r["x"] * page_w
        x1 = page_x0 + (r["x"] + r["w"]) * page_w
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


def _extract_text_from_pdf(content: bytes, regions: list[dict] | None = None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF parsing requires the 'pypdf' package") from exc

    reader = PdfReader(io.BytesIO(content), strict=False)

    if regions:
        page_texts = [_extract_text_in_regions(page, regions) for page in reader.pages]
        return _preprocess_text("\n".join(p for p in page_texts if p).strip())

    plain_parts: list[str] = []
    for page in reader.pages:
        plain_parts.append((page.extract_text() or "").strip())

    text_plain = _preprocess_text("\n".join(p for p in plain_parts if p).strip())
    n_plain = len(STRING_EXTRACT_PATTERN.findall(text_plain))

    # Only run the slower layout extraction if plain text found no strings
    if n_plain > 0:
        text = text_plain
    else:
        layout_parts: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                layout_parts.append((page.extract_text(extraction_mode="layout") or "").strip())
            except Exception:
                layout_parts.append(plain_parts[i])
        text_layout = _preprocess_text("\n".join(p for p in layout_parts if p).strip())
        n_layout = len(STRING_EXTRACT_PATTERN.findall(text_layout))
        text = text_layout if n_layout >= n_plain else text_plain

    if not text:
        raise ValueError("No text could be extracted from the PDF")
    return text

# ---------------------------------------------------------------------------
# Code normalisation & row building
# ---------------------------------------------------------------------------

def _pattern_search_regex(pattern_regex: str | None) -> re.Pattern[str]:
    if not pattern_regex:
        return STRING_EXTRACT_PATTERN
    inner = pattern_regex.strip()
    if inner.startswith("^"):
        inner = inner[1:]
    if inner.endswith("$"):
        inner = inner[:-1]
    return re.compile(rf"(?<![A-Za-z0-9])(?:{inner})(?![A-Za-z0-9])", re.IGNORECASE)


def _pattern_inner_for_partial(pattern_regex: str | None) -> str:
    """Inner regex fragment (no anchors) used to build a relaxed scan for near-misses."""
    if not pattern_regex:
        return r"S\.?\d+\.\d+\.\d+(?:\.\d+)?"
    inner = pattern_regex.strip()
    if inner.startswith("^"):
        inner = inner[1:]
    if inner.endswith("$"):
        inner = inner[:-1]
    return inner


def _relax_regex_digit_runs(inner: str) -> str:
    """Allow letter suffixes on numeric runs and extra dotted/hyphen segments (invalid strict matches)."""
    out = re.sub(r"\\d\{[^}]*\}", r"\\d+[A-Za-z0-9]*", inner)
    out = re.sub(r"\\d\+", r"\\d+[A-Za-z0-9]*", out)
    out = re.sub(r"\[0-9]\+", r"[0-9]+[A-Za-z0-9]*", out)
    return out


def _partial_pattern_search_regex(pattern_regex: str | None) -> re.Pattern[str] | None:
    """
    Search regex derived from the approved pattern: matches tokens that *look like* string codes
    (partial / relaxed shape) so they can be marked invalid when strict fullmatch fails.
    """
    inner = _pattern_inner_for_partial(pattern_regex)
    relaxed = _relax_regex_digit_runs(inner)
    body = f"(?:{relaxed})(?:[-.][A-Za-z0-9]+)*"
    try:
        return re.compile(
            rf"(?<![A-Za-z0-9])(?:{body})(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
    except re.error:
        return None


def _normalize_string_match(raw_value: str) -> dict[str, Any] | None:
    digits = [int(part) for part in re.findall(r"\d+", raw_value)]
    if len(digits) not in (3, 4):
        return None
    normalized = f"S.{digits[0]}.{digits[1]}.{digits[2]}"
    if len(digits) == 4:
        normalized += f".{digits[3]}"
    return {
        "raw_value": raw_value,
        "string_code": normalized,
        "section_no": digits[0],
        "block_no": digits[1],
        "string_no": digits[2],
        "fourth_no": digits[3] if len(digits) == 4 else None,
    }


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
        ranked.append(
            {
                **pattern,
                "match_count": match_count,
                "_rank": index,
            }
        )

    ranked.sort(
        key=lambda item: (
            -(item.get("match_count") or 0),
            0 if preferred_pattern_name and item.get("pattern_name") == preferred_pattern_name else 1,
            item.get("_rank", 0),
        )
    )

    detected = next((item for item in ranked if item.get("match_count", 0) > 0), None)
    selected = (
        next((item for item in ranked if preferred_pattern_name and item.get("pattern_name") == preferred_pattern_name), None)
        or detected
        or (ranked[0] if ranked else None)
    )

    return {
        "patterns": [
            {k: v for k, v in item.items() if k != "_rank"}
            for item in ranked
        ],
        "detected_pattern_name": detected.get("pattern_name") if detected else None,
        "selected_pattern_name": selected.get("pattern_name") if selected else None,
    }


def _extract_string_rows(
    text: str,
    pattern_regex: str | None = None,
    pattern_name: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    seen_valid_raw: set[str] = set()
    seen_invalid_raw: set[str] = set()
    row_id = 1

    search_re = _pattern_search_regex(pattern_regex)
    invalid_reason = (
        f"Does not match approved string pattern '{pattern_name}'."
        if pattern_name
        else "Does not match the expected string pattern."
    )

    for match in search_re.finditer(text):
        raw_value = match.group(0)
        upper_raw_val = raw_value.upper()
        if upper_raw_val in seen_valid_raw:
            continue
        normalized_parts = _normalize_string_match(raw_value)
        if normalized_parts is None:
            continue
        normalized = normalized_parts["string_code"]
        duplicate = normalized in seen_codes
        if not duplicate:
            seen_codes.add(normalized)
        seen_valid_raw.add(upper_raw_val)

        rows.append({
            "row_id": row_id,
            **normalized_parts,
            "is_valid": not duplicate,
            "invalid_reason": "Duplicate string code in document." if duplicate else None,
        })
        row_id += 1

    for match in STRING_TOKEN_PATTERN.finditer(text):
        raw_val = match.group(0)
        upper_raw = raw_val.upper()
        if upper_raw in seen_valid_raw or upper_raw in seen_invalid_raw:
            continue
        if search_re.fullmatch(raw_val):
            continue
        normalized_parts = _normalize_string_match(raw_val)
        seen_invalid_raw.add(upper_raw)
        rows.append({
            "row_id": row_id,
            "raw_value": raw_val,
            "string_code": None,
            "section_no": normalized_parts["section_no"] if normalized_parts else None,
            "block_no": normalized_parts["block_no"] if normalized_parts else None,
            "string_no": normalized_parts["string_no"] if normalized_parts else None,
            "fourth_no": normalized_parts["fourth_no"] if normalized_parts else None,
            "is_valid": False,
            "invalid_reason": invalid_reason,
        })
        row_id += 1

    for candidate in ANOMALY_PATTERN.findall(text):
        upper_candidate = candidate.upper()
        if upper_candidate in seen_valid_raw or upper_candidate in seen_invalid_raw:
            continue
        seen_invalid_raw.add(upper_candidate)
        rows.append({
            "row_id": row_id,
            "raw_value": candidate,
            "string_code": None,
            "section_no": None,
            "block_no": None,
            "string_no": None,
            "fourth_no": None,
            "is_valid": False,
            "invalid_reason": invalid_reason,
        })
        row_id += 1

    _LOOSE_RAW_MAX_LEN = 64
    partial_re = _partial_pattern_search_regex(pattern_regex)
    if partial_re:
        for match in partial_re.finditer(text):
            raw_val = match.group(0)
            if len(raw_val) > _LOOSE_RAW_MAX_LEN:
                continue
            if not any(ch.isdigit() for ch in raw_val):
                continue
            upper_raw = raw_val.upper()
            if upper_raw in seen_valid_raw or upper_raw in seen_invalid_raw:
                continue
            if search_re.fullmatch(raw_val):
                continue
            normalized_parts = _normalize_string_match(raw_val)
            seen_invalid_raw.add(upper_raw)
            rows.append({
                "row_id": row_id,
                "raw_value": raw_val,
                "string_code": None,
                "section_no": normalized_parts["section_no"] if normalized_parts else None,
                "block_no": normalized_parts["block_no"] if normalized_parts else None,
                "string_no": normalized_parts["string_no"] if normalized_parts else None,
                "fourth_no": normalized_parts["fourth_no"] if normalized_parts else None,
                "is_valid": False,
                "invalid_reason": invalid_reason,
            })
            row_id += 1

    for match in LOOSE_STRING_CANDIDATE_RE.finditer(text):
        raw_val = match.group(0)
        if len(raw_val) > _LOOSE_RAW_MAX_LEN:
            continue
        if not any(ch.isdigit() for ch in raw_val):
            continue
        upper_raw = raw_val.upper()
        if upper_raw in seen_valid_raw or upper_raw in seen_invalid_raw:
            continue
        if search_re.fullmatch(raw_val):
            continue
        normalized_parts = _normalize_string_match(raw_val)
        seen_invalid_raw.add(upper_raw)
        rows.append({
            "row_id": row_id,
            "raw_value": raw_val,
            "string_code": None,
            "section_no": normalized_parts["section_no"] if normalized_parts else None,
            "block_no": normalized_parts["block_no"] if normalized_parts else None,
            "string_no": normalized_parts["string_no"] if normalized_parts else None,
            "fourth_no": normalized_parts["fourth_no"] if normalized_parts else None,
            "is_valid": False,
            "invalid_reason": invalid_reason,
        })
        row_id += 1

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
        codes.sort(key=lambda code: tuple(int(p) for p in code.split(".")[1:]))
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
        low, high = min(numbers), max(numbers)
        missing = [f"{group_key}.{v}" for v in range(low, high + 1) if v not in numbers]
        if missing:
            gaps[group_key] = missing

    return dict(sorted(gaps.items(), key=lambda item: tuple(int(p) for p in item[0].split(".")[1:])))


def _build_duplicates(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            row["string_code"]
            for row in rows
            if row["invalid_reason"] == "Duplicate string code in document." and row["string_code"]
        },
        key=lambda code: tuple(int(p) for p in code.split(".")[1:]),
    )


def _build_anomalies(text: str) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for candidate in ANOMALY_PATTERN.findall(text):
        parts = candidate.split(".")
        first = parts[0].upper()
        if first == "S" and len(parts) >= 5:
            key = ".".join(parts[:4])
        elif first.startswith("S") and first[1:].isdigit() and len(parts) >= 4:
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
# 4-level string support: inverter key detection and row annotation
# ---------------------------------------------------------------------------

def _detect_string_level(rows: list[dict[str, Any]]) -> int:
    """
    Returns 4 if majority of valid rows carry a fourth_no, else 3.
    In 4-level mode: S.A.B.C.D → inverter key = A.B.C, string number = D.
    In 3-level mode: S.A.B.C   → inverter key = A.B,   string number = C.
    """
    valid = [r for r in rows if r.get("is_valid") and r.get("string_code")]
    if not valid:
        return 3
    with_fourth = sum(1 for r in valid if r.get("fourth_no") is not None)
    return 4 if with_fourth > len(valid) / 2 else 3


def _annotate_rows_with_inverter_key(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Adds two derived fields to every row in-place:
      inverter_key    – the grouping key for the parent inverter
      actual_string_no – the leaf string number within that inverter
    """
    level = _detect_string_level(rows)
    for row in rows:
        s = row.get("section_no")
        b = row.get("block_no")
        c = row.get("string_no")
        d = row.get("fourth_no")
        if s is None or b is None:
            row["inverter_key"] = None
            row["actual_string_no"] = None
        elif level == 4 and d is not None:
            row["inverter_key"] = f"{s}.{b}.{c}"
            row["actual_string_no"] = d
        else:
            row["inverter_key"] = f"{s}.{b}"
            row["actual_string_no"] = c
    return rows


# ---------------------------------------------------------------------------
# Per-inverter analytics (user parser improvement)
# ---------------------------------------------------------------------------

def _build_per_inverter_gaps(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    """
    {inverter_key: [missing_string_numbers]}

    Uses cluster-based gap detection rather than a raw min→max scan.
    String numbers are split into contiguous clusters (consecutive numbers
    with gaps ≤ MAX_CLUSTER_GAP between them).  Only the largest cluster is
    used for missing-string analysis, which prevents isolated outlier string
    numbers (e.g. misattributed high-numbered strings) from inflating the
    reported gap range.

    Example: inverter 1.16 has strings {1..22, 44, 45, 46, 47, 48}.
    → Cluster A: [1..22] (22 members)
    → Cluster B: [44..48] (5 members, jump of 22 — a separate cluster)
    → Main cluster: A → no missing strings reported for 1.16.
    """
    MAX_CLUSTER_GAP = 3  # numbers within this distance are in the same cluster

    grouped: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if not row.get("is_valid") or row.get("inverter_key") is None:
            continue
        n = row.get("actual_string_no")
        if n is not None:
            grouped[row["inverter_key"]].add(int(n))

    result: dict[str, list[int]] = {}
    for key, numbers in sorted(grouped.items()):
        if not numbers:
            continue

        sorted_nums = sorted(numbers)

        # Split into clusters separated by gaps > MAX_CLUSTER_GAP
        clusters: list[list[int]] = []
        current: list[int] = [sorted_nums[0]]
        for n in sorted_nums[1:]:
            if n - current[-1] <= MAX_CLUSTER_GAP:
                current.append(n)
            else:
                clusters.append(current)
                current = [n]
        clusters.append(current)

        # Use the largest cluster for gap analysis (most strings → main inverter body)
        main_cluster = max(clusters, key=len)
        lo, hi = main_cluster[0], main_cluster[-1]
        cluster_set = set(main_cluster)
        missing = [v for v in range(lo, hi + 1) if v not in cluster_set]
        if missing:
            result[key] = missing
    return result


def _build_per_inverter_duplicates(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    """
    {inverter_key: [duplicate_string_numbers]}
    Numbers that appear more than once under the same inverter key.
    """
    from collections import Counter
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        k = row.get("inverter_key")
        n = row.get("actual_string_no")
        if k and n is not None:
            grouped[k].append(int(n))

    result: dict[str, list[int]] = {}
    for key, numbers in sorted(grouped.items()):
        counts = Counter(numbers)
        dups = sorted(n for n, cnt in counts.items() if cnt > 1)
        if dups:
            result[key] = dups
    return result


def _build_per_inverter_outliers(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    """
    {inverter_key: [outlier_string_numbers]}

    Uses a conservative 3×IQR fence to detect string numbers that are
    anomalously distant from the bulk of strings for each inverter.
    Requires at least 4 strings and a non-zero IQR before flagging anything,
    which prevents false positives on inverters with naturally large string counts.
    """
    grouped: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if not row.get("is_valid") or row.get("inverter_key") is None:
            continue
        n = row.get("actual_string_no")
        if n is not None:
            grouped[row["inverter_key"]].add(int(n))

    result: dict[str, list[int]] = {}
    for key, numbers in sorted(grouped.items()):
        if len(numbers) < 4:
            continue  # too few points for meaningful statistics
        sorted_nums = sorted(numbers)
        cnt = len(sorted_nums)
        q1 = sorted_nums[cnt // 4]
        q3 = sorted_nums[(3 * cnt) // 4]
        iqr = q3 - q1
        if iqr == 0:
            continue  # all same — skip
        lo = q1 - 3 * iqr
        hi = q3 + 3 * iqr
        outliers = sorted(x for x in sorted_nums if x < lo or x > hi)
        if outliers:
            result[key] = outliers
    return result


def _build_inverter_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    {inverter_key: {string_count, min_string_no, max_string_no, string_numbers}}
    Only counts valid rows.
    """
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if not row.get("is_valid"):
            continue
        k = row.get("inverter_key")
        n = row.get("actual_string_no")
        if k and n is not None:
            grouped[k].append(int(n))

    result: dict[str, dict[str, Any]] = {}
    for key in sorted(grouped.keys()):
        numbers = sorted(set(grouped[key]))
        result[key] = {
            "string_count": len(numbers),
            "min_string_no": numbers[0] if numbers else None,
            "max_string_no": numbers[-1] if numbers else None,
            "string_numbers": numbers,
        }
    return result


def _extract_dc_buckets(text: str) -> list[int]:
    """
    Extract 'input DC N Strings' bucket sizes declared in the drawing.
    e.g. "input DC 21 Strings" → 21. Multiple values possible (variable-length inputs).
    Also collects counts matched by AREA_STRING_COUNT_PATTERN (18-22 STRINGS).
    """
    seen: set[int] = set()
    result: list[int] = []
    for m in DC_BUCKET_RE.finditer(text):
        v = int(m.group(1))
        if v not in seen:
            seen.add(v)
            result.append(v)
    # Also check AREA_STRING_COUNT_PATTERN for secondary area-level string counts
    try:
        for match_str in AREA_STRING_COUNT_PATTERN.findall(text):
            c = int(match_str)
            if c not in seen:
                seen.add(c)
                result.append(c)
    except Exception:
        pass
    return sorted(result)


# ---------------------------------------------------------------------------
# Token extraction (labels from raw text)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Split text into individual word tokens for label matching."""
    return [t.strip() for t in re.split(r"\s+", text) if t.strip()]


# ---------------------------------------------------------------------------
# Inverter extraction (from_chatgpt InverterService + PatternService)
# ---------------------------------------------------------------------------

_INVERTER_FREQ_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\b")
_INVERTER_TRACKER_FREQ_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{1,2})\b")
# Minimum occurrences for a N.N token to be considered a real inverter label.
# Real inverter labels repeat many times (once per connected string); noise appears ≤ a few times.
_INVERTER_MIN_FREQ = 5


def _extract_inverters(
    tokens: list[str],
    string_rows: list[dict[str, Any]] | None = None,
    text: str | None = None,
) -> list[dict[str, Any]]:
    """
    Detect inverter labels using frequency-based word-boundary scanning on the full text.
    In design PDFs, inverter labels (N.N) appear many times because each string label
    S.N.B.X embeds the N.B pair. Noise tokens appear only 1-3 times.

    Falls back to string-row derivation for inverters that have no strings assigned,
    then to whitespace-token scan if no text or string data is available.
    """
    from collections import Counter

    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Primary: frequency scan on full text (catches all labeled inverters)
    if text:
        counts = Counter(m.group(0) for m in _INVERTER_FREQ_RE.finditer(text))
        for token, cnt in sorted(
            counts.items(),
            key=lambda x: tuple(int(p) for p in x[0].split(".")),
        ):
            if cnt >= _INVERTER_MIN_FREQ and token not in seen:
                seen.add(token)
                results.append({"raw_name": token, "normalized_name": token, "pattern": "frequency_scan"})

    # Supplementary: string-row derivation fills in inverters with no strings assigned.
    # Uses inverter_key if rows have been annotated (supports both 3-level and 4-level).
    if string_rows:
        for row in sorted(
            string_rows,
            key=lambda r: (r.get("section_no") or 999, r.get("block_no") or 999,
                           r.get("string_no") or 999),
        ):
            if not row.get("is_valid"):
                continue
            # Prefer inverter_key if available (set by _annotate_rows_with_inverter_key)
            inv = row.get("inverter_key")
            if inv is None:
                s = row.get("section_no")
                b = row.get("block_no")
                if s is None or b is None:
                    continue
                inv = f"{s}.{b}"
            if inv not in seen:
                seen.add(inv)
                results.append({"raw_name": inv, "normalized_name": inv, "pattern": "derived_from_string"})

    if results:
        return results

    # Last-resort: whitespace-token scan (when neither text nor string data available)
    for t in tokens:
        if t in seen:
            continue
        if INVERTER_STATIC_RE.match(t):
            seen.add(t)
            results.append({"raw_name": t, "normalized_name": t, "pattern": "static"})
        elif INVERTER_TRACKER_RE.match(t):
            seen.add(t)
            results.append({"raw_name": t, "normalized_name": t, "pattern": "tracker"})
        if len(results) >= 500:
            break
    return results


def _fill_and_extend_inverters(
    inverters: list[dict[str, Any]],
    doc_count: int | None,
    string_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    1. Gap-fill: add inverters missing within a section's min-max range.
    2. Extend: if total still < doc_count, grow sections symmetrically.
    Returns sorted list with strings_count added per inverter.
    """
    from collections import defaultdict

    # Build per-inverter string count from valid string rows
    inv_str_counts: dict[str, int] = defaultdict(int)
    if string_rows:
        for row in string_rows:
            s = row.get("section_no")
            b = row.get("block_no")
            if s and b and row.get("is_valid"):
                inv_str_counts[f"{s}.{b}"] += 1

    seen: set[str] = {inv["raw_name"] for inv in inverters}
    result: list[dict[str, Any]] = [dict(inv) for inv in inverters]

    # Step 1: gap-fill within each section's range
    by_section: dict[int, set[int]] = defaultdict(set)
    for inv in result:
        parts = inv["raw_name"].split(".")
        if len(parts) == 2:
            by_section[int(parts[0])].add(int(parts[1]))

    for section, blocks in sorted(by_section.items()):
        for b in range(min(blocks), max(blocks) + 1):
            label = f"{section}.{b}"
            if label not in seen:
                seen.add(label)
                by_section[section].add(b)
                result.append({"raw_name": label, "normalized_name": label, "pattern": "gap_fill"})

    # Step 2: extend to doc_count by growing sections with lower max
    if doc_count and len(result) < doc_count:
        # Recalculate after gap fill
        by_section2: dict[int, set[int]] = defaultdict(set)
        for inv in result:
            parts = inv["raw_name"].split(".")
            if len(parts) == 2:
                by_section2[int(parts[0])].add(int(parts[1]))

        global_max = max(max(blocks) for blocks in by_section2.values())

        while len(result) < doc_count:
            # Extend the section with the smallest current max block
            section = min(by_section2.keys(), key=lambda s: max(by_section2[s]))
            next_b = max(by_section2[section]) + 1
            if next_b > global_max + 10:  # safety cap
                break
            label = f"{section}.{next_b}"
            if label not in seen:
                seen.add(label)
                by_section2[section].add(next_b)
                result.append({"raw_name": label, "normalized_name": label, "pattern": "inferred"})

    # Add strings_count to every inverter
    for inv in result:
        inv["strings_count"] = inv_str_counts.get(inv["raw_name"], 0)

    return sorted(result, key=lambda x: tuple(int(p) for p in x["raw_name"].split(".")))


# ---------------------------------------------------------------------------
# AC asset extraction (from_chatgpt AcService)
# ---------------------------------------------------------------------------

def _extract_ac_assets(tokens: list[str]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for t in tokens:
        upper = t.upper()
        if upper in seen:
            continue
        if any(k in upper for k in AC_KEYWORDS):
            seen.add(upper)
            results.append({"asset_type": "ac", "raw_name": t, "normalized_name": t})
    return results


# ---------------------------------------------------------------------------
# Battery extraction (from_chatgpt BatteryService)
# ---------------------------------------------------------------------------

def _extract_batteries(tokens: list[str]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for t in tokens:
        upper = t.upper()
        if upper in seen:
            continue
        if any(k in upper for k in BATTERY_KEYWORDS):
            seen.add(upper)
            results.append({"asset_type": "battery", "raw_name": t, "normalized_name": t})
    return results


# ---------------------------------------------------------------------------
# MPPT channel extraction
# ---------------------------------------------------------------------------

_MPPT_CH_RE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{1,2})\.(\d{1,2})\.(\d+)([AB])')
_MAX_MPPT = 15
_MAX_DC = 5
_MAX_SECTION = 9
_MAX_UNIT = 9


def _extract_mppt_channels(text: str) -> list[dict[str, Any]]:
    """
    Extract MPPT channel assignments: {section}.{unit}.{dc_terminal}.{mppt_no}.{pos}{side}
    e.g. '2.2.2.5.1A' → ICB-area-2.2, DC terminal 2, MPPT 5, channel 1A.
    """
    from collections import defaultdict
    by_key: dict[str, list[str]] = defaultdict(list)

    for m in _MPPT_CH_RE.finditer(text):
        s, u, dc, mp, pos, side = m.groups()
        s, u, dc, mp, pos = int(s), int(u), int(dc), int(mp), int(pos)
        # Filter: realistic value ranges
        if s > _MAX_SECTION or u > _MAX_UNIT or dc > _MAX_DC or mp > _MAX_MPPT or pos > _MAX_MPPT:
            continue
        key = f"{s}.{u}|DC{dc}|MPPT{mp}"
        raw_label = m.group(0)
        if raw_label not in by_key[key]:
            by_key[key].append(raw_label)

    results: list[dict[str, Any]] = []
    for key, labels in sorted(by_key.items()):
        zone_part, dc_part, mppt_part = key.split("|")
        dc_no = int(dc_part[2:])
        mppt_no = int(mppt_part[4:])
        results.append({
            "icb_zone": f"ICB-area-{zone_part}",
            "dc_terminal_no": dc_no,
            "mppt_no": mppt_no,
            "string_count": len(labels),
            "channel_labels": labels,
            "expected_string_count": None,
        })
    return results


def _extract_icb_zones(text: str) -> list[dict[str, Any]]:
    """Extract ICB area labels from design document."""
    _ICB_RE = re.compile(r'ICB-area-(\d+\.\d+)', re.IGNORECASE)
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for m in _ICB_RE.finditer(text):
        label = m.group(1)
        if label not in seen:
            seen.add(label)
            results.append({"label": f"ICB-area-{label}", "zone_id": label})
    return results


# ---------------------------------------------------------------------------
# Suffix string extraction (A/B side pairs)
# ---------------------------------------------------------------------------

def _extract_suffix_strings(text: str) -> list[dict[str, Any]]:
    """Extract A/B suffix string pairs like 1.1.1.1A and 1.1.1.1B."""
    results: list[dict[str, Any]] = []
    try:
        for m in SUFFIX_STRING_PATTERN.finditer(text):
            base_id = m.group(1)
            suffix = m.group(2).upper()
            results.append({"base_id": base_id, "suffix": suffix, "full_id": f"{base_id}{suffix}"})
    except Exception:
        pass
    return results


def _validate_suffix_pairs(suffix_strings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check that every A has a matching B and vice versa."""
    from collections import defaultdict
    issues: list[dict[str, Any]] = []
    try:
        by_base: dict[str, set] = defaultdict(set)
        for s in suffix_strings:
            by_base[s["base_id"]].add(s["suffix"])
        for base_id, sides in sorted(by_base.items()):
            if "A" in sides and "B" not in sides:
                issues.append({"base_id": base_id, "issue": "missing_B", "found": "A only"})
            elif "B" in sides and "A" not in sides:
                issues.append({"base_id": base_id, "issue": "missing_A", "found": "B only"})
    except Exception:
        pass
    return issues


# ---------------------------------------------------------------------------
# MPPT label grouping (from_chatgpt extractors.extract_mppt_summary)
# ---------------------------------------------------------------------------

# PV-label ranges assigned per MPPT index (1-based).
# Mirrors the logic in from_chatgpt/solarica_parsers/extractors.py.
_MPPT_PV_RANGES: dict[int, list[int]] = {
    1: [1, 2, 3, 4],
    2: [5, 6, 7, 8, 9],
    3: [10, 11, 12, 13, 14],
    4: [15, 16, 17, 18],
    5: [19, 20, 21, 22, 23],
    6: [24, 25, 26, 27, 28],
}


def _extract_mppt_groups(text: str) -> list[dict[str, Any]]:
    """
    Find all MPPT labels (MPPT1, MPPT2, …) and PV labels (PV1, PV2, …) in *text*.
    Group PV labels to their parent MPPT based on a fixed sequence mapping.
    Each group also carries an estimated_string_count equal to the number of
    PV labels assigned to it.

    Returns a list of dicts::

        [
            {
                "mppt_no": 1,
                "mppt_label": "MPPT1",
                "pv_labels": ["PV1", "PV2", "PV3"],
                "estimated_string_count": 3,
            },
            …
        ]
    """
    try:
        mppt_nums = sorted(set(int(n) for n in MPPT_LABEL_PATTERN.findall(text)))
        pv_nums = sorted(set(int(n) for n in PV_LABEL_PATTERN.findall(text)))
        pv_set = set(pv_nums)

        # Extract ST labels (e.g. ST1, ST2, …)
        st_nums = sorted(set(int(n) for n in ST_LABEL_PATTERN.findall(text)))

        groups: list[dict[str, Any]] = []
        for idx, mppt_n in enumerate(mppt_nums):
            candidate_pvs = _MPPT_PV_RANGES.get(mppt_n, [])
            assigned = [f"PV{i}" for i in candidate_pvs if i in pv_set]
            # Assign ST labels sequentially — one ST label per MPPT in order
            st_label = f"ST{st_nums[idx]}" if idx < len(st_nums) else None
            st_labels = [st_label] if st_label is not None else []
            groups.append({
                "mppt_no": mppt_n,
                "mppt_label": f"MPPT{mppt_n}",
                "pv_labels": assigned,
                "st_labels": st_labels,
                "estimated_string_count": len(assigned),
            })
        return groups
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Per-page text extraction (pdfplumber)
# ---------------------------------------------------------------------------

def _extract_text_per_page(pdf_path: str) -> dict[int, str]:
    """
    Extract text from each page of the PDF at *pdf_path* using pdfplumber.
    Returns ``{page_num: text}`` where page_num is 1-based.

    Falls back to an empty dict (non-fatal) if pdfplumber is unavailable or
    any error occurs.
    """
    try:
        import pdfplumber  # type: ignore
        result: dict[int, str] = {}
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    result[i] = page.extract_text() or ""
                except Exception:
                    result[i] = ""
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Extended metadata (from_chatgpt MetadataService)
# ---------------------------------------------------------------------------

def _extract_extended_metadata(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, pattern in _META_PATTERNS.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        raw = m.group(1).replace(",", "")
        value: float | int = float(raw) if "." in raw else int(raw)
        if key == "battery_capacity_mwh" and len(m.groups()) > 1 and m.group(2).lower() == "kwh":
            value = float(raw) / 1000
        out[key] = value
    # inverter_count_doc alternative: "Strings Inverters - N x"
    if "inverter_count_doc" not in out:
        m2 = DECLARED_INVERTERS_RE.search(text)
        if m2:
            out["inverter_count_doc"] = int(m2.group(1))

    # Tracker: if System Rotation was extracted → tracker site; also catch "tracker" keyword
    out["tracker_enabled"] = (
        "tracker_rotation_deg" in out
        or bool(re.search(r"\btracker\b", text, re.IGNORECASE))
    )
    # Battery coupling (text value — extracted separately)
    coupling_m = re.search(
        r"(?:Storage\s+coupling|Battery\s+coupling)\s*[-:]\s*([A-Za-z][A-Za-z\s]{2,30}coupling)",
        text, re.IGNORECASE,
    )
    if coupling_m:
        out["battery_coupling"] = coupling_m.group(1).strip()

    # ── Extra fields from extra_patterns (non-fatal) ────────────────────────
    try:
        # Project name (extra_patterns PROJECT_NAME_PATTERNS)
        project_name = _first_match(PROJECT_NAME_PATTERNS, text)
        if project_name:
            out["project_name"] = project_name
    except Exception:
        pass

    try:
        # Inverter models, battery type, BESS inverter (extra_patterns)
        inverter_models = list(set(INVERTER_MODEL_PATTERN.findall(text)))
        if inverter_models:
            out["inverter_models"] = inverter_models
        battery_type = _first_match([BATTERY_TYPE_PATTERN], text)
        if battery_type:
            out["battery_type"] = battery_type
        bess_inv = _first_match([BESS_INV_PATTERN], text)
        if bess_inv:
            out["bess_inv"] = bess_inv
    except Exception:
        pass

    try:
        # Coordinates (raw string, e.g. "33°12'N 36°45'E")
        if "coordinates" not in out:
            coords_raw = _first_match(COORDINATES_PATTERN, text)
            if coords_raw:
                out["coordinates"] = coords_raw.strip()

        # Country / region (extra_patterns versions are more permissive)
        if "country" not in out:
            c = _first_match(COUNTRY_PATTERN, text)
            if c:
                out["country"] = c.strip()
        if "region" not in out:
            r = _first_match(REGION_PATTERN, text)
            if r:
                out["region"] = r.strip()

        # Site dimensions
        if "building_area_ha" not in out:
            out["building_area_ha"] = _to_float(_first_match(BUILDING_AREA_PATTERN, text))
        if "fenced_area_ha" not in out:
            out["fenced_area_ha"] = _to_float(_first_match(FENCED_AREA_PATTERN, text))
        if "fence_length_m" not in out:
            out["fence_length_m"] = _to_float(_first_match(FENCE_LENGTH_PATTERN, text))

        # System rating (extra_patterns variant uses "Plant System Rating")
        if "system_rating_kwp" not in out:
            out["system_rating_kwp"] = _to_float(_first_match(SYSTEM_RATING_PATTERN, text))

        # System license
        if "system_license" not in out:
            out["system_license"] = _first_match(SYSTEM_LICENSE_PATTERN, text)

        # Storage capacity (MWh — extra_patterns pattern)
        if "storage_capacity_mwh" not in out:
            sc_raw = _first_match(STORAGE_CAPACITY_PATTERN, text)
            if sc_raw:
                out["storage_capacity_mwh"] = _to_float(sc_raw)
    except Exception:
        pass

    return out


# ---------------------------------------------------------------------------
# Output validation (from_chatgpt OutputValidationService)
# ---------------------------------------------------------------------------

def _validate_output(
    meta: dict[str, Any],
    ext_meta: dict[str, Any],
    string_count: int,
    inverters: list[dict[str, Any]] | None = None,
    # ext_meta is already passed for all rules; this signature is intentional
) -> list[dict[str, Any]]:
    """
    Cross-check extracted metadata against calculated values.
    Returns list of validation findings.
    """
    findings: list[dict[str, Any]] = []

    module_count       = meta.get("module_count")
    module_power_wp    = ext_meta.get("module_power_wp")
    reported_kwp       = ext_meta.get("system_rating_kwp")
    plant_capacity_mw  = meta.get("plant_capacity_mw")
    modules_per_string = ext_meta.get("modules_per_string")

    # Use plant_capacity_mw → kWp if system_rating_kwp not found
    if reported_kwp is None and plant_capacity_mw is not None:
        reported_kwp = plant_capacity_mw * 1000

    # Rule 1: calculated kWp vs reported kWp
    if module_count and module_power_wp and reported_kwp is not None:
        calculated_kwp = round((module_count * module_power_wp) / 1000, 1)
        if abs(round(reported_kwp, 1) - calculated_kwp) > max(1.0, calculated_kwp * 0.01):
            findings.append({
                "risk_code": "DESIGN_OUTPUT_MISMATCH",
                "severity": "high",
                "title": "Reported output differs from calculated output",
                "description": f"Reported {reported_kwp} kWp, calculated {calculated_kwp} kWp "
                               f"({module_count} modules × {module_power_wp} Wp)",
                "recommendations": ["Verify module count and module power in the design document"],
            })

    # Rule 2: module count divisibility by modules per string
    if module_count and modules_per_string:
        if int(module_count) % int(modules_per_string) != 0:
            findings.append({
                "risk_code": "MODULE_STRING_DIVISIBILITY",
                "severity": "medium",
                "title": "Module count not divisible by modules per string",
                "description": f"{module_count} modules / {modules_per_string} per string = "
                               f"{module_count / modules_per_string:.2f}",
                "recommendations": ["Check for mixed string lengths", "Review module count"],
            })

    # Rule 3: detected string count vs expected
    if module_count and modules_per_string and string_count > 0:
        if int(module_count) % int(modules_per_string) == 0:
            expected = int(module_count) // int(modules_per_string)
            if expected != string_count:
                findings.append({
                    "risk_code": "STRING_COUNT_MISMATCH",
                    "severity": "high",
                    "title": "Detected string count differs from expected",
                    "description": f"Expected {expected} strings, detected {string_count}",
                    "recommendations": [
                        "Review OCR/parser coverage",
                        "Check if all string labels are captured",
                    ],
                })

    # Rule 4: no inverters detected
    if inverters is not None and not inverters:
        findings.append({
            "risk_code": "NO_INVERTERS_DETECTED",
            "severity": "high",
            "title": "No inverters detected",
            "description": "No inverter entities were extracted from the drawing.",
            "recommendations": ["Review inverter label format", "Check if inverter section is captured"],
        })

    # Rule 5: inverter count mismatch (documented vs detected)
    inverter_count_doc = ext_meta.get("inverter_count_doc")
    if inverters is not None and inverter_count_doc and len(inverters) != int(float(inverter_count_doc)):
        findings.append({
            "risk_code": "INVERTER_COUNT_MISMATCH",
            "severity": "medium",
            "title": "Detected inverter count differs from documented count",
            "description": f"Document states {int(float(inverter_count_doc))} inverters, "
                           f"detected {len(inverters)} from string assignments.",
            "recommendations": [
                "Check if all inverters have strings assigned in the drawing",
                "Verify inverter numbering is complete",
            ],
        })

    return findings


# ---------------------------------------------------------------------------
# Risk identification (from_chatgpt RiskService)
# ---------------------------------------------------------------------------

def _identify_risks(
    duplicates: list[str],
    ext_meta: dict[str, Any],
    ac_assets: list[dict[str, Any]],
    batteries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Additional risk rules from from_chatgpt RiskService:
    DUPLICATE_STRING, TRACKER_SITE_LOW_CONTEXT, BESS_COUPLING_UNCLEAR.
    """
    findings: list[dict[str, Any]] = []

    for d in duplicates:
        findings.append({
            "risk_code": "DUPLICATE_STRING",
            "severity": "high",
            "title": "Duplicate string label detected",
            "description": f"String label appears more than once: {d}",
            "recommendations": ["Review drawing for duplicate annotations"],
        })

    if ext_meta.get("tracker_enabled") and not ac_assets:
        findings.append({
            "risk_code": "TRACKER_SITE_LOW_CONTEXT",
            "severity": "medium",
            "title": "Tracker site without AC context",
            "description": "Tracker site detected but no AC assets were extracted.",
            "recommendations": ["Check parser coverage", "Review DXF layers for AC equipment"],
        })

    if batteries and not ext_meta.get("battery_coupling"):
        findings.append({
            "risk_code": "BESS_COUPLING_UNCLEAR",
            "severity": "medium",
            "title": "Battery system detected but coupling type not extracted",
            "description": "Battery/BESS assets found but coupling type metadata was not extracted.",
            "recommendations": ["Extract coupling type from design documents"],
        })

    return findings


# ---------------------------------------------------------------------------
# MPPT sequence validation
# ---------------------------------------------------------------------------

def _validate_mppt_sequence(mppt_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect missing or duplicate MPPT numbers in the sequence."""
    issues: list[dict[str, Any]] = []
    try:
        if not mppt_groups:
            return issues
        mppt_numbers = [g["mppt_no"] for g in mppt_groups]
        seen: set[int] = set()
        for n in mppt_numbers:
            if n in seen:
                issues.append({"mppt_no": n, "issue": "duplicate_mppt_label"})
            seen.add(n)
        expected = set(range(min(mppt_numbers), max(mppt_numbers) + 1))
        for missing in sorted(expected - seen):
            issues.append({"mppt_no": missing, "issue": "missing_mppt_label"})
    except Exception:
        pass
    return issues


# ---------------------------------------------------------------------------
# Site metadata parsing
# ---------------------------------------------------------------------------

def _search(pattern: str, text: str, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return None


def _detect_installation_type(text: str, site_name: str) -> str:
    """
    Classify the installation type from site name and drawing text.
    Returns one of: floating_utility_scale_pv, utility_scale_pv, rooftop, unknown.
    """
    combined = (site_name + " " + text[:2000]).upper()
    if "FPV" in combined or "FLOATING" in combined:
        return "floating_utility_scale_pv"
    if re.search(r"\b(UTILITY|GROUND.MOUNT|GROUND MOUNT|GROUND-MOUNT|MW|MWP|MWH)\b", combined):
        return "utility_scale_pv"
    if re.search(r"\b(ROOFTOP|ROOF.TOP|CARPORT|CANOPY)\b", combined):
        return "rooftop"
    return "unknown"


def _extract_invalid_ab_labels(text: str) -> list[str]:
    """
    Bare five-level numeric tokens + trailing A/B without an S prefix (e.g. 2.2.2.5.1A).
    S-prefixed and other non-conforming names are picked up by _extract_string_rows via
    LOOSE_STRING_CANDIDATE_RE and appear in invalid_rows / scan analytics.
    """
    found: set[str] = set()
    for m in INVALID_BARE_AB_RE.finditer(text):
        found.add(m.group(1))
    return sorted(found)


def _extract_module_breakdown(text: str) -> list[dict[str, Any]]:
    """
    Parse multi-type module declarations like:
      "17,170 x 610W and 2,268 x 620W"
      "15,498 modules 580Wp"
    Returns list of {count, power_wp} dicts.
    Only returns results when more than one type is found, or when a multi-module
    sentence is detected (to avoid duplicating the single MODULE_POWER_PATTERN logic).
    """
    matches = MODULE_BREAKDOWN_PATTERN.findall(text)
    if len(matches) < 2:
        return []
    breakdown = []
    for count_str, power_str in matches:
        count = int(count_str.replace(",", ""))
        power = int(power_str)
        breakdown.append({"count": count, "power_wp": power})
    return breakdown


def _compute_module_math_kwp(breakdown: list[dict[str, Any]]) -> float | None:
    """
    Given [{count, power_wp}, ...], compute total kWp.
    Returns None if breakdown is empty.
    """
    if not breakdown:
        return None
    return round(sum(b["count"] * b["power_wp"] for b in breakdown) / 1000, 2)


def _check_capacity_inconsistency(
    system_rating_kwp: float | None,
    plant_capacity_mw: float | None,
    module_math_kwp: float | None,
) -> list[dict[str, Any]]:
    """
    Cross-check all three declared capacity figures.
    Reports CAPACITY_INCONSISTENCY when any two differ by more than 1%.
    """
    findings: list[dict[str, Any]] = []
    values: dict[str, float] = {}
    if system_rating_kwp is not None:
        values["Plant System Rating"] = round(system_rating_kwp, 2)
    if plant_capacity_mw is not None:
        values["System Capacity"] = round(plant_capacity_mw * 1000, 2)
    if module_math_kwp is not None:
        values["Module math"] = module_math_kwp

    if len(values) < 2:
        return findings

    keys = list(values.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a_label, b_label = keys[i], keys[j]
            a_val, b_val = values[a_label], values[b_label]
            avg = (a_val + b_val) / 2
            if avg == 0:
                continue
            diff_pct = abs(a_val - b_val) / avg * 100
            if diff_pct > 1.0:
                findings.append({
                    "risk_code": "CAPACITY_INCONSISTENCY",
                    "severity": "high",
                    "title": "Declared capacity figures are inconsistent",
                    "description": (
                        f"{a_label} = {a_val:,.2f} kWp vs "
                        f"{b_label} = {b_val:,.2f} kWp "
                        f"(Δ {diff_pct:.1f}%)"
                    ),
                    "recommendations": [
                        "Clarify the authoritative capacity figure before final design approval",
                        "Check if module count, module power, or system rating contains a typo",
                    ],
                })

    return findings


def _derive_layout_name(text: str, filename: str) -> str:
    from_text = _search(r"\b([A-Z]{3}_[A-Z]_\d+_Color Map)\b", text, re.IGNORECASE)
    if from_text:
        return from_text.replace(" ", "_")
    stem = Path(filename).stem
    stem = re.sub(r"_rev[^_]+$", "", stem, flags=re.IGNORECASE)
    return stem.replace(" ", "_")


def _derive_site_code(layout_name: str) -> str:
    match = re.match(r"([A-Za-z0-9]+_[A-Za-z0-9]+_\d+)", layout_name)
    if match:
        return match.group(1).upper()
    return layout_name.split("_")[0].upper()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_site_design_preview(
    content: bytes,
    filename: str,
    regions: list[dict] | None = None,
    approved_pattern_regex: str | None = None,
    approved_pattern_name: str | None = None,
    extracted_text: str | None = None,
) -> dict[str, Any]:
    """
    Parse a PDF design file and return strings, gaps, duplicates, anomalies
    and site metadata.  Does NOT write to DB.
    """
    text = extracted_text if extracted_text is not None else _extract_text_from_pdf(content, regions=regions)
    rows = _extract_string_rows(
        text,
        pattern_regex=approved_pattern_regex,
        pattern_name=approved_pattern_name,
    )

    if not rows:
        raise ValueError("No solar string IDs were found in the PDF")

    layout_name = _derive_layout_name(text, filename)
    site_code = _derive_site_code(layout_name)
    site_name_match = _search(r"\b([A-Za-z0-9-]+-FPV)\b", text)
    site_name = site_name_match or site_code

    rows_sorted = sorted(
        rows,
        key=lambda r: (
            r["section_no"] if r["section_no"] is not None else 10**9,
            r["block_no"] if r["block_no"] is not None else 10**9,
            r["string_no"] if r["string_no"] is not None else 10**9,
            r["raw_value"],
        ),
    )
    # Annotate rows with inverter_key + actual_string_no (4-level aware)
    _annotate_rows_with_inverter_key(rows_sorted)
    valid_rows = [r for r in rows_sorted if r["is_valid"]]
    invalid_rows = [r for r in rows_sorted if not r["is_valid"]]

    strings_map = _build_strings_map(rows_sorted)
    gaps = _build_gaps(rows_sorted)
    duplicates = _build_duplicates(rows_sorted)
    anomalies = _build_anomalies(text)

    latitude = _parse_float(_search(r"Coordinates\s+([0-9.]+)\s*N", text, re.IGNORECASE))
    longitude = _parse_float(_search(r"Coordinates\s+[0-9.]+\s*N\s+([0-9.]+)\s*E", text, re.IGNORECASE))
    country = _search(r"Country\s*-\s*([A-Z][A-Z ]+)", text)
    region = _search(r"Region\s*/\s*Province\s*-\s*([A-Z][A-Z ]+)", text)
    plant_capacity_mw = _parse_float(_search(r"System Capacity\s*-\s*([0-9.]+)\s*MW", text, re.IGNORECASE))
    module_type = _search(r"Type of Module / Power\s*-\s*([A-Z0-9-]+)", text, re.IGNORECASE)
    module_count = _parse_int(_search(r"Number of\s+Modules\s*-\s*([0-9,]+)", text, re.IGNORECASE))

    # ── Extended analysis (from_chatgpt integration) ──
    tokens = _tokenize(text)
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
    mppt_channels = _extract_mppt_channels(text)
    icb_zones = _extract_icb_zones(text)
    dc_buckets = _extract_dc_buckets(text)

    # ── Installation type ──
    installation_type = _detect_installation_type(text, site_name)

    # ── Invalid bare A/B labels (e.g. 2.2.2.5.1A — break string naming rule) ──
    invalid_ab_labels = _extract_invalid_ab_labels(text)

    # ── Multi-type module breakdown + module-math kWp ──
    module_breakdown = _extract_module_breakdown(text)
    module_math_kwp = _compute_module_math_kwp(module_breakdown)

    # ── Capacity inconsistency check ──
    capacity_findings = _check_capacity_inconsistency(
        system_rating_kwp=ext_meta.get("system_rating_kwp"),
        plant_capacity_mw=plant_capacity_mw,
        module_math_kwp=module_math_kwp,
    )

    # ── Suffix string extraction (A/B pairs) ──
    # Only valid for sites where strings use an explicit A/B side suffix
    # (e.g. S.1.1.1.1A / S.1.1.1.1B).  For standard S.N.N.N sites this
    # produces only false-positives from MPPT channel labels, so we skip it.
    suffix_strings: list[dict[str, Any]] = []
    suffix_string_issues: list[dict[str, Any]] = []
    # (suffix analysis deliberately disabled — use only for A/B-suffix sites)

    # ── MPPT label grouping (new) ──
    mppt_groups: list[dict[str, Any]] = []
    mppt_validation_issues: list[dict[str, Any]] = []
    try:
        mppt_groups = _extract_mppt_groups(text)
        mppt_validation_issues = _validate_mppt_sequence(mppt_groups)
    except Exception:
        pass

    # ── Per-page text extraction (pdfplumber) + page count ──
    _page_texts: dict[int, str] = {}
    page_count: int | None = None
    try:
        # _extract_text_per_page requires a file path; only call when content was
        # originally a path string.  For in-memory bytes we skip pdfplumber and
        # fall back to pypdf page count only.
        _page_texts = _extract_text_per_page(None)  # no-op — returns {}
        page_count = len(_page_texts) if _page_texts else None
    except Exception:
        _page_texts = {}
        page_count = None
    if page_count is None:
        try:
            from pypdf import PdfReader as _PdfReader
            page_count = len(_PdfReader(io.BytesIO(content), strict=False).pages)
        except Exception:
            pass

    # ── Per-inverter analytics ──
    inverter_summary = _build_inverter_summary(valid_rows)
    missing_strings_by_inverter = _build_per_inverter_gaps(valid_rows)
    duplicate_string_numbers_by_inverter = _build_per_inverter_duplicates(rows_sorted)
    outlier_strings_by_inverter = _build_per_inverter_outliers(valid_rows)

    # ── Reclassify outlier rows as invalid ────────────────────────────────
    # Strings whose number is statistically far outside the cluster for their
    # inverter are almost always PDF text-extraction artifacts (e.g. "S.1.16.1"
    # concatenated with adjacent text "21" → "S.1.16.121").  Mark them invalid
    # so they are excluded from DB save and appear in the invalid-strings list.
    if outlier_strings_by_inverter:
        for row in rows_sorted:
            if not row.get("is_valid") or row.get("inverter_key") is None:
                continue
            inv_key = row["inverter_key"]
            actual_no = row.get("actual_string_no")
            if actual_no is not None and actual_no in (outlier_strings_by_inverter.get(inv_key) or []):
                row["is_valid"] = False
                row["invalid_reason"] = (
                    f"String number {actual_no} is far outside the expected range for "
                    f"inverter {inv_key} — likely a PDF text-extraction artifact."
                )
        # Rebuild valid/invalid splits and clear outlier map (they are now in invalid_rows)
        valid_rows   = [r for r in rows_sorted if r["is_valid"]]
        invalid_rows = [r for r in rows_sorted if not r["is_valid"]]
        outlier_strings_by_inverter = {}   # no longer separate — merged into invalid

    base_meta: dict[str, Any] = {
        "module_count": module_count,
        "plant_capacity_mw": plant_capacity_mw,
    }
    validation_findings = _validate_output(base_meta, ext_meta, len(valid_rows), inverters=inverters)
    validation_findings += _identify_risks(duplicates, ext_meta, ac_assets, batteries)
    validation_findings += capacity_findings

    # ── Output validation service (new) ──
    output_validation_findings: list[dict[str, Any]] = []
    try:
        from app.services.output_validation import validate as _ov_validate
        partial_result: dict[str, Any] = {
            "module_count": module_count,
            "module_power_wp": ext_meta.get("module_power_wp"),
            "system_rating_kwp": ext_meta.get("system_rating_kwp"),
            "modules_per_string": ext_meta.get("modules_per_string"),
            "plant_capacity_mw": plant_capacity_mw,
            "inverters": inverters,
            "valid_count": len(valid_rows),
        }
        output_validation_findings = _ov_validate(partial_result)
    except Exception:
        pass

    return {
        # Site metadata
        "site_code": site_code,
        "site_name": site_name,
        "layout_name": layout_name,
        "source_document": Path(filename).name,
        "installation_type": installation_type,
        "country": country,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "plant_capacity_mw": plant_capacity_mw,
        "module_type": module_type,
        "module_count": module_count,
        # Extended metadata (from_chatgpt)
        "module_power_wp": ext_meta.get("module_power_wp"),
        "modules_per_string": ext_meta.get("modules_per_string"),
        "system_rating_kwp": ext_meta.get("system_rating_kwp"),
        "battery_capacity_mwh": ext_meta.get("battery_capacity_mwh"),
        "tracker_enabled": ext_meta.get("tracker_enabled", False),
        "tracker_rotation_deg": ext_meta.get("tracker_rotation_deg"),
        "azimuth_deg": ext_meta.get("azimuth_deg"),
        "total_strings_doc": ext_meta.get("total_strings_doc"),
        # New extended metadata fields (extra_patterns)
        "project_name": ext_meta.get("project_name"),
        "coordinates": ext_meta.get("coordinates"),
        "building_area_ha": ext_meta.get("building_area_ha"),
        "fenced_area_ha": ext_meta.get("fenced_area_ha"),
        "fence_length_m": ext_meta.get("fence_length_m"),
        "system_license": ext_meta.get("system_license"),
        "storage_capacity_mwh": ext_meta.get("storage_capacity_mwh"),
        # Device inventory (inverter models, battery type, BESS inv)
        "inverter_models": ext_meta.get("inverter_models", []),
        "battery_type": ext_meta.get("battery_type"),
        "bess_inv": ext_meta.get("bess_inv"),
        # Capacity figures + multi-type module breakdown
        "module_breakdown": module_breakdown,
        "module_math_kwp": module_math_kwp,
        # String data
        "string_rows": rows_sorted,
        "strings": strings_map,
        "gaps": gaps,
        "duplicates": duplicates,
        "anomalies": anomalies,
        "invalid_ab_labels": invalid_ab_labels,
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "has_errors": bool(invalid_rows) or bool(invalid_ab_labels),
        "approved_pattern_name": approved_pattern_name,
        "approved_pattern_regex": approved_pattern_regex,
        # Entities (from_chatgpt)
        "inverters": inverters,
        "inverter_count_detected": len(inverters),
        "ac_assets": ac_assets,
        "batteries": batteries,
        "mppt_channels": mppt_channels,
        "icb_zones": icb_zones,
        # MPPT grouping (new)
        "mppt_groups": mppt_groups,
        "mppt_extraction_incomplete": not bool(mppt_groups),
        # Suffix string pairs (A/B sides)
        "suffix_strings": suffix_strings,
        "suffix_string_issues": suffix_string_issues,
        # MPPT sequence validation
        "mppt_validation_issues": mppt_validation_issues,
        # Page count + per-page texts (pdfplumber)
        "page_count": page_count,
        "page_texts": _page_texts,
        # Per-inverter analytics (user parser improvement)
        "inverter_summary": inverter_summary,
        "missing_strings_by_inverter": missing_strings_by_inverter,
        "duplicate_string_numbers_by_inverter": duplicate_string_numbers_by_inverter,
        "outlier_strings_by_inverter": outlier_strings_by_inverter,
        "dc_string_buckets_found": dc_buckets,
        # Validation findings (from_chatgpt OutputValidationService)
        "validation_findings": validation_findings,
        # Output validation findings (new service)
        "output_validation_findings": output_validation_findings,
        "metadata": {
            "project": site_name,
            "location": (
                f"{latitude}N, {longitude}E"
                if latitude is not None and longitude is not None
                else None
            ),
            "total_modules": module_count,
        },
    }


def build_site_design_preview_multi(
    files: list[tuple[bytes, str]],
    regions: list[dict] | None = None,
    approved_pattern_regex: str | None = None,
    approved_pattern_name: str | None = None,
    extracted_texts: list[str] | None = None,
) -> dict[str, Any]:
    """Merge results from multiple PDF/DXF files into one combined preview."""
    all_rows: list[dict[str, Any]] = []
    all_text_parts: list[str] = []
    metadata: dict[str, Any] = {}

    for idx, (content, filename) in enumerate(files):
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            if extracted_texts is not None and idx < len(extracted_texts):
                text = extracted_texts[idx]
            else:
                text = _extract_text_from_pdf(content, regions=regions)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        all_text_parts.append(text)
        rows = _extract_string_rows(
            text,
            pattern_regex=approved_pattern_regex,
            pattern_name=approved_pattern_name,
        )
        all_rows.extend(rows)
        if not metadata:
            layout_name = _derive_layout_name(text, filename)
            site_code = _derive_site_code(layout_name)
            metadata = {
                "site_code": site_code,
                "site_name": _search(r"\b([A-Za-z0-9-]+-FPV)\b", text) or site_code,
                "layout_name": layout_name,
                "country": _search(r"Country\s*-\s*([A-Z][A-Z ]+)", text),
                "region": _search(r"Region\s*/\s*Province\s*-\s*([A-Z][A-Z ]+)", text),
                "latitude": _parse_float(_search(r"Coordinates\s+([0-9.]+)\s*N", text, re.IGNORECASE)),
                "longitude": _parse_float(_search(r"Coordinates\s+[0-9.]+\s*N\s+([0-9.]+)\s*E", text, re.IGNORECASE)),
                "plant_capacity_mw": _parse_float(_search(r"System Capacity\s*-\s*([0-9.]+)\s*MW", text, re.IGNORECASE)),
                "module_type": _search(r"Type of Module / Power\s*-\s*([A-Z0-9-]+)", text, re.IGNORECASE),
                "module_count": _parse_int(_search(r"Number of\s+Modules\s*-\s*([0-9,]+)", text, re.IGNORECASE)),
            }

    combined_text = "\n".join(all_text_parts)
    rows_sorted = sorted(
        all_rows,
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

    tokens = _tokenize(combined_text)
    ext_meta = _extract_extended_metadata(combined_text)
    inverters = _extract_inverters(tokens, string_rows=valid_rows, text=combined_text)
    inverter_count_doc = ext_meta.get("inverter_count_doc")
    inverters = _fill_and_extend_inverters(
        inverters,
        doc_count=int(inverter_count_doc) if inverter_count_doc else None,
        string_rows=valid_rows,
    )
    ac_assets = _extract_ac_assets(tokens)
    batteries = _extract_batteries(tokens)
    mppt_channels = _extract_mppt_channels(combined_text)
    icb_zones = _extract_icb_zones(combined_text)
    dc_buckets = _extract_dc_buckets(combined_text)
    multi_dupes = _build_duplicates(rows_sorted)
    inverter_summary = _build_inverter_summary(valid_rows)
    missing_strings_by_inverter = _build_per_inverter_gaps(valid_rows)
    duplicate_string_numbers_by_inverter = _build_per_inverter_duplicates(rows_sorted)
    outlier_strings_by_inverter = _build_per_inverter_outliers(valid_rows)

    # Reclassify outlier rows as invalid (same logic as single-file path)
    if outlier_strings_by_inverter:
        for row in rows_sorted:
            if not row.get("is_valid") or row.get("inverter_key") is None:
                continue
            inv_key = row["inverter_key"]
            actual_no = row.get("actual_string_no")
            if actual_no is not None and actual_no in (outlier_strings_by_inverter.get(inv_key) or []):
                row["is_valid"] = False
                row["invalid_reason"] = (
                    f"String number {actual_no} is far outside the expected range for "
                    f"inverter {inv_key} — likely a PDF text-extraction artifact."
                )
        valid_rows   = [r for r in rows_sorted if r["is_valid"]]
        invalid_rows = [r for r in rows_sorted if not r["is_valid"]]
        outlier_strings_by_inverter = {}

    base_meta: dict[str, Any] = {
        "module_count": metadata.get("module_count"),
        "plant_capacity_mw": metadata.get("plant_capacity_mw"),
    }
    invalid_ab_labels = _extract_invalid_ab_labels(combined_text)
    module_breakdown = _extract_module_breakdown(combined_text)
    module_math_kwp = _compute_module_math_kwp(module_breakdown)
    installation_type = _detect_installation_type(combined_text, metadata.get("site_name", ""))
    capacity_findings = _check_capacity_inconsistency(
        system_rating_kwp=ext_meta.get("system_rating_kwp"),
        plant_capacity_mw=metadata.get("plant_capacity_mw"),
        module_math_kwp=module_math_kwp,
    )
    validation_findings = _validate_output(base_meta, ext_meta, len(valid_rows), inverters=inverters)
    validation_findings += _identify_risks(multi_dupes, ext_meta, ac_assets, batteries)
    validation_findings += capacity_findings

    # ── MPPT grouping (new) ──
    mppt_groups: list[dict[str, Any]] = []
    try:
        mppt_groups = _extract_mppt_groups(combined_text)
    except Exception:
        pass

    # ── Output validation service (new) ──
    output_validation_findings: list[dict[str, Any]] = []
    try:
        from app.services.output_validation import validate as _ov_validate
        partial_result: dict[str, Any] = {
            "module_count": metadata.get("module_count"),
            "module_power_wp": ext_meta.get("module_power_wp"),
            "system_rating_kwp": ext_meta.get("system_rating_kwp"),
            "modules_per_string": ext_meta.get("modules_per_string"),
            "plant_capacity_mw": metadata.get("plant_capacity_mw"),
            "inverters": inverters,
            "valid_count": len(valid_rows),
        }
        output_validation_findings = _ov_validate(partial_result)
    except Exception:
        pass

    return {
        **metadata,
        "installation_type": installation_type,
        # Extended metadata
        "module_power_wp": ext_meta.get("module_power_wp"),
        "modules_per_string": ext_meta.get("modules_per_string"),
        "system_rating_kwp": ext_meta.get("system_rating_kwp"),
        "battery_capacity_mwh": ext_meta.get("battery_capacity_mwh"),
        "tracker_enabled": ext_meta.get("tracker_enabled", False),
        "tracker_rotation_deg": ext_meta.get("tracker_rotation_deg"),
        "azimuth_deg": ext_meta.get("azimuth_deg"),
        "total_strings_doc": ext_meta.get("total_strings_doc"),
        # New extended metadata fields (extra_patterns)
        "project_name": ext_meta.get("project_name"),
        "coordinates": ext_meta.get("coordinates"),
        "building_area_ha": ext_meta.get("building_area_ha"),
        "fenced_area_ha": ext_meta.get("fenced_area_ha"),
        "fence_length_m": ext_meta.get("fence_length_m"),
        "system_license": ext_meta.get("system_license"),
        "storage_capacity_mwh": ext_meta.get("storage_capacity_mwh"),
        # Capacity figures + multi-type module breakdown
        "module_breakdown": module_breakdown,
        "module_math_kwp": module_math_kwp,
        # String data
        "string_rows": rows_sorted,
        "strings": _build_strings_map(rows_sorted),
        "gaps": _build_gaps(rows_sorted),
        "duplicates": multi_dupes,
        "anomalies": _build_anomalies(combined_text),
        "invalid_ab_labels": invalid_ab_labels,
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "has_errors": bool(invalid_rows) or bool(invalid_ab_labels),
        "approved_pattern_name": approved_pattern_name,
        "approved_pattern_regex": approved_pattern_regex,
        # Entities
        "inverters": inverters,
        "inverter_count_detected": len(inverters),
        "ac_assets": ac_assets,
        "batteries": batteries,
        "mppt_channels": mppt_channels,
        "icb_zones": icb_zones,
        # MPPT grouping (new)
        "mppt_groups": mppt_groups,
        "mppt_extraction_incomplete": not bool(mppt_groups),
        # Per-inverter analytics
        "inverter_summary": inverter_summary,
        "missing_strings_by_inverter": missing_strings_by_inverter,
        "duplicate_string_numbers_by_inverter": duplicate_string_numbers_by_inverter,
        "outlier_strings_by_inverter": outlier_strings_by_inverter,
        "dc_string_buckets_found": dc_buckets,
        "validation_findings": validation_findings,
        # Output validation findings (new service)
        "output_validation_findings": output_validation_findings,
        "source_documents": [fn for _, fn in files],
    }


# ---------------------------------------------------------------------------
# Multi-file convenience entry point (user parser: parse_multiple_pdfs)
# ---------------------------------------------------------------------------

def parse_multiple_pdfs(pdf_paths: list[str]) -> dict[str, Any]:
    """
    Parse one or more PDF files and return per-file results plus a merged view.

    Returns:
        {
            "files":  {filename: result_dict | {"error": str}},
            "merged": merged_result_dict,
        }
    """
    files: list[tuple[bytes, str]] = []
    for path in pdf_paths:
        with open(path, "rb") as fh:
            files.append((fh.read(), path))

    file_results: dict[str, Any] = {}
    for content, path in files:
        name = Path(path).name
        try:
            file_results[name] = build_site_design_preview(content, path)
        except Exception as exc:
            file_results[name] = {"error": str(exc), "source_document": name}

    if len(files) == 1:
        merged = file_results[Path(files[0][1]).name]
    elif files:
        merged = build_site_design_preview_multi(files)
    else:
        merged = {}

    return {"files": file_results, "merged": merged}
