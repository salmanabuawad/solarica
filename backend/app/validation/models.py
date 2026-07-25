"""
Validation Engine — domain models.

Typed enums plus the ``Finding`` / ``Repair`` dataclasses that make up the
plugin contract: every validator is a pure function that returns a list of
``Finding`` objects, and the store (see :mod:`app.validation.store`) persists
each one as a ``validation_results`` row.

Kept to the standard library only, so validators stay pure and trivially
unit-testable. String-valued enums serialise straight to JSON / SQL text.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    """How badly a finding hurts. Drives colour + sort order everywhere."""
    CRITICAL = "critical"   # blocks energization / breaks the twin
    WARNING = "warning"     # degrades data quality
    INFO = "info"           # advisory / probabilistic


class Validator(str, Enum):
    """The eleven validator plugins (Module 1..11)."""
    MAP = "map"
    METADATA = "metadata"
    NAMING = "naming"
    GAP = "gap"
    DUPLICATE = "duplicate"
    HIERARCHY = "hierarchy"
    CROSS_SOURCE = "cross_source"
    CAPACITY = "capacity"
    SPATIAL = "spatial"
    COMMISSIONING = "commissioning"
    AI = "ai"


class Category(str, Enum):
    """Taxonomy grouping, independent of which validator raised it."""
    EXISTENCE = "existence"
    COMPLETENESS = "completeness"
    CONVENTION = "convention"
    SEQUENCE = "sequence"
    UNIQUENESS = "uniqueness"
    STRUCTURE = "structure"
    CONSISTENCY = "consistency"
    ELECTRICAL = "electrical"
    GEOMETRY = "geometry"
    READINESS = "readiness"
    ANOMALY = "anomaly"


class Source(str, Enum):
    """Which system the conflicting / missing data came from."""
    ENGINEERING = "engineering"
    METADATA = "metadata"
    GIS = "gis"
    DIGITAL_TWIN = "digital_twin"
    COMMISSIONING = "commissioning"
    PVPM = "pvpm"
    SCADA = "scada"
    ASSET_DB = "asset_db"


class ResultStatus(str, Enum):
    """Lifecycle of a single finding."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    FIXED = "fixed"
    MUTED = "muted"
    RESOLVED = "resolved"
    REOPENED = "reopened"


class RunTrigger(str, Enum):
    """What kicked off a validation run."""
    MANUAL = "manual"
    UPLOAD = "upload"
    IMPORT = "import"
    SCHEDULED = "scheduled"
    CONTINUOUS = "continuous"


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RepairAction(str, Enum):
    """A suggested correction. Never applied without explicit user approval."""
    CREATE = "create"
    RENAME = "rename"
    MERGE = "merge"
    REPARENT = "reparent"
    RELOCATE = "relocate"
    SET_FIELD = "set_field"
    LINK = "link"
    REMOVE = "remove"


class RepairStatus(str, Enum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"


# Default severity per validator — a rule can override this per project.
DEFAULT_SEVERITY: dict[Validator, Severity] = {
    Validator.MAP: Severity.CRITICAL,
    Validator.METADATA: Severity.WARNING,
    Validator.NAMING: Severity.WARNING,
    Validator.GAP: Severity.WARNING,
    Validator.DUPLICATE: Severity.CRITICAL,
    Validator.HIERARCHY: Severity.CRITICAL,
    Validator.CROSS_SOURCE: Severity.CRITICAL,
    Validator.CAPACITY: Severity.WARNING,
    Validator.SPATIAL: Severity.WARNING,
    Validator.COMMISSIONING: Severity.WARNING,
    Validator.AI: Severity.INFO,
}


@dataclass
class Repair:
    """A suggested, never-auto-applied correction attached to a Finding."""
    action: RepairAction
    reason: str = ""
    confidence: Optional[float] = None          # 0.0 .. 1.0
    patch: dict = field(default_factory=dict)   # the proposed change (data only)


@dataclass
class Finding:
    """The unit a validator emits; persisted as one ``validation_results`` row.

    Carries every field the spec mandates: severity, category, source, asset,
    description, suggested fix, confidence, status and (added by the store on
    insert) a timestamp.
    """
    validator: Validator
    code: str                                    # stable taxonomy code, e.g. "NAMING_FORMAT"
    category: Category
    severity: Severity
    description: str
    asset_ref: Optional[str] = None              # asset code, e.g. "B1.INV03.S18"
    asset_type: Optional[str] = None             # "string" | "panel" | "inverter" | ...
    source: Optional[Source] = None
    suggested_fix: Optional[str] = None          # human-readable one-liner
    confidence: Optional[float] = None           # 0.0 .. 1.0
    evidence: dict = field(default_factory=dict)  # structured proof (e.g. per-source values)
    repair: Optional[Repair] = None              # optional machine-applicable fix
    status: ResultStatus = ResultStatus.OPEN

    def fingerprint(self) -> str:
        """Stable hash identifying the *same* issue on the *same* asset across
        runs, so findings can be de-duplicated / carried forward."""
        raw = "|".join([self.validator.value, self.code, self.asset_ref or "", self.asset_type or ""])
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
