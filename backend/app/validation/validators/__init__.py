"""
Validation Engine — validator plugins.

Importing this package registers every built-in validator, so the engine can
discover them via ``base.get_validators()``. Add a new validator by creating a
module here, subclassing ``BaseValidator``, and registering it below.
"""
from app.validation.validators.base import register
from app.validation.validators.ai import AIAnomalyValidator
from app.validation.validators.commissioning import CommissioningValidator
from app.validation.validators.duplicate import DuplicateValidator
from app.validation.validators.gap import GapValidator
from app.validation.validators.metadata import MetadataValidator
from app.validation.validators.naming import NamingValidator

# Register the built-in plugins (order is cosmetic — findings sort by severity).
register(GapValidator())
register(NamingValidator())
register(DuplicateValidator())
register(MetadataValidator())
register(CommissioningValidator())
register(AIAnomalyValidator())

__all__ = [
    "GapValidator", "NamingValidator", "DuplicateValidator",
    "MetadataValidator", "CommissioningValidator", "AIAnomalyValidator",
]
