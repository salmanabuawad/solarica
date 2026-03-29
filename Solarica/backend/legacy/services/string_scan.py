"""String scan service: DB-driven pattern classification, design comparison, issue generation."""

from __future__ import annotations

import re
import json
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Pattern management
# ---------------------------------------------------------------------------

def get_all_patterns(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, pattern_code, pattern_name, match_regex, parse_regex,
                      example_value, level_count, levels_json,
                      max_digits_per_level, no_leading_zero, is_active
               FROM string_id_pattern ORDER BY id"""
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0], "pattern_code": r[1], "pattern_name": r[2],
            "match_regex": r[3], "parse_regex": r[4], "example_value": r[5],
            "level_count": r[6], "levels": r[7] if isinstance(r[7], list) else json.loads(r[7]),
            "max_digits_per_level": r[8], "no_leading_zero": r[9], "is_active": r[10],
        }
        for r in rows
    ]


def get_active_pattern(site_id: int, conn) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.id, p.pattern_code, p.pattern_name, p.match_regex, p.parse_regex,
                      p.example_value, p.level_count, p.levels_json,
                      p.max_digits_per_level, p.no_leading_zero, p.is_active
               FROM site_string_pattern sp
               JOIN string_id_pattern p ON p.id = sp.pattern_id
               WHERE sp.site_id = %s AND sp.is_active = true
               LIMIT 1""",
            (site_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "pattern_code": row[1], "pattern_name": row[2],
        "match_regex": row[3], "parse_regex": row[4], "example_value": row[5],
        "level_count": row[6], "levels": row[7] if isinstance(row[7], list) else json.loads(row[7]),
        "max_digits_per_level": row[8], "no_leading_zero": row[9], "is_active": row[10],
    }


def set_active_pattern(site_id: int, pattern_id: int, conn) -> dict:
    with conn.cursor() as cur:
        # Deactivate existing
        cur.execute(
            "UPDATE site_string_pattern SET is_active = false WHERE site_id = %s",
            (site_id,),
        )
        # Insert new active
        cur.execute(
            """INSERT INTO site_string_pattern (site_id, pattern_id, is_active)
               VALUES (%s, %s, true)""",
            (site_id, pattern_id),
        )
    conn.commit()
    return get_active_pattern(site_id, conn)


# ---------------------------------------------------------------------------
# Fast detect
# ---------------------------------------------------------------------------

def fast_detect_pattern(text: str, patterns: list[dict], configured_pattern_code: str) -> dict:
    tokens = text.split()
    counts: dict[str, int] = {}
    compiled: dict[str, re.Pattern] = {}
    for p in patterns:
        rx = re.compile(p["match_regex"], re.IGNORECASE)
        compiled[p["pattern_code"]] = rx
        counts[p["pattern_code"]] = 0

    for token in tokens:
        t = token.strip(".,;:()[]\"'")
        for code, rx in compiled.items():
            if rx.fullmatch(t):
                counts[code] += 1
                break  # each token can only match one pattern

    total = sum(counts.values())
    best_code = max(counts, key=counts.get) if counts else configured_pattern_code
    confidence = round(counts.get(best_code, 0) / total, 4) if total > 0 else 0.0

    return {
        "configured_pattern_code": configured_pattern_code,
        "detected_pattern_code": best_code,
        "confidence": confidence,
        "token_counts": counts,
    }


# ---------------------------------------------------------------------------
# Token classification
# ---------------------------------------------------------------------------

# Matches S.X.X.X.X (4 numeric groups) — spurious dot after S from PDF extraction
_S4_WITH_DOT = re.compile(r'^S\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)\.([1-9]\d?)$', re.IGNORECASE)


def classify_token(raw: str, pattern: dict) -> dict:
    token = raw.strip(".,;:()[]\"'\n\r\t ")
    # Normalize S.X.X.X.X → SX.X.X.X (PDFs sometimes emit a spurious dot after S for 4-level codes)
    if _S4_WITH_DOT.fullmatch(token):
        token = "S" + token[2:]
    match_re = re.compile(pattern["match_regex"], re.IGNORECASE)
    parse_re = re.compile(pattern["parse_regex"], re.IGNORECASE)
    levels: list[str] = pattern["levels"]

    if match_re.fullmatch(token):
        m = parse_re.fullmatch(token)
        parsed: dict[str, int] = {}
        if m:
            for i, lvl in enumerate(levels):
                parsed[lvl] = int(m.group(i + 1))
        return {
            "raw_text": raw,
            "normalized_text": token,
            "classification": "valid_string",
            "reason": None,
            "parsed_levels": parsed,
        }

    upper = token.upper()
    if upper.startswith("S") and len(token) > 1:
        reason = "pattern_mismatch"
        if re.search(r"\.0\d", token):
            reason = "leading_zero"
        elif re.search(r"[A-Za-z]", token[1:]):
            reason = "non_numeric_segment"
        return {
            "raw_text": raw,
            "normalized_text": token,
            "classification": "invalid_string_name",
            "reason": reason,
            "parsed_levels": None,
        }

    return {
        "raw_text": raw,
        "normalized_text": token,
        "classification": "non_string",
        "reason": None,
        "parsed_levels": None,
    }


def classify_all_tokens(text: str, pattern: dict) -> list[dict]:
    results = []
    seen_tokens: set[str] = set()
    for raw in text.split():
        token = raw.strip(".,;:()[]\"'")
        if not token:
            continue
        result = classify_token(token, pattern)
        if result["classification"] == "non_string":
            continue
        result["is_duplicate"] = token in seen_tokens
        if result["classification"] == "valid_string":
            seen_tokens.add(token)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _inverter_key(parsed: dict, levels: list[str]) -> str:
    """Return the group key (everything except the last level)."""
    keys = [str(parsed[lvl]) for lvl in levels[:-1]]
    return ".".join(keys)


def group_by_inverter(
    classified: list[dict],
    pattern: dict,
) -> dict[str, dict]:
    """Group valid (non-duplicate) strings by their inverter key."""
    levels = pattern["levels"]
    groups: dict[str, dict] = {}

    for item in classified:
        if item["classification"] != "valid_string" or item.get("is_duplicate"):
            continue
        parsed = item.get("parsed_levels") or {}
        key = _inverter_key(parsed, levels)
        if key not in groups:
            groups[key] = {"strings": [], "string_nos": []}
        groups[key]["strings"].append(item["normalized_text"])
        last_level = levels[-1]
        if last_level in parsed:
            groups[key]["string_nos"].append(parsed[last_level])

    return groups


# ---------------------------------------------------------------------------
# Design comparison
# ---------------------------------------------------------------------------

def _load_design_groups(site_id: int, conn) -> dict[str, int]:
    """Return {inverter_key: expected_string_count} from site_strings."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT section_no, block_no, COUNT(*) as cnt
               FROM site_strings
               WHERE site_id = %s
               GROUP BY section_no, block_no
               ORDER BY section_no, block_no""",
            (site_id,),
        )
        rows = cur.fetchall()
    return {f"{r[0]}.{r[1]}": int(r[2]) for r in rows}


