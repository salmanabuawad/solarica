
import re
from collections import defaultdict

STRING_PATTERN = re.compile(r"S\.?\d+\.\d+\.\d+")

def extract_strings(text):
    return STRING_PATTERN.findall(text)

def detect_duplicates(strings):
    counts = {}
    for s in strings:
        counts[s] = counts.get(s, 0) + 1
    return {k:v for k,v in counts.items() if v > 1}

def normalize_invalid(labels):
    normalized = []
    for l in labels:
        if l.endswith("A") or l.endswith("B"):
            parts = l.split(".")
            if len(parts) >= 5:
                normalized.append(f"S.{parts[-3]}.{parts[-2]}.{parts[-1][:-1]}")
        else:
            normalized.append(l)
    return normalized

def group_by_inverter(strings):
    groups = defaultdict(list)
    for s in strings:
        parts = s.split(".")
        if len(parts) == 4:
            inv = f"{parts[1]}.{parts[2]}"
            groups[inv].append(int(parts[3]))
    return groups

def detect_missing(groups):
    result = {}
    for inv, nums in groups.items():
        nums = sorted(set(nums))
        expected = set(range(1, max(nums)+1))
        missing = sorted(expected - set(nums))
        if missing:
            result[inv] = missing
    return result

def run(text):
    raw = extract_strings(text)
    duplicates = detect_duplicates(raw)
    normalized = normalize_invalid(raw)
    groups = group_by_inverter(normalized)
    missing = detect_missing(groups)

    return {
        "total_strings": len(set(normalized)),
        "duplicates": duplicates,
        "missing": missing
    }
