"""
Label normalization utilities for Solarica parsers.

Ported / extended from
from_chatgpt/app/services/normalization/name_normalizer.py.
"""
from __future__ import annotations
import re
import unicodedata

# ---------------------------------------------------------------------------
# Arabic / Unicode → ASCII equivalents for digits and common punctuation
# ---------------------------------------------------------------------------

_ARABIC_INDIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789",
)

_EXTENDED_ARABIC_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789",
)


def _to_ascii_digits(text: str) -> str:
    """Replace Arabic-Indic and Extended Arabic-Indic digits with ASCII equivalents."""
    text = text.translate(_ARABIC_INDIC_DIGITS)
    text = text.translate(_EXTENDED_ARABIC_DIGITS)
    return text


def _normalize_unicode(text: str) -> str:
    """Decompose unicode characters and strip non-ASCII."""
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# Inverter label normalization
# ---------------------------------------------------------------------------

# Matches patterns like "INV-1.1", "INV1.1", "S.INV-2.3", etc.
_INV_PREFIX_RE = re.compile(r"^(?:S\.)?(?:INV[-_ ]?)", re.IGNORECASE)

# Matches "1-1", "1 1", "01-02" and similar two-part separators → "1.1"
_DASH_SEP_RE = re.compile(r"^(\d+)[-_ ]+(\d+)$")

# Matches "1.1.something" (already dotted) — keep as-is after prefix strip
_ALREADY_DOTTED_RE = re.compile(r"^\d+\.\d+")


def normalize_inverter_label(raw: str) -> str:
    """
    Normalise an inverter label string to canonical ``"<section>.<block>"`` format.

    Transformations applied (in order):
    1. Replace Arabic/Unicode digits with ASCII equivalents.
    2. Strip leading ``S.`` or ``s.`` prefix.
    3. Strip leading ``INV-``, ``INV_``, ``INV`` (case-insensitive).
    4. Convert ``N-M``, ``N M`` formats to ``N.M``.
    5. Strip surrounding whitespace.

    Examples::

        normalize_inverter_label("INV-1.1")   → "1.1"
        normalize_inverter_label("INV1.1")    → "1.1"
        normalize_inverter_label("S.INV-2.3") → "2.3"
        normalize_inverter_label("1-1")       → "1.1"
        normalize_inverter_label("٢.٣")       → "2.3"   (Arabic digits)

    Returns the normalised string, or the original stripped string if no
    transformation matches.
    """
    if not isinstance(raw, str):
        raw = str(raw)

    # Step 1: Unicode / Arabic digit normalisation
    label = _to_ascii_digits(raw)
    label = _normalize_unicode(label)
    label = label.strip()

    # Step 2: Strip leading "S." or "s."
    if label.lower().startswith("s."):
        label = label[2:].strip()

    # Step 3: Strip leading "INV-", "INV_", "INV " prefixes
    label = _INV_PREFIX_RE.sub("", label).strip()

    # Step 4: Convert dash/space separator to dot
    dash_match = _DASH_SEP_RE.match(label)
    if dash_match:
        label = f"{int(dash_match.group(1))}.{int(dash_match.group(2))}"

    return label


# ---------------------------------------------------------------------------
# Generic name normalizer (ported from from_chatgpt NameNormalizer)
# ---------------------------------------------------------------------------

class NameNormalizer:
    """Simple template-based name normalizer."""

    def normalize(self, raw_name: str, template: str | None = None) -> str:
        if template:
            return template.replace("{raw}", raw_name)
        return raw_name.strip()
