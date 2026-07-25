"""Unit tests for the validator plugins (pure — synthetic context, no DB)."""
from app.validation.validators.base import Asset, ValidationContext
from app.validation.validators.commissioning import CommissioningValidator
from app.validation.validators.gap import GapValidator
from app.validation.validators.naming import NamingValidator


def _ctx(strings=None, piers=None, blocks=None) -> ValidationContext:
    c = ValidationContext("TEST", "00000000-0000-0000-0000-000000000000")
    c.strings = strings or []
    c.piers = piers or []
    c.blocks = blocks or []
    return c


def test_gap_detects_the_missing_number_only():
    piers = [Asset(code=f"INV{n:02d}", type="pier") for n in (1, 2, 4, 5, 6)]  # INV03 missing
    findings = GapValidator().run(_ctx(piers=piers))
    assert [f.asset_ref for f in findings] == ["INV03"]
    assert findings[0].code == "SEQUENCE_GAP"
    assert findings[0].repair.patch["code"] == "INV03"


def test_gap_ignores_short_or_sparse_series():
    piers = [Asset(code="INV01", type="pier"), Asset(code="INV09", type="pier")]
    assert GapValidator().run(_ctx(piers=piers)) == []


def test_naming_flags_the_outlier():
    strings = [Asset(code=f"1.2.1.{n}", type="string") for n in range(1, 12)]
    strings.append(Asset(code="str_44", type="string"))       # off-pattern
    findings = NamingValidator().run(_ctx(strings=strings))
    assert [f.asset_ref for f in findings] == ["str_44"]
    assert findings[0].code == "NAMING_FORMAT"


def test_naming_skips_when_no_clear_convention():
    codes = ["A1", "B-2", "3.3", "ROW9", "x_y", "10", "Q:Q", "zz99"]     # no dominant shape
    assert NamingValidator().run(_ctx(strings=[Asset(code=c, type="string") for c in codes])) == []


def test_commissioning_flags_only_issue_strings():
    strings = [
        Asset(code="1.1", type="string", status="tga_commissioning"),
        Asset(code="1.2", type="string", status="issue"),
        Asset(code="1.3", type="string", status="new"),
    ]
    findings = CommissioningValidator().run(_ctx(strings=strings))
    assert [f.asset_ref for f in findings] == ["1.2"]
    assert findings[0].severity.value == "warning"
