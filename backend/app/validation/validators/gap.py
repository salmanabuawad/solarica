"""Gap detection — finds missing members in numbered asset sequences.

Groups each asset type's codes by their non-numeric shape (prefix + suffix +
digit width), then reports holes in an otherwise contiguous run. Guards against
sparse / multi-sequence data so we don't invent thousands of "missing" assets.
"""
from __future__ import annotations

import re
from collections import defaultdict

from app.validation.models import (
    Category, DEFAULT_SEVERITY, Finding, Repair, RepairAction, Source, Validator,
)
from app.validation.validators.base import BaseValidator, ValidationContext

_NUM = re.compile(r"^(.*?)(\d+)(\D*)$")


class GapValidator(BaseValidator):
    validator = Validator.GAP
    name = "Sequence gap detection"

    def run(self, ctx: ValidationContext) -> list[Finding]:
        findings: list[Finding] = []
        for atype, assets in (("pier", ctx.piers), ("string", ctx.strings), ("block", ctx.blocks)):
            groups: dict[tuple, list[int]] = defaultdict(list)
            for a in assets:
                m = _NUM.match(a.code)
                if not m:
                    continue
                prefix, num, suffix = m.group(1), m.group(2), m.group(3)
                groups[(prefix, suffix, len(num))].append(int(num))
            for (prefix, suffix, width), nums in groups.items():
                present = sorted(set(nums))
                if len(present) < 4:              # need a real sequence to infer intent
                    continue
                lo, hi = present[0], present[-1]
                missing = [n for n in range(lo, hi + 1) if n not in set(present)]
                if not missing or len(missing) > len(present):   # too sparse -> likely distinct series
                    continue
                for n in missing:
                    code = f"{prefix}{str(n).zfill(width)}{suffix}"
                    findings.append(Finding(
                        validator=Validator.GAP,
                        code="SEQUENCE_GAP",
                        category=Category.SEQUENCE,
                        severity=DEFAULT_SEVERITY[Validator.GAP],
                        description=(f"Missing {atype} '{code}' — gap in sequence "
                                     f"{prefix}{'#' * width}{suffix} ({lo}–{hi})"),
                        asset_ref=code,
                        asset_type=atype,
                        source=Source.ASSET_DB,
                        suggested_fix=f"Create {atype} {code}, or confirm it is intentionally absent",
                        confidence=0.8,
                        evidence={"prefix": prefix, "suffix": suffix, "range": [lo, hi], "missing": n},
                        repair=Repair(RepairAction.CREATE, reason="fill sequence gap",
                                      confidence=0.8, patch={"type": atype, "code": code}),
                    ))
        return findings
