from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ClassificationType = Literal["valid_string", "invalid_string_name", "non_string"]
SeverityType = Literal["info", "warning", "error", "blocker"]
StatusType = Literal["match", "mismatch", "manual_review_required"]


class StringPattern(BaseModel):
    id: int
    pattern_code: str
    pattern_name: str
    match_regex: str
    parse_regex: str
    level_count: int
    levels: List[str]
    no_leading_zero: bool = True
    max_digits_per_level: int = 2
    is_active: bool = True


class ScanRectangle(BaseModel):
    section_code: str
    page_no: int = 1
    x_pct: float = Field(..., ge=0, le=100)
    y_pct: float = Field(..., ge=0, le=100)
    w_pct: float = Field(..., gt=0, le=100)
    h_pct: float = Field(..., gt=0, le=100)


class PrepareScanRequest(BaseModel):
    site_id: int
    page_no: int = 1
    rectangles: List[ScanRectangle] = []
    run_fast_detect: bool = True


class FastDetectResult(BaseModel):
    configured_pattern_code: str
    detected_pattern_code: str
    confidence: float
    token_counts: Dict[str, int]


class PrepareScanResponse(BaseModel):
    design_file_id: int
    page_no: int
    fast_detect: FastDetectResult


class ScanStringsRequest(BaseModel):
    site_id: int
    page_no: int = 1
    rectangles: List[ScanRectangle] = []
    use_manual_rectangles: bool = True
    compare_to_design: bool = True
    save_run: bool = True


class TokenClassification(BaseModel):
    raw_text: str
    normalized_text: str
    classification: ClassificationType
    reason: Optional[str] = None
    section_code: Optional[str] = None
    parsed_levels: Optional[Dict[str, Any]] = None


class ScanIssue(BaseModel):
    issue_type: str
    severity: SeverityType
    entity_type: Literal["project", "section", "inverter", "string"]
    entity_key: str
    message: str
    details: Dict[str, Any] = {}


class InverterSummary(BaseModel):
    inverter_key: str
    expected_strings: int
    found_valid_strings: int
    duplicate_count: int
    invalid_name_count: int
    missing_sequence: List[int]
    status: StatusType


class SectionSummary(BaseModel):
    section_code: str
    found_inverters: int
    found_valid_strings: int
    inverter_summaries: List[InverterSummary]


class DesignComparisonSummary(BaseModel):
    expected_total_strings: int
    found_total_valid_strings: int
    expected_inverter_groups: int
    found_inverter_groups: int
    matches_design: bool


class ScanStringsResponse(BaseModel):
    design_file_id: int
    site_id: int
    run_id: int
    pattern_code_used: str
    fast_detect: FastDetectResult
    summary: Dict[str, int]
    design_comparison: DesignComparisonSummary
    sections: List[SectionSummary]
    invalid_string_names: List[TokenClassification]
    issues: List[ScanIssue]
