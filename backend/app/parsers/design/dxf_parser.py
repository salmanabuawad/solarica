"""
DXF scan entry points for ``map_parser_v7`` and tooling.

Parsing is implemented in :mod:`app.parsers.design.unified_layout_parser`.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


def parse_dxf(
    content: bytes,
    filename: str,
    approved_pattern_regex: str | None = None,
    approved_pattern_name: str | None = None,
    extracted_text: str | None = None,
) -> dict[str, Any]:
    """Parse DXF bytes; returns the legacy string-scan result dict."""
    _ = extracted_text
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        return parse_dxf_path(
            tmp_path,
            filename,
            approved_pattern_regex=approved_pattern_regex,
            approved_pattern_name=approved_pattern_name,
            extracted_text=None,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def parse_dxf_path(
    path: str,
    filename: str,
    approved_pattern_regex: str | None = None,
    approved_pattern_name: str | None = None,
    extracted_text: str | None = None,
) -> dict[str, Any]:
    """Parse a DXF on disk; returns the legacy string-scan result dict."""
    _ = extracted_text
    from app.parsers.design.unified_layout_parser import run_full
    from app.parsers.design.unified_scan_adapter import adapt_unified_report_to_legacy_scan_result

    report = run_full([Path(path)])
    return adapt_unified_report_to_legacy_scan_result(
        report,
        source_document=Path(filename).name,
        approved_pattern_name=approved_pattern_name,
        approved_pattern_regex=approved_pattern_regex,
    )
