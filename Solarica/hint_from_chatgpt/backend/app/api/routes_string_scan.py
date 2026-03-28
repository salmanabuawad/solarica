from fastapi import APIRouter

from app.schemas.string_scan import (
    PrepareScanRequest,
    PrepareScanResponse,
    ScanStringsRequest,
    ScanStringsResponse,
)

router = APIRouter(prefix="/api", tags=["string-scan"])


@router.post("/design-files/{design_file_id}/scan-strings/prepare", response_model=PrepareScanResponse)
async def prepare_scan(design_file_id: int, payload: PrepareScanRequest) -> PrepareScanResponse:
    # Replace with service call
    return PrepareScanResponse(
        design_file_id=design_file_id,
        page_no=payload.page_no,
        fast_detect={
            "configured_pattern_code": "S_DOT_3",
            "detected_pattern_code": "S_DOT_3",
            "confidence": 0.98,
            "token_counts": {"S_DOT_3": 701, "S4_LEVEL": 0},
        },
    )


@router.post("/design-files/{design_file_id}/scan-strings", response_model=ScanStringsResponse)
async def scan_strings(design_file_id: int, payload: ScanStringsRequest) -> ScanStringsResponse:
    # Replace with service call
    return ScanStringsResponse(
        design_file_id=design_file_id,
        site_id=payload.site_id,
        run_id=1,
        pattern_code_used="S_DOT_3",
        fast_detect={
            "configured_pattern_code": "S_DOT_3",
            "detected_pattern_code": "S_DOT_3",
            "confidence": 0.98,
            "token_counts": {"S_DOT_3": 701, "S4_LEVEL": 0},
        },
        summary={
            "total_valid_strings": 701,
            "total_invalid_string_names": 2,
            "total_duplicates": 1,
            "total_inverters_found": 34,
        },
        design_comparison={
            "expected_total_strings": 702,
            "found_total_valid_strings": 701,
            "expected_inverter_groups": 34,
            "found_inverter_groups": 34,
            "matches_design": False,
        },
        sections=[
            {
                "section_code": "1.2",
                "found_inverters": 1,
                "found_valid_strings": 21,
                "inverter_summaries": [
                    {
                        "inverter_key": "1.2",
                        "expected_strings": 21,
                        "found_valid_strings": 21,
                        "duplicate_count": 1,
                        "invalid_name_count": 0,
                        "missing_sequence": [2],
                        "status": "mismatch",
                    }
                ],
            }
        ],
        invalid_string_names=[
            {
                "raw_text": "S.01.2.3",
                "normalized_text": "S.01.2.3",
                "classification": "invalid_string_name",
                "reason": "leading_zero",
                "section_code": "1.2",
                "parsed_levels": None,
            }
        ],
        issues=[
            {
                "issue_type": "duplicate_string",
                "severity": "error",
                "entity_type": "string",
                "entity_key": "S.1.2.4",
                "message": "Duplicate string ID detected",
                "details": {"count": 2},
            },
            {
                "issue_type": "design_total_mismatch",
                "severity": "error",
                "entity_type": "project",
                "entity_key": "project",
                "message": "Found string total does not match expected design total",
                "details": {"expected_total_strings": 702, "found_total_valid_strings": 701},
            },
        ],
    )