# ---------------------------------------------------------------------------
# Issue generation
# ---------------------------------------------------------------------------

def _missing_sequence(string_nos: list[int]) -> list[int]:
    if not string_nos:
        return []
    lo, hi = min(string_nos), max(string_nos)
    present = set(string_nos)
    return [n for n in range(lo, hi + 1) if n not in present]


def build_scan_result(
    classified: list[dict],
    pattern: dict,
    site_id: int,
    fast_detect: dict,
    conn,
    run_id: int = 0,
    compare_to_design: bool = True,
) -> dict:
    levels = pattern["levels"]
    groups = group_by_inverter(classified, pattern)
    design_groups = _load_design_groups(site_id, conn) if compare_to_design else {}

    valid_strings = [c for c in classified if c["classification"] == "valid_string" and not c.get("is_duplicate")]
    invalid_names = [c for c in classified if c["classification"] == "invalid_string_name"]
    duplicates = [c for c in classified if c.get("is_duplicate")]

    issues: list[dict] = []

    # Duplicate issues
    for c in duplicates:
        issues.append({
            "issue_type": "duplicate_string",
            "severity": "error",
            "entity_type": "string",
            "entity_key": c["normalized_text"],
            "message": f"Duplicate string ID detected: {c['normalized_text']}",
            "details": {},
        })

    # Invalid name issues
    for c in invalid_names:
        issues.append({
            "issue_type": "invalid_string_name",
            "severity": "warning",
            "entity_type": "string",
            "entity_key": c["normalized_text"],
            "message": f"Invalid string name: {c['normalized_text']} ({c.get('reason','')})",
            "details": {"reason": c.get("reason")},
        })

    # Per-inverter analysis
    inverter_summaries: list[dict] = []
    for inv_key, group_data in sorted(groups.items()):
        string_nos = group_data["string_nos"]
        found = len(group_data["strings"])
        expected = design_groups.get(inv_key, 0)
        missing = _missing_sequence(string_nos)

        if missing:
            issues.append({
                "issue_type": "missing_sequence",
                "severity": "warning",
                "entity_type": "inverter",
                "entity_key": inv_key,
                "message": f"Missing string sequence in inverter {inv_key}: {missing}",
                "details": {"missing": missing},
            })

        if compare_to_design and expected > 0 and found != expected:
            issues.append({
                "issue_type": "inverter_string_count_mismatch",
                "severity": "error",
                "entity_type": "inverter",
                "entity_key": inv_key,
                "message": f"Inverter {inv_key}: expected {expected} strings, found {found}",
                "details": {"expected": expected, "found": found},
            })
            status = "mismatch"
        elif compare_to_design and expected > 0 and found == expected and not missing:
            status = "match"
        else:
            status = "manual_review_required"

        inverter_summaries.append({
            "inverter_key": inv_key,
            "expected_strings": expected,
            "found_valid_strings": found,
            "duplicate_count": sum(1 for c in duplicates if _inverter_key(c.get("parsed_levels") or {}, levels) == inv_key),
            "invalid_name_count": sum(1 for c in invalid_names if _inverter_key(c.get("parsed_levels") or {}, levels) == inv_key),
            "missing_sequence": missing,
            "status": status,
        })

    # Section-level grouping
    sections_map: dict[str, list[dict]] = defaultdict(list)
    for inv_sum in inverter_summaries:
        sec_key = inv_sum["inverter_key"].rsplit(".", 1)[0] if "." in inv_sum["inverter_key"] else inv_sum["inverter_key"]
        sections_map[sec_key].append(inv_sum)

    sections = [
        {
            "section_code": sec,
            "found_inverters": len(summaries),
            "found_valid_strings": sum(s["found_valid_strings"] for s in summaries),
            "inverter_summaries": summaries,
        }
        for sec, summaries in sorted(sections_map.items())
    ]

    # Design comparison summary
    expected_total = sum(design_groups.values())
    found_total = len(valid_strings)
    expected_inv_groups = len(design_groups)
    found_inv_groups = len(groups)
    matches_design = (
        found_total == expected_total
        and found_inv_groups == expected_inv_groups
        and not any(s["status"] == "mismatch" for s in inverter_summaries)
    ) if compare_to_design and expected_total > 0 else False

    if compare_to_design and expected_total > 0 and found_total != expected_total:
        issues.append({
            "issue_type": "design_total_mismatch",
            "severity": "error",
            "entity_type": "project",
            "entity_key": f"site_{site_id}",
            "message": f"Found {found_total} strings, expected {expected_total}",
            "details": {"expected": expected_total, "found": found_total},
        })

    return {
        "site_id": site_id,
        "run_id": run_id,
        "pattern_code_used": pattern["pattern_code"],
        "fast_detect": fast_detect,
        "summary": {
            "total_valid_strings": found_total,
            "total_invalid_string_names": len(invalid_names),
            "total_duplicates": len(duplicates),
            "total_inverters_found": found_inv_groups,
        },
        "design_comparison": {
            "expected_total_strings": expected_total,
            "found_total_valid_strings": found_total,
            "expected_inverter_groups": expected_inv_groups,
            "found_inverter_groups": found_inv_groups,
            "matches_design": matches_design,
        },
        "sections": sections,
        "invalid_string_names": invalid_names,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# Save run to DB
# ---------------------------------------------------------------------------

def save_scan_run(
    site_id: int,
    pattern: dict,
    fast_detect: dict,
    result: dict,
    conn,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO string_scan_run
                   (site_id, pattern_id, detected_pattern_code, confidence, compare_to_design)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (
                site_id,
                pattern["id"],
                fast_detect["detected_pattern_code"],
                fast_detect["confidence"],
                True,
            ),
        )
        run_id = cur.fetchone()[0]

        dc = result["design_comparison"]
        s = result["summary"]
        cur.execute(
            """INSERT INTO string_scan_summary
                   (scan_run_id, expected_total_strings, found_total_valid_strings,
                    total_invalid_string_names, total_duplicates,
                    expected_inverter_groups, found_inverter_groups, matches_design)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                run_id,
                dc["expected_total_strings"] or None,
                s["total_valid_strings"],
                s["total_invalid_string_names"],
                s["total_duplicates"],
                dc["expected_inverter_groups"] or None,
                dc["found_inverter_groups"],
                dc["matches_design"],
            ),
        )

        for issue in result["issues"]:
            import json as _json
            cur.execute(
                """INSERT INTO string_scan_issue
                       (scan_run_id, issue_type, severity, entity_type, entity_key, message, details)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    run_id,
                    issue["issue_type"],
                    issue["severity"],
                    issue["entity_type"],
                    issue["entity_key"],
                    issue["message"],
                    _json.dumps(issue.get("details", {})),
                ),
            )
    conn.commit()
    return run_id
