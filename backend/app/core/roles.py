"""Project role vocabulary.

The deployed auth system recognises only three roles — `admin`, `editor`,
`viewer` — which are stored in the `users.role` column and surfaced in
the UI's user-management screen.

`PROJECT_ROLES` below lists the full 12-role matrix the roadmap targets
(construction + inventory + commissioning + operations + security
modules all reference these). They're not yet enforced — keeping the
list in one place so future permission checks can import from here
instead of stringly-typed duplicates.
"""
from typing import Final

PROJECT_ROLES: Final[tuple[str, ...]] = (
    "admin",
    "project_manager",
    "site_manager",
    "field_supervisor",
    "qc_engineer",
    "inventory_keeper",
    "technician",
    "electrician",
    "construction_worker",
    "security_guard_company",
    "client_representative",
    "higher_manager",
)

# Current shipping subset (see backend/app/main.py:_require_admin etc.)
ACTIVE_ROLES: Final[tuple[str, ...]] = ("admin", "editor", "viewer")
