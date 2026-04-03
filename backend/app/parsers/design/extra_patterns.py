"""
Extra regex patterns ported from from_chatgpt/solarica_parsers/patterns.py.
These complement the patterns already defined in pdf_string_extractor.py and
cover project metadata, MPPT topology, module specs, and site dimensions.
"""
from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Project / site identification
# ---------------------------------------------------------------------------

PROJECT_NAME_PATTERNS = [
    re.compile(r"Solar Plant\s+([A-Za-z0-9 _\-]+)", re.IGNORECASE),
    re.compile(r"(Qunitra\-FPV\s+\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Solar Plant\s+([A-Za-z0-9 _\-]+?)\s+Coordinates", re.IGNORECASE),
]

COORDINATES_PATTERN = re.compile(r"Coordinates\s+([0-9°'\".NSWE\s]+)", re.IGNORECASE)
COUNTRY_PATTERN = re.compile(r"Country\s*-\s*([A-Za-z ]+)", re.IGNORECASE)
REGION_PATTERN = re.compile(r"Region\s*/\s*Province\s*-\s*([A-Za-z ]+)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Site dimensions
# ---------------------------------------------------------------------------

BUILDING_AREA_PATTERN = re.compile(r"Building Area\s*-\s*([0-9.]+)\s*ha", re.IGNORECASE)
FENCED_AREA_PATTERN = re.compile(r"Fenced Area\s*-\s*([0-9.]+)\s*ha", re.IGNORECASE)
FENCE_LENGTH_PATTERN = re.compile(r"Fence Length\s*-\s*([0-9.]+)\s*m", re.IGNORECASE)

# ---------------------------------------------------------------------------
# System specifications
# ---------------------------------------------------------------------------

SYSTEM_RATING_PATTERN = re.compile(
    r"Plant System Rating\s*-\s*([0-9,.\-]+)\s*kWp", re.IGNORECASE
)
SYSTEM_CAPACITY_MW_PATTERN = re.compile(
    r"System Capacity\s*-\s*([0-9,.\-]+)\s*MW(?!h)", re.IGNORECASE
)
SYSTEM_LICENSE_PATTERN = re.compile(
    r"System License\s*-\s*([0-9,.\-]+)\s*(?:kW|MW|MVA)", re.IGNORECASE
)
STORAGE_CAPACITY_PATTERN = re.compile(
    r"Storage Capacity\s*-\s*([0-9,.\-]+)\s*MWh", re.IGNORECASE
)

# Multi-type module breakdown: "17,170 x 610W and 2,268 x 620W" or "17,170 modules 610Wp"
# Captures (count, power_wp) pairs
MODULE_BREAKDOWN_PATTERN = re.compile(
    r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})\s*(?:modules?\s*)?[x×]\s*([0-9]{3,4})\s*W(?:p\b|\b(?!h))",
    re.IGNORECASE,
)

# Invalid bare A/B labels: N.N.N.N.N[AB] not prefixed with S.
# e.g. 2.2.2.5.1A, 1.1.2.9.3B
INVALID_BARE_AB_RE = re.compile(
    r"(?<![S\w])(?<!\.)(\b[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}\.[0-9]+[AB]\b)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Module specifications
# ---------------------------------------------------------------------------

MODULE_TYPE_PATTERN = re.compile(
    r"Type of Module\s*/\s*Power\s*-\s*([A-Za-z0-9\-\/ ]+)", re.IGNORECASE
)
MODULE_COUNT_PATTERN = re.compile(
    r"Number of Modules\s*-\s*([0-9,]+)", re.IGNORECASE
)
MODULE_POWER_PATTERN = re.compile(r"(\d{3,4})\s*Wp", re.IGNORECASE)
MODULES_PER_STRING_PATTERN = re.compile(
    r"Connection\s*-\s*([0-9]+)\s*/\s*String", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# MPPT / PV / string topology labels
# ---------------------------------------------------------------------------

MPPT_LABEL_PATTERN = re.compile(r"\bMPPT\s*([1-9]\d*)\b", re.IGNORECASE)
PV_LABEL_PATTERN = re.compile(r"\bPV\s*([1-9]\d*)\b", re.IGNORECASE)
ST_LABEL_PATTERN = re.compile(r"\bST\s*([1-9]\d*)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Suffix string pairs (A/B sides)
# Requires the S. prefix so bare MPPT channel identifiers (e.g. 1.2.9.10A)
# are NOT incorrectly treated as string-label suffix pairs.
# ---------------------------------------------------------------------------

SUFFIX_STRING_PATTERN = re.compile(r'\bS\.(\d+\.\d+\.\d+\.\d+)([AB])\b', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Device inventory
# ---------------------------------------------------------------------------

INVERTER_MODEL_PATTERN = re.compile(
    r'\b(SG\d+[A-Z]+|SUN\d{4}-\d+[A-Z]+|SUNGROW\s+\w+|HUAWEI\s+SUN\w+)\b', re.IGNORECASE
)
BATTERY_TYPE_PATTERN = re.compile(r'BESS\s+type\s*[-–]\s*([^\n]+)', re.IGNORECASE)
BESS_INV_PATTERN = re.compile(r'BESS\s+INV\s*[-–]\s*([^\n]+)', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Secondary DC string area count
# ---------------------------------------------------------------------------

AREA_STRING_COUNT_PATTERN = re.compile(r'\b(1[89]|2[0-2])\s*STRINGS\b', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Tracker / battery
# ---------------------------------------------------------------------------

TRACKER_PATTERN = re.compile(r"\btracker\b", re.IGNORECASE)
BATTERY_CAPACITY_PATTERN = re.compile(
    r"(?:Storage Capacity|BESS\s+kWh\s+BoL)\s*[-:]\s*([0-9,\.]+)\s*(MWh|kWh)", re.IGNORECASE
)
BATTERY_UNIT_PATTERN = re.compile(r"\b(MWh|kWh)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers (mirrors from_chatgpt extractors helpers — pure, no I/O)
# ---------------------------------------------------------------------------

def _first_match(patterns, text: str) -> str | None:
    """Return first captured group from the first matching pattern."""
    if not isinstance(patterns, list):
        patterns = [patterns]
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            groups = [g for g in m.groups() if g]
            return (groups[0] if groups else m.group(0)).strip()
    return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value.replace(",", "").strip()))
    except ValueError:
        return None
