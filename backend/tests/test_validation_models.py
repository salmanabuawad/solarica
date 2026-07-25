"""Unit tests for the Validation Engine domain models (pure — no DB needed)."""
from app.validation.models import (
    Category, Finding, Repair, RepairAction, ResultStatus, Severity, Source, Validator,
)


def test_finding_fingerprint_is_stable_and_asset_scoped():
    a = Finding(Validator.GAP, "SEQUENCE_GAP", Category.SEQUENCE, Severity.WARNING,
                "Missing INV03", asset_ref="B1.INV03", asset_type="inverter")
    b = Finding(Validator.GAP, "SEQUENCE_GAP", Category.SEQUENCE, Severity.WARNING,
                "Missing INV03 (reworded description)", asset_ref="B1.INV03", asset_type="inverter")
    c = Finding(Validator.GAP, "SEQUENCE_GAP", Category.SEQUENCE, Severity.WARNING,
                "Missing INV04", asset_ref="B1.INV04", asset_type="inverter")
    # Same issue on the same asset -> same fingerprint (wording is irrelevant).
    assert a.fingerprint() == b.fingerprint()
    # Different asset -> different fingerprint.
    assert a.fingerprint() != c.fingerprint()
    assert len(a.fingerprint()) == 16


def test_enums_serialise_to_stable_text():
    assert Severity.CRITICAL.value == "critical"
    assert Validator.CROSS_SOURCE.value == "cross_source"
    assert Source.SCADA.value == "scada"
    assert ResultStatus.OPEN.value == "open"


def test_finding_defaults_and_repair():
    f = Finding(
        Validator.NAMING, "NAMING_FORMAT", Category.CONVENTION, Severity.WARNING,
        "off-policy name", asset_ref="str_44", asset_type="string",
        suggested_fix="rename to ROW-##-STRING-##",
        repair=Repair(RepairAction.RENAME, reason="policy", confidence=0.9,
                      patch={"to": "ROW-01-STRING-44"}),
    )
    assert f.status is ResultStatus.OPEN          # default lifecycle state
    assert f.repair.action is RepairAction.RENAME
    assert f.repair.confidence == 0.9
    assert f.evidence == {}                        # default empty
