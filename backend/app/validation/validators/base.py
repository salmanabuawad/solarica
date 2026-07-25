"""
Validation Engine — plugin framework.

- ``Asset``              : a normalized twin node, shared across validators.
- ``ValidationContext``  : loads a project's assets ONCE (reusing db_store), so
                           validators read one in-memory snapshot instead of
                           each re-querying the database.
- ``BaseValidator``      : the plugin contract — a pure function context→findings.
- ``register`` / ``get_validators`` : the registry the engine discovers through.

Add a validator by subclassing ``BaseValidator`` and registering it in
``validators/__init__.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.validation.models import Finding, Validator


@dataclass
class Asset:
    """A normalized view of one twin node, shared across validators."""
    code: str
    type: str                                  # 'pier' | 'string' | 'block' | 'tracker'
    block: Optional[str] = None
    row: Optional[str] = None
    status: Optional[str] = None
    statuses: list = field(default_factory=list)
    voltage: Optional[float] = None
    data: dict = field(default_factory=dict)


class ValidationContext:
    """Loads and holds a project's assets for a single validation run.

    Reuses the existing ``db_store`` reads for blocks/piers and reads
    ``string_records`` directly (strings are managed in ``main.py``). Tests may
    skip :meth:`load` and set ``piers`` / ``strings`` / ``blocks`` directly.
    """

    def __init__(self, project_slug: str, project_uuid: str):
        self.project_slug = project_slug
        self.project_uuid = project_uuid
        self.blocks: list[Asset] = []
        self.piers: list[Asset] = []
        self.strings: list[Asset] = []

    def load(self) -> "ValidationContext":
        # Imported here (not at module load) so the plugin framework — and the
        # validators' unit tests — don't require a live DB/config to import.
        from app.db import get_conn
        from app.services import db_store

        for b in db_store.get_blocks(self.project_uuid):
            code = b.get("block_code") or b.get("code")
            if code:
                self.blocks.append(Asset(code=str(code), type="block", data=b))
        for p in db_store.get_piers(self.project_uuid):
            code = p.get("pier_code")
            if code:
                self.piers.append(Asset(
                    code=str(code), type="pier",
                    block=str(p["block_code"]) if p.get("block_code") else None,
                    row=str(p["row_num"]) if p.get("row_num") not in (None, "") else None,
                    data=p,
                ))
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT string_id, status, statuses, voltage FROM string_records WHERE project_id = %s",
                (self.project_uuid,),
            )
            for r in cur.fetchall():
                self.strings.append(Asset(
                    code=str(r["string_id"]), type="string",
                    status=r.get("status"),
                    statuses=list(r.get("statuses") or []),
                    voltage=float(r["voltage"]) if r.get("voltage") is not None else None,
                ))
        return self

    @property
    def total_assets(self) -> int:
        return len(self.blocks) + len(self.piers) + len(self.strings)


class BaseValidator(ABC):
    """The plugin contract: a pure function from context to findings."""
    validator: Validator
    name: str = ""

    @abstractmethod
    def run(self, ctx: ValidationContext) -> list[Finding]:
        ...


_REGISTRY: "dict[Validator, BaseValidator]" = {}


def register(v: BaseValidator) -> BaseValidator:
    """Register a validator instance so the engine can discover it."""
    _REGISTRY[v.validator] = v
    return v


def get_validators(names: Optional[list[str]] = None) -> list[BaseValidator]:
    """All registered validators, or just the subset named (by enum value)."""
    if not names:
        return list(_REGISTRY.values())
    wanted = {n.lower() for n in names}
    return [v for v in _REGISTRY.values() if v.validator.value in wanted]
