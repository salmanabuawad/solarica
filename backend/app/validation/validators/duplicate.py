"""Duplicate detection — the same code must not identify two assets.

Exact-code duplicates within an asset type. (Codes are DB-unique today, so this
is defensive; it also catches duplicates introduced by imports before they are
persisted, and is the natural home for future GPS / geometry / embedding-based
fuzzy duplicate detection.)
"""
from __future__ import annotations

from collections import Counter

from app.validation.models import (
    Category, DEFAULT_SEVERITY, Finding, Repair, RepairAction, Source, Validator,
)
from app.validation.validators.base import BaseValidator, ValidationContext


class DuplicateValidator(BaseValidator):
    validator = Validator.DUPLICATE
    name = "Duplicate detection"

    def run(self, ctx: ValidationContext) -> list[Finding]:
        findings: list[Finding] = []
        for atype, assets in (("pier", ctx.piers), ("string", ctx.strings), ("block", ctx.blocks)):
            for code, n in Counter(a.code for a in assets).items():
                if n > 1:
                    findings.append(Finding(
                        validator=Validator.DUPLICATE,
                        code="ASSET_DUPLICATE",
                        category=Category.UNIQUENESS,
                        severity=DEFAULT_SEVERITY[Validator.DUPLICATE],
                        description=f"Duplicate {atype} code '{code}' appears {n} times",
                        asset_ref=code,
                        asset_type=atype,
                        source=Source.ASSET_DB,
                        suggested_fix="Merge the duplicates, keeping one canonical asset",
                        confidence=1.0,
                        evidence={"count": n},
                        repair=Repair(RepairAction.MERGE, reason="duplicate code",
                                      confidence=0.7, patch={"code": code}),
                    ))
        return findings
