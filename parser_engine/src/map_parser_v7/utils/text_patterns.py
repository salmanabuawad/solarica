from __future__ import annotations

import re
from collections import Counter

# 4-level: S.a.b.c.d  — inverter key = a.b.c, string idx = d
STRING_4_RE = re.compile(r"\bS\.?([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)\b")
# 3-level: S.a.b.c    — inverter key = a.b,   string idx = c
STRING_3_RE = re.compile(r"\bS\.?([0-9]+)\.([0-9]+)\.([0-9]+)\b")

# Keep the old name as an alias so existing imports don't break
STRING_RE = STRING_4_RE

INVERTER_GROUP_RE = re.compile(r"\b([0-9]+)\.([0-9]+)\b")
INVALID_AB_RE = re.compile(r"\b(?:S\.)?[0-9]+(?:\.[0-9]+){3,}[AB]\b|\b[0-9]+(?:\.[0-9]+){3,}[AB]\b")
MPPT_RE = re.compile(r"\bMPPT\s*([0-9]+)\b", re.IGNORECASE)
STRINGS_COUNT_RE = re.compile(r"\b(20|21|22)\s*STRINGS\b", re.IGNORECASE)
PANELS_PER_STRING_RE = re.compile(r"\b(26|27)\s*/\s*String\b", re.IGNORECASE)
COORD_RE = re.compile(r"Coordinates?\s*([0-9°'\.\"NSEW\s]+)[, ]+([0-9°'\.\"NSEW\s]+)", re.IGNORECASE)
NUMBER_RE = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)")


def normalize_string_label(raw: str) -> str:
    raw = raw.replace(" ", "")
    if raw.startswith("S") and not raw.startswith("S."):
        m = re.match(r"S([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)$", raw)
        if m:
            return f"S.{m.group(1)}"
    return raw.replace("S", "S.", 1) if re.match(r"^S[0-9]", raw) else raw


def find_string_labels(text: str) -> list[str]:
    """
    Find all valid string labels in text.
    Collects both 4-level (S.a.b.c.d) and 3-level (S.a.b.c) matches and returns
    whichever level has more unique hits.  When counts are equal and both are
    non-empty, 4-level wins (it is more specific).

    This avoids the old "first match wins" bug where a handful of accidental
    4-part dotted tokens in a 3-level document caused all real strings to be lost.
    """
    labels_4 = sorted(
        {f"S.{m.group(1)}.{m.group(2)}.{m.group(3)}.{m.group(4)}" for m in STRING_4_RE.finditer(text)},
        key=sort_key,
    )
    labels_3 = sorted(
        {f"S.{m.group(1)}.{m.group(2)}.{m.group(3)}" for m in STRING_3_RE.finditer(text)},
        key=sort_key,
    )

    # Majority wins: return whichever level produced more unique labels.
    # 4-level is only trusted when it has substantially more matches than 3-level
    # OR when 3-level found nothing.  A small handful of 4-level hits in a
    # predominantly 3-level document are treated as false positives.
    if not labels_3:
        return labels_4
    if not labels_4:
        return labels_3
    # Both found something — prefer the larger set.
    # Tie-break: 4-level wins (it is more specific).
    return labels_4 if len(labels_4) >= len(labels_3) else labels_3


def _detect_level(strings: list[str]) -> int:
    """Return 4 if a majority of string labels have 4 numeric parts, else 3."""
    if not strings:
        return 3
    four_part = sum(1 for s in strings if len(s.split(".")) >= 5)
    return 4 if four_part > len(strings) / 2 else 3


def find_invalid_labels(text: str) -> list[str]:
    return sorted(set(m.group(0) for m in INVALID_AB_RE.finditer(text)))


def find_inverter_groups(text: str, level: int = 3) -> list[str]:
    """
    Extract inverter group keys from raw text.
    For 3-level strings the group key is "a.b" (2-part).
    For 4-level strings the group key is "a.b.c" (3-part).
    """
    if level == 4:
        # Collect 3-part dotted tokens that look like inverter IDs
        three_part_re = re.compile(r"\b([0-9]+)\.([0-9]+)\.([0-9]+)\b")
        candidates = []
        for m in three_part_re.finditer(text):
            a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= a <= 9 and 1 <= b <= 99 and 1 <= c <= 99:
                candidates.append(f"{a}.{b}.{c}")
        counts = Counter(candidates)
        return sorted(counts.keys(), key=sort_key)
    else:
        candidates = []
        for m in INVERTER_GROUP_RE.finditer(text):
            a, b = int(m.group(1)), int(m.group(2))
            if 1 <= a <= 9 and 1 <= b <= 99:
                candidates.append(f"{a}.{b}")
        counts = Counter(candidates)
        return sorted(counts.keys(), key=sort_key)


def find_mppts(text: str) -> list[str]:
    return sorted({f"MPPT{m.group(1)}" for m in MPPT_RE.finditer(text)}, key=lambda s: int(s[4:]))


def sort_key(label: str):
    parts = re.findall(r"\d+", label)
    return tuple(int(p) for p in parts)


def derive_inverter_groups_from_strings(strings: list[str]) -> list[str]:
    level = _detect_level(strings)
    if level == 4:
        groups = sorted(
            {".".join(s.split(".")[1:4]) for s in strings if len(s.split(".")) >= 5},
            key=sort_key,
        )
    else:
        groups = sorted(
            {".".join(s.split(".")[1:3]) for s in strings if len(s.split(".")) >= 4},
            key=sort_key,
        )
    return groups


def group_strings(strings: list[str]) -> dict[str, list[str]]:
    level = _detect_level(strings)
    out: dict[str, list[str]] = {}
    for s in strings:
        parts = s.split(".")  # ["S", n1, n2, ...]
        if level == 4 and len(parts) >= 5:
            group = f"{parts[1]}.{parts[2]}.{parts[3]}"
        elif len(parts) >= 4:
            group = f"{parts[1]}.{parts[2]}"
        else:
            continue
        out.setdefault(group, []).append(s)
    for v in out.values():
        v.sort(key=sort_key)
    return dict(sorted(out.items(), key=lambda kv: sort_key(kv[0])))


def detect_duplicates(strings: list[str]) -> list[str]:
    counts = Counter(strings)
    return sorted([k for k, v in counts.items() if v > 1], key=sort_key)


def missing_indices_for_group(strings: list[str]) -> list[int]:
    """
    Return the missing string indices within the main cluster of the group.

    Uses cluster-based detection (MAX_CLUSTER_GAP = 3) to avoid reporting
    huge gaps caused by a few outlier string numbers that are far outside the
    main body. This mirrors the fix in _build_per_inverter_gaps.
    """
    MAX_CLUSTER_GAP = 3
    idxs = sorted(int(s.split(".")[-1]) for s in strings)
    if not idxs:
        return []

    # Split into contiguous clusters
    clusters: list[list[int]] = []
    current: list[int] = [idxs[0]]
    for n in idxs[1:]:
        if n - current[-1] <= MAX_CLUSTER_GAP:
            current.append(n)
        else:
            clusters.append(current)
            current = [n]
    clusters.append(current)

    # Use the largest cluster for gap analysis
    main = max(clusters, key=len)
    main_set = set(main)
    return [i for i in range(main[0], main[-1] + 1) if i not in main_set]
