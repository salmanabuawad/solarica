"""Naming convention — flags codes that break the project's own pattern.

Rather than require a template up front, it infers the dominant structural
signature per asset type (letters→A, digit-runs→9, separators kept) and flags
the outliers. When ≥70% of codes share a shape, the rest are suspicious. An
explicit regex rule (Phase 3, via validation_rules.config) can override this.
"""
from __future__ import annotations

import re
from collections import Counter

from app.validation.models import (
    Category, DEFAULT_SEVERITY, Finding, Repair, RepairAction, Source, Validator,
)
from app.validation.validators.base import BaseValidator, ValidationContext

_MIN_SAMPLE = 8
_DOMINANCE = 0.70


def _signature(code: str) -> str:
    """Structural fingerprint: 'INV-001' -> 'A-9', '1.2.1.18' -> '9.9.9.9'."""
    return re.sub(r"\d+", "9", re.sub(r"[A-Za-z]+", "A", code))


class NamingValidator(BaseValidator):
    validator = Validator.NAMING
    name = "Naming convention"

    def run(self, ctx: ValidationContext) -> list[Finding]:
        findings: list[Finding] = []
        for atype, assets in (("pier", ctx.piers), ("string", ctx.strings)):
            if len(assets) < _MIN_SAMPLE:
                continue
            sigs = Counter(_signature(a.code) for a in assets)
            dominant, dom_n = sigs.most_common(1)[0]
            share = dom_n / len(assets)
            if share < _DOMINANCE:               # no single clear convention -> don't guess
                continue
            for a in assets:
                got = _signature(a.code)
                if got == dominant:
                    continue
                findings.append(Finding(
                    validator=Validator.NAMING,
                    code="NAMING_FORMAT",
                    category=Category.CONVENTION,
                    severity=DEFAULT_SEVERITY[Validator.NAMING],
                    description=(f"{atype.capitalize()} '{a.code}' does not match the project "
                                 f"naming pattern '{dominant}'"),
                    asset_ref=a.code,
                    asset_type=atype,
                    source=Source.ASSET_DB,
                    suggested_fix=f"Rename to match the '{dominant}' pattern used by the other {atype}s",
                    confidence=round(share, 2),
                    evidence={"expected_pattern": dominant, "got_pattern": got,
                              "dominance": round(share, 3)},
                    repair=Repair(RepairAction.RENAME, reason="match majority naming pattern",
                                  confidence=round(share, 2), patch={"pattern": dominant}),
                ))
        return findings
