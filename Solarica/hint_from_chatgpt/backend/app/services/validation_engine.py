from collections import defaultdict
import re

def validate_string_code_pattern(strings, regex):
    pattern = re.compile(regex)
    issues = []
    for item in strings:
        code = item["string_code"]
        if not pattern.match(code):
            issues.append({
                "rule_code": "STRING_CODE_PATTERN",
                "severity": "error",
                "entity_type": "string",
                "entity_key": code,
                "issue_message": f"Invalid string format: {code}"
            })
    return issues

def validate_string_uniqueness(strings):
    seen = set()
    issues = []
    for item in strings:
        code = item["string_code"]
        if code in seen:
            issues.append({
                "rule_code": "STRING_ID_UNIQUE",
                "severity": "blocker",
                "entity_type": "string",
                "entity_key": code,
                "issue_message": f"Duplicate string code found: {code}"
            })
        seen.add(code)
    return issues

def validate_sequence(strings):
    grouped = defaultdict(list)
    issues = []

    for item in strings:
        section = item["section_code"]
        inverter = item["inverter_code"]
        idx = item["string_index"]
        grouped[(section, inverter)].append(idx)

    for (section, inverter), indexes in grouped.items():
        indexes = sorted(indexes)
        if indexes and indexes[0] != 1:
            issues.append({
                "rule_code": "STRING_SEQUENCE_STARTS_AT_ONE",
                "severity": "error",
                "entity_type": "inverter",
                "entity_key": f"{section}:{inverter}",
                "issue_message": f"Section {section}, inverter {inverter} must start from 1"
            })
        expected = list(range(1, len(indexes) + 1))
        if indexes != expected:
            issues.append({
                "rule_code": "STRING_SEQUENCE_NO_GAPS",
                "severity": "blocker",
                "entity_type": "inverter",
                "entity_key": f"{section}:{inverter}",
                "issue_message": f"Section {section}, inverter {inverter} has gaps. Expected {expected}; found {indexes}"
            })
    return issues
