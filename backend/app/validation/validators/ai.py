"""AI / anomaly detection — finds outliers no hand-written rule anticipated.

The first anomaly model is a statistical voltage outlier detector (per-project
z-score): it learns the plant's own normal voltage distribution and flags
strings that deviate strongly — the same "learn the plant, then flag the weird"
approach the AI tier generalises. Pure stdlib (no external AI dependency); the
plugin slot is where embedding / ML models attach later.
"""
from __future__ import annotations

import statistics

from app.validation.models import Category, Finding, Severity, Source, Validator
from app.validation.validators.base import BaseValidator, ValidationContext

_MIN_SAMPLE = 12
_Z_THRESHOLD = 3.0


class AIAnomalyValidator(BaseValidator):
    validator = Validator.AI
    name = "AI anomaly detection"

    def run(self, ctx: ValidationContext) -> list[Finding]:
        findings: list[Finding] = []
        volts = [(s.code, s.voltage) for s in ctx.strings if s.voltage is not None]
        if len(volts) < _MIN_SAMPLE:
            return findings
        vals = [v for _, v in volts]
        mean = statistics.fmean(vals)
        sd = statistics.pstdev(vals)
        if sd <= 0:
            return findings
        for code, v in volts:
            z = (v - mean) / sd
            if abs(z) >= _Z_THRESHOLD:
                findings.append(Finding(
                    validator=Validator.AI,
                    code="ANOMALY_VOLTAGE",
                    category=Category.ANOMALY,
                    severity=Severity.INFO,
                    description=(f"String '{code}' voltage {v:.2f} V is a statistical outlier "
                                 f"(z={z:.1f}; plant mean {mean:.2f} V)"),
                    asset_ref=code,
                    asset_type="string",
                    source=Source.SCADA,
                    suggested_fix="Field-verify this string's voltage measurement",
                    confidence=min(0.99, abs(z) / 5.0),
                    evidence={"voltage": v, "mean": round(mean, 3), "stdev": round(sd, 3), "z": round(z, 2)},
                ))
        return findings
