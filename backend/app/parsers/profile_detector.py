"""Site-profile detector.

Looks at the uploaded design documents and decides which parser branch to
run:

  - `ground_pier`      — pile-driven trackers with ROW/TRK anchors and a
                         separate ramming plan. Today's Ashalim / BHK.
  - `floating_string`  — floating PV (FPV): modules on pontoons anchored
                         by mooring cables, no piers, no ramming plan.
                         Today's Qunaitra.
  - `rooftop`          — roof-mounted arrays (no anchors, no floats).

The detector reads the text layer of the provided PDFs and scores each
profile against a small set of keyword + structural signals.  It is
deliberately conservative: if no signal is strong enough, it returns
`ground_pier` (the historical default) so existing behaviour is
preserved.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Literal

SiteProfile = Literal["ground_pier", "floating_string", "rooftop"]


# Token-level signals. Each hit contributes a score; whichever profile
# scores highest wins. Regexes are case-insensitive and single-word so
# they're cheap to evaluate on multi-thousand-token pages.
_FLOATING_TOKENS = (
    r"\bFPV\b",
    r"\bfloating[\s-]?(pv|solar|plant|system|structure|array)\b",
    r"\bpontoon",
    r"\bmooring",
    r"\banchor[\s-]?line",
    r"\bbuoy",
    r"\braft\b",
    r"\bwalkway\b.*\bfloat",
)
_GROUND_PIER_TOKENS = (
    r"\bROW:\s*TRK:",
    r"\bramming\s+plan\b",
    r"\bpier\s+plan\b",
    r"\btracker\b",
    r"\bnextracker\b",
    r"\bXTR[-_]?\d",
    r"\bHAP\b|\bHMP\b|\bSAP\b|\bSAPE\b|\bSAPEND\b|\bSMP\b",
)
_ROOFTOP_TOKENS = (
    r"\brooftop\b",
    r"\broof[\s-]?mount",
    r"\bballast(ed)?\b",
    r"\bparapet\b",
)


def _score(text: str, patterns: Iterable[str]) -> int:
    total = 0
    for p in patterns:
        total += len(re.findall(p, text, re.IGNORECASE))
    return total


def detect_site_profile_from_text(text: str) -> SiteProfile:
    """Classify based on pre-extracted text."""
    if not text:
        return "ground_pier"
    s_float = _score(text, _FLOATING_TOKENS)
    s_ground = _score(text, _GROUND_PIER_TOKENS)
    s_roof = _score(text, _ROOFTOP_TOKENS)
    # Strongest signal wins. Ties break toward ground (historical default).
    scores = {"floating_string": s_float, "ground_pier": s_ground, "rooftop": s_roof}
    top = max(scores.values())
    if top == 0:
        return "ground_pier"
    for profile in ("floating_string", "rooftop", "ground_pier"):
        if scores[profile] == top:
            return profile  # type: ignore[return-value]
    return "ground_pier"


def detect_site_profile_from_files(paths: Iterable[str | Path]) -> SiteProfile:
    """Open each PDF and feed its text to `detect_site_profile_from_text`."""
    try:
        import fitz  # PyMuPDF
    except Exception:  # pragma: no cover — fitz is a hard backend dep
        return "ground_pier"
    chunks: list[str] = []
    for p in paths:
        try:
            with fitz.open(str(p)) as doc:
                for page in doc:
                    chunks.append(page.get_text() or "")
        except Exception:
            continue
    return detect_site_profile_from_text("\n".join(chunks))
