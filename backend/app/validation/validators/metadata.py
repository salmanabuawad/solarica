"""Metadata completeness — required fields must be present for an asset's stage.

Currently checks the highest-signal case in the live data: a string that has
progressed to (or past) the voltage-test stage must carry a recorded voltage.
Extensible to any required-field policy per asset type.
"""
from __future__ import annotations

from app.validation.models import (
    Category, Finding, Repair, RepairAction, Severity, Source, Validator,
)
from app.validation.validators.base import BaseValidator, ValidationContext

# Statuses at/after which a voltage value is expected to exist.
_VOLT_TESTED = {"volt_checked", "cable_to_tga", "tga_commissioning"}


class MetadataValidator(BaseValidator):
    validator = Validator.METADATA
    name = "Metadata completeness"

    def run(self, ctx: ValidationContext) -> list[Finding]:
        findings: list[Finding] = []
        for s in ctx.strings:
            st = (s.status or "").lower()
            if st in _VOLT_TESTED and s.voltage is None:
                findings.append(Finding(
                    validator=Validator.METADATA,
                    code="METADATA_MISSING_VOLTAGE",
                    category=Category.COMPLETENESS,
                    severity=Severity.WARNING,
                    description=(f"String '{s.code}' reached '{st}' but has no recorded voltage value"),
                    asset_ref=s.code,
                    asset_type="string",
                    source=Source.METADATA,
                    suggested_fix="Record the tested voltage for this string",
                    confidence=0.9,
                    evidence={"status": st, "voltage": None},
                    repair=Repair(RepairAction.SET_FIELD, reason="voltage expected at this stage",
                                  confidence=0.6, patch={"field": "voltage"}),
                ))
        return findings
