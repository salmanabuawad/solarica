"""Commissioning readiness — pre-energization gate over the string pipeline.

Reads the real string-status model (the ``issue`` / staged-commissioning
statuses on ``string_records``) and raises one finding per string that carries
an open issue — i.e. an unresolved punch item that must clear before the block
can be energized.
"""
from __future__ import annotations

from app.validation.models import (
    Category, Finding, Severity, Source, Validator,
)
from app.validation.validators.base import BaseValidator, ValidationContext


class CommissioningValidator(BaseValidator):
    validator = Validator.COMMISSIONING
    name = "Commissioning readiness"

    def run(self, ctx: ValidationContext) -> list[Finding]:
        findings: list[Finding] = []
        for s in ctx.strings:
            if (s.status or "").lower() == "issue":
                findings.append(Finding(
                    validator=Validator.COMMISSIONING,
                    code="COMMISSIONING_ISSUE",
                    category=Category.READINESS,
                    severity=Severity.WARNING,
                    description=(f"String '{s.code}' is flagged as an issue — an open punch item "
                                 f"that must be cleared before energization"),
                    asset_ref=s.code,
                    asset_type="string",
                    source=Source.COMMISSIONING,
                    suggested_fix="Investigate and resolve the string issue, then re-test",
                    confidence=1.0,
                    evidence={"status": s.status},
                ))
        return findings
